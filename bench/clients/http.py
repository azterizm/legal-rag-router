"""One timed HTTP request, split by httpx's trace hooks (roadmap M11).

Every client in the comparison times its calls the same way: the round trip with
``perf_counter_ns``, the time to first byte from the trace events, and whether the call had
to open a connection (the harness keeps connections warm, so a reconnect is worth knowing).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class Timing:
    total_ns: int
    ttfb_ns: int | None
    connected: bool


def timed(
    client: httpx.Client, method: str, url: str, **kwargs: Any
) -> tuple[httpx.Response, Timing]:
    events: dict[str, int] = {}

    def trace(name: str, _info: dict[str, Any]) -> None:
        events[name] = time.perf_counter_ns()

    start = time.perf_counter_ns()
    response = client.request(method, url, extensions={"trace": trace}, **kwargs)
    total = time.perf_counter_ns() - start
    sent = events.get("http11.send_request_headers.started")
    first_byte = events.get("http11.receive_response_headers.complete")
    return response, Timing(
        total_ns=total,
        ttfb_ns=first_byte - sent if sent is not None and first_byte is not None else None,
        connected="connection.connect_tcp.complete" in events,
    )
