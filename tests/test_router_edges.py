"""Rarer router branches: identifiers, caps, back-references, contexts and ranges."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ingest.build_index import build_index, write_index
from ingest.records import CatalogueEntry
from legal_rag_router import Coordinate, NextAction, Router, RouteStatus
from legal_rag_router.router import _official_number, _order_key
from tests.conftest import FIXTURE_INDEX
from tests.test_build_index import write_aliases, write_records

BOUND, AMBIGUOUS, OOC = RouteStatus.BOUNDED, RouteStatus.AMBIGUOUS, RouteStatus.OUT_OF_COVERAGE
ERA, S124 = "uk/ukpga/1996/18", "uk/ukpga/1996/18/s124"
SI_2011, SI_2026 = "uk/uksi/2011/3006", "uk/uksi/2026/310"
ORDER_2011 = "The Employment Rights (Increase of Limits) Order 2011"
ORDER_2026 = "The Employment Rights (Increase of Limits) Order 2026"


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


# ---------------------------------------------------------------- former titles and acronyms


def test_former_title_binds_with_a_note(router: Router) -> None:
    result = router.route("Industrial Tribunals Act 1996, s. 4")
    assert [str(c) for c in result.coordinates] == ["uk/ukpga/1996/17/s4"]
    assert result.messages == (
        "“Industrial Tribunals Act 1996” is a former title of the Employment Tribunals Act 1996.",
    )
    assert router.route("Employment Tribunals Act 1996, s. 4").messages == ()


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("TA 1968 s. 1", ["uk/ukpga/1968/60/s1"]),  # generated, typed in capitals
        ("cfa 1996", ["uk/ukpga/1996/4"]),  # lower case: not a title word, three letters
    ],
)
def test_generated_acronym_with_a_year_binds(
    router: Router, query: str, expected: list[str]
) -> None:
    result = router.route(query)
    assert [str(c) for c in result.coordinates] == expected
    assert result.messages[0].startswith(f"“{query.split(' s.', maxsplit=1)[0]}” read as the ")


def test_generated_acronym_that_fits_two_acts_asks(router: Router) -> None:
    result = router.route("MLA 1897")
    assert (result.status, result.reason) == (AMBIGUOUS, "acronym")
    assert len(result.candidates) == 2


@pytest.mark.parametrize("query", ["in 1996 the tribunal sat", "ta 1968", "TA 1999"])
def test_words_and_unknown_acronyms_are_not_citations(router: Router, query: str) -> None:
    assert router.route(query).status is RouteStatus.UNRESOLVED


def test_curated_alias_wins_over_the_generated_acronym(router: Router) -> None:
    result = router.route("EA 2010 s. 13")  # curated → Equality Act 2010, no "read as" note
    assert [str(c) for c in result.coordinates] == ["uk/ukpga/2010/15/s13"]
    assert result.messages == ()


# ---------------------------------------------------------------- rare paths, pinned


def test_an_internal_error_fails_safe(router: Router, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_: object) -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(router, "_route", broken)
    result = router.route("Employment Rights Act 1996 s. 124")
    assert result.status is RouteStatus.UNRESOLVED
    assert result.next_action is NextAction.DISCOVER_THEN_BIND


@pytest.mark.parametrize(
    ("query", "status", "reason", "coordinates"),
    [
        ("ERA 1996 Bill", BOUND, None, ["uk/ukpga/1996/18"]),  # an overlapping cue is dropped
        ("Code civil the Act", AMBIGUOUS, "context_needed", []),  # "the Act" skips foreign law
        ("SI 1948/1000", OOC, "series", []),  # catalogued, not downloaded
        ("1963 c. 10", OOC, "series", []),
        ("; 2024", RouteStatus.UNRESOLVED, None, []),
        ("Act Arbitration 1996", BOUND, None, ["uk/ukpga/1996/23"]),  # reordered title
        ("[2020] UKSC", OOC, "case", []),
        ("not [2020] UKSC", RouteStatus.UNRESOLVED, "excluded", []),
        ("Marchwood Act 1996 (c. 99)", RouteStatus.INSTRUMENT_NOT_FOUND, "no_such_title", []),
        ("section 124 except section 125", AMBIGUOUS, "provision_without_instrument", []),
        ("Parts II to IV of the Employment Rights Act 1996", AMBIGUOUS, "range", []),
        ("s. 1(1) to s. 3 of the Employment Rights Act 1996", AMBIGUOUS, "range", []),
        ("ss. 98-1 of the Employment Rights Act 1996", AMBIGUOUS, "range", []),
        ("Employment Rights Act 1996 except s. 999", BOUND, None, ["uk/ukpga/1996/18"]),
        ("IA 1986 Sch. B1 para. 15(3)", AMBIGUOUS, "duplicated_in_source", []),  # decision 13
        ("TULRCA 1992 Sch. A1 para. 1", BOUND, None, ["uk/ukpga/1992/52/schA1/para1"]),
        # a negation cue too far from the citation excludes nothing
        ("not relevant here: section 124 of the Employment Rights Act 1996", BOUND, None, [S124]),
        # SI lists (UK-I-22), series notes (UK-I-29), years ending a provision list (UK-P-06)
        ("S.I. 2011/3006 (C. 5) and 2026/310", BOUND, None, [SI_2011, SI_2026]),
        ("S.I. 2011 No. 3006 and 2026 No. 310", BOUND, None, [SI_2011, SI_2026]),
        ("S.I. 2011/3006, and 2026/310", BOUND, None, [SI_2011, SI_2026]),
        ("S.I. 2011/3006 (S. 1)", BOUND, None, [SI_2011]),
        ("S.I.s 2011/3006 and 2026/310", BOUND, None, [SI_2011, SI_2026]),
        ("S.I. 2011/ 3006", BOUND, None, [SI_2011]),
        (
            "S.I. 2011/3006 (article 3), 2026/310 (article 2)",
            BOUND,
            None,
            [f"{SI_2011}/art3", f"{SI_2026}/art2"],
        ),
        ("S.I. 2011/3006, art. 3 and 1996 c. 18", BOUND, None, [f"{SI_2011}/art3", ERA]),
        (
            "S.I. 2011/3006, article 3, 2026/310, article 2",
            BOUND,
            None,
            [f"{SI_2011}/art3", f"{SI_2026}/art2"],
        ),
        (  # an unbracketed pinpoint continues the list only before an item with its year
            "S.I. 2011/3006, article 3, 400 and 2026/310",
            RouteStatus.PROVISION_NOT_FOUND,
            "provision_not_in_instrument",
            [],
        ),
        # an unknown title with a real SI number is asked, never refused (UK-I-30)
        ("Marchwood Order 2011 (S.I. 2011/3006)", AMBIGUOUS, "title_number_conflict", []),
        # a title and a bracketed SI number that name different SIs are asked (UK-I-30)
        (f"{ORDER_2011} (S.I. 2026/310)", AMBIGUOUS, "number_mismatch", []),
        (f"{ORDER_2011} (S.I. 2011/3006)", BOUND, None, [SI_2011]),
        (f"{ORDER_2011}, S.I. 2026/310", BOUND, None, [SI_2011, SI_2026]),  # a list, not a note
        (  # the bracket numbers both titles named before it
            f"{ORDER_2011} and the {ORDER_2026[4:]} (S.I. 2011/3006 and 2026/310)",
            BOUND,
            None,
            [SI_2011, SI_2026],
        ),
    ],
)
def test_pinned_outcomes(
    router: Router,
    query: str,
    status: RouteStatus,
    reason: str | None,
    coordinates: list[str],
) -> None:
    result = router.route(query)
    assert (result.status, result.reason) == (status, reason)
    assert [str(c) for c in result.coordinates] == coordinates


def test_a_url_ending_in_a_word_is_not_an_acronym(router: Router) -> None:
    result = router.route("https://www.legislation.gov.uk/ukpga/1996/18/contents 2010")
    assert [str(c) for c in result.coordinates] == ["uk/ukpga/1996/18"]


def test_abbreviation_full_stops_do_not_end_the_clause(router: Router) -> None:
    # "Sch. B1" is not a sentence end: the paragraph links to the one Act named (decision 15).
    result = router.route("In the Insolvency Act 1986, what does Sch. B1 para. 14 say?")
    assert [str(c) for c in result.coordinates] == ["uk/ukpga/1986/45/schB1/para14"]


@pytest.mark.parametrize(
    ("query", "status", "reason", "coordinates"),
    [
        ("Employment Rights Act 1996, Sch. 1", BOUND, None, ["uk/ukpga/1996/18/sch1"]),
        ("ERA ! 96", RouteStatus.UNRESOLVED, None, []),  # an alias split by a full stop
        ("the Act Lands 1897", RouteStatus.INSTRUMENT_NOT_FOUND, "no_such_title", []),
        ("other than art. 3 and Finance 2024", RouteStatus.UNRESOLVED, "excluded", []),
        ("ss. 100-119 of the Employment Rights Act 1996", AMBIGUOUS, "range", []),  # > 20
        (
            "Rights Employment Act 1996 ss. 1-3",
            BOUND,
            None,
            [f"uk/ukpga/1996/18/s{n}" for n in (1, 2, 3)],
        ),
        ("Military Lands 1897 regulation 2", BOUND, None, ["uk/ukpga/Vict/60-61/6/s2"]),
    ],
)
def test_more_pinned_outcomes(
    router: Router,
    query: str,
    status: RouteStatus,
    reason: str | None,
    coordinates: list[str],
) -> None:
    result = router.route(query)
    assert (result.status, result.reason) == (status, reason)
    assert [str(c) for c in result.coordinates] == coordinates


def test_provision_matching_neither_case_variant_asks(tmp_path: Path) -> None:
    write_records(
        tmp_path / "data",
        {
            "uk/ukpga/2000/1": (
                "Test Act 2000",
                ["uk/ukpga/2000/1/s1", "uk/ukpga/2000/1/s1/Aa", "uk/ukpga/2000/1/s1/aA"],
            )
        },
    )
    built = build_index(
        tmp_path / "data", catalogue=None, aliases_dir=write_aliases(tmp_path / "a", "")
    )
    write_index(
        built, tmp_path / "index", snapshot=date(2026, 9, 27), sources=["legislation.gov.uk"]
    )
    result = Router.from_path(tmp_path / "index").route("Test Act 2000 s. 1(AA)")
    assert (result.status, result.reason) == (AMBIGUOUS, "case_variants")
    assert result.clarification == "The Test Act 2000 has both s1/Aa and s1/aA. Which do you mean?"


def test_an_unknown_title_with_a_real_si_number_names_the_si(router: Router) -> None:
    result = router.route("Marchwood Order 2011 (S.I. 2011/3006)")
    assert [c.label for c in result.candidates] == [
        "The Employment Rights (Increase of Limits) Order 2011"
    ]
    assert result.clarification == (
        "No instrument is titled “Marchwood Order 2011”, but its SI number is that of "
        "The Employment Rights (Increase of Limits) Order 2011. Did you mean that?"
    )


def test_a_title_and_a_different_si_number_offer_both(router: Router) -> None:
    result = router.route(f"{ORDER_2011} (S.I. 2026/310)")
    assert [c.label for c in result.candidates] == [
        ORDER_2011,
        "The Employment Rights (Increase of Limits) Order 2026",
    ]
    assert result.clarification is not None
    assert "the SI number names a different instrument" in result.clarification


def test_unknown_title_checks_count_against_the_work_limit(router: Router) -> None:
    # Each check costs UNKNOWN_TITLE_COST lookups (roadmap Q-B-3, grammar.md UK-W-03).
    nine = "; ".join(f"employment theft {1970 + i}" for i in range(9))
    assert router.route(nine).reason == "no_such_title"
    ten = "; ".join(f"employment theft {1970 + i}" for i in range(10))
    result = router.route(ten)
    assert (result.status, result.reason) == (RouteStatus.UNRESOLVED, "too_complex")
