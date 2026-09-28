"""Behaviours found by the coverage sweep over real statute text (M7k).

Each case is the smallest form of a failure seen in harvested citations: editorial lists,
chapter notes, amendment phrasing ("inserted by <Act>"), dates, commas inside titles and
references back to an Act just named.
"""

from __future__ import annotations

from datetime import date

import pytest

from ingest.build_index import build_index, write_index
from legal_rag_router import Router, RouteStatus
from legal_rag_router.grammars.uk_grammar import GRAMMAR
from legal_rag_router.normalise import fold
from tests.conftest import FIXTURE_INDEX
from tests.test_build_index import write_aliases, write_records

BOUND, AMBIGUOUS = RouteStatus.BOUNDED, RouteStatus.AMBIGUOUS


@pytest.fixture(scope="module")
def router() -> Router:
    return Router.from_path(FIXTURE_INDEX)


def coords(router: Router, query: str) -> list[str]:
    return [str(c) for c in router.route(query).coordinates]


# ---------------------------------------------------------------- grammar


@pytest.mark.parametrize(
    ("query", "keys"),
    [
        ("S.I. 2008/2767, 2010/641 and 2011/2425", ["si/2008/2767", "si/2010/641", "si/2011/2425"]),
        ("S.I. 1988/663 and 1445", ["si/1988/663", "si/1988/1445"]),
        ("S.I. 2011/3006, 2 employees", ["si/2011/3006"]),  # a short bare number is not an SI
    ],
)
def test_si_number_lists(query: str, keys: list[str]) -> None:
    assert [n.key for n in GRAMMAR.numbers(query, fold(query))] == keys


@pytest.mark.parametrize(
    "query", ["1.3.2007", "(20.7.1998)", "1 April 1996", "6th April 2020", "(E.W.)"]
)
def test_dates_and_extents_are_cues_not_citations(query: str) -> None:
    assert any(c.kind == "date" for c in GRAMMAR.cues(query, fold(query)))


def test_provision_scan_resumes_after_a_list_stops() -> None:
    query = "s. 84, Sch. 14 para. 46"
    labels = [[r.label() for r in p.refs] for p in GRAMMAR.provisions(query, fold(query))]
    assert labels == [["s.84"], ["Sch. 14 para. 46"]]


# ---------------------------------------------------------------- linking


def test_listed_provisions_chain_to_the_instrument(router: Router) -> None:
    result = router.route("Employment Rights Act 1996 (c. 18), ss. 94, 95, Sch. 1 para. 2")
    assert [str(c) for c in result.coordinates] == [
        "uk/ukpga/1996/18/s94", "uk/ukpga/1996/18/s95", "uk/ukpga/1996/18/sch1/para2",
    ]  # fmt: skip


def test_agentive_by_blocks_default_linking(router: Router) -> None:
    # "S. 999" belongs to the amended (host) Act, not to the amending Act: never linked by default.
    result = router.route("S. 999 inserted by Employment Rights Act 1996")
    assert result.status is not RouteStatus.PROVISION_NOT_FOUND


def test_default_linking_stays_within_a_clause(router: Router) -> None:
    result = router.route("Employment Rights Act 1996; paragraph 999 was inserted later.")
    assert result.status is not RouteStatus.PROVISION_NOT_FOUND


def test_comma_joined_instrument_wins_over_a_bare_neighbour(router: Router) -> None:
    result = router.route("SI 2010/2926, art. 3 1996 c. 18")
    assert "uk/uksi/2010/2926/art3" in [str(c) for c in result.coordinates]


# ---------------------------------------------------------------- titles


def test_chapter_note_is_part_of_the_citation(router: Router) -> None:
    assert coords(router, "Employment Rights Act 1996 (c. 18), s. 124") == ["uk/ukpga/1996/18/s124"]
    assert coords(router, "Employment Rights Act 1996 (c.18, SIF 43:5), s. 124") == [
        "uk/ukpga/1996/18/s124"
    ]


def test_chapter_mismatch_asks(router: Router) -> None:
    result = router.route("Employment Rights Act 1996 (c. 23)")
    assert result.status is AMBIGUOUS
    assert result.reason == "chapter_mismatch"
    ids = {c.coordinate.instrument_id for c in result.candidates}
    assert ids == {"uk_ukpga_1996_18", "uk_ukpga_1996_23"}  # the title's Act and c. 23's Act


def test_wrong_title_with_a_real_chapter_asks_instead_of_refusing(router: Router) -> None:
    result = router.route("Employment Liberties Act 1996 (c. 18), s. 124")
    assert result.status is AMBIGUOUS
    assert result.reason == "title_number_conflict"
    assert str(result.candidates[0].coordinate) == "uk/ukpga/1996/18"


def test_title_followed_by_its_chapter_is_one_citation(router: Router) -> None:
    assert coords(router, "Theft Act 1968 c. 60, s. 1") == ["uk/ukpga/1968/60/s1"]


def test_capitals_mark_where_a_title_starts(router: Router) -> None:
    assert coords(router, "words omitted by virtue of Theft Act 1968 (c. 60), s. 1") == [
        "uk/ukpga/1968/60/s1"
    ]
    lower = router.route("marchwood commercial arbitration act 1996")
    assert lower.status is AMBIGUOUS  # the plan's lower-case rule still applies


def test_regnal_act_cited_by_calendar_chapter(router: Router) -> None:
    assert coords(router, "1925 c. 20, s. 1") == ["uk/ukpga/Geo5/15-16/20/s1"]


def test_amending_act_reference_is_not_a_title(router: Router) -> None:
    result = router.route("with effect in accordance with s. 42(2) of the amending Act")
    assert result.status is not RouteStatus.INSTRUMENT_NOT_FOUND
    assert result.reason in ("context_needed", "provision_without_instrument")


def test_refers_back_to_the_act_just_named(router: Router) -> None:
    result = router.route("Part X of the Employment Rights Act 1996 (see section 124 of that Act)")
    assert "uk/ukpga/1996/18/s124" in [str(c) for c in result.coordinates]
    defined = router.route(
        "Employment Rights Act 1996 (“the 1996 Act”); section 98 of the 1996 Act"
    )
    assert "uk/ukpga/1996/18/s98" in [str(c) for c in defined.coordinates]


# ---------------------------------------------------------------- provisions


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("ERA 1996 s. 124(3)(4)", ["uk/ukpga/1996/18/s124/3", "uk/ukpga/1996/18/s124/4"]),
        (
            "ERA 1996 s. 124(1ZA)(a)(b)",
            ["uk/ukpga/1996/18/s124/1ZA/a", "uk/ukpga/1996/18/s124/1ZA/b"],
        ),
        ("ERA 1996 s. 124(1)(a)(5)", ["uk/ukpga/1996/18/s124/1/a", "uk/ukpga/1996/18/s124/5"]),
    ],
)
def test_editorial_sibling_lists(router: Router, query: str, expected: list[str]) -> None:
    assert coords(router, query) == expected


def test_nested_reading_wins_when_it_exists(router: Router) -> None:
    assert coords(router, "ERA 1996 s. 124(1ZA)(a)") == ["uk/ukpga/1996/18/s124/1ZA/a"]


# ---------------------------------------------------------------- titles with commas


@pytest.fixture(scope="module")
def comma_router(tmp_path_factory: pytest.TempPathFactory) -> Router:
    root = tmp_path_factory.mktemp("comma")
    write_records(
        root / "data",
        {
            "uk/ukpga/2009/20": (
                "Local Democracy, Economic Development and Construction Act 2009",
                ["uk/ukpga/2009/20/s103"],
            )
        },
    )
    built = build_index(root / "data", catalogue=None, aliases_dir=write_aliases(root / "a", ""))
    write_index(built, root / "index", snapshot=date(2026, 9, 27), sources=["legislation.gov.uk"])
    return Router.from_path(root / "index")


def test_commas_inside_titles(comma_router: Router) -> None:
    result = comma_router.route(
        "section 103 of the Local Democracy, Economic Development and Construction Act 2009"
    )
    assert [str(c) for c in result.coordinates] == ["uk/ukpga/2009/20/s103"]


def test_truncated_long_unknown_title_is_not_refused(router: Router) -> None:
    words = " ".join(f"Word{i}" for i in range(25))
    result = router.route(f"The {words} Order 2015")
    assert result.status is not RouteStatus.INSTRUMENT_NOT_FOUND
