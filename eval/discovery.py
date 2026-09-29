"""Evaluate ``Router.discover`` on the concept battery (roadmap D4 tuning, D5 sealed run).

    uv run python -m eval.discovery                       # dev slice (tuning)
    uv run python -m eval.discovery --baseline headings   # the vault's headings-only design
    uv run python -m eval.discovery --split test --seal seals/concept-2026-09-29.json  # D5

The test slice runs only against a verified concept seal, and is meant to run once, at D5.
Tuning looks at dev rows only (roadmap D2).

Per row: the rank of the first candidate that is a gold coordinate or lies beneath one,
whether the result is ``confident``, whether every candidate exists in the router index,
and whether ``route()`` returns the row's ``route_status``.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from batteries.schema import CONCEPT_DIR, ConceptRow, read_concepts
from eval.seal import REPO, SealError, verify_battery_seal
from legal_rag_router import Router
from legal_rag_router.coordinate import Coordinate
from legal_rag_router.discovery import DEFAULT_DISCOVERY, DiscoveryPolicy

BASELINES: Final = {
    "headings": replace(
        DEFAULT_DISCOVERY,
        field_weights=(1.0, 0.0, 0.0, 0.0, 0.0),
        synonym_weight=0.0,
        prior_penalties=(1.0,) * 6,
        in_degree_weight=0.0,
    ),
}
"""The vault's design (02 §5, 05 §4): search over section headings only. Same terms and
common-word cut-off as ``discover``, but no other field, no thesaurus and no priors."""


@dataclass(frozen=True, slots=True)
class RowResult:
    row: ConceptRow
    rank: int | None
    confident: bool
    route_ok: bool
    phantom: int
    millis: float
    top: str | None


def hit_rank(gold: tuple[str, ...], candidates: list[str]) -> int | None:
    """1-based rank of the first candidate that is a gold coordinate or lies beneath one."""
    wanted = [Coordinate.parse(g) for g in gold]
    for rank, found in enumerate(candidates, start=1):
        coordinate = Coordinate.parse(found)
        if any(g == coordinate or g.is_ancestor_of(coordinate) for g in wanted):
            return rank
    return None


def evaluate(router: Router, rows: list[ConceptRow]) -> list[RowResult]:
    out = []
    for row in rows:
        start = time.perf_counter()
        result = router.discover(row.query)
        millis = (time.perf_counter() - start) * 1000
        found = [str(c.coordinate) for c in result.candidates]
        phantom = sum(1 for c in found if c not in router.index.coordinates and not
                      router.index.instrument(Coordinate.parse(c).instrument_id))  # fmt: skip
        out.append(
            RowResult(
                row=row,
                rank=hit_rank(row.gold, found) if row.gold else None,
                confident=result.confident,
                route_ok=router.route(row.query).status.value == row.route_status,
                phantom=phantom,
                millis=millis,
                top=result.candidates[0].label if result.candidates else None,
            )
        )
    return out


def _rates(results: list[RowResult]) -> dict[str, Any]:
    gold = [r for r in results if r.row.gold]
    none = [r for r in results if not r.row.gold]
    out: dict[str, Any] = {"rows": len(results)}
    if gold:
        n = len(gold)
        out |= {
            "hit@1": round(sum(1 for r in gold if r.rank == 1) / n, 3),
            "hit@5": round(sum(1 for r in gold if r.rank and r.rank <= 5) / n, 3),  # noqa: PLR2004
            "hit@10": round(sum(1 for r in gold if r.rank) / n, 3),
            "mrr": round(sum(1 / r.rank for r in gold if r.rank) / n, 3),
            "confident": round(sum(r.confident for r in gold) / n, 3),
        }
    if none:
        out["negatives_confident"] = round(sum(r.confident for r in none) / len(none), 3)
    return out


def report(results: list[RowResult]) -> dict[str, Any]:
    millis = sorted(r.millis for r in results)
    by_source: dict[str, list[RowResult]] = defaultdict(list)
    by_area: dict[str, list[RowResult]] = defaultdict(list)
    for r in results:
        by_source[r.row.source].append(r)
        by_area[r.row.area].append(r)
    return {
        "all": _rates(results),
        "by_source": {k: _rates(v) for k, v in sorted(by_source.items())},
        "by_area": {k: _rates(v) for k, v in sorted(by_area.items())},
        "safety": {
            "phantom_candidates": sum(r.phantom for r in results),
            "route_status_mismatches": [r.row.id for r in results if not r.route_ok],
        },
        "latency_ms": {
            "p50": round(statistics.median(millis), 2),
            "p99": round(millis[min(len(millis) - 1, int(0.99 * len(millis)))], 2),
            "max": round(millis[-1], 2),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--index", type=Path, default=REPO / "data" / "index")
    parser.add_argument("--concepts", type=Path, default=REPO / "data" / "concepts")
    parser.add_argument("--battery", type=Path, default=CONCEPT_DIR / "uk.jsonl")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--seal", type=Path, help="the concept seal; required for --split test")
    parser.add_argument("--baseline", choices=sorted(BASELINES))
    parser.add_argument("--misses", action="store_true", help="list dev rows without a hit")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--details", action="store_true", help="per-row results in --json")
    args = parser.parse_args(argv)
    if args.split == "test":
        if args.misses:
            parser.error("--misses is for the dev slice only")
        if args.seal is None:
            parser.error("the test slice runs only against a verified concept seal (--seal)")
        try:
            seal = verify_battery_seal(args.seal, REPO, args.index)
        except SealError as exc:
            print(f"SEAL ERROR: {exc}")
            return 1
        if seal["kind"] != "concept":
            parser.error(f"{args.seal} is a {seal['kind']} seal, not a concept seal")
    policy: DiscoveryPolicy = BASELINES[args.baseline] if args.baseline else DEFAULT_DISCOVERY
    router = Router.from_path(args.index, concepts=args.concepts, discovery_policy=policy)
    rows = [r for r in read_concepts(args.battery) if r.split == args.split]
    results = evaluate(router, rows)
    summary: dict[str, Any] = {"split": args.split, "baseline": args.baseline, **report(results)}
    if args.details:
        summary["rows"] = [
            {"id": r.row.id, "source": r.row.source, "area": r.row.area, "query": r.row.query,
             "rank": r.rank, "confident": r.confident, "route_ok": r.route_ok, "top": r.top,
             "notes": r.row.notes}
            for r in results
        ]  # fmt: skip
    print(json.dumps(summary, indent=2))
    if args.misses:
        for r in results:
            if r.row.gold and r.rank is None:
                print(f"MISS {r.row.id} [{r.row.area}] {r.row.query!r} -> {r.top}")
        print(Counter(r.rank for r in results if r.row.gold))
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
