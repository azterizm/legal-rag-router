"""Sealed-run metrics (roadmap M10): the Clopper-Pearson bound and the scoring rules."""

from __future__ import annotations

import pytest

from eval.metrics import Outcome, Rate, binomial_cdf, domain_metrics, upper_bound

ERA = "uk/ukpga/1996/18"
CA06 = "uk/ukpga/2006/46"


@pytest.mark.parametrize(
    ("k", "n", "expected"),
    [
        (0, 600, 0.004980),  # the plan's rule of three: < 0.5 % after 0 in 600
        (0, 100, 0.029513),
        (1, 100, 0.046560),  # R: binom.test(1, 100, alternative = "less")
        (5, 100, 0.102253),
        (10, 10, 1.0),
        (0, 0, 1.0),
    ],
)
def test_upper_bound_known_values(k: int, n: int, expected: float) -> None:
    assert upper_bound(k, n) == pytest.approx(expected, abs=1e-6)


def test_upper_bound_is_where_the_tail_is_five_percent() -> None:
    for k, n in ((1, 100), (3, 50), (7, 1000)):
        assert binomial_cdf(k, n, upper_bound(k, n)) == pytest.approx(0.05, abs=1e-9)
        assert upper_bound(k, n) > k / n


def test_binomial_cdf_edges() -> None:
    assert binomial_cdf(0, 10, 0.0) == 1.0
    assert binomial_cdf(9, 10, 1.0) == 0.0
    assert binomial_cdf(10, 10, 1.0) == 1.0
    assert binomial_cdf(10, 10, 0.3) == pytest.approx(1.0)


def test_rate_as_dict() -> None:
    assert Rate(0, 0).as_dict() == {"count": 0, "total": 0, "rate": 0.0, "upper_95": 1.0}


def _o(
    battery: str,
    status: str,
    bound: tuple[str, ...] = (),
    *,
    expected_status: str = "ROUTE_BOUNDED",
    expected: tuple[str, ...] = (f"{ERA}/s124",),
    source: str = "hand",
    top: str | None = None,
    corrected: bool = False,
    split: str | None = None,
) -> Outcome:
    return Outcome(battery, f"uk-{battery}-0001", source, expected_status, expected, status,
                   bound, top, corrected, split)  # fmt: skip


@pytest.mark.parametrize(
    ("bound", "met", "wrong_instrument"),
    [
        ((f"{ERA}/s124",), True, False),
        ((f"{ERA}/s124/1ZA",), True, False),  # beneath the expected coordinate
        ((ERA,), True, False),  # the whole instrument above it
        ((f"{ERA}/s125",), False, False),  # right Act, wrong provision
        ((f"{CA06}/s124",), False, True),  # another Act: a collision
    ],
)
def test_met_and_wrong_instrument(
    bound: tuple[str, ...], met: bool, wrong_instrument: bool
) -> None:
    outcome = _o("collision", "ROUTE_BOUNDED", bound)
    assert (outcome.met, outcome.wrong_instrument) == (met, wrong_instrument)


def test_an_unbound_result_is_neither_met_nor_a_collision() -> None:
    outcome = _o("collision", "ROUTE_UNRESOLVED")
    assert (outcome.met, outcome.wrong_instrument) == (False, False)


def test_domain_metrics() -> None:
    refused = "EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND"
    not_found = "EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND"
    outcomes = [
        _o("collision", "ROUTE_BOUNDED", (f"{ERA}/s124",)),
        _o("collision", "ROUTE_BOUNDED", (f"{CA06}/s124",)),
        _o("misroute", "ROUTE_UNRESOLVED", source="real_document"),
        _o("misroute", "ROUTE_BOUNDED", (f"{ERA}/s125",), source="real_document"),
        _o("false_abstention", refused),
        _o("false_abstention", "ROUTE_OUT_OF_COVERAGE"),
        _o("invented", "ROUTE_BOUNDED", (ERA,), expected_status=refused, expected=()),
        _o("invented", refused, expected_status=refused, expected=()),
        _o("catalogue", refused, expected_status="ROUTE_OUT_OF_COVERAGE", expected=()),
        _o("typo", "ROUTE_BOUNDED", (ERA,), expected=(ERA,), corrected=True, split="test"),
        _o("typo", "ROUTE_AMBIGUOUS", expected_status="ROUTE_AMBIGUOUS", expected=(ERA,),
           top=ERA, split="test"),
        _o("typo", "ROUTE_BOUNDED", (ERA,), expected_status=not_found, expected=(), split="test"),
        _o("typo", "ROUTE_UNRESOLVED", expected=(ERA,), split="dev"),  # dev rows are not scored
    ]  # fmt: skip
    m = domain_metrics(outcomes)

    def count(key: str) -> tuple[int, int]:
        return m[key]["count"], m[key]["total"]

    assert count("collision") == (1, 2)
    assert count("misroute") == (2, 6)  # CA06 s124 for ERA s124, and s125 for s124
    assert count("misroute_wrong_instrument") == (1, 6)
    assert count("miss_heldout") == (1, 2)
    assert count("false_abstention") == (1, 6)
    assert count("covered_reported_out_of_coverage") == (1, 8)
    assert count("uncovered_refused") == (1, 1)
    assert count("bound_on_invented") == (1, 2)
    assert count("strict_abstention") == (1, 2)
    assert count("typo_auto_correct_precision") == (1, 1)
    assert count("typo_auto_correct_recall") == (1, 1)
    assert count("typo_clarify_recall") == (1, 1)
    assert count("typo_bound_when_it_should_not") == (1, 2)
    collision = m["batteries"]["collision"]
    assert collision["met"]["count"] == 1
    assert collision["wrong_instrument"]["count"] == 1
    assert m["batteries"]["invented"].get("met") is None  # no bound rows expected
