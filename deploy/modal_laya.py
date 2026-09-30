"""Laya on an NVIDIA T4 on Modal: speed and footprint only (roadmap M11, §4 decision 3 as amended).

The T4 is the GPU of the vendor's published figure (33-40 ms per call). The container runs
the same timing code as the Mac and the rig (``bench.clients.laya.measure``) on the same
seeded call plan, written on the Mac. It measures the model's time inside the container, so
no network time is included:

    uv run python -m bench.clients.laya --plan-out /tmp/laya-plan.json
    modal run deploy/modal_laya.py --plan /tmp/laya-plan.json                # the run
    modal run deploy/modal_laya.py --plan /tmp/laya-plan.json --smoke        # 20 calls

The image installs laya 0.3.22, transformers 5.17.0 and torch 2.14.0 (the Mac's versions;
PyPI's Linux torch is a CUDA build). It fetches the weights at the pinned revision during
the build. Laya refuses them unless every SHA-256 matches the ones recorded on the Mac. The
answers are never read. This file is imported by the local Modal CLI too, so it stays
Python 3.9-compatible at import.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import modal

ROOT = Path(__file__).resolve().parents[1]
REVISION = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
FILES = [
    "model.safetensors",
    "rl_agent_config.json",
    "encoder/config.json",
    "tokenizer/tokenizer_config.json",
    "tokenizer/tokenizer.json",
]
FETCH = (
    "from huggingface_hub import snapshot_download; "
    f"snapshot_download('convaiinnovations/laya', revision='{REVISION}', allow_patterns={FILES})"
)
SKIP = ["**/__pycache__", "**/results", "**/*.jsonl"]

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "laya==0.3.22",
        "transformers==5.17.0",
        "torch==2.14.0",
        "pydantic==2.13.5",
        "httpx==0.28.1",
    )
    .env({"HF_HOME": "/hf"})
    .run_commands(f'python -c "{FETCH}"')
    .env({"HF_HUB_OFFLINE": "1"})
    .add_local_dir(ROOT / "src" / "legal_rag_router", "/root/legal_rag_router")
    .add_local_dir(ROOT / "bench", "/root/bench", ignore=SKIP)
    .add_local_dir(ROOT / "batteries", "/root/batteries", ignore=SKIP)
)
app = modal.App("legal-rag-router-laya", image=image)


@app.function(gpu="T4", cpu=4.0, memory=8192, timeout=1800)
def measure(plan: dict[str, Any], resamples: int) -> dict[str, Any]:
    from bench.clients.laya import measure as run  # noqa: PLC0415 - exists only in the container

    return run("cuda", plan, resamples, host="modal T4 (4 cores, 8 GiB)")


@app.local_entrypoint()
def main(plan: str, smoke: bool = False, resamples: int = 1000) -> None:  # noqa: FBT001, FBT002 - Modal CLI flags
    calls = json.loads(Path(plan).read_text(encoding="utf-8"))
    if smoke:
        calls["calls"] = [c for c in calls["calls"] if c[0] == 3][:20]  # noqa: PLR2004
        calls["warmup"] = calls["warmup"][:5]
        resamples = 50
    result = measure.remote(calls, resamples)
    out = ROOT / "bench" / "results"
    date = result["measured_utc"][:10]
    name = f"laya-modal-t4{'-smoke' if smoke else ''}-{date}.json"
    path = out / name
    if path.exists():
        print(f"{path} exists: a measurement is never overwritten.")
        return
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["machine"], indent=1))
    print(json.dumps(result["footprint"], indent=1))
    for n, row in result["by_option_count"].items():
        lat = row["latency"] or {}
        print(f"{n:>2} options: p50 {lat.get('p50_ms')} ms, p99 {lat.get('p99_ms')} ms")
    print(f"-> {path}")
