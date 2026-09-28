"""Rarer router branches: identifiers, caps, back-references, contexts and ranges."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ingest.build_index import build_index, write_index
from ingest.records import CatalogueEntry
from legal_rag_router import Coordinate, Router, RouteStatus
from legal_rag_router.router import _official_number, _order_key
from tests.conftest import FIXTURE_INDEX
from tests.test_build_index import write_aliases, write_records

BOUND, AMBIGUOUS, OOC = RouteStatus.BOUNDED, RouteStatus.AMBIGUOUS, RouteStatus.OUT_OF_COVERAGE


@pytest.fixture(scope="module")
def router() -> Router:
    return Router.from_path(FIXTURE_INDEX)


def test_non_string_query_fails_safe(router: Router) -> None:
    result = router.route(123)  # type: ignore[arg-type]
    assert (result.status, result.reason) == (RouteStatus.UNRESOLVED, "not_a_string")


def test_too_many_cues_fail_safe(router: Router) -> None:
    result = router.route("s.1 " + "not " * 70)
    assert (result.status, result.reason) == (RouteStatus.UNRESOLVED, "too_complex")


@pytest.mark.parametrize(
    ("query", "status", "reason"),
    [
        ("uk/asp/2010/13", OOC, "series"),
        ("uk/ukpga/1996/999", RouteStatus.INSTRUMENT_NOT_FOUND, "identifier_not_in_index"),
        ("uk/uksi/1981/292/art3", OOC, "provision_structure_unavailable"),
        ("uk/uksi/1990/2145/sch1/para34/A", BOUND, None),
        ("uk/uksi/1990/2145/sch1/PARA34/A", AMBIGUOUS, "case_variants"),  # decision 7
        ("SI 1999/99999", RouteStatus.INSTRUMENT_NOT_FOUND, "number_not_in_index"),
        ("SR 1996/123", OOC, "series"),
    ],
)
def test_identifier_and_number_outcomes(
    router: Router, query: str, status: RouteStatus, reason: str | None
) -> None:
    result = router.route(query)
    assert (result.status, result.reason) == (status, reason)


def test_identifier_case_matching_neither_variant_asks(router: Router) -> None:
    result = router.route("uk/uksi/1990/2145/SCH1/para34/a2")
    assert result.status in (AMBIGUOUS, RouteStatus.PROVISION_NOT_FOUND)


def test_back_reference_needs_the_same_kind_and_year(router: Router) -> None:
    assert router.route("SI 2010/2926 art. 3 and s. 1 of that Act").reason in (
        "context_needed",
        "provision_without_instrument",
    )


def test_year_only_reference_takes_its_provision(router: Router) -> None:
    # The fixture holds one Act of 1968 and its catalogue no other: that Act is meant.
    assert [str(c) for c in router.route("the 1968 Act, s. 1").coordinates] == [
        "uk/ukpga/1968/60/s1"
    ]
    result = router.route("Employment Rights Act 1996 and section 124 of the 2010 Act")
    assert "uk/ukpga/2010/15/s124" in [str(c) for c in result.coordinates]
    # Several Acts of 1996: narrowed to those with a s.124, and asked, never guessed.
    asked = router.route("section 124 of the 1996 Act")
    assert (asked.status, asked.reason) == (AMBIGUOUS, "year_only")
    assert {c.coordinate.instrument_id for c in asked.candidates} == {"uk_ukpga_1996_18"}


def test_year_only_reference_asks_when_the_catalogue_knows_another_act(tmp_path: Path) -> None:
    write_records(
        tmp_path / "data", {"uk/ukpga/2010/15": ("Equality Act 2010", ["uk/ukpga/2010/15/s1"])}
    )
    catalogue = tmp_path / "catalogue.jsonl"
    other = CatalogueEntry(
        coordinate="uk/ukpga/2010/99", series="ukpga", year=2010, number=99,
        title="Another Act 2010", source="t",
    )  # fmt: skip
    catalogue.write_text(other.model_dump_json() + "\n")
    built = build_index(
        tmp_path / "data", catalogue=catalogue, aliases_dir=write_aliases(tmp_path / "a", "")
    )
    write_index(
        built, tmp_path / "index", snapshot=date(2026, 9, 27), sources=["legislation.gov.uk"]
    )
    result = Router.from_path(tmp_path / "index").route("section 1 of the 2010 Act")
    assert result.status is AMBIGUOUS
    assert not result.coordinates


def test_title_without_year_narrowed_by_provision(router: Router) -> None:
    result = router.route("Employment Rights Act section 124")
    assert result.status is AMBIGUOUS  # both the 1996 and 2025 Acts have a s.124
    assert result.reason == "title_without_year"


def test_excluded_instrument_with_its_provision_binds_nothing_from_it(router: Router) -> None:
    result = router.route("not the Employment Rights Act 1996 s.124")
    assert not any(c.instrument_id == "uk_ukpga_1996_18" for c in result.coordinates)


def test_context_spanning_two_instruments_is_ignored(router: Router) -> None:
    result = router.route(
        "what about section 125?", context=["uk/ukpga/1996/18/s124", "uk/ukpga/2010/15/s124"]
    )
    assert result.source != "context"


def test_wide_range_asks(router: Router) -> None:
    result = router.route("ss. 1-200 of the Employment Rights Act 1996")
    assert (result.status, result.reason) == (AMBIGUOUS, "range")
    assert result.clarification


def test_overlapping_blocked_spans_merge(router: Router) -> None:
    result = router.route("ERA 1996 s.124 as it stood on 1 April 2012")
    assert [str(c) for c in result.coordinates] == ["uk/ukpga/1996/18/s124"]
    assert result.temporal_hint


def test_helpers() -> None:
    assert _official_number(Coordinate.parse("uk/uksi/2011/3006")) == "SI 2011/3006"
    assert _official_number(Coordinate.parse("uk/ukpga/1996/18")) == "c. 18"
    assert _order_key("A") == (0, 0, "A")
    assert _order_key("98") < _order_key("98ZA") < _order_key("98A") < _order_key("99")
