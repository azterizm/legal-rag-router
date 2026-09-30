"""Row B's router client (roadmap M11): pairing, timing, intervals and answer agreement."""

from __future__ import annotations

import json
from collections import Counter

import httpx

from bench.row_b import agreement, bootstrap_ci, plan_pairs, run_pairs, stats_ms, summarise
from legal_rag_router import Router
from tests.conftest import FIXTURE_INDEX


def test_every_query_is_paired_with_a_floor_call_in_a_seeded_order() -> None:
    pairs = plan_pairs(queries=4, repeats=3)
    assert Counter(q for q, _ in pairs) == {0: 3, 1: 3, 2: 3, 3: 3}
    assert all(sorted(order) == ["/floor", "/route"] for _, order in pairs)
    assert pairs == plan_pairs(queries=4, repeats=3)
    assert [q for q, _ in pairs] != sorted(q for q, _ in pairs)


def test_the_interval_brackets_the_estimate() -> None:
    values = [float(v) for v in range(1, 1001)]
    low, high = bootstrap_ci(values, 0.5, resamples=200)
    assert low <= 500 <= high
    report = stats_ms([v * 1_000_000 for v in range(1, 101)], resamples=50)
    assert report is not None
    assert report["p50_ci95_ms"][0] <= report["p50_ms"] <= report["p50_ci95_ms"][1]
    assert stats_ms([], resamples=10) is None


def test_a_run_against_a_service_that_routes_locally_agrees() -> None:
    router = Router.from_path(FIXTURE_INDEX)

    def service(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        if request.url.path == "/floor":
            return httpx.Response(200, json={"status": None, "coordinates": [], "compute_ns": 0})
        result = router.route(query)
        return httpx.Response(
            200,
            json={
                "status": "ROUTE_UNRESOLVED" if "Marchwood" in query else result.status.value,
                "coordinates": [str(c) for c in result.coordinates],
                "compute_ns": 1234,
            },
        )

    queries = ["ERA 1996 s.124", "Marchwood Order 2022"]
    with httpx.Client(base_url="https://service", transport=httpx.MockTransport(service)) as c:
        calls = run_pairs(c, queries, plan_pairs(len(queries), repeats=2))
    assert len(calls) == 8
    report = summarise(calls, resamples=20)
    assert report["route_round_trip"]["calls"] == 4
    assert report["router_compute_in_container"]["p50_ms"] == 0.001
    checked = agreement(router, queries, calls)
    assert checked["route_calls"] == 4
    assert checked["differ_count"] == 2  # the service above misreports Marchwood
    assert checked["differ"][0]["query"] == "Marchwood Order 2022"
