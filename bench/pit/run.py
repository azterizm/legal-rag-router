"""CS2 Control 3, end to end: the sealed audit probes through router, date, lookup.

    uv run python -m bench.pit.run --battery DIR --passes 1000 --cold 3

Input is the point-in-time family of the battery the August 2026 audit sealed (CS2's "System C"
run; ``DIR`` holds its ``probes.jsonl`` and ``ground_truth.json``), read verbatim after their
SHA-256 is checked against the hashes CS2 publishes. The battery is named here only by those
hashes, as CS2 names the audited system only by a letter. Each probe goes through
``Router.route``, the hint's date and one SQL query over ``bench/pit/limits.json``
(:mod:`bench.pit.lookup`); the answer text is scored against the sealed ground truth with the
audit's own point-in-time rule, so the labels are the audit's, not ours.

Recorded per probe: the figure and the Order that set it, router and lookup latency over
``--passes`` timed passes (``perf_counter_ns``, garbage collector paused, one untimed warm-up),
the number of distinct answers across passes, and the tool and network calls made: the chain
has no model and no tool interface, and a socket guard counts any connection attempt.
``--cold`` adds fresh-process runs of the CS2 probe: index load, table load, first answer.

Writes ``results/pit-cs2-{date}.json`` and ``.md`` and ``seals/results-pit-cs2-{date}.json``
(verifiable with :func:`eval.seal.verify_results_seal`).
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import socket
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from bench.pit.limits import LIMITS_JSON
from bench.pit.lookup import SQL, Limits, render, resolve
from eval.seal import SEAL_FORMAT, canonical, sha256_of
from legal_rag_router import Router, __version__

REPO: Final = Path(__file__).resolve().parents[2]
PROBES_SHA256: Final = "08c3b9b5fd9b5274c152738ed23c2d8faa3cb451273ba6bf34a9c5ca3a2d5964"
GROUND_TRUTH_SHA256: Final = "0b249b5b4752d5ae9b860463d476731a20b05da279a3ea124f4ba705186b4316"
"""As published in CS2 §2 and §9 (sealed 2026-08-07T08:51:57Z)."""
CS2_PROBE: Final = "pit-era-124-1"


class _NetworkGuard:
    """Counts, and refuses, every socket connection attempted while installed."""

    def __init__(self) -> None:
        self.attempts = 0
        self._original = socket.socket.connect

    def __enter__(self) -> _NetworkGuard:
        guard = self

        def refuse(sock: socket.socket, address: Any) -> None:
            guard.attempts += 1
            raise OSError(f"network refused during the run: {address!r}")

        socket.socket.connect = refuse  # type: ignore[method-assign,assignment]
        return self

    def __exit__(self, *_: object) -> None:
        socket.socket.connect = self._original  # type: ignore[method-assign]


def _head_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],  # noqa: S607
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _cpu() -> str:
    if platform.system() == "Darwin":
        brand = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if brand:
            return brand
    return platform.processor() or "unknown CPU"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_battery(directory: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """The sealed point-in-time probes and their expectations, after the hash check."""
    probes_path, truth_path = directory / "probes.jsonl", directory / "ground_truth.json"
    for path, expected in ((probes_path, PROBES_SHA256), (truth_path, GROUND_TRUTH_SHA256)):
        if _sha256(path) != expected:
            raise SystemExit(f"{path} does not match the sealed hash {expected[:12]}…")
    probes = [json.loads(line) for line in probes_path.read_text(encoding="utf-8").splitlines()]
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    expectations = {e["probe_id"]: e for e in truth["expectations"]}
    return [p for p in probes if p.get("family") == "point_in_time"], expectations


def _normalise(text: str) -> str:
    """The audit's matching rule (``legal_rag_audit.evaluators._common.normalise``)."""
    return " ".join(unicodedata.normalize("NFC", text).lower().split())


def score(answer: str, expectation: dict[str, Any]) -> dict[str, Any]:
    """The audit's point-in-time rule: the in-force reading present passes, else the superseded
    one present fails, else nothing was captured."""
    have = _normalise(answer)
    correct = [t for t in expectation["must_contain"] if _normalise(t) in have]
    wrong = [t for t in expectation["must_not_contain"] if _normalise(t) in have]
    if correct:
        return {"status": "pass", "outcome": "version_correct", "appeared": correct}
    if wrong:
        return {"status": "fail", "outcome": "version_mismatch", "appeared": wrong}
    return {"status": "not_captured", "outcome": "no_version_returned", "appeared": []}


def _percentile_us(ordered_ns: list[int], q: float) -> float:
    """Nearest rank, the rule ``bench.latency`` publishes."""
    return round(ordered_ns[min(len(ordered_ns) - 1, int(q * len(ordered_ns)))] / 1000, 2)


def _stats(ns: list[int]) -> dict[str, Any]:
    ordered = sorted(ns)
    return {
        "calls": len(ordered),
        "p50_us": _percentile_us(ordered, 0.50),
        "p99_us": _percentile_us(ordered, 0.99),
        "max_us": round(ordered[-1] / 1000, 2),
    }


def run_probe(router: Router, limits: Limits, text: str, passes: int) -> dict[str, Any]:
    first = resolve(router.route(text), limits)  # warm-up, untimed
    route_ns: list[int] = []
    lookup_ns: list[int] = []
    total_ns: list[int] = []
    answers: Counter[str] = Counter()
    gc.collect()
    gc.disable()
    try:
        for _ in range(passes):
            start = time.perf_counter_ns()
            routed = router.route(text)
            bound = time.perf_counter_ns()
            answer = render(resolve(routed, limits))
            end = time.perf_counter_ns()
            route_ns.append(bound - start)
            lookup_ns.append(end - bound)
            total_ns.append(end - start)
            answers[answer] += 1
    finally:
        gc.enable()
    routed = router.route(text)
    return {
        "coordinate": [str(c) for c in routed.coordinates],
        "temporal_hint": routed.temporal_hint,
        "answer": {name: getattr(first, name) for name in first.__slots__},
        "text": render(first),
        "distinct_answers": len(answers),
        "latency": {
            "route": _stats(route_ns),
            "lookup": _stats(lookup_ns),
            "total": _stats(total_ns),
        },
    }


def cold_child(index: Path, probe_text: str) -> dict[str, Any]:
    """One fresh process: load the index, load the table, answer once."""
    t0 = time.perf_counter_ns()
    router = Router.from_path(index)
    t1 = time.perf_counter_ns()
    with Limits.from_path() as limits:
        t2 = time.perf_counter_ns()
        text = render(resolve(router.route(probe_text), limits))
        t3 = time.perf_counter_ns()
    return {
        "index_load_ms": round((t1 - t0) / 1e6, 2),
        "table_load_ms": round((t2 - t1) / 1e6, 2),
        "first_answer_ms": round((t3 - t2) / 1e6, 3),
        "text": text,
    }


def cold_runs(index: Path, battery: Path, count: int) -> list[dict[str, Any]]:
    runs = []
    for _ in range(count):
        start = time.perf_counter_ns()
        child = subprocess.run(  # noqa: S603 - this interpreter, this module
            [
                sys.executable,
                "-m",
                "bench.pit.run",
                "--cold-child",
                "--index",
                str(index),
                "--battery",
                str(battery),
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(child.stdout)
        result["process_wall_ms"] = round((time.perf_counter_ns() - start) / 1e6, 1)
        runs.append(result)
    return runs


def render_report(results: dict[str, Any]) -> str:
    head = results["probes"][CS2_PROBE]
    env = results["environment"]
    lat = head["latency"]
    lines = [
        f"# CS2 Control 3 on the sealed audit probes ({results['run_date']})",
        "",
        (
            "The point-in-time probes of the battery sealed on 7 August 2026 "
            f"(probes `{PROBES_SHA256[:12]}…`, ground truth `{GROUND_TRUTH_SHA256[:12]}…`), "
            "routed by `legal-rag-router`, dated from its `temporal_hint`, and answered by one SQL "
            "query over the limits table built from the Increase of Limits Orders as made "
            "(`bench/pit/limits.json`). Scored against the sealed ground truth with the audit's "
            "point-in-time rule."
        ),
        "",
        f"## The CS2 probe: `{CS2_PROBE}`",
        "",
        f"> {results['probe_texts'][CS2_PROBE]}",
        "",
        f"- **Answer:** {head['text']}",
        f"- **Sealed verdict:** {head['score']['status']} ({head['score']['outcome']})",
        f"- **Distinct answers over {lat['total']['calls']:,} passes:** {head['distinct_answers']}",
        (
            f"- **Latency, router + lookup:** p50 {lat['total']['p50_us']} µs, "
            f"p99 {lat['total']['p99_us']} µs, max {lat['total']['max_us']} µs "
            f"(router p50 {lat['route']['p50_us']} µs, lookup p50 {lat['lookup']['p50_us']} µs)"
        ),
        (
            f"- **LLM calls:** 0. **Tool calls:** 0. **Network connections attempted:** "
            f"{results['network_attempts']}"
        ),
        "",
        "| Cold start (fresh process) | Index load | Table load | First answer | Process wall |",
        "|---|---|---|---|---|",
    ]
    for i, cold in enumerate(results["cold_starts"], 1):
        lines.append(
            f"| {i} | {cold['index_load_ms']} ms | {cold['table_load_ms']} ms | "
            f"{cold['first_answer_ms']} ms | {cold['process_wall_ms']} ms |"
        )
    lines += [
        "",
        "## Every sealed point-in-time probe",
        "",
        "| Probe | Bound | Hint | Answer | Order | Verdict | Distinct | p50 / p99 µs |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for pid, probe in results["probes"].items():
        answer = probe["answer"]
        figure = answer["amount"] or f"no figure ({answer['status']})"
        lines.append(
            f"| `{pid}` | `{', '.join(probe['coordinate'])}` | {probe['temporal_hint'] or '—'} "
            f"| {figure} | {answer['si'] or '—'} | {probe['score']['status']} "
            f"| {probe['distinct_answers']} | {probe['latency']['total']['p50_us']} / "
            f"{probe['latency']['total']['p99_us']} |"
        )
    summary = results["summary"]
    lines += [
        "",
        (
            "**Covered by the table (ERA 1996 s.124, s.186, s.227):** "
            f"{summary['covered_pass']} of {summary['covered']} pass. **Not covered** (s.94 / "
            "s.108 and Companies Act s.382 / s.465 need other instruments): "
            f"{summary['not_covered']}, each answered with no figure."
        ),
        "",
        "## Method and limits",
        "",
        f"- SQL: `{SQL}`.",
        (
            "- Passes: one untimed warm-up, then the timed passes with the garbage collector "
            f"paused. Machine: {env['machine']}, Python {env['python']}."
        ),
        (
            "- The table holds Orders from SI 2010/2926 (in force 1 February 2011); earlier dates "
            "return no row. It was built knowing which sections the battery asks about; it holds "
            "every Order from 2011 to 2026 for them, not only the probe dates, and its figures are "
            "copied from the Orders' Schedules with the source bytes' SHA-256."
        ),
        (
            '- Each Order applies by its "appropriate date" (for an unfair dismissal award, the '
            "effective date of termination), not the date a question is asked; the Order's "
            "transitional clause is returned with every row. Choosing that date is the caller's."
        ),
        (
            "- Not tested: colloquial questions with no citation; Control 4 (the tool-call limit "
            "belongs to the orchestrator); Northern Ireland limits."
        ),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--index", type=Path, default=REPO / "data" / "index")
    parser.add_argument(
        "--battery", type=Path, required=True, help="the sealed audit battery's directory"
    )
    parser.add_argument("--passes", type=int, default=1000)
    parser.add_argument("--cold", type=int, default=3)
    parser.add_argument("--cold-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--out-dir", type=Path, default=REPO / "results")
    args = parser.parse_args(argv)

    probes, expectations = load_battery(args.battery)
    texts = {p["probe_id"]: p["text"] for p in probes}
    if args.cold_child:
        with _NetworkGuard():
            print(json.dumps(cold_child(args.index, texts[CS2_PROBE])))
        return 0

    with _NetworkGuard() as guard, Limits.from_path() as limits:
        router = Router.from_path(args.index)
        per_probe: dict[str, Any] = {}
        for pid, text in texts.items():
            result = run_probe(router, limits, text, args.passes)
            result["score"] = score(result["text"], expectations[pid])
            per_probe[pid] = result
        cold = cold_runs(args.index, args.battery, args.cold)

    covered = [p for p in per_probe.values() if p["answer"]["status"] == "FOUND"]
    now = datetime.now(UTC)
    results: dict[str, Any] = {
        "run_date": now.date().isoformat(),
        "run_at": now.isoformat(timespec="seconds"),
        "battery": {
            "source": "legal-rag-audit battery sealed for CS2 (System C)",
            "probes_sha256": PROBES_SHA256,
            "ground_truth_sha256": GROUND_TRUTH_SHA256,
            "sealed_at": "2026-08-07T08:51:57Z",
        },
        "limits_sha256": _sha256(LIMITS_JSON),
        "router_version": __version__,
        "index_snapshot": router.route(texts[CS2_PROBE]).index_snapshot,
        "git_commit": _head_commit(),
        "passes": args.passes,
        "network_attempts": guard.attempts,
        "llm_calls": 0,
        "tool_calls": 0,
        "environment": {
            "machine": f"{platform.system()} {platform.machine()} ({_cpu()})",
            "python": platform.python_version(),
        },
        "probe_texts": texts,
        "probes": per_probe,
        "cold_starts": cold,
        "summary": {
            "probes": len(per_probe),
            "covered": len(covered),
            "covered_pass": sum(p["score"]["status"] == "pass" for p in covered),
            "not_covered": len(per_probe) - len(covered),
            "all_deterministic": all(p["distinct_answers"] == 1 for p in per_probe.values()),
            "cold_answers_match": all(c["text"] == per_probe[CS2_PROBE]["text"] for c in cold),
        },
    }
    stem = f"pit-cs2-{results['run_date']}"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = args.out_dir / f"{stem}.json", args.out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md_path.write_text(render_report(results), encoding="utf-8")
    print(md_path.read_text(encoding="utf-8"))
    if not args.out_dir.resolve().is_relative_to(REPO):
        print(f"-> {json_path}, {md_path} (outside the repo: not sealed)")
        return 0
    seal_path = write_seal(REPO, [json_path, md_path], results, now)
    print(f"-> {json_path.name}, {md_path.name}, sealed in {seal_path.relative_to(REPO)}")
    return 0


def write_seal(repo: Path, files: list[Path], results: dict[str, Any], now: datetime) -> Path:
    """A results seal in :mod:`eval.seal`'s format, citing the audit battery's hashes."""
    contents = {
        "results": {f.resolve().relative_to(repo).as_posix(): _sha256(f) for f in files},
        "audit_battery": results["battery"],
        "limits_sha256": results["limits_sha256"],
        "package_version": __version__,
    }
    seal = {
        "seal_format": SEAL_FORMAT,
        "kind": "results",
        "sealed_at": now.isoformat(timespec="seconds"),
        "git_commit": results["git_commit"],
        "seal_sha256": sha256_of(canonical(contents)),
        "contents": contents,
    }
    path = repo / "seals" / f"results-pit-cs2-{results['run_date']}.json"
    path.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    sys.exit(main())
