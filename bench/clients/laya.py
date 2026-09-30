"""Laya, speed and footprint only (roadmap M11; section 4, decision 3 as amended).

    export HF_HOME=~/.cache/lrr-laya
    uv run --with laya==0.3.22 python -m bench.clients.laya --device cpu
    uv run --with laya==0.3.22 python -m bench.clients.laya --device mps    # Apple GPU
    uv run --with laya==0.3.22 python -m bench.clients.laya --device cuda   # the rig's GPU

It loads the base checkpoint directly, at a pinned revision, and refuses any other bytes. Each
state is a battery query; each call asks one ``choice`` question whose options are 3, 10 or 30
real instrument titles from the index. Every call is timed; the answers are never read or
recorded, since the vendor documents the base checkpoint as near chance without fine-tuning.
A call whose options do not fit the model's context is counted as not fitting, not trimmed.
The footprint (install, weights, load time, memory) is recorded with the timings.

Laya and PyTorch are not project dependencies: ``uv run --with`` puts them in a temporary
environment, and ``HF_HOME`` keeps the weights in one folder that is deleted afterwards.
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import sys
import time
import warnings
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Final

from batteries.schema import BATTERIES, BATTERY_DIR, read_battery
from bench.row_b import stats_ms
from legal_rag_router import Router
from legal_rag_router.coordinate import Coordinate

REPO: Final = "convaiinnovations/laya"
REVISION: Final = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
SHA256: Final = {
    "model.safetensors": "891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c",
    "rl_agent_config.json": "ae287b56bbcf5f8c4f4541ae9dfd00c914c4c48b940b8398c3058af37ba92bbd",
    "encoder/config.json": "bf3ab80598fdccf414855a2ce80f22859e4492d06ca8a62ddd1cfb63972f8979",
    "tokenizer/tokenizer_config.json": (
        "50044de60daaa73df97d262e15a40d4faf0160e7d742df64b377877a1320dd12"
    ),
    "tokenizer/tokenizer.json": "6c8aaa9a542084f2457eab775d4eeb51f92a70c0fd9de28d5edb0ddec3c08d30",
}
"""Recorded on the Mac on 30 Sept 2026, from the first download; the rig gets the same files."""
OPTION_COUNTS: Final = (3, 10, 30)
SAMPLE: Final = 300
WARMUP: Final = 20
SEED: Final = 20260930
INSTRUCTIONS: Final = "Which instrument does this text cite?"


def battery_rows() -> list[tuple[str, tuple[str, ...]]]:
    return [
        (row.query, row.expected_coordinates)
        for battery in BATTERIES
        for row in read_battery(BATTERY_DIR / "uk" / f"{battery}.jsonl")
    ]


def title_pool(router: Router, coordinates: Sequence[str]) -> list[str]:
    """The distinct titles of the instruments the batteries cite, in a stable order."""
    titles = set()
    for text in coordinates:
        coordinate = Coordinate.try_parse(text)
        info = router.index.instrument(coordinate.instrument_id) if coordinate else None
        if info is not None:
            titles.add(info.title)
    return sorted(titles)


def plan_calls(
    states: Sequence[str], titles: Sequence[str], counts: Sequence[int], seed: int = SEED
) -> list[tuple[int, str, list[str]]]:
    """``(option count, state, options)`` per call: every sampled state at every count."""
    rng = random.Random(seed)
    return [(n, state, rng.sample(list(titles), n)) for n in counts for state in states]


HEAD_MAX_LEN: Final = 192
OPTION_CAP: Final = 48
HEAD_RESERVE: Final = 16
MIN_PER_OPTION: Final = 4


def option_cut(
    lengths: Sequence[int], head_max_len: int = HEAD_MAX_LEN
) -> tuple[int | None, float]:
    """How much of each option Laya shows the model: ``(tokens per option or None, share of the
    options' tokens kept)``. ``lengths`` are the options' token counts.

    The rule is Laya 0.3.22's own (``laya.common.build_sequence``): each option is a marker plus
    at most 48 tokens; if they overrun the head budget, every option is cut to
    ``max(4, (head_max_len - 16) // n)`` tokens, marker included. Nothing is raised or flagged
    unless two options end up identical.
    """
    capped = [1 + min(n, OPTION_CAP) for n in lengths]
    per = None
    if head_max_len - sum(capped) < HEAD_RESERVE:
        per = max(MIN_PER_OPTION, (head_max_len - HEAD_RESERVE) // max(1, len(capped)))
        capped = [min(c, per) for c in capped]
    total = sum(lengths)
    return per, (sum(c - 1 for c in capped) / total if total else 1.0)


def question(options: Sequence[str]) -> dict[str, Any]:
    return {
        "instrument": {
            "type": "choice",
            "instructions": INSTRUCTIONS,
            "criteria": {f"option_{i}": title for i, title in enumerate(options)},
        }
    }


def time_calls(
    predict: Callable[[str, dict[str, Any]], Mapping[str, Any]],
    calls: Sequence[tuple[int, str, list[str]]],
) -> dict[int, dict[str, Any]]:
    """Per option count: each fitting call's nanoseconds, the calls that did not fit, the calls
    whose options collapsed to the same tokens, and the input token counts."""
    out: dict[int, dict[str, Any]] = {}
    for n, state, options in calls:
        row = out.setdefault(n, {"ns": [], "not_fitting": 0, "collapsed": 0, "input_tokens": []})
        start = time.perf_counter_ns()
        try:
            result = predict(state, question(options))
        except ValueError:
            row["not_fitting"] += 1
            continue
        row["ns"].append(time.perf_counter_ns() - start)
        usage = result.get("usage") or {}
        row["collapsed"] += bool(usage.get("options"))
        if "input_tokens" in usage:
            row["input_tokens"].append(int(usage["input_tokens"]))
    return out


def title_cuts(
    count_tokens: Callable[[str], int], calls: Sequence[tuple[int, str, list[str]]]
) -> dict[int, dict[str, Any]]:
    """Per option count, from ``option_cut``: the tokens each option was allowed and the median
    share of the titles' tokens the model saw. Computed outside the timed calls."""
    by_count: dict[int, list[tuple[int | None, float]]] = {}
    for n, _, options in calls:
        by_count.setdefault(n, []).append(option_cut([count_tokens(o) for o in options]))
    out = {}
    for n, cuts in by_count.items():
        shares = sorted(share for _, share in cuts)
        caps = {per for per, _ in cuts}
        out[n] = {
            "tokens_per_option": sorted(caps, key=lambda c: -1 if c is None else c),
            "title_tokens_kept_p50": round(shares[len(shares) // 2], 3),
        }
    return out


def report(
    timed: Mapping[int, Mapping[str, Any]],
    resamples: int,
    cuts: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    out = {}
    for n, row in sorted(timed.items()):
        tokens = sorted(row["input_tokens"])
        out[str(n)] = {
            "calls": len(row["ns"]) + row["not_fitting"],
            "not_fitting": row["not_fitting"],
            "collapsed_options": row["collapsed"],
            "input_tokens_p50": tokens[len(tokens) // 2] if tokens else None,
            **(cuts or {}).get(n, {}),
            "latency": stats_ms(row["ns"], resamples),
        }
    return out


def _dir_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _peak_rss_mb() -> float | None:
    try:
        import resource  # noqa: PLC0415 - not on Windows
    except ImportError:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)


def _cuts_and_example(
    tok: Any, titles: Sequence[str], calls: Sequence[tuple[int, str, list[str]]]
) -> tuple[dict[int, dict[str, Any]], dict[str, str]]:  # pragma: no cover - needs laya
    """The title cuts per option count, and the longest title as the model sees it at 30."""

    def ids(text: str) -> list[int]:
        return list(tok(" " + text, add_special_tokens=False)["input_ids"])

    longest = max(titles, key=lambda title: len(ids(title)))
    per = option_cut([len(ids(longest))] * OPTION_COUNTS[-1])[0] or OPTION_CAP + 1
    seen = str(tok.decode(ids(longest)[: per - 1])).strip()
    return title_cuts(lambda text: len(ids(text)), calls), {"title": longest, "as_seen": seen}


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs laya and torch
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--device", required=True, choices=["cpu", "mps", "cuda"])
    parser.add_argument("--sample", type=int, default=SAMPLE)
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--index", type=Path, default=Path("data/index"))
    parser.add_argument("--out", type=Path, default=Path("bench/results"))
    args = parser.parse_args(argv)

    import laya  # type: ignore[import-not-found]  # noqa: PLC0415 - uv run --with laya
    import torch  # type: ignore[import-not-found]  # noqa: PLC0415

    router = Router.from_path(args.index)
    rows = battery_rows()
    titles = title_pool(router, [c for _, coords in rows for c in coords])
    states = [q for q, _ in random.Random(SEED).sample(rows, args.sample)]
    warmup = plan_calls(states[:WARMUP], titles, (OPTION_COUNTS[0],), seed=SEED + 1)
    calls = plan_calls(states, titles, OPTION_COUNTS)

    rss_before = _peak_rss_mb()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        started = time.perf_counter()
        agent = laya.load(REPO, device=args.device, revision=REVISION, expected_sha256=SHA256)
        load_s = time.perf_counter() - started
    device = str(agent.device)
    kind = device.partition(":")[0]
    if kind != args.device:
        print(f"Asked for {args.device}, but Laya is on {device}; nothing was measured.")
        return 1
    rss_loaded = _peak_rss_mb()
    from huggingface_hub import constants  # type: ignore[import-not-found]  # noqa: PLC0415

    weights = Path(constants.HF_HUB_CACHE) / f"models--{REPO.replace('/', '--')}" / "snapshots"
    weights /= REVISION
    weights_mb = round(sum(f.stat().st_size for f in weights.rglob("*") if f.is_file()) / 2**20)
    time_calls(agent.predict, warmup)
    timed = time_calls(agent.predict, calls)
    cuts, example = _cuts_and_example(agent.tok, titles, calls)

    gpu_mb = None
    if device.startswith("cuda"):
        gpu_mb = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    elif device == "mps":
        gpu_mb = round(torch.mps.driver_allocated_memory() / 2**20, 1)
    site = Path(laya.__file__).resolve().parents[1]
    result: dict[str, Any] = {
        "measured_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": {"repo": REPO, "revision": REVISION, "sha256_verified": True},
        "versions": {
            "laya": metadata.version("laya"),
            "torch": torch.__version__,
            "transformers": metadata.version("transformers"),
            "python": sys.version.split()[0],
        },
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "device": device,
            "gpu": torch.cuda.get_device_name(0) if device.startswith("cuda") else None,
            "torch_threads": torch.get_num_threads(),
        },
        "footprint": {
            "install_mb": round(_dir_bytes(site) / 2**20),
            "weights_mb": weights_mb,
            "load_s": round(load_s, 2),
            "peak_rss_mb_before_load": rss_before,
            "peak_rss_mb_after_load": rss_loaded,
            "peak_rss_mb_after_run": _peak_rss_mb(),
            "gpu_memory_mb": gpu_mb,
        },
        "load_warnings": sorted({str(w.message) for w in caught}),
        "states": len(states),
        "title_pool": len(titles),
        "warmup_calls_discarded": len(warmup),
        "seed": SEED,
        "answers_recorded": False,
        "option_cut_rule": "laya 0.3.22 common.build_sequence: 48-token cap per option; over "
        "the 192-token head budget, each option is cut to max(4, 176 // n) tokens, marker included",
        "example_at_30_options": example,
        "by_option_count": report(timed, args.resamples, cuts),
    }
    name = f"laya-{platform.system().lower()}-{kind}-{result['measured_utc'][:10]}"
    path = args.out / f"{name}.json"
    if path.exists():
        print(f"{path} exists: a measurement is never overwritten.")
        return 1
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for n, row in result["by_option_count"].items():
        lat = row["latency"] or {}
        print(f"{n:>2} options: p50 {lat.get('p50_ms')} ms, p99 {lat.get('p99_ms')} ms, "
              f"not fitting {row['not_fitting']}/{row['calls']}")  # fmt: skip
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
