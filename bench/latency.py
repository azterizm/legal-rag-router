"""Routing latency per status (plan step 9, roadmap M10): the published p50 / p99.

    uv run python -m bench.latency --index data/index --queries results/raw/replays-100k.txt \
        --json bench/results/latency-darwin-arm64.json

Queries are every row of the UK plan batteries, plus an optional file with one query per
line: the 100,000 replayed real citations of the coverage sweep, written by
``--write-replays``. Each query is routed once to warm up, then timed ``--repeats`` times
with ``time.perf_counter_ns`` and the garbage collector paused. Timings are grouped by the
status the query routes to. The platform is recorded, so the Apple Silicon and x86-64 runs
can sit side by side.
"""

from __future__ import annotations

import argparse
import gc
import json
import platform
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Final

from batteries.schema import BATTERIES, BATTERY_DIR, read_battery
from legal_rag_router import Router

REPLAY_SEED: Final = 20260927
"""The coverage sweep's seed (``eval.sweep``), so the replays are the swept sample."""


def battery_queries(jurisdiction: str = "uk") -> list[str]:
    return [
        row.query
        for battery in BATTERIES
        for row in read_battery(BATTERY_DIR / jurisdiction / f"{battery}.jsonl")
    ]


def write_replays(router: Router, harvest: Path, out: Path, sample: int) -> int:
    """The coverage sweep's replay queries, one per line (newlines folded to spaces)."""
    from eval.sweep import eligible, replay_query  # noqa: PLC0415 - build machine only

    with harvest.open(encoding="utf-8") as fh:
        rows = list(eligible(router, (json.loads(line) for line in fh if line.strip())))
    chosen = random.Random(REPLAY_SEED).sample(rows, min(sample, len(rows)))
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [" ".join(replay_query(c).split()) for c in chosen]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def _percentile(sorted_ns: list[int], q: float) -> float:
    return sorted_ns[min(len(sorted_ns) - 1, int(q * len(sorted_ns)))] / 1000


def measure(router: Router, queries: list[str], repeats: int) -> dict[str, list[int]]:
    """Nanoseconds per call, grouped by the status each query routes to."""
    status_of = {q: router.route(q).status.value for q in queries}  # warm-up
    timings: dict[str, list[int]] = defaultdict(list)
    gc.collect()
    gc.disable()
    try:
        for _ in range(repeats):
            for query in queries:
                start = time.perf_counter_ns()
                router.route(query)
                timings[status_of[query]].append(time.perf_counter_ns() - start)
    finally:
        gc.enable()
    return timings


def summary(timings: dict[str, list[int]]) -> dict[str, Any]:
    def stats(ns: list[int]) -> dict[str, Any]:
        ordered = sorted(ns)
        return {
            "calls": len(ordered),
            "p50_us": round(_percentile(ordered, 0.50), 1),
            "p99_us": round(_percentile(ordered, 0.99), 1),
            "max_us": round(ordered[-1] / 1000, 1),
        }

    everything = [t for ns in timings.values() for t in ns]
    return {
        "all": stats(everything),
        "per_status": {status: stats(ns) for status, ns in sorted(timings.items())},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--index", type=Path, default=Path("data/index"))
    parser.add_argument("--queries", type=Path, help="extra queries, one per line")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--write-replays", type=Path, help="write the sweep's replays and stop")
    parser.add_argument("--harvest", type=Path, default=Path("data/harvest/uk_citations.jsonl"))
    parser.add_argument("--sample", type=int, default=100_000)
    args = parser.parse_args(argv)
    router = Router.from_path(args.index)
    if args.write_replays:
        count = write_replays(router, args.harvest, args.write_replays, args.sample)
        print(f"wrote {count} replay queries to {args.write_replays}")
        return 0
    queries = battery_queries()
    sources = {"batteries": len(queries)}
    if args.queries:
        extra = [q for q in args.queries.read_text(encoding="utf-8").splitlines() if q.strip()]
        sources[args.queries.name] = len(extra)
        queries += extra
    result = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": sys.version.split()[0],
        "index_snapshot": router.index.snapshot,
        "queries": sources,
        "repeats": args.repeats,
        **summary(measure(router, queries, args.repeats)),
    }
    text = json.dumps(result, indent=2)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
