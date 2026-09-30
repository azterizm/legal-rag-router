"""Controlled latency re-run on the Mac (roadmap stop 18): three bench passes on the v2 seal.

The Mac counterpart of ``scripts/latency_rig.ps1``: the same files, the same quiet gate and
the same reporting rule. Close every other application, then from the repository root:

    uv run python -m scripts.latency_mac --smoke    # about a minute: checks the script
    uv run python -m scripts.latency_mac            # the real run

It writes ``bench/results/mac-rerun-<date>/``:

- ``env-before.json``, ``env-after.json``: OS, CPU, memory, disk, power, services, load;
- ``pass-N.json``: the bench output, the same format as every earlier run;
- ``pass-N-conditions.json``: the quiet check before, CPU busy during, load after.

Nothing in it names the machine or the user; process lists hold names only.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, TypeVar

from eval.seal import REPO, SealError, verify_battery_seal

SEAL: Final = "seals/battery-2026-09-29-v2.json"
REPLAYS: Final = "results/raw/replays-100k.txt"
BROWSERS: Final = frozenset(
    {
        "Google Chrome",
        "Chromium",
        "Safari",
        "firefox",
        "Microsoft Edge",
        "Brave Browser",
        "Arc",
        "Opera",
    }
)
ACTIVE_PCT: Final = 0.5
"""A process is listed when it uses at least this share of the machine."""
_CPU_LINE: Final = re.compile(r"CPU usage: ([\d.]+)% user, ([\d.]+)% sys, ([\d.]+)% idle")

T = TypeVar("T")


def run(*args: str) -> str:
    return subprocess.run(  # noqa: S603 - fixed tool arguments, no shell
        args, check=True, capture_output=True, text=True
    ).stdout.strip()


def probe(fn: Callable[[], T]) -> T | str:
    try:
        return fn()
    except (OSError, ValueError, KeyError, IndexError, subprocess.CalledProcessError) as exc:
        return f"unavailable: {exc}"


def summarise(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "avg": round(sum(values) / len(values), 1),
        "min": round(min(values), 1),
        "max": round(max(values), 1),
        "samples": len(values),
    }


def busy_from_top(text: str) -> list[float]:
    """CPU busy % (user + sys) per ``top`` sample. The first has no interval, so it is dropped."""
    return [float(user) + float(sys_) for user, sys_, _ in _CPU_LINE.findall(text)][1:]


def load_sample(seconds: int = 15) -> dict[str, Any]:
    top = run("top", "-l", str(seconds + 1), "-s", "1", "-n", "0")
    free = re.search(r"(\d+)%", run("memory_pressure", "-Q"))
    return {
        "cpu_busy_pct": summarise(busy_from_top(top)),
        "memory_free_pct": int(free.group(1)) if free else None,
    }


def processes() -> list[tuple[int, float, int, str]]:
    """``(pid, cpu % of one core, resident MB, name)`` for every process."""
    rows = []
    for line in run("ps", "-Ao", "pid=,pcpu=,rss=,comm=").splitlines():
        pid, pcpu, rss, comm = line.split(None, 3)
        rows.append((int(pid), float(pcpu), int(rss) // 1024, Path(comm).name))
    return rows


def browsers_running() -> list[str]:
    """Browsers by name, counting their helper processes (``Google Chrome Helper (Renderer)``)."""
    names = {name.split(" Helper")[0] for *_, name in processes()}
    return sorted(names & BROWSERS)


def active_processes() -> list[dict[str, Any]]:
    """Processes using at least 0.5 % of the machine, by name (``ps``'s recent-CPU figure)."""
    cores = os.cpu_count() or 1
    rows: list[dict[str, Any]] = [
        {"name": name, "cpu_pct": round(pcpu / cores, 1), "resident_mb": rss}
        for pid, pcpu, rss, name in processes()
        if pid != os.getpid() and pcpu / cores >= ACTIVE_PCT
    ]
    return sorted(rows, key=lambda row: -row["cpu_pct"])[:15]


def fields(text: str, *keys: str) -> dict[str, str]:
    """``key: value`` lines of a tool's report, for the keys asked."""
    found = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() in keys:
            found[key.strip()] = value.strip()
    return found


def sysctl(name: str) -> str:
    return run("sysctl", "-n", name)


def uptime_hours() -> float:
    booted = re.search(r"sec = (\d+)", sysctl("kern.boottime"))
    if booted is None:
        raise ValueError("kern.boottime has no seconds")
    return round((time.time() - int(booted.group(1))) / 3600, 1)


def power() -> dict[str, Any]:
    settings = dict(line.split(None, 1) for line in run("pmset", "-g").splitlines()[1:] if line)
    source = re.search(r"'([^']+)'", run("pmset", "-g", "batt"))
    return {
        "low_power_mode": settings.get("lowpowermode", "not listed").strip(),
        "power_mode": settings.get("powermode", "not listed").strip(),
        "source": source.group(1) if source else None,
        "thermal": run("pmset", "-g", "therm").splitlines(),
    }


def git_state() -> dict[str, Any]:
    return {
        "commit": run("git", "rev-parse", "HEAD"),
        "tracked_changes": bool(run("git", "status", "--porcelain", "--untracked-files=no")),
    }


def environment() -> dict[str, Any]:
    return {
        "captured_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "launched_over_ssh": bool(os.environ.get("SSH_CONNECTION")),
        "os": probe(
            lambda: {
                "version": run("sw_vers", "-productVersion"),
                "build": run("sw_vers", "-buildVersion"),
                "uptime_hours": uptime_hours(),
            }
        ),
        "cpu": probe(
            lambda: {
                "name": sysctl("machdep.cpu.brand_string"),
                "model": sysctl("hw.model"),
                "cores": int(sysctl("hw.ncpu")),
                "performance_cores": int(sysctl("hw.perflevel0.physicalcpu")),
                "efficiency_cores": int(sysctl("hw.perflevel1.physicalcpu")),
            }
        ),
        "memory_gb": probe(lambda: int(sysctl("hw.memsize")) // 1024**3),
        "repo_disk": probe(
            lambda: fields(
                run("diskutil", "info", "/"), "Device / Media Name", "Protocol", "Solid State"
            )
        ),
        "power": probe(power),
        "gatekeeper": probe(lambda: run("spctl", "--status")),
        "spotlight": probe(lambda: " ".join(run("mdutil", "-s", "/").split())),
        "time_machine_running": probe(lambda: "Running = 1" in run("tmutil", "status")),
        "browsers_running": probe(browsers_running),
        "process_count": probe(lambda: len(processes())),
        "active_processes": probe(active_processes),
        "load": probe(load_sample),
        "python": f"{sys.version.split()[0]} {platform.python_compiler().strip()}",
        "perf_counter": vars(time.get_clock_info("perf_counter")),
        "uv": probe(lambda: run("uv", "--version")),
        "repo": probe(git_state),
        "seal": SEAL,
    }


def wait_quiet(pass_no: int, settle: int, quiet_pct: float) -> dict[str, Any]:
    """Decided before any result is seen: a pass starts only when the 15 s average CPU busy is
    at most ``quiet_pct``. Three tries; a pass that never got a quiet start is marked so."""
    load: dict[str, Any] = {}
    for attempt in range(1, 4):
        print(f"pass {pass_no}: settling for {settle} s (try {attempt} of 3). Hands off the Mac.")
        time.sleep(settle)
        load = load_sample()
        busy = load["cpu_busy_pct"]
        if busy is None:
            return {"attempts": attempt, "quiet": None, "load": load}
        if busy["avg"] <= quiet_pct:
            return {"attempts": attempt, "quiet": True, "load": load}
        print(f"CPU busy {busy['avg']} % (limit {quiet_pct} %); waiting again.")
    return {"attempts": 3, "quiet": False, "load": load}


def save(payload: object, path: Path) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def measure(out: Path, pass_no: int, queries: list[str]) -> tuple[float, str]:
    """One pass of the unchanged bench in a fresh process, with ``top`` sampling alongside."""
    with tempfile.TemporaryFile("w+") as log:
        sampler = subprocess.Popen(
            ["top", "-l", "0", "-s", "5", "-n", "0"],  # noqa: S607 - macOS's own top
            stdout=log,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        started = time.monotonic()
        try:
            subprocess.run(  # noqa: S603 - fixed arguments, no shell
                ["uv", "run", "python", "-m", "bench.latency", *queries, "--repeats", "3",  # noqa: S607 - uv from PATH
                 "--json", str(out / f"pass-{pass_no}.json")],
                check=True,
                stdout=subprocess.DEVNULL,
                cwd=REPO,
            )  # fmt: skip
        finally:
            sampler.terminate()
            sampler.wait()
        duration = time.monotonic() - started
        log.seek(0)
        return duration, log.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--settle", type=int, default=120, help="seconds idle before a pass")
    parser.add_argument("--quiet-pct", type=float, default=10.0)
    parser.add_argument("--smoke", action="store_true", help="one short pass, battery rows only")
    args = parser.parse_args(argv)

    if platform.system() != "Darwin":
        print("This is not macOS: on the rig, use scripts/latency_rig.ps1.", file=sys.stderr)
        return 1
    queries = ["--queries", REPLAYS]
    out = REPO / "bench" / "results" / f"mac-rerun-{datetime.now(UTC):%Y-%m-%d}"
    if args.smoke:
        args.passes, args.settle, queries = 1, 5, []
        out = out.with_name(out.name + "-smoke")
        shutil.rmtree(out, ignore_errors=True)
    elif open_browsers := browsers_running():
        print(f"A browser is running ({', '.join(open_browsers)}). Close it and start again.")
        return 1
    elif "AC Power" not in run("pmset", "-g", "batt"):
        print("The Mac is on battery. Plug it in and start again.")
        return 1
    if os.environ.get("SSH_CONNECTION"):
        print("Started over SSH: recorded. It does not enter the in-process timings.")
    try:
        seal = verify_battery_seal(REPO / SEAL, REPO, REPO / "data" / "index")
    except SealError as exc:
        print(f"SEAL ERROR: {exc}\nNothing was measured.")
        return 1
    print(f"OK: {SEAL} matches ({seal['seal_sha256']})")
    if out.exists():
        print(f"{out.relative_to(REPO)} exists: a measurement is never overwritten.")
        return 1
    out.mkdir(parents=True)

    print("recording the machine's state")
    save(environment(), out / "env-before.json")
    what = "the battery rows only, 6,336 calls" if args.smoke else "306,336 calls; several minutes"
    for pass_no in range(1, args.passes + 1):
        conditions: dict[str, Any] = {
            "pass": pass_no,
            "start": wait_quiet(pass_no, args.settle, args.quiet_pct),
        }
        print(f"pass {pass_no} of {args.passes}: measuring ({what})")
        duration, top = measure(out, pass_no, queries)
        conditions["duration_s"] = round(duration)
        conditions["during"] = {
            "note": "sampled every ~5 s; busy % includes the bench itself (one core)",
            "cpu_busy_pct": summarise(busy_from_top(top)),
        }
        conditions["after"] = {
            "load": probe(load_sample),
            "active_processes": probe(active_processes),
            "thermal": probe(lambda: run("pmset", "-g", "therm").splitlines()),
        }
        save(conditions, out / f"pass-{pass_no}-conditions.json")
        everything = json.loads((out / f"pass-{pass_no}.json").read_text(encoding="utf-8"))["all"]
        print(
            f"pass {pass_no}: p50 {everything['p50_us']} us, p99 {everything['p99_us']} us, "
            f"max {everything['max_us']} us"
        )
    save(environment(), out / "env-after.json")
    print(f"done: {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
