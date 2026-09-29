"""Fixes for what the first sealed run found (roadmap M10, reports/sealed-run-uk.md)."""

from __future__ import annotations

import pytest

from ingest.build_index import main as build_main
from ingest.build_index import title_variants
from legal_rag_router import Router, RouteStatus
from legal_rag_router.typo import TypoPolicy
from tests.test_build_index import write_aliases, write_records

RTA = "uk/ukpga/1988/52"
COMPETITION = "uk/ukpga/1998/41"
EXEMPTION = "uk/uksi/2001/2993"
EXPIRED = "uk/uksi/2019/9"


@pytest.fixture(scope="module")
def router(tmp_path_factory: pytest.TempPathFactory) -> Router:
    root = tmp_path_factory.mktemp("fixes")
    write_records(
        root / "data",
        {
            RTA: ("Road Traffic Act 1988", [f"{RTA}/s1"]),
            "uk/uksi/2005/9": ("The Road Trafic Signs Regulations 2005", []),  # a source typo
            COMPETITION: ("Competition Act 1998", [f"{COMPETITION}/s11"]),
            EXEMPTION: (
                "The Competition Act 1998 (Section 11 Exemption) Regulations 2001",
                [f"{EXEMPTION}/reg3", f"{EXEMPTION}/reg3/2"],
            ),
            "uk/uksi/2010/1": ("The Harbour Lights Order 2010", []),
            "uk/uksi/2010/2": ("The Harbours Light Order 2010", []),
            EXPIRED: (
                "The Immigration (Amendment) (EU Exit) Regulations 2019 (expired—not approved)",
                [f"{EXPIRED}/reg4"],
            ),
        },
    )
    out = root / "index"
    args = ["--data", str(root / "data"), "--out", str(out), "--snapshot", "2026-09-29"]
    assert build_main([*args, "--aliases", str(write_aliases(root / "a", ""))]) == 0
    # A tiny index cannot hold "traffic" in 20 titles: the ratio is lowered for the test only.
    return Router.from_path(out, typo_policy=TypoPolicy(rare_word_ratio=1))


@pytest.mark.parametrize(
    ("query", "coordinates"),
    [
        ("Road Trafic Act 1988", [RTA]),  # a known but rare word is itself a typo
        ("Competition Act 1998 (Section 11 Exemption) Regulations 2001, reg. 3(2)",
         [f"{EXEMPTION}/reg3/2"]),
        ("Competition Act 1998 (Section 11 Exemption) Regulations 2001 (S.I. 2001/2993), reg. 3(2)",
         [f"{EXEMPTION}/reg3/2"]),
        ("section 11 of the Competition Act 1998", [f"{COMPETITION}/s11"]),  # prose unaffected
        ("regulation 4 of the Immigration (Amendment) (EU Exit) Regulations 2019",
         [f"{EXPIRED}/reg4"]),
    ],
)  # fmt: skip
def test_fixed_forms_bind(router: Router, query: str, coordinates: list[str]) -> None:
    result = router.route(query)
    assert result.status is RouteStatus.BOUNDED, (result.status, result.reason)
    assert [str(c) for c in result.coordinates] == coordinates


def test_the_rare_word_correction_is_recorded(router: Router) -> None:
    assert router.route("Road Trafic Act 1988").corrections == (("trafic", "traffic"),)


@pytest.mark.parametrize(
    ("title", "key"),
    [
        ("The Immigration (Amendment) (EU Exit) Regulations 2019 (expired—not approved)",
         "immigration amendment eu exit regulations|2019"),
        ("Road Act 1965 ( repealed 1.11.1996)", "road act|1965"),
        ("Finance (No. 2) Act 2023", "finance no 2 act|2023"),  # distinguishing words stay
    ],
)  # fmt: skip
def test_editorial_notes_leave_the_title_key(title: str, key: str) -> None:
    assert title_variants(title)[0] == key


def test_two_single_word_corrections_that_fit_different_titles_ask(router: Router) -> None:
    result = router.route("The Harbour Light Order 2010")  # "harbours light" or "lights"?
    assert (result.status, result.reason) == (RouteStatus.AMBIGUOUS, "typo")
    assert {str(c.coordinate) for c in result.candidates} == {"uk/uksi/2010/1", "uk/uksi/2010/2"}


def test_more_citations_than_the_mention_limit_is_refused(router: Router) -> None:
    query = "Road Traffic Act 1988 s.1, " * 13  # 13 titles (26 anchors) and 13 provisions
    result = router.route(query)
    assert (result.status, result.reason) == (RouteStatus.UNRESOLVED, "too_many_citations")


@pytest.mark.parametrize(
    ("query", "bound"),
    [
        ("Road Traffic Act 1988 s.1 and its explanatory notes to come", [f"{RTA}/s1"]),
        (
            "the explanatory notes to its guidance and the Road Traffic Act 1988",
            [RTA],
        ),  # words between
    ],
)
def test_the_notes_cue_marks_only_the_instrument_right_after_it(
    router: Router, query: str, bound: list[str]
) -> None:
    result = router.route(query)
    assert [str(c) for c in result.coordinates] == bound
