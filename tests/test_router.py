"""Router behaviour on the committed fixture index (M7-UK).

Golden probes follow the plan's Verification section (UK part) and docs/grammar.md rows.
"""

from __future__ import annotations

import gc
import json
import logging
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from bench.stress import GENERATORS
from legal_rag_router import (
    Coordinate,
    NextAction,
    RouteContext,
    Router,
    RouteResult,
    RouteStatus,
)
from legal_rag_router.grammars.uk_grammar import BOUNDARY_WORDS
from legal_rag_router.normalise import MAX_QUERY_CHARS, tokenise
from tests.conftest import FIXTURE_INDEX

BOUND, AMBIGUOUS, OOC = RouteStatus.BOUNDED, RouteStatus.AMBIGUOUS, RouteStatus.OUT_OF_COVERAGE
INSTR_NF, PROV_NF, UNRES = (
    RouteStatus.INSTRUMENT_NOT_FOUND,
    RouteStatus.PROVISION_NOT_FOUND,
    RouteStatus.UNRESOLVED,
)
# Timing budget per query; CI runners are shared and noisy, so CI raises it via the env.
# Coverage tracing slows Python several-fold, so timing budgets widen while it is active.
_TRACED = sys.gettrace() is not None or "COV_CORE_SOURCE" in os.environ
_SCALE = float(os.environ.get("LRR_LATENCY_BUDGET_MS", "2")) / 2 * (10 if _TRACED else 1)
BUDGET_NS = int(2_000_000 * _SCALE)
"""Real queries: < 2 ms p99 (plan step 7)."""
_STRESS = Path(__file__).resolve().parents[1] / "bench" / "results" / "stress-darwin-arm64.json"
NOISE_FLOOR_MS = float(json.loads(_STRESS.read_text())["floor_ms"])
NOISE_BUDGET_NS = int(NOISE_FLOOR_MS * 2 * 1_000_000 * _SCALE)
"""4 KB noise: twice the measured worst case of bench/stress.py (roadmap Q-M7-2)."""
DOUBLING_FACTOR = 3.0 if _SCALE > 1 else 2.5
"""Linear doubling: ≤ 2.5x on a quiet machine, where some classes measure 2.2-2.47x; 3x on CI
or under coverage (roadmap decision 16, amended 2 Oct 2026). Quadratic growth would be ~4x."""


@pytest.fixture(scope="module")
def router() -> Router:
    return Router.from_path(FIXTURE_INDEX)


def coords(result: RouteResult) -> list[str]:
    return [str(c) for c in result.coordinates]


# ---------------------------------------------------------------- bound


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "compensation limit under Employment Rights Act 1996 section 124",
            ["uk/ukpga/1996/18/s124"],
        ),
        ("Equality Act 2010 section 124", ["uk/ukpga/2010/15/s124"]),
        ("s.124(1ZA)(a) of ERA 1996", ["uk/ukpga/1996/18/s124/1ZA/a"]),
        ("ERA 96 s.124", ["uk/ukpga/1996/18/s124"]),
        ("ERA '96, s.124", ["uk/ukpga/1996/18/s124"]),
        ("employment rights act 1996 s124", ["uk/ukpga/1996/18/s124"]),
        ("EMPLOYMENT RIGHTS ACT 1996 SECTION 124", ["uk/ukpga/1996/18/s124"]),
        ("the 1996 Employment Rights Act, s.124", ["uk/ukpga/1996/18/s124"]),
        ("Employment Rights Act of 1996 s.124", ["uk/ukpga/1996/18/s124"]),
        ("Employment Rights Act (1996) s.124", ["uk/ukpga/1996/18/s124"]),
        ("employment rights 1996 s124", ["uk/ukpga/1996/18/s124"]),
        ("Employment Rights Act 1996 article 124", ["uk/ukpga/1996/18/s124"]),
        ("Explain Employment Rights Act 1996 s.124", ["uk/ukpga/1996/18/s124"]),
        ("Employment Rights Act 1996", ["uk/ukpga/1996/18"]),
        ("Law of Property Act 1925 s.1", ["uk/ukpga/Geo5/15-16/20/s1"]),
        ("15 & 16 Geo. 5 c. 20 s.1", ["uk/ukpga/Geo5/15-16/20/s1"]),
        ("Offences against the Person Act 1861 s.18", ["uk/ukpga/Vict/24-25/100/s18"]),
        ("1996 c. 18 s.124", ["uk/ukpga/1996/18/s124"]),
        ("SI 2010/2926 art. 3", ["uk/uksi/2010/2926/art3"]),
        ("S.I. 2010 No. 2926, article 3", ["uk/uksi/2010/2926/art3"]),
        ("SI 2010/2926 s.3", ["uk/uksi/2010/2926/art3"]),  # UK-P-15: s. read as art. for an SI
        ("CPR r. 3.1(2)", ["uk/uksi/1998/3132/rule3.1/2"]),
        ("Sch. 1 para 2 of the Employment Rights Act 1996", ["uk/ukpga/1996/18/sch1/para2"]),
        ("uk/ukpga/1996/18/s124/1ZA/a", ["uk/ukpga/1996/18/s124/1ZA/a"]),
        ("UK/UKPGA/1996/18/S124/1za/A", ["uk/ukpga/1996/18/s124/1ZA/a"]),
        ("uk_ukpga_1996_18", ["uk/ukpga/1996/18"]),
        ("https://www.legislation.gov.uk/ukpga/1996/18/section/124", ["uk/ukpga/1996/18/s124"]),
        ("uk/ukpga/1996/18 section 124", ["uk/ukpga/1996/18/s124"]),  # UK-X-04
        ("SI 2013/2729", ["uk/wsi/2013/2729"]),  # a Welsh SI cited by its UK SI number
        ("Theft Act 1968", ["uk/ukpga/1968/60"]),
        ("ERA 1988", ["uk/ukpga/1988/40"]),
    ],
)
def test_bound(router: Router, query: str, expected: list[str]) -> None:
    result = router.route(query)
    assert result.status is BOUND, (result.status, result.reason, result.clarification)
    assert coords(result) == expected
    assert result.next_action is NextAction.RETRIEVE_BOUNDED
    assert result.index_snapshot == "2026-09-28"


def test_multiple_citations_bind_all(router: Router) -> None:
    result = router.route("ERA 1996 s.124 and Equality Act 2010 s.124")
    assert coords(result) == ["uk/ukpga/1996/18/s124", "uk/ukpga/2010/15/s124"]


def test_lists_ranges_and_parts(router: Router) -> None:
    result = router.route("sections 94, 95 and 98 of the Employment Rights Act 1996")
    assert coords(result) == [f"uk/ukpga/1996/18/s{n}" for n in (94, 95, 98)]
    result = router.route("ss.94-98 of the Employment Rights Act 1996")
    assert coords(result) == [f"uk/ukpga/1996/18/s{n}" for n in (94, 95, 96, 97, 98)]
    part = router.route("Part X of the Employment Rights Act 1996")
    assert "uk/ukpga/1996/18/s124" in coords(part)
    assert coords(router.route("Part 10 of the Employment Rights Act 1996")) == coords(part)


def test_repealed_instruments_bind(router: Router) -> None:
    result = router.route("House of Commons (Clergy Disqualification) Act 1801")
    assert result.status is BOUND
    assert result.repealed


# ---------------------------------------------------------------- typo tiers (plan verification)


def test_small_typo_binds_with_correction(router: Router) -> None:
    result = router.route("Employment Rihgts Act 1996 s.124")
    assert coords(result) == ["uk/ukpga/1996/18/s124"]
    assert result.corrections == (("rihgts", "rights"),)


def test_two_misspelled_words_ask(router: Router) -> None:
    result = router.route("Emplyment Rihgts Act 1996")
    assert result.status is AMBIGUOUS
    assert str(result.candidates[0].coordinate) == "uk/ukpga/1996/18"
    assert result.corrections == ()  # nothing was auto-corrected


def test_reordered_title_binds(router: Router) -> None:
    result = router.route("Rights of Employment Act 1996")
    assert coords(result) == ["uk/ukpga/1996/18"]
    assert result.corrections == (("reordered", "Employment Rights Act 1996"),)


@pytest.mark.parametrize(
    ("query", "first_suggestion"),
    [
        ("Employment Rights Act 1995", "uk/ukpga/1996/18"),
        ("rights of employment act 1990", "uk/ukpga/1996/18"),
        ("Marchwood Commercial Arbitration Act 1996", "uk/ukpga/1996/23"),
    ],
)
def test_refused_with_suggestion(router: Router, query: str, first_suggestion: str) -> None:
    result = router.route(query)
    assert result.status is INSTR_NF
    assert str(result.suggestions[0].coordinate) == first_suggestion
    assert result.next_action is NextAction.REFUSE
    assert result.coordinates == ()
    assert "2026-09-28" in result.messages[0]


def test_codigo_style_particles_and_accents_fold(router: Router) -> None:
    assert router.route("Offences against the Person Act 1861 s.18").status is BOUND


@pytest.mark.parametrize(
    "query",
    [
        "arbitration rules in Marchwood Commercial Arbitration Order 2022",
        "Family Rights Act 1996",
        "Marchwood Commercial Arbitration Order 2022 s.4",
        "the Employment Rights (Increase of Limits) Order 1812",
    ],
)
def test_invented_law_is_refused(router: Router, query: str) -> None:
    result = router.route(query)
    assert result.status is INSTR_NF
    assert result.coordinates == ()
    assert result.latency_ns < BUDGET_NS


@pytest.mark.parametrize(
    "query",
    [
        "marchwood commercial arbitration act 1996",  # lower case: ask, never bind
        "employment rights 1990",  # no type word: not a clear claim
        "Emplyment Rihgts Act 1996",
    ],
)
def test_near_misses_ask(router: Router, query: str) -> None:
    result = router.route(query)
    assert result.status is AMBIGUOUS
    assert result.next_action is NextAction.ASK_USER
    assert result.clarification


# ---------------------------------------------------------------- provisions


@pytest.mark.parametrize(
    "query",
    ["Employment Rights Act 1996 s.999", "ERA 1996 s.124(9)", "uk/ukpga/1996/18/s999"],
)
def test_missing_provision(router: Router, query: str) -> None:
    result = router.route(query)
    assert result.status is PROV_NF
    assert result.next_action is NextAction.REFUSE


def test_open_range_asks(router: Router) -> None:
    assert router.route("s.98 et seq. ERA 1996").reason == "open_range"


def test_case_variants_bind_on_exact_case(router: Router) -> None:  # decision 7
    assert coords(router.route("uk/uksi/1990/2145/sch1/para34/a")) == [
        "uk/uksi/1990/2145/sch1/para34/a"
    ]
    assert coords(router.route("uk/uksi/1990/2145/sch1/para34/A")) == [
        "uk/uksi/1990/2145/sch1/para34/A"
    ]
    bound = router.route("The Civil Aviation Act 1982 (Jersey) Order 1990 Sch. 1 para 34(A)")
    assert coords(bound) == ["uk/uksi/1990/2145/sch1/para34/A"]


def test_duplicated_source_ids_ask(router: Router) -> None:  # decision 13
    result = router.route("uk/uksi/1987/50/sch/parai")
    assert result.status is AMBIGUOUS
    assert result.reason == "duplicated_in_source"


# ---------------------------------------------------------------- ambiguity


def test_bare_provision_lists_salient_instruments(router: Router) -> None:
    result = router.route("section 124")
    assert result.status is AMBIGUOUS
    ids = {c.coordinate.instrument_id for c in result.candidates}
    assert {"uk_ukpga_1996_18", "uk_ukpga_2010_15"} <= ids


def test_the_1996_act(router: Router) -> None:
    result = router.route("the 1996 Act")
    assert result.status is AMBIGUOUS
    assert all(c.coordinate.instrument[1] == "1996" for c in result.candidates)


def test_title_without_year(router: Router) -> None:
    result = router.route("Finance Act")
    assert result.status is AMBIGUOUS
    assert {c.coordinate.instrument_id for c in result.candidates} == {
        "uk_ukpga_2024_3",
        "uk_ukpga_2025_8",
    }


def test_same_title_same_year_asks_with_numbers(router: Router) -> None:
    result = router.route("Military Lands Act 1897")
    assert result.status is AMBIGUOUS
    assert [c.label for c in result.candidates] == [
        "Military Lands Act 1897 (c. 6)",
        "Military Lands Act 1897 (c. 7)",
    ]


# ---------------------------------------------------------------- coverage


@pytest.mark.parametrize(
    ("query", "reason"),
    [
        ("Criminal Justice and Licensing (Scotland) Act 2010 s.1", "series"),
        ("Employment Rights Bill", "bill"),
        ("[2020] UKSC 1", "case"),
        ("Article 82 UK GDPR", "eu"),
        ("Art. 42.1 letra b) CdC", "es"),
        (
            "art. 3 of the Sugar Beet (Research and Education) Order 1981",
            "provision_structure_unavailable",
        ),
        ("ERA 1996 s.124 and Article 82 UK GDPR", "eu"),  # decision 14
        ("SSI 2003/623", "series"),
    ],
)
def test_out_of_coverage(router: Router, query: str, reason: str) -> None:
    result = router.route(query)
    assert result.status is OOC, (result.status, result.reason)
    assert result.reason == reason
    assert result.coordinates == ()
    assert result.next_action in (NextAction.VERIFY_LIVE, NextAction.DECLARE_OUT_OF_COVERAGE)


def test_pdf_only_instrument_binds_as_a_whole(router: Router) -> None:
    result = router.route("The Sugar Beet (Research and Education) Order 1981")
    assert coords(result) == ["uk/uksi/1981/292"]


# ---------------------------------------------------------------- exclusion (decision 15)


def test_provision_exclusion_binds_the_rest(router: Router) -> None:
    result = router.route(
        "In the Employment Rights Act 1996, what applies across all sections except section 124?"
    )
    assert coords(result) == ["uk/ukpga/1996/18"]
    assert [str(c) for c in result.excluded] == ["uk/ukpga/1996/18/s124"]
    assert [c.resolution for c in result.citations] == ["resolved"]


def test_excluded_instrument_is_not_a_target(router: Router) -> None:
    result = router.route("s.124, not the Equality Act 2010 one, the ERA 1996")
    assert coords(result) == ["uk/ukpga/1996/18/s124"]
    assert not any(c.instrument_id == "uk_ukpga_2010_15" for c in result.coordinates)


def test_plain_not_is_not_an_exclusion(router: Router) -> None:
    result = router.route("does s.124 of the Employment Rights Act 1996 not apply here")
    assert coords(result) == ["uk/ukpga/1996/18/s124"]
    assert result.excluded == ()


def test_single_instrument_links_loose_provision(router: Router) -> None:
    result = router.route(
        "In the Employment Rights Act 1996, what does the cap in section 124 cover?"
    )
    assert coords(result) == ["uk/ukpga/1996/18/s124"]


# ---------------------------------------------------------------- context


def test_context_follow_up(router: Router) -> None:
    context = RouteContext((Coordinate.parse("uk/ukpga/1996/18/s124"),))
    result = router.route("what about section 125?", context=context)
    assert coords(result) == ["uk/ukpga/1996/18/s125"]
    assert result.source == "context"
    assert (
        router.route("and under that Act, s.98?", context=["uk/ukpga/1996/18"]).source == "context"
    )


def test_named_instrument_beats_context(router: Router) -> None:
    result = router.route("Equality Act 2010 s.124", context=["uk/ukpga/1996/18/s124"])
    assert coords(result) == ["uk/ukpga/2010/15/s124"]
    assert result.source == "grammar"


def test_invalid_context_is_ignored(router: Router) -> None:
    result = router.route(
        "what about section 125?", context=["uk/ukpga/1996/99/s1", "not a coordinate"]
    )
    assert result.status is not BOUND


def test_context_ref_without_context_asks(router: Router) -> None:
    assert router.route("what does that Act say?").reason == "context_needed"


# ---------------------------------------------------------------- misc


def test_temporal_hint_is_extracted_not_bound(router: Router) -> None:
    result = router.route(
        "what did s.124 of the Employment Rights Act 1996 say as it stood in 2012"
    )
    assert coords(result) == ["uk/ukpga/1996/18/s124"]
    assert result.temporal_hint == "as it stood in 2012"


@pytest.mark.parametrize(
    "query",
    ["unfair dismissal compensation cap", "£124 for 124 employees on 1 April 1996", "", "   "],
)
def test_no_citation_is_unresolved(router: Router, query: str) -> None:
    result = router.route(query)
    assert result.status is UNRES
    assert result.next_action is NextAction.DISCOVER_THEN_BIND


def test_overlong_query(router: Router) -> None:
    result = router.route("s.124 " * (MAX_QUERY_CHARS // 5))
    assert (result.status, result.reason) == (UNRES, "query_too_long")


def test_many_citations_are_capped(router: Router) -> None:
    result = router.route(" and ".join(f"ERA 1996 s.{n}" for n in range(1, 40)))
    assert (result.status, result.reason) == (UNRES, "too_many_citations")


def test_jurisdiction_scope(router: Router) -> None:
    assert router.route("ERA 1996 s.124", jurisdictions=["es"]).status is UNRES
    assert router.route("ERA 1996 s.124", jurisdictions=["uk"]).status is BOUND


def test_citations_always_filled(router: Router) -> None:
    result = router.route("Marchwood Order 2021 section 4")
    [citation] = result.citations
    assert citation.title_as_cited == "Marchwood Order 2021"
    assert (citation.year, citation.provision, citation.resolution) == (2021, "s.4", "not_in_index")


def test_live_checkable_freshness_window(router: Router) -> None:
    closed = router.route("Marchwood Commercial Arbitration Order 2022")
    assert not closed.citations[0].live_checkable  # before the snapshot year: closed period
    fresh = router.route("Marchwood Commercial Arbitration Order 2026")
    assert fresh.citations[0].live_checkable


def test_miss_logging_is_opt_in_and_redacted(caplog: pytest.LogCaptureFixture) -> None:
    quiet = Router.from_path(FIXTURE_INDEX)
    with caplog.at_level(logging.INFO, logger="legal_rag_router.misses"):
        quiet.route("s.124 of the Blah")
    assert not caplog.records
    loud = Router.from_path(FIXTURE_INDEX, log_misses=True)
    with caplog.at_level(logging.INFO, logger="legal_rag_router.misses"):
        result = loud.route("what does the Blah Act say?")
    assert result.status is UNRES
    [record] = caplog.records
    assert record.event == "unresolved_with_signal"  # type: ignore[attr-defined]
    assert record.query is None  # type: ignore[attr-defined] # no text without a redactor
    assert len(record.query_sha256) == 64  # type: ignore[attr-defined]


# ---------------------------------------------------------------- invariants


INVARIANT_QUERIES = [
    "compensation limit under Employment Rights Act 1996 section 124",
    "Marchwood Commercial Arbitration Act 1996",
    "marchwood commercial arbitration act 1996",
    "Family Arbitration Act 1996",
    "Commercial Arbitration Act 1996 s.1",
    "Northern Employment Rights Act 1996 s.124",
    "the Scottish Theft Act 1968",
    "Welsh Human Rights Act 1998 s.3",
    "Revised Finance Act 2024",
]


@pytest.mark.parametrize("query", INVARIANT_QUERIES)
def test_bound_results_account_for_their_span(router: Router, query: str) -> None:
    """No BOUNDED result may leave title-like words next to its citation (plan step 7)."""
    result = router.route(query)
    if result.status is not BOUND or result.source != "grammar":
        return
    for citation in result.citations:
        start = citation.span[0]
        before = [t for t in tokenise(query[:start]) if t.kind == "word"]
        if before:
            assert before[-1].text in BOUNDARY_WORDS, (query, before[-1].text)


def test_routing_is_deterministic_and_thread_safe(router: Router) -> None:
    queries = INVARIANT_QUERIES * 20
    expected = [router.route(q) for q in queries]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(router.route, queries))
    strip = [(r.status, r.coordinates, r.candidates, r.reason) for r in results]
    assert strip == [(r.status, r.coordinates, r.candidates, r.reason) for r in expected]


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.text(max_size=MAX_QUERY_CHARS))
def test_router_never_raises_and_stays_fast(text: str) -> None:
    router = _shared_router()
    result = router.route(text)
    assert result.reason != "internal_error"
    assert result.latency_ns < NOISE_BUDGET_NS


@settings(max_examples=40, deadline=None)
@given(st.lists(st.sampled_from(
    ["Act", "1996", "s.124", "of", "the", "Employment", "Rights", "Order", "(", ")", "Sch.", "2",
     "para", "4", "except", "not", "ERA", "SI", "2011/3006", "§", "Part", "X", ",", "and"]
), max_size=400))  # fmt: skip
def test_adversarial_citation_soup_stays_bounded(parts: list[str]) -> None:
    result = _shared_router().route(" ".join(parts))
    assert result.reason != "internal_error"
    assert result.latency_ns < NOISE_BUDGET_NS


_ROUTER: list[Router] = []


def _shared_router() -> Router:
    if not _ROUTER:
        _ROUTER.append(Router.from_path(FIXTURE_INDEX))
    return _ROUTER[0]


def test_warm_latency_under_budget(router: Router) -> None:
    for query in INVARIANT_QUERIES:
        router.route(query)  # warm-up
    worst = max(min(router.route(q).latency_ns for _ in range(5)) for q in INVARIANT_QUERIES)
    assert worst < BUDGET_NS, f"{worst / 1e6:.2f} ms"


def test_regex_patterns_are_linear() -> None:
    """ReDoS guard: long pathological inputs finish within the measured noise budget."""
    router = _shared_router()
    for probe in (
        "s" * 4000,
        "(" * 4000,
        "1" * 4000,
        "a " * 2000,
        "s.1(" * 1000,
        "Act 1996 " * 450,
    ):
        assert router.route(probe[:MAX_QUERY_CHARS]).latency_ns < NOISE_BUDGET_NS, probe[:20]


@pytest.mark.parametrize("name", sorted(GENERATORS))
def test_doubling_input_is_linear(name: str) -> None:
    """Doubling a 4 KB-class input never more than 2.5x's the time (roadmap Q-M7-2)."""
    router = _shared_router()
    text = GENERATORS[name](random.Random(f"20260927:{name}:test"), MAX_QUERY_CHARS)

    def best_pair(short: str, long: str) -> tuple[int, int]:
        # Alternate the two sizes, GC paused, so a noisy moment on a shared CI runner hits
        # both rather than one; the best of 15 rounds is each input's own cost.
        times: tuple[list[int], list[int]] = ([], [])
        gc.disable()
        try:
            for _ in range(15):
                times[0].append(router.route(short).latency_ns)
                times[1].append(router.route(long).latency_ns)
        finally:
            gc.enable()
        return min(times[0]), min(times[1])

    for n in (MAX_QUERY_CHARS // 4, MAX_QUERY_CHARS // 2):
        small, large = best_pair(text[:n], text[: 2 * n])
        assert large <= DOUBLING_FACTOR * max(small, 50_000), (name, n, small, large)


def test_results_never_carry_query_text_into_coordinates(router: Router) -> None:
    result = router.route('uk/ukpga/1996/18/s124" or "1"=="1')
    for coordinate in result.coordinates:
        assert re.fullmatch(r"[0-9A-Za-z./-]+", str(coordinate))
