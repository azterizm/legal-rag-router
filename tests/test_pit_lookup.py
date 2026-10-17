"""Point-in-time lookup (bench/pit): dates, the range query, the chain and the sealed scoring."""

import json
from datetime import date, timedelta

import pytest

from bench.pit.limits import LIMITS_JSON
from bench.pit.lookup import Answer, Limits, parse_date, render, resolve
from bench.pit.run import score
from legal_rag_router import Router
from tests.conftest import FIXTURE_INDEX

S124 = "uk/ukpga/1996/18/s124"
CS2_PROBE = (
    "As at 1 January 2012, what was the maximum compensatory award for unfair dismissal "
    "under section 124 of the Employment Rights Act 1996?"
)


@pytest.fixture(scope="module")
def limits() -> Limits:
    return Limits.from_path()


@pytest.mark.parametrize(
    ("hint", "expected"),
    [
        ("As at 1 January 2012", (date(2012, 1, 1), None)),
        ("as of 6th April 2020", (date(2020, 4, 6), None)),
        ("as at January 1, 2012", (date(2012, 1, 1), None)),
        ("as in force on 1.2.2012", (date(2012, 2, 1), None)),
        ("as at 2012-01-31", (date(2012, 1, 31), None)),
        ("as at 2012", (None, "IMPRECISE_DATE")),
        ("as of March 2013", (None, "IMPRECISE_DATE")),
        ("as at 31 February 2012", (None, "IMPRECISE_DATE")),
        ("as enacted", (None, "NO_DATE")),
        (None, (None, "NO_DATE")),
        ("between 1 January 2012 and 1 March 2012", (None, "AMBIGUOUS")),
    ],
)
def test_parse_date(hint: str | None, expected: tuple[date | None, str | None]) -> None:
    assert parse_date(hint) == expected


@pytest.mark.parametrize(
    ("on", "amount", "si"),
    [
        (date(2012, 1, 1), "£68,400", "uk/uksi/2010/2926"),
        (date(2011, 2, 1), "£68,400", "uk/uksi/2010/2926"),
        (date(2012, 1, 31), "£68,400", "uk/uksi/2010/2926"),
        (date(2012, 2, 1), "£72,300", "uk/uksi/2011/3006"),
        (date(2014, 1, 1), "£74,200", "uk/uksi/2012/3007"),
        (date(2030, 1, 1), "£123,543", "uk/uksi/2026/310"),
    ],
)
def test_range_query(limits: Limits, on: date, amount: str, si: str) -> None:
    answer = limits.at(S124, on)
    assert (answer.status, answer.amount, answer.si) == ("FOUND", amount, si)


def test_every_boundary_day_either_side(limits: Limits) -> None:
    for row in json.loads(LIMITS_JSON.read_text(encoding="utf-8")):
        start = date.fromisoformat(row["valid_from"])
        assert limits.at(row["coordinate"], start).si == row["si"]
        before = limits.at(row["coordinate"], start - timedelta(days=1))
        assert before.si != row["si"]
        if row["valid_to"]:
            last = date.fromisoformat(row["valid_to"]) - timedelta(days=1)
            assert limits.at(row["coordinate"], last).si == row["si"]


def test_outside_the_table(limits: Limits) -> None:
    assert limits.at(S124, date(2011, 1, 31)).status == "NO_ROW"
    assert limits.at("uk/ukpga/2006/46/s382", date(2014, 1, 1)).status == "NOT_COVERED"


def test_the_chain_answers_the_cs2_probe(limits: Limits) -> None:
    answer = resolve(Router.from_path(FIXTURE_INDEX).route(CS2_PROBE), limits)
    assert (answer.status, answer.amount, answer.si, answer.on) == (
        "FOUND",
        "£68,400",
        "uk/uksi/2010/2926",
        "2012-01-01",
    )
    assert "1st February 2011" in (answer.transitional or "")
    assert render(answer).startswith("£68,400. ")


def test_no_figure_without_a_date() -> None:
    router = Router.from_path(FIXTURE_INDEX)
    answer = resolve(router.route("ERA 1996 s.124 as at 2012"), Limits.from_path())
    assert answer.status == "IMPRECISE_DATE"
    assert "£" not in render(answer)


def test_no_figure_without_a_single_binding(limits: Limits) -> None:
    router = Router.from_path(FIXTURE_INDEX)
    assert resolve(router.route("section 124"), limits).status == "NOT_BOUND"
    assert render(Answer("NOT_BOUND")).startswith("No figure")


def test_score_follows_the_audit_rule() -> None:
    expectation = {"must_contain": ["£68,400"], "must_not_contain": ["£74,200"]}
    assert score("The cap was £68,400.", expectation)["status"] == "pass"
    assert score("It was £68,400, now £74,200.", expectation)["status"] == "pass"
    assert score("The cap was £74,200.", expectation)["status"] == "fail"
    assert score("The cap was £72,300.", expectation)["status"] == "not_captured"
