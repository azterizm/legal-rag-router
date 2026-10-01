"""Jev on OpenRouter's Decisions API (roadmap M11, System 1B).

Ported from ``jev-vs-sovereign-benchmark/src/clients/jev_client.py``: the same endpoint,
model, payload (``model``, ``state``, ``questions``) and headers, with the key read from
``OPENROUTER_API_KEY``. Changes from the original:

- the call is timed by ``bench.clients.http.timed`` (round trip, time to first byte,
  reconnects) like every other system in the comparison, over one keep-alive client;
- ``floor()`` times a request that runs no model on the same host and connection
  (``GET /api/v1/key``), for Row A's network floor;
- ``upstream_latency()`` reads OpenRouter's own provider timing for one generation,
  synchronously (the original batched it with asyncio);
- answers stay plain dicts, so nothing the API returns is dropped by a schema.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

import httpx

from bench.clients.http import Timing, timed

ORIGIN: Final = "https://openrouter.ai"
DECISIONS: Final = "/api/alpha/decisions"
FLOOR: Final = "/api/v1/key"
MODEL: Final = "typesafe/jev-1.13"
SITE_URL: Final = "https://memonsystems.com"
SITE_NAME: Final = "Sovereign Legal AI Benchmark"


class JevError(RuntimeError):
    """The Decisions API answered with something other than a decision."""


@dataclass(frozen=True, slots=True)
class Decision:
    id: str
    model: str
    answers: dict[str, dict[str, Any]]
    input_tokens: int
    output_tokens: int
    cost: float
    timing: Timing


class JevClient:
    """One keep-alive connection to OpenRouter; ``decide`` is one Decisions API call."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = MODEL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise JevError("OPENROUTER_API_KEY is not set")
        self.model = model
        self._client = httpx.Client(
            base_url=ORIGIN,
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": SITE_URL,
                "X-Title": SITE_NAME,
            },
        )

    def __enter__(self) -> JevClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self._client.close()

    def decide(self, state: str, questions: Mapping[str, Mapping[str, Any]]) -> Decision:
        payload = {"model": self.model, "state": state, "questions": dict(questions)}
        response, timing = timed(self._client, "POST", DECISIONS, json=payload)
        if response.status_code != httpx.codes.OK:
            raise JevError(f"HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        usage = data.get("usage") or {}
        return Decision(
            id=str(data.get("id", "")),
            model=str(data.get("model", self.model)),
            answers={k: dict(v) for k, v in (data.get("answers") or {}).items()},
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            cost=float(usage.get("cost", 0.0)),
            timing=timing,
        )

    def floor(self) -> Timing:
        """A request that runs no model, to the same host over the same connection."""
        response, timing = timed(self._client, "GET", FLOOR)
        response.raise_for_status()
        return timing

    def upstream_latency(self, generation_id: str) -> float | None:
        """OpenRouter's provider latency for one call, in ms, where it reports one."""
        response = self._client.get("/api/v1/generation", params={"id": generation_id})
        if response.status_code != httpx.codes.OK:
            return None
        providers = (response.json().get("data") or {}).get("provider_responses") or []
        latency = providers[0].get("latency") if providers else None
        return float(latency) if latency is not None else None
