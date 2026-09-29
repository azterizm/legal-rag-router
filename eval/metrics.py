"""Per-domain metrics for the sealed run (plan step 9, roadmap M10).

Every rate carries a one-sided 95 % Clopper-Pearson upper bound: the largest error rate
still consistent with the observed count. With 0 errors in 600 rows it is 0.50 % (the
plan's "rule of three"). Computed exactly from the binomial distribution, stdlib only.

Scoring (``docs/batteries.md``, "Intended scoring"):

- A ``ROUTE_BOUNDED`` row is **met** when each expected coordinate is bound, or something
  above or beneath it is.
- Bound but not met is a **misroute** (the plan: "bound, but to the wrong coordinate"),
  reported in two parts:
  - **wrong instrument**: an expected instrument has no bound coordinate. In the
    ``collision`` battery this is a **collision**.
  - **wrong provision**: the right instrument, another provision.
- On a ``ROUTE_BOUNDED`` row, a refusal is a **false abstention** and ``ROUTE_UNRESOLVED``
  is a **miss**.
- Other rows compare the status only.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Final

from legal_rag_router.coordinate import Coordinate

CONFIDENCE: Final = 0.95
BOUND: Final = "ROUTE_BOUNDED"
AMBIGUOUS: Final = "ROUTE_AMBIGUOUS"
UNRESOLVED: Final = "ROUTE_UNRESOLVED"
OUT_OF_COVERAGE: Final = "ROUTE_OUT_OF_COVERAGE"
REFUSALS: Final = frozenset(
    {"EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND", "EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND"}
)


def binomial_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p)."""
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    log_p, log_q = math.log(p), math.log1p(-p)
    total = 0.0
    for i in range(k + 1):
        log_pmf = (
            math.lgamma(n + 1)
            - math.lgamma(i + 1)
            - math.lgamma(n - i + 1)
            + i * log_p
            + (n - i) * log_q
        )
        total += math.exp(log_pmf)
    return min(1.0, total)


def upper_bound(k: int, n: int, confidence: float = CONFIDENCE) -> float:
    """One-sided Clopper-Pearson upper bound on a rate of ``k`` in ``n``.

    The ``p`` at which observing ``k`` or fewer has probability ``1 - confidence``.
    """
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0
    alpha = 1.0 - confidence
    if k == 0:
        return float(1.0 - alpha ** (1.0 / n))
    lo, hi = k / n, 1.0
    for _ in range(100):  # bisection: the CDF falls as p rises
        mid = (lo + hi) / 2
        if binomial_cdf(k, n, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


@dataclass(frozen=True, slots=True)
class Rate:
    """``count`` events in ``total`` rows, with the upper bound."""

    count: int
    total: int

    @property
    def rate(self) -> float:
        return self.count / self.total if self.total else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "total": self.total,
            "rate": round(self.rate, 6),
            "upper_95": round(upper_bound(self.count, self.total), 6),
        }


def related(a: Coordinate, b: Coordinate) -> bool:
    return a == b or a.is_ancestor_of(b) or b.is_ancestor_of(a)


@dataclass(frozen=True, slots=True)
class Outcome:
    """One battery row, routed."""

    battery: str
    row_id: str
    source: str
    expected_status: str
    expected: tuple[str, ...]
    status: str
    bound: tuple[str, ...]
    top_candidate: str | None
    corrected: bool
    split: str | None = None

    @property
    def met(self) -> bool:
        if self.status != BOUND:
            return False
        bound = [Coordinate.parse(c) for c in self.bound]
        return all(any(related(Coordinate.parse(e), b) for b in bound) for e in self.expected)

    @property
    def wrong_instrument(self) -> bool:
        if self.status != BOUND or self.met:
            return False
        instruments = {Coordinate.parse(c).instrument_id for c in self.bound}
        return any(Coordinate.parse(e).instrument_id not in instruments for e in self.expected)


def _count(rows: Iterable[Outcome], test: Any) -> int:
    return sum(1 for row in rows if test(row))


def battery_metrics(rows: list[Outcome]) -> dict[str, Any]:
    """Status accuracy for every battery, and the plan's rates where they apply."""
    out: dict[str, Any] = {"rows": len(rows)}
    out["status_as_expected"] = Rate(
        _count(rows, lambda r: r.status == r.expected_status), len(rows)
    ).as_dict()
    bound = [r for r in rows if r.expected_status == BOUND]
    if bound:
        n = len(bound)
        out["met"] = Rate(_count(bound, lambda r: r.met), n).as_dict()
        out["misroute"] = Rate(
            _count(bound, lambda r: r.status == BOUND and not r.met), n
        ).as_dict()
        out["wrong_instrument"] = Rate(_count(bound, lambda r: r.wrong_instrument), n).as_dict()
        out["wrong_provision"] = Rate(
            _count(bound, lambda r: r.status == BOUND and not r.met and not r.wrong_instrument), n
        ).as_dict()
        out["false_abstention"] = Rate(_count(bound, lambda r: r.status in REFUSALS), n).as_dict()
        out["miss"] = Rate(_count(bound, lambda r: r.status == UNRESOLVED), n).as_dict()
        out["asked"] = Rate(_count(bound, lambda r: r.status == AMBIGUOUS), n).as_dict()
        out["out_of_coverage"] = Rate(
            _count(bound, lambda r: r.status == OUT_OF_COVERAGE), n
        ).as_dict()
    return out


def domain_metrics(outcomes: list[Outcome]) -> dict[str, Any]:
    """The plan's metrics for one domain (plan step 9)."""
    by_battery: dict[str, list[Outcome]] = {}
    for outcome in outcomes:
        by_battery.setdefault(outcome.battery, []).append(outcome)
    typo = [r for r in by_battery.get("typo", []) if r.split == "test"]
    invented = by_battery.get("invented", [])
    heldout = [r for r in by_battery.get("misroute", []) if r.source == "real_document"]
    bound_rows = [r for r in outcomes if r.expected_status == BOUND and r.battery != "typo"]
    not_ooc = [r for r in outcomes if r.expected_status != OUT_OF_COVERAGE and r.battery != "typo"]
    ooc = [r for r in outcomes if r.expected_status == OUT_OF_COVERAGE]
    corrected = [r for r in typo if r.corrected and r.status == BOUND]
    should_bind = [r for r in typo if r.expected_status == BOUND]
    clarify = [r for r in typo if r.expected_status == AMBIGUOUS and r.expected]
    never_bind = [r for r in typo if r.expected_status != BOUND]
    collision = by_battery.get("collision", [])
    return {
        "collision": Rate(
            _count(collision, lambda r: r.wrong_instrument), len(collision)
        ).as_dict(),
        "misroute": Rate(
            _count(bound_rows, lambda r: r.status == BOUND and not r.met), len(bound_rows)
        ).as_dict(),
        "misroute_wrong_instrument": Rate(
            _count(bound_rows, lambda r: r.wrong_instrument), len(bound_rows)
        ).as_dict(),
        "miss_heldout": Rate(
            _count(heldout, lambda r: r.status == UNRESOLVED), len(heldout)
        ).as_dict(),
        "false_abstention": Rate(
            _count(bound_rows, lambda r: r.status in REFUSALS), len(bound_rows)
        ).as_dict(),
        "covered_reported_out_of_coverage": Rate(
            _count(not_ooc, lambda r: r.status == OUT_OF_COVERAGE), len(not_ooc)
        ).as_dict(),
        "uncovered_refused": Rate(_count(ooc, lambda r: r.status in REFUSALS), len(ooc)).as_dict(),
        "bound_on_invented": Rate(
            _count(invented, lambda r: r.status == BOUND), len(invented)
        ).as_dict(),
        "strict_abstention": Rate(
            _count(invented, lambda r: r.status == r.expected_status), len(invented)
        ).as_dict(),
        "typo_auto_correct_precision": Rate(
            _count(corrected, lambda r: r.met), len(corrected)
        ).as_dict(),
        "typo_auto_correct_recall": Rate(
            _count(should_bind, lambda r: r.met), len(should_bind)
        ).as_dict(),
        "typo_clarify_recall": Rate(
            _count(
                clarify,
                lambda r: (
                    r.status == AMBIGUOUS
                    and r.top_candidate is not None
                    and related(Coordinate.parse(r.expected[0]), Coordinate.parse(r.top_candidate))
                ),
            ),
            len(clarify),
        ).as_dict(),
        "typo_bound_when_it_should_not": Rate(
            _count(never_bind, lambda r: r.status == BOUND), len(never_bind)
        ).as_dict(),
        "batteries": {name: battery_metrics(rows) for name, rows in sorted(by_battery.items())},
    }
