"""The Jev and Gemini comparison runner (roadmap M11): resumable, made to run unattended.

    uv run python -m bench.compare run --dir results/raw/compare --pass accuracy --limit 20
    uv run python -m bench.compare estimate --dir results/raw/compare
    uv run python -m bench.compare run --dir results/raw/compare --pass accuracy --confirmed
    uv run python -m bench.compare run --dir results/raw/compare --pass determinism --confirmed
    uv run python -m bench.compare run --dir results/raw/compare --pass latency --confirmed
    uv run python -m bench.compare score --dir results/raw/compare

Passes (§4 design, 1 Oct 2026):

- ``accuracy``: every battery row. Gemini end to end once, and Jev and Gemini on the choice
  question at 3, 10 and 30 options. Calls run concurrently, with back-off on rate limits.
- ``determinism``: a seeded 200 rows, five times each, for Gemini end to end and Jev at 10
  options.
- ``latency``: a seeded 300 rows, one call at a time. Per row: Gemini end to end, Jev at 10
  options, the router on Modal (Row B), each paired with its own no-model floor call on the same
  connection, and the router in process (Row C). The order is shuffled per row, so the systems
  share the network's conditions.

Every call is appended to ``<pass>.jsonl`` the moment it returns. A rerun skips every call
already recorded, so a crash, a reboot or a lost connection loses at most the calls in flight.
Nothing is overwritten. A pass other than a smoke run (``--limit`` of 30 rows or fewer) refuses
to start without ``--confirmed``: the cost estimate comes first (the M11 halt point).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import sys
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import httpx

from batteries.schema import BATTERIES, BATTERY_DIR, BatteryRow, read_battery
from bench.clients.gemini import GeminiError
from bench.clients.gemini_proxy import BASE_URL as GEMINI_ENDPOINT
from bench.clients.gemini_proxy import GeminiProxyClient
from bench.clients.http import Timing, timed
from bench.clients.jev import JevClient, JevError
from bench.row_b import stats_ms
from bench.unit1 import (
    CONTRACT,
    INDEX_DEPENDENT,
    OPTION_COUNTS,
    ROUTE_SCHEMA,
    Choice,
    Neighbours,
    Routed,
    build_choice,
    choice_from_gemini,
    choice_from_jev,
    citations_of,
    gemini_choice_prompt,
    gemini_choice_schema,
    jev_question,
    outcome,
    read_route,
    resolve_extraction,
    route_prompt,
    score_choices,
)
from eval.metrics import domain_metrics
from legal_rag_router import Router

GEMINI_MODEL: Final = "gemini-3.8-flash-high"
"""Through the author's proxy (``bench.clients.gemini_proxy``), the only Gemini endpoint used."""
SEED: Final = 20261001
DETERMINISM_ROWS: Final = 200
DETERMINISM_REPEATS: Final = 5
LATENCY_ROWS: Final = 300
LATENCY_COUNT: Final = 10
SMOKE_ROWS: Final = 30
PRICES: Final = {
    "gemini_promotional_per_m": {"input": 0.75, "output": 3.75},
    "gemini_regular_per_m": {"input": 1.50, "output": 7.50},
    "jev_per_m": {"input": 0.042, "output": 0.0},
}
"""Gemini 3.x Flash: $0.75 / $3.75 per 1M "through December 31, 2026", $1.50 / $7.50 after;
output includes thinking tokens. Jev: $0.042 / $0 per 1M (your figures, 1 Oct 2026)."""
RETRY_STATUSES: Final = frozenset({408, 429, 500, 502, 503, 504})
MAX_ATTEMPTS: Final = 6


@dataclass(frozen=True, slots=True)
class Job:
    key: str
    system: str
    row: BatteryRow
    battery: str
    count: int | None = None
    rep: int = 0
    choice: Choice | None = field(default=None, compare=False)


def battery_rows(limit: int | None = None) -> list[tuple[str, BatteryRow]]:
    rows = [(b, row) for b in BATTERIES for row in read_battery(BATTERY_DIR / "uk" / f"{b}.jsonl")]
    if limit is not None:
        rows = random.Random(SEED).sample(rows, min(limit, len(rows)))
    return rows


def accuracy_jobs(rows: Sequence[tuple[str, BatteryRow]], neighbours: Neighbours) -> list[Job]:
    jobs = []
    for battery, row in rows:
        jobs.append(Job(f"gemini_route|{row.id}", "gemini_route", row, battery))
        for n in OPTION_COUNTS:
            choice = build_choice(row, n, neighbours)
            if choice is None:
                continue
            jobs.extend(
                Job(f"{system}|{row.id}|{n}", system, row, battery, n, 0, choice)
                for system in ("jev_choice", "gemini_choice")
            )
    return jobs


def determinism_jobs(rows: Sequence[tuple[str, BatteryRow]], neighbours: Neighbours) -> list[Job]:
    sample = random.Random(SEED + 2).sample(list(rows), min(DETERMINISM_ROWS, len(rows)))
    jobs = []
    for battery, row in sample:
        choice = build_choice(row, LATENCY_COUNT, neighbours)
        for rep in range(DETERMINISM_REPEATS):
            jobs.append(
                Job(f"gemini_route|{row.id}|r{rep}", "gemini_route", row, battery, None, rep)
            )
            if choice is not None:
                key = f"jev_choice|{row.id}|{LATENCY_COUNT}|r{rep}"
                jobs.append(Job(key, "jev_choice", row, battery, LATENCY_COUNT, rep, choice))
    return jobs


LATENCY_SYSTEMS: Final = (
    "gemini_route",
    "gemini_floor",
    "jev_choice",
    "jev_floor",
    "router_service",
    "router_service_floor",
    "router_in_process",
)


def latency_jobs(
    rows: Sequence[tuple[str, BatteryRow]], neighbours: Neighbours, *, with_service: bool
) -> list[Job]:
    """Per sampled row, one call per system in a seeded random order; rows stay in sequence."""
    rng = random.Random(SEED + 3)
    sample = rng.sample(list(rows), min(LATENCY_ROWS, len(rows)))
    jobs = []
    for battery, row in sample:
        choice = build_choice(row, LATENCY_COUNT, neighbours)
        systems = [
            s
            for s in LATENCY_SYSTEMS
            if (with_service or not s.startswith("router_service"))
            and (choice is not None or s != "jev_choice")
        ]
        rng.shuffle(systems)
        for system in systems:
            count = LATENCY_COUNT if system == "jev_choice" else None
            jobs.append(Job(f"{system}|{row.id}", system, row, battery, count, 0, choice))
    return jobs


# ---------------------------------------------------------------- calling the systems


def _timing(t: Timing) -> dict[str, Any]:
    return {"total_ns": t.total_ns, "ttfb_ns": t.ttfb_ns, "connected": t.connected}


class Systems:
    """The live clients, one keep-alive connection each; ``call`` runs one job."""

    def __init__(self, index: Path, *, with_service: bool, systems: set[str]) -> None:
        """Clients only for ``systems``, so a Jev-only run never needs a Gemini key."""
        uses = {s.split("_", 1)[0] for s in systems}
        self.gemini = GeminiProxyClient(GEMINI_MODEL) if "gemini" in uses else None
        self.jev = JevClient() if "jev" in uses else None
        self.router = Router.from_path(index)
        self.service: httpx.Client | None = None
        if with_service:
            url, key, secret = (
                os.environ.get(v) for v in ("MODAL_ROUTER_URL", "MODAL_KEY", "MODAL_SECRET")
            )
            if not (url and key and secret):
                raise SystemExit(
                    "Set MODAL_ROUTER_URL, MODAL_KEY and MODAL_SECRET, or pass --no-service."
                )
            self.service = httpx.Client(
                base_url=url, headers={"Modal-Key": key, "Modal-Secret": secret}, timeout=60.0
            )

    def call(self, job: Job) -> dict[str, Any]:  # noqa: PLR0911 - one branch per system
        if job.system == "gemini_route":
            assert self.gemini is not None  # noqa: S101 - built for the systems run
            g = self.gemini.generate(route_prompt(job.row), ROUTE_SCHEMA, system=CONTRACT)
            routed = read_route(g.output)
            return {
                "status": routed.status,
                "coordinates": list(routed.coordinates),
                "malformed": list(routed.malformed),
                "citations": citations_of(g.output),
                "text": g.text if g.output is None else None,
                **_gemini_meta(g),
            }
        if job.system == "gemini_choice":
            assert job.choice is not None  # noqa: S101 - built with the job
            assert self.gemini is not None  # noqa: S101
            g = self.gemini.generate(
                gemini_choice_prompt(job.row, job.choice), gemini_choice_schema(job.choice)
            )
            return {
                "picked": choice_from_gemini(g.output),
                **_choice_meta(job.choice),
                **_gemini_meta(g),
            }
        if job.system == "jev_choice":
            assert job.choice is not None  # noqa: S101
            assert self.jev is not None  # noqa: S101
            d = self.jev.decide(job.row.query, jev_question(job.choice))
            return {
                "picked": choice_from_jev(d.answers),
                **_choice_meta(job.choice),
                "model": d.model,
                "generation_id": d.id,
                "input_tokens": d.input_tokens,
                "output_tokens": d.output_tokens,
                "api_cost": d.cost,
                "timing": _timing(d.timing),
            }
        if job.system == "gemini_floor":
            assert self.gemini is not None  # noqa: S101
            return {"timing": _timing(self.gemini.floor())}
        if job.system == "jev_floor":
            assert self.jev is not None  # noqa: S101
            return {"timing": _timing(self.jev.floor())}
        if job.system == "router_in_process":
            start = time.perf_counter_ns()
            result = self.router.route(job.row.query, context=list(job.row.context or ()) or None)
            ns = time.perf_counter_ns() - start
            return {
                "status": result.status.value,
                "timing": {"total_ns": ns, "ttfb_ns": None, "connected": False},
            }
        assert self.service is not None  # noqa: S101 - router_service jobs need it
        path = "/route" if job.system == "router_service" else "/floor"
        response, timing = timed(self.service, "POST", path, json={"query": job.row.query})
        response.raise_for_status()
        return {"status": response.json().get("status"), "timing": _timing(timing)}


def _gemini_meta(g: Any) -> dict[str, Any]:
    return {
        "model_version": g.model_version,
        "response_id": g.response_id,
        "finish_reason": g.finish_reason,
        "prompt_tokens": g.prompt_tokens,
        "output_tokens": g.output_tokens,
        "thinking_tokens": g.thinking_tokens,
        "timing": _timing(g.timing),
    }


def _choice_meta(choice: Choice) -> dict[str, Any]:
    return {"right": sorted(choice.right), "options": choice.options}


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRY_STATUSES
    if isinstance(exc, (GeminiError, JevError)):
        text = str(exc)
        return any(f"HTTP {code}" in text for code in RETRY_STATUSES) or "no candidates" in text
    return False


# ---------------------------------------------------------------- the runner


class Log:
    """``<pass>.jsonl``: one line per finished call, flushed at once, keys never repeated."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.done: set[str] = set()
        # Only a call that succeeded is done: a rerun retries the failed ones. Their failed
        # records stay in the file; the new answer supersedes them (``current``).
        self.done = {str(r["key"]) for r in read_log(path) if r.get("ok")}
        self._lock = threading.Lock()
        self._fh = path.open("a", encoding="utf-8")
        if path.stat().st_size and not path.read_bytes().endswith(b"\n"):
            self._fh.write("\n")  # a line cut off by a hard stop stays apart, and is skipped

    def write(self, record: Mapping[str, Any]) -> None:
        with self._lock:
            self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._fh.flush()
            self.done.add(str(record["key"]))

    def close(self) -> None:
        self._fh.close()


def attempt(
    call: Callable[[Job], dict[str, Any]], job: Job, sleep: Callable[[float], None] = time.sleep
) -> dict[str, Any]:
    """One job, retried with exponential back-off on rate limits and transient failures."""
    started = datetime.now(UTC).isoformat(timespec="seconds")
    error = None
    for n in range(1, MAX_ATTEMPTS + 1):
        try:
            result = call(job)
        except Exception as exc:  # noqa: BLE001 - recorded, and retried only when transient
            error = f"{type(exc).__name__}: {str(exc)[:1200]}"
            if not _retryable(exc) or n == MAX_ATTEMPTS:
                break
            asked = getattr(exc, "retry_after", None)
            backoff = min(60.0, 2.0**n + random.random())
            sleep(max(backoff, float(asked) + 1.0) if asked else backoff)
            continue
        return _record(job, started, n, result, None)
    return _record(job, started, n, None, error)


def _record(
    job: Job, started: str, attempts: int, result: dict[str, Any] | None, error: str | None
) -> dict[str, Any]:
    return {
        "key": job.key,
        "system": job.system,
        "battery": job.battery,
        "row_id": job.row.id,
        "count": job.count,
        "rep": job.rep,
        "started_utc": started,
        "attempts": attempts,
        "ok": error is None,
        "error": error,
        "result": result,
    }


def run_jobs(
    call: Callable[[Job], dict[str, Any]],
    jobs: Iterable[Job],
    log: Log,
    *,
    workers: int,
    progress: Callable[[int, int], None] | None = None,
) -> int:
    """Every job not yet in ``log``; ``workers`` at a time (1 keeps the given order)."""
    todo = [j for j in jobs if j.key not in log.done]
    finished = 0

    def one(job: Job) -> None:
        nonlocal finished
        log.write(attempt(call, job))
        finished += 1
        if progress is not None:
            progress(finished, len(todo))

    if workers <= 1:
        for job in todo:
            one(job)
        return len(todo)
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        for future in as_completed([pool.submit(one, job) for job in todo]):
            future.result()
    except BaseException:
        # Ctrl-C or a crash: drop the queued calls; the ones in flight finish and are kept.
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown()
    return len(todo)


# ---------------------------------------------------------------- scoring


def read_log(path: Path) -> list[dict[str, Any]]:
    """Every complete record; a line cut off by a hard stop is skipped (its call runs again)."""
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line) if line.strip() else None
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and "key" in record:
            records.append(record)
    return records


def current(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One record per call: its latest success, else its latest failure. A failed call that a
    rerun answered counts as answered; its failed records stay in the file as history."""
    best: dict[str, dict[str, Any]] = {}
    for record in records:
        key = str(record["key"])
        if record.get("ok") or not best.get(key, {}).get("ok"):
            best[key] = dict(record)
    return list(best.values())


def superseded(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Failed records later answered by a rerun: how many, by system and error."""
    answered = {str(r["key"]) for r in records if r.get("ok")}
    gone = [r for r in records if not r.get("ok") and str(r["key"]) in answered]
    errors: dict[str, int] = {}
    for r in gone:
        head = str(r.get("error") or "")[:80]
        errors[head] = errors.get(head, 0) + 1
    return {"count": len(gone), "errors": errors}


def gemini_cost(records: Iterable[Mapping[str, Any]], prices: Mapping[str, float]) -> float:
    total = 0.0
    for r in records:
        res = r.get("result") or {}
        total += res.get("prompt_tokens", 0) * prices["input"]
        total += (res.get("output_tokens", 0) + res.get("thinking_tokens", 0)) * prices["output"]
    return total / 1e6


def usage(records: Sequence[Mapping[str, Any]], system: str) -> dict[str, Any]:
    mine = [r for r in records if r["system"] == system and r["ok"]]
    out: dict[str, Any] = {
        "calls": len(mine),
        "failed": sum(1 for r in records if r["system"] == system and not r["ok"]),
    }
    if not mine:
        return out
    if system.startswith("gemini"):
        out["prompt_tokens_mean"] = round(
            sum(r["result"]["prompt_tokens"] for r in mine) / len(mine), 1
        )
        out["output_tokens_mean"] = round(
            sum(r["result"]["output_tokens"] for r in mine) / len(mine), 1
        )
        out["thinking_tokens_mean"] = round(
            sum(r["result"]["thinking_tokens"] for r in mine) / len(mine), 1
        )
        out["cost_usd_promotional"] = round(
            gemini_cost(mine, PRICES["gemini_promotional_per_m"]), 4
        )
        out["cost_usd_regular"] = round(gemini_cost(mine, PRICES["gemini_regular_per_m"]), 4)
        out["model_versions"] = sorted({r["result"]["model_version"] for r in mine})
    else:
        out["input_tokens_mean"] = round(
            sum(r["result"]["input_tokens"] for r in mine) / len(mine), 1
        )
        out["cost_usd_reported"] = round(sum(r["result"]["api_cost"] for r in mine), 6)
        out["cost_usd_list"] = round(
            sum(r["result"]["input_tokens"] for r in mine) * PRICES["jev_per_m"]["input"] / 1e6, 6
        )
        out["models"] = sorted({r["result"]["model"] for r in mine})
    out["cost_basis"] = "list price per token; Gemini also at the regular price after the promotion"
    return out


def _existence(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Reading 3, Unit 2: the outcome on invented law, and real law refused."""
    return {k: metrics[k] for k in ("bound_on_invented", "strict_abstention", "false_abstention")}


def score_accuracy(
    records: Sequence[Mapping[str, Any]],
    rows: Mapping[str, tuple[str, BatteryRow]],
    router: Router | None = None,
) -> dict[str, Any]:
    """Gemini end to end, read three ways (``router`` resolves reading 1), and the choices."""
    out: dict[str, Any] = {}
    route = [r for r in records if r["system"] == "gemini_route" and r["ok"]]
    llm_only, parsed = [], []
    for r in route:
        battery, row = rows[r["row_id"]]
        res = r["result"]
        own = Routed(res["status"], tuple(res["coordinates"]), tuple(res["malformed"]))
        llm_only.append(outcome(battery, row, own))
        if router is not None:
            if res["status"] is None:
                parsed.append(outcome(battery, row, Routed(None, ())))
            else:
                extracted = resolve_extraction(router, res.get("citations") or [])
                parsed.append(outcome(battery, row, extracted))
    if llm_only:
        knowable = [o for o in llm_only if o.expected_status not in INDEX_DEPENDENT]
        whole = domain_metrics(llm_only)
        out["gemini_route"] = {
            "reading": "2: Gemini as an LLM-only router (its own outcome and coordinates)",
            "all_rows": whole,
            "knowable_rows": domain_metrics(knowable),
            "unusable_answers": sum(1 for r in route if r["result"]["status"] is None),
            "malformed_coordinates": sum(len(r["result"]["malformed"]) for r in route),
        }
        out["gemini_existence"] = {
            "reading": "3: Gemini on existence (Unit 2), from reading 2's outcomes",
            **_existence(whole),
        }
    if parsed:
        knowable = [o for o in parsed if o.expected_status not in INDEX_DEPENDENT]
        out["gemini_parser"] = {
            "reading": "1: Gemini as a parser (Unit 1); its extracted citations resolved by the "
            "router's index, its own coordinates unused",
            "all_rows": domain_metrics(parsed),
            "knowable_rows": domain_metrics(knowable),
        }
    for system in ("jev_choice", "gemini_choice"):
        answered = []
        for r in records:
            if r["system"] != system or not r["ok"]:
                continue
            res = r["result"]
            choice = Choice(
                r["row_id"], int(r["count"]), dict(res["options"]), {}, frozenset(res["right"])
            )
            answered.append((choice, res["picked"]))
        if answered:
            out[system] = score_choices(answered)
    return out


def score_determinism(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out = {}
    for system in ("gemini_route", "jev_choice"):
        answers: dict[str, list[Any]] = {}
        for r in records:
            if r["system"] == system and r["ok"]:
                res = r["result"]
                answer = (
                    (res["status"], tuple(res["coordinates"]))
                    if system == "gemini_route"
                    else res["picked"]
                )
                answers.setdefault(r["row_id"], []).append(answer)
        complete = {k: v for k, v in answers.items() if len(v) == DETERMINISM_REPEATS}
        changed = sum(1 for v in complete.values() if len(set(v)) > 1)
        out[system] = {"rows": len(complete), "rows_whose_answer_changed": changed}
    return out


def score_latency(records: Sequence[Mapping[str, Any]], resamples: int) -> dict[str, Any]:
    by_system: dict[str, list[int]] = {}
    by_row: dict[str, dict[str, int]] = {}
    for r in records:
        if r["ok"]:
            ns = int(r["result"]["timing"]["total_ns"])
            by_system.setdefault(r["system"], []).append(ns)
            by_row.setdefault(r["row_id"], {})[r["system"]] = ns
    out: dict[str, Any] = {s: stats_ms(v, resamples) for s, v in sorted(by_system.items())}
    for system, floor in (
        ("gemini_route", "gemini_floor"),
        ("jev_choice", "jev_floor"),
        ("router_service", "router_service_floor"),
    ):
        diffs = [
            calls[system] - calls[floor]
            for calls in by_row.values()
            if system in calls and floor in calls
        ]
        out[f"{system}_minus_floor"] = stats_ms(sorted(diffs), resamples) if diffs else None
    return out


# ---------------------------------------------------------------- command line


def _manifest(directory: Path, args: argparse.Namespace) -> None:
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"runs": []}
    manifest["runs"].append(
        {
            "pass": args.stage,
            "started_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "limit": args.limit,
            "workers": args.workers,
            "client_region": os.environ.get("LRR_CLIENT_REGION"),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "gemini_model": GEMINI_MODEL,
            "jev_model": "typesafe/jev-1.13",
            "seed": SEED,
            "prices": PRICES,
            "gemini_endpoint": GEMINI_ENDPOINT,
            "note": "Gemini 3.8 Flash (high thinking) through a private OpenAI-compatible proxy "
            "run by the author's engineer, not Google's public API: token counts are the proxy's, "
            "costs are at Google's published list price, and Gemini latency is the proxy's path.",
        }
    )
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _run(args: argparse.Namespace) -> int:  # pragma: no cover - live calls
    smoke = args.limit is not None and args.limit <= SMOKE_ROWS
    if not smoke and not args.confirmed:
        print("Refused: confirm the cost estimate first (bench.compare estimate), "
              "then pass --confirmed.")  # fmt: skip
        return 1
    router = Router.from_path(args.index)
    neighbours = Neighbours.from_index(router.index)
    rows = battery_rows(args.limit)
    with_service = args.stage == "latency" and not args.no_service
    builders = {
        "accuracy": lambda: accuracy_jobs(rows, neighbours),
        "determinism": lambda: determinism_jobs(rows, neighbours),
        "latency": lambda: latency_jobs(rows, neighbours, with_service=with_service),
    }
    jobs = select(builders[args.stage](), args.systems)
    systems = Systems(args.index, with_service=with_service, systems={j.system for j in jobs})
    _manifest(args.dir, args)
    log = Log(args.dir / f"{args.stage}.jsonl")
    workers = 1 if args.stage == "latency" else args.workers
    left = sum(1 for j in jobs if j.key not in log.done)
    print(f"{args.stage}: {len(jobs)} calls, {left} to make (failed ones included), "
          f"{workers} at a time", flush=True)  # fmt: skip

    def progress(done: int, total: int) -> None:
        if done % 200 == 0 or done == total:
            print(f"  {done} of {total}", flush=True)

    try:
        run_jobs(systems.call, jobs, log, workers=workers, progress=progress)
    finally:
        log.close()
    failed = sum(1 for r in current(read_log(log.path)) if not r["ok"])
    print(f"done; {failed} calls failed after retries (they stay recorded)")
    return 0


def select(jobs: list[Job], systems: Sequence[str] | None) -> list[Job]:
    """The jobs of ``systems`` (a system's floor calls go with it), or all of them."""
    if not systems:
        return jobs
    keep = set(systems) | {f"{s.split('_', 1)[0]}_floor" for s in systems}
    return [j for j in jobs if j.system in keep]


def progress_table(
    planned: Mapping[str, Sequence[Job]], logs: Mapping[str, Sequence[Mapping[str, Any]]]
) -> list[str]:
    """One line per pass and system: calls done of planned, the percentage, and failures."""
    lines = []
    for stage, jobs in planned.items():
        records = {r["key"]: r for r in logs.get(stage, [])}
        for system in sorted({j.system for j in jobs}):
            mine = [j.key for j in jobs if j.system == system]
            done = [records[k] for k in mine if k in records]
            failed = sum(1 for r in done if not r["ok"])
            pct = 100.0 * len(done) / len(mine) if mine else 0.0
            lines.append(
                f"{stage:12} {system:22} {len(done):6}/{len(mine):<6} {pct:6.1f}%  failed {failed}"
            )
    return lines


def _status(args: argparse.Namespace) -> int:  # pragma: no cover - reads a live run
    router = Router.from_path(args.index)
    neighbours = Neighbours.from_index(router.index)
    rows = battery_rows()
    planned = {
        "accuracy": select(accuracy_jobs(rows, neighbours), args.systems),
        "determinism": select(determinism_jobs(rows, neighbours), args.systems),
        "latency": select(
            latency_jobs(rows, neighbours, with_service=not args.no_service), args.systems
        ),
    }
    logs = {stage: current(read_log(args.dir / f"{stage}.jsonl")) for stage in planned}
    print("\n".join(progress_table(planned, logs)))
    return 0


def call_cost(record: Mapping[str, Any]) -> tuple[float, float]:
    """One call's cost at list price: (promotional or Jev's price, regular price)."""
    if record["system"].startswith("gemini"):
        promo = gemini_cost([record], PRICES["gemini_promotional_per_m"])
        return promo, gemini_cost([record], PRICES["gemini_regular_per_m"])
    tokens = (record.get("result") or {}).get("input_tokens", 0)
    cost = tokens * PRICES["jev_per_m"]["input"] / 1e6
    return cost, cost


def estimate_remaining(
    planned: Mapping[str, Sequence[Job]], logs: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, dict[str, float]]:
    """Per system: the calls still to make in every pass, at the mean cost per call measured so
    far for that system (in any pass), promotional and regular."""
    measured: dict[str, list[tuple[float, float]]] = {}
    done: set[str] = set()
    for records in logs.values():
        for r in records:
            if r["ok"]:
                done.add(str(r["key"]))
            if r["ok"] and r["system"] in {"gemini_route", "gemini_choice", "jev_choice"}:
                measured.setdefault(r["system"], []).append(call_cost(r))
    out: dict[str, dict[str, float]] = {}
    for jobs in planned.values():
        for job in jobs:
            costs = measured.get(job.system)
            if job.key in done or not costs:
                continue
            row = out.setdefault(job.system, {"calls_left": 0, "usd": 0.0, "usd_regular": 0.0})
            row["calls_left"] += 1
            row["usd"] += sum(c[0] for c in costs) / len(costs)
            row["usd_regular"] += sum(c[1] for c in costs) / len(costs)
    return out


def _estimate(args: argparse.Namespace) -> int:  # pragma: no cover - reads a live run
    router = Router.from_path(args.index)
    neighbours = Neighbours.from_index(router.index)
    rows = battery_rows()
    planned = {
        "accuracy": accuracy_jobs(rows, neighbours),
        "determinism": determinism_jobs(rows, neighbours),
        "latency": latency_jobs(rows, neighbours, with_service=False),
    }
    logs = {stage: current(read_log(args.dir / f"{stage}.jsonl")) for stage in planned}
    measured = [r for records in logs.values() for r in records if r["ok"]]
    for system in ("gemini_route", "gemini_choice", "jev_choice"):
        mine = [r for r in measured if r["system"] == system]
        if mine:
            promo = sum(call_cost(r)[0] for r in mine) / len(mine)
            print(f"{system:14} measured on {len(mine)} calls: ${promo:.5f} per call")
    print("Still to run, at those means:")
    for system, row in estimate_remaining(planned, logs).items():
        print(f"  {system:14} {row['calls_left']:6} calls  ${row['usd']:8.2f} "
              f"(${row['usd_regular']:.2f} at the regular price)")  # fmt: skip
    return 0


def _score(args: argparse.Namespace) -> int:  # pragma: no cover - reads a live run
    router = Router.from_path(args.index)
    rows_by_id = {row.id: (b, row) for b, row in battery_rows()}
    accuracy = current(read_log(args.dir / "accuracy.jsonl"))
    summary = {
        "scored_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "index_snapshot": router.index.snapshot,
        "accuracy": score_accuracy(accuracy, rows_by_id, router),
        "determinism": score_determinism(current(read_log(args.dir / "determinism.jsonl"))),
        "latency": score_latency(current(read_log(args.dir / "latency.jsonl")), args.resamples),
        "superseded_failures": {
            stage: superseded(read_log(args.dir / f"{stage}.jsonl"))
            for stage in ("accuracy", "determinism", "latency")
        },
        "usage": {s: usage(accuracy, s) for s in ("gemini_route", "gemini_choice", "jev_choice")},
        "prices": PRICES,
    }
    (args.dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"-> {args.dir / 'summary.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - live calls
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--dir", type=Path, required=True)
    run.add_argument(
        "--pass", dest="stage", choices=["accuracy", "determinism", "latency"], required=True
    )
    run.add_argument("--limit", type=int, help="a seeded sample of this many rows (a smoke run)")
    run.add_argument("--workers", type=int, default=8)
    run.add_argument("--index", type=Path, default=Path("data/index"))
    run.add_argument("--no-service", action="store_true", help="leave out the router on Modal")
    run.add_argument("--confirmed", action="store_true", help="you have confirmed the estimate")
    run.add_argument("--systems", nargs="+", help="only these systems, e.g. jev_choice")
    status = sub.add_parser("status")
    status.add_argument("--dir", type=Path, required=True)
    status.add_argument("--index", type=Path, default=Path("data/index"))
    status.add_argument("--systems", nargs="+")
    status.add_argument("--no-service", action="store_true", help="as the run was started")
    for name in ("estimate", "score"):
        p = sub.add_parser(name)
        p.add_argument("--dir", type=Path, required=True)
        p.add_argument("--index", type=Path, default=Path("data/index"))
        p.add_argument("--resamples", type=int, default=1000)
    args = parser.parse_args(argv)
    args.dir.mkdir(parents=True, exist_ok=True)
    commands = {"run": _run, "status": _status, "estimate": _estimate, "score": _score}
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
