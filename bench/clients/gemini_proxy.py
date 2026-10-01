"""Gemini through the author's OpenAI-compatible proxy (roadmap M11, 1 Oct 2026).

The comparison's only Gemini endpoint, at the author's direction: a private proxy at
``http://localhost:8317/v1`` set up by their engineer, serving ``gemini-3.8-flash-high``
(Gemini 3.8 Flash at the high thinking level; the proxy reports the model it ran). It is not
Google's public API: answers and token counts are Gemini's, but latency is the proxy's path.

``generate`` sends a chat completion with a JSON-schema ``response_format`` (Gemini-style
schemas are converted) and returns the same ``Generation`` as the direct client. Token counts
come from the proxy's ``usage``: ``completion_tokens`` includes the ``reasoning_tokens``, which
are reported as thinking. The key is read from ``LRR_GEMINI_PROXY_KEY``, never stored.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any, Final

import httpx

from bench.clients.gemini import GeminiError, Generation
from bench.clients.http import Timing, timed

BASE_URL: Final = "http://localhost:8317/v1"
MODEL: Final = "gemini-3.8-flash-high"


def json_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """A Gemini response schema (``OBJECT``, ``propertyOrdering``) as plain JSON Schema."""
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "type":
            out["type"] = str(value).lower()
        elif key == "propertyOrdering":
            continue
        elif key == "properties":
            out["properties"] = {k: json_schema(v) for k, v in value.items()}
        elif key == "items":
            out["items"] = json_schema(value)
        else:
            out[key] = value
    if out.get("type") == "object":
        out["additionalProperties"] = False
    return out


class GeminiProxyClient:
    """One keep-alive connection to the proxy, for one model."""

    def __init__(
        self,
        model: str = MODEL,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = 300.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("LRR_GEMINI_PROXY_KEY")
        if not key:
            raise GeminiError("LRR_GEMINI_PROXY_KEY is not set")
        self.model = model
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {key}"},
        )

    def __enter__(self) -> GeminiProxyClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self._client.close()

    def generate(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        *,
        system: str | None = None,
        temperature: float | None = None,
        thinking_budget: int | None = None,
    ) -> Generation:
        """One chat completion held to ``schema``; ``temperature`` stays the model default
        unless given."""
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "answer", "strict": True, "schema": json_schema(schema)},
            },
        }
        if temperature is not None:
            body["temperature"] = temperature
        response, timing = timed(self._client, "POST", "/chat/completions", json=body)
        if response.status_code != httpx.codes.OK:
            raise GeminiError(f"HTTP {response.status_code}: {response.text[:1200]}")
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise GeminiError(f"no candidates: {json.dumps(data)[:300]}")
        text = str((choices[0].get("message") or {}).get("content") or "")
        try:
            output = json.loads(text)
        except json.JSONDecodeError:
            output = None
        usage = data.get("usage") or {}
        completion = int(usage.get("completion_tokens", 0))
        thinking = int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0))
        return Generation(
            output=output,
            text=text,
            model_version=str(data.get("model", self.model)),
            response_id=str(data.get("id", "")),
            finish_reason=str(choices[0].get("finish_reason", "")),
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=completion - thinking,
            thinking_tokens=thinking,
            timing=timing,
        )

    def floor(self) -> Timing:
        """``GET /models``: no model runs. Here it measures the hop to the proxy only."""
        response, timing = timed(self._client, "GET", "/models")
        response.raise_for_status()
        return timing
