"""Row B, the router's side (roadmap M11): the router called over the network as a service.

    export MODAL_ROUTER_URL=https://<workspace>--legal-rag-router-routerservice-web.modal.run
    export MODAL_KEY=wk-...  MODAL_SECRET=ws-...        # a Modal proxy auth token
    uv run python -m bench.row_b --client-region "<city, country>" --limit 20   # smoke
    uv run python -m bench.row_b --client-region "<city, country>"              # the run

The service is ``deploy/modal_router.py``. Every battery row is sent ``--repeats`` times, each
paired with a ``/floor`` call: the same request to the same host over the same warm connection,
with no routing. The pairs go in a seeded random order, and each pair's order is random too, so
both sides share the network's conditions. Warm-up pairs are discarded.

Per call it keeps the round trip, the time to first byte and, from ``/route``, the router's own
in-process time. It checks every answer against the local router on the same index. p50 and
p99 carry bootstrap 95 % intervals. The raw calls are appended to ``calls.jsonl`` as they are
made, so an interrupted run keeps what it measured (and is reported as interrupted, not as a
run); ``summary.json`` is written at the end. The directory is never overwritten.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import httpx

from bench.latency import battery_queries
from legal_rag_router import Router

SEED: Final = 20260930
ENDPOINTS: Final = ("/route", "/floor")


@dataclass(frozen=True, slots=True)
class Call:
    """One timed request. ``pair`` links a ``/route`` call to its ``/floor`` twin."""

    pair: int
    endpoint: str
    query: int
    total_ns: int
    ttfb_ns: int | None
    connected: bool
    compute_ns: int
    status: str | None
    coordinates: list[str]


def plan_pairs(queries: int, repeats: int, seed: int = SEED) -> list[tuple[int, tuple[str, str]]]:
    """``(query, endpoint order)`` for every pair, in a seeded random order."""
    rng = random.Random(seed)
    pairs = [(q, tuple(rng.sample(ENDPOINTS, 2))) for q in range(queries) for _ in range(repeats)]
    rng.shuffle(pairs)
    return [(q, (order[0], order[1])) for q, order in pairs]


def timed_call(client: httpx.Client, pair: int, endpoint: str, query: int, text: str) -> Call:
    events: dict[str, int] = {}

    def trace(name: str, _info: dict[str, Any]) -> None:
        events[name] = time.perf_counter_ns()

    start = time.perf_counter_ns()
    response = client.post(endpoint, json={"query": text}, extensions={"trace": trace})
    total = time.perf_counter_ns() - start
    response.raise_for_status()
    body = response.json()
    sent = events.get("http11.send_request_headers.started")
    first_byte = events.get("http11.receive_response_headers.complete")
    return Call(
        pair=pair,
        endpoint=endpoint,
        query=query,
        total_ns=total,
        ttfb_ns=first_byte - sent if sent is not None and first_byte is not None else None,
        connected="connection.connect_tcp.complete" in events,
        compute_ns=int(body["compute_ns"]),
        status=body["status"],
        coordinates=list(body["coordinates"]),
    )


def run_pairs(
    client: httpx.Client,
    queries: Sequence[str],
    pairs: Sequence[tuple[int, tuple[str, str]]],
    on_pair: Callable[[int, list[Call]], None] | None = None,
) -> list[Call]:
    """Every pair in order; ``on_pair`` sees each pair's calls as soon as they are made."""
    calls: list[Call] = []
    for n, (query, order) in enumerate(pairs):
        pair = [timed_call(client, n, endpoint, query, queries[query]) for endpoint in order]
        calls.extend(pair)
        if on_pair is not None:
            on_pair(n + 1, pair)
    return calls


def percentile(ordered: Sequence[float], q: float) -> float:
    """The same nearest-rank rule as ``bench.latency``."""
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def bootstrap_ci(
    values: Sequence[float], q: float, resamples: int, seed: int = SEED
) -> tuple[float, float]:
    """A 95 % percentile-bootstrap interval for the ``q`` quantile."""
    rng = random.Random(seed)
    n = len(values)
    estimates = sorted(percentile(sorted(rng.choices(values, k=n)), q) for _ in range(resamples))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def stats_ms(values_ns: Sequence[int], resamples: int) -> dict[str, Any] | None:
    if not values_ns:
        return None
    ms = [v / 1e6 for v in values_ns]
    ordered = sorted(ms)
    out: dict[str, Any] = {"calls": len(ms)}
    for name, q in (("p50", 0.50), ("p99", 0.99)):
        low, high = bootstrap_ci(ms, q, resamples)
        out[f"{name}_ms"] = round(percentile(ordered, q), 3)
        out[f"{name}_ci95_ms"] = [round(low, 3), round(high, 3)]
    out["max_ms"] = round(ordered[-1], 3)
    return out


def summarise(calls: Sequence[Call], resamples: int) -> dict[str, Any]:
    route = [c for c in calls if c.endpoint == "/route"]
    floor = {c.pair: c for c in calls if c.endpoint == "/floor"}
    return {
        "route_round_trip": stats_ms([c.total_ns for c in route], resamples),
        "floor_round_trip": stats_ms([c.total_ns for c in floor.values()], resamples),
        "route_ttfb": stats_ms([c.ttfb_ns for c in route if c.ttfb_ns is not None], resamples),
        "floor_ttfb": stats_ms(
            [c.ttfb_ns for c in floor.values() if c.ttfb_ns is not None], resamples
        ),
        "router_compute_in_container": stats_ms([c.compute_ns for c in route], resamples),
        "reconnects": sum(c.connected for c in calls),
    }


def agreement(router: Router, queries: Sequence[str], calls: Sequence[Call]) -> dict[str, Any]:
    """Every remote answer against the local router on the same index."""
    local = {}
    for q in sorted({c.query for c in calls}):
        result = router.route(queries[q])
        local[q] = (result.status.value, [str(c) for c in result.coordinates])
    differ = [
        {"query": queries[c.query], "remote": [c.status, c.coordinates], "local": local[c.query]}
        for c in calls
        if c.endpoint == "/route" and (c.status, c.coordinates) != tuple(local[c.query])
    ]
    return {
        "route_calls": sum(c.endpoint == "/route" for c in calls),
        "differ_count": len(differ),
        "differ": differ[:20],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--url", default=os.environ.get("MODAL_ROUTER_URL"))
    parser.add_argument("--client-region", required=True, help="where this client sits")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=50, help="pairs sent first, discarded")
    parser.add_argument("--limit", type=int, help="the first N battery rows only (a smoke run)")
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--index", type=Path, default=Path("data/index"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    key, secret = os.environ.get("MODAL_KEY"), os.environ.get("MODAL_SECRET")
    if not args.url or not key or not secret:
        print("Set MODAL_ROUTER_URL, MODAL_KEY and MODAL_SECRET (a Modal proxy auth token).")
        return 1
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M")
    out = args.out or Path("results/raw") / f"row-b-router-{stamp}{'-smoke' if args.limit else ''}"
    if out.exists():
        print(f"{out} exists: a measurement is never overwritten.")
        return 1

    queries = battery_queries()[: args.limit]
    pairs = plan_pairs(len(queries), args.repeats)
    warmup = plan_pairs(len(queries), 1, seed=SEED + 1)[: args.warmup]
    headers = {"Modal-Key": key, "Modal-Secret": secret}
    started = datetime.now(UTC).isoformat(timespec="seconds")
    out.mkdir(parents=True)
    with (
        httpx.Client(base_url=args.url, headers=headers, timeout=60.0) as client,
        (out / "calls.jsonl").open("w", encoding="utf-8") as log,
    ):
        machine_before = client.get("/machine").raise_for_status().json()
        run_pairs(client, queries, warmup)

        def record(done: int, pair: list[Call]) -> None:
            log.writelines(json.dumps(asdict(c)) + "\n" for c in pair)
            if done % 500 == 0 or done == len(pairs):
                log.flush()
                print(f"  {done} of {len(pairs)} pairs", flush=True)

        began = time.monotonic()
        try:
            calls = run_pairs(client, queries, pairs, record)
        except httpx.HTTPError as exc:
            log.flush()
            print(f"INTERRUPTED: {exc!r}. The calls made so far are in {out / 'calls.jsonl'};")
            print("this is not a complete run. Start a new one (a new directory).")
            return 1
        elapsed = time.monotonic() - began
        machine_after = client.get("/machine").raise_for_status().json()

    summary = {
        "started_utc": started,
        "elapsed_s": round(elapsed),
        "client": {
            "region": args.client_region,
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "httpx": httpx.__version__,
        },
        "service": {
            "url_host": httpx.URL(args.url).host,
            "before": machine_before,
            "after": machine_after,
        },
        "container_restarted": machine_after["container_uptime_s"]
        < machine_before["container_uptime_s"] + elapsed - 5,
        "queries": len(queries),
        "repeats": args.repeats,
        "warmup_pairs_discarded": len(warmup),
        "seed": SEED,
        **summarise(calls, args.resamples),
        "agreement": agreement(Router.from_path(args.index), queries, calls),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    route, floor = summary["route_round_trip"], summary["floor_round_trip"]
    print(f"route: p50 {route['p50_ms']} ms, p99 {route['p99_ms']} ms")
    print(f"floor: p50 {floor['p50_ms']} ms, p99 {floor['p99_ms']} ms")
    print(f"answers differing from the local router: {summary['agreement']['differ_count']}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
