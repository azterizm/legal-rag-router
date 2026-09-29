"""The latency bench (roadmap M10): timings grouped by status, with the platform recorded."""

from __future__ import annotations

import json
from pathlib import Path

from bench.latency import main, measure, summary
from legal_rag_router import Router
from tests.conftest import FIXTURE_INDEX


def test_timings_are_grouped_by_status() -> None:
    router = Router.from_path(FIXTURE_INDEX)
    queries = ["section 124 of the Employment Rights Act 1996", "Marchwood Order 2022", "hello"]
    timings = measure(router, queries, repeats=2)
    assert set(timings) == {
        "ROUTE_BOUNDED",
        "EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND",
        "ROUTE_UNRESOLVED",
    }
    assert all(len(ns) == 2 for ns in timings.values())
    report = summary(timings)
    assert report["all"]["calls"] == 6
    assert report["all"]["p50_us"] <= report["all"]["p99_us"] <= report["all"]["max_us"]


def test_the_cli_records_the_platform(tmp_path: Path) -> None:
    queries = tmp_path / "q.txt"
    queries.write_text("ERA 1996 s.124\n\n")
    out = tmp_path / "latency.json"
    args = ["--index", str(FIXTURE_INDEX), "--queries", str(queries), "--repeats", "1"]
    assert main([*args, "--json", str(out)]) == 0
    result = json.loads(out.read_text())
    assert result["queries"]["q.txt"] == 1
    assert result["queries"]["batteries"] > 2000
    assert result["machine"]
