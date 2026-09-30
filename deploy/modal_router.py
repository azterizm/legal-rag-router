"""The router as a small HTTP service on Modal (roadmap M11, Row B).

Row B asks "if both are services, which is faster?": the router is called over the network
like Gemini and Jev, from the same client. This file deploys it as one warm CPU container:

    modal deploy deploy/modal_router.py      # deploy; nothing is billed until it is called
    modal app stop legal-rag-router          # take it down when the runs are done

One ASGI app with three routes on one host, so a single keep-alive connection serves all:

- ``POST /route``: ``{"query": ...}`` -> status, coordinates and the in-process ``compute_ns``;
- ``POST /floor``: the same request shape, no routing: the network floor of Row A;
- ``GET /machine``: what the container runs on, for the disclosure.

Every route needs Modal proxy auth (``Modal-Key`` / ``Modal-Secret`` headers), so strangers are
turned away at Modal's edge without waking a container. One container at most, one physical
core, 1 GiB; it scales to zero five minutes after the last call.

The index and the package source are copied into the image, so the image pins their bytes.
This file is imported by the local Modal CLI too, so it stays Python 3.9-compatible at import.
"""

from __future__ import annotations

import os
import platform
import time
from pathlib import Path
from typing import Any

import modal

ROOT = Path(__file__).resolve().parents[1]
INDEX = "/index"
FASTAPI = "fastapi==0.115.12"
"""Pinned: the only package in the image; the router itself has no dependencies."""

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(FASTAPI)
    .add_local_dir(ROOT / "data" / "index", INDEX, copy=True)
    .add_local_dir(ROOT / "src" / "legal_rag_router", "/root/legal_rag_router", copy=True)
)
app = modal.App("legal-rag-router", image=image)


CPU_FIELDS = ("model name", "vendor_id", "cpu family", "model", "stepping", "cpu MHz")


def _cpu() -> dict[str, Any]:
    """The first processor's identifying fields, as far as the gVisor sandbox shows them."""
    fields: dict[str, Any] = {}
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if not line.strip():
                break
            key, _, value = line.partition(":")
            if key.strip() in CPU_FIELDS:
                fields[key.strip()] = value.strip()
    except OSError:
        pass
    fields["usable_cpus"] = len(os.sched_getaffinity(0))
    fields["host_cpu_count"] = os.cpu_count()
    return fields


REGION = "us-east"
"""Pinned (Modal bills a pinned narrow region at 1.75x). Unpinned, Modal moved the container
between AWS us-east and GCP us-central from one start to the next. The client is in Pakistan,
which has no Modal region; the region is the candidate with the lowest measured network floor
from the client (roadmap M11)."""


@app.cls(cpu=1.0, memory=1024, max_containers=1, scaledown_window=300, timeout=600, region=REGION)
class RouterService:
    @modal.enter()
    def load(self) -> None:
        from legal_rag_router import Router  # noqa: PLC0415 - exists only in the container

        self.router = Router.from_path(Path(INDEX))
        self.router.route("Employment Rights Act 1996 s.94")  # first-touch the index pages
        self.started = time.time()

    @modal.asgi_app(requires_proxy_auth=True)
    def web(self) -> Any:
        from fastapi import FastAPI  # noqa: PLC0415 - exists only in the container

        api = FastAPI()
        router = self.router

        @api.post("/route")
        def route(body: dict[str, str]) -> dict[str, Any]:
            start = time.perf_counter_ns()
            result = router.route(body["query"])
            compute_ns = time.perf_counter_ns() - start
            return {
                "status": result.status.value,
                "coordinates": [str(c) for c in result.coordinates],
                "compute_ns": compute_ns,
            }

        @api.post("/floor")
        def floor(body: dict[str, str]) -> dict[str, Any]:
            return {"status": None, "coordinates": [], "compute_ns": 0}

        @api.get("/machine")
        def machine() -> dict[str, Any]:
            return {
                "cpu": _cpu(),
                "requested_cores": 1.0,
                "python": platform.python_version(),
                "platform": platform.platform(),
                "index_snapshot": router.index.snapshot,
                "pinned_region": REGION,
                "modal_region": os.environ.get("MODAL_REGION"),
                "modal_cloud_provider": os.environ.get("MODAL_CLOUD_PROVIDER"),
                "container_uptime_s": round(time.time() - self.started),
            }

        return api
