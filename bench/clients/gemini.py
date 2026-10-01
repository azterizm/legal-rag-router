"""Gemini Flash with structured output (roadmap M11, System 1A).

Plain REST on ``generativelanguage.googleapis.com`` (no SDK), with the key read from
``GEMINI_API_KEY`` and sent in the ``x-goog-api-key`` header. ``generate`` asks for JSON
matching a response schema at a fixed temperature and returns the parsed object, the token
counts Google reports, the resolved model version and the timing. ``floor()`` times
``GET models/{model}``, which runs no model, on the same host and connection (Row A). The
model id is pinned by the caller and recorded with every result.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

import httpx

from bench.clients.http import Timing, timed

ORIGIN: Final = "https://generativelanguage.googleapis.com"
API: Final = "/v1beta"


class GeminiError(RuntimeError):
    """The API answered without a usable structured response."""


@dataclass(frozen=True, slots=True)
class Generation:
    output: Any
    """The parsed JSON, or ``None`` if the model's text was not valid JSON."""
    text: str
    model_version: str
    response_id: str
    finish_reason: str
    prompt_tokens: int
    output_tokens: int
    thinking_tokens: int
    timing: Timing


class GeminiClient:
    """One keep-alive connection to the Gemini API for one pinned model."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        *,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
        if not key:
            raise GeminiError("GEMINI_API_KEY is not set")
        self.model = model
        self._client = httpx.Client(
            base_url=ORIGIN, timeout=timeout, transport=transport, headers={"x-goog-api-key": key}
        )

    def __enter__(self) -> GeminiClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self._client.close()

    def generate(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        *,
        system: str | None = None,
        temperature: float = 0.0,
        thinking_budget: int | None = None,
    ) -> Generation:
        config: dict[str, Any] = {
            "temperature": temperature,
            "responseMimeType": "application/json",
            "responseSchema": dict(schema),
        }
        if thinking_budget is not None:
            config["thinkingConfig"] = {"thinkingBudget": thinking_budget}
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": config,
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        url = f"{API}/models/{self.model}:generateContent"
        response, timing = timed(self._client, "POST", url, json=body)
        if response.status_code != httpx.codes.OK:
            raise GeminiError(f"HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise GeminiError(f"no candidates: {json.dumps(data)[:300]}")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(str(p.get("text", "")) for p in parts if not p.get("thought"))
        try:
            output = json.loads(text)
        except json.JSONDecodeError:
            output = None
        usage = data.get("usageMetadata") or {}
        return Generation(
            output=output,
            text=text,
            model_version=str(data.get("modelVersion", self.model)),
            response_id=str(data.get("responseId", "")),
            finish_reason=str(candidates[0].get("finishReason", "")),
            prompt_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
            thinking_tokens=int(usage.get("thoughtsTokenCount", 0)),
            timing=timing,
        )

    def floor(self) -> Timing:
        """``GET models/{model}``: no model runs, same host, same connection."""
        response, timing = timed(self._client, "GET", f"{API}/models/{self.model}")
        response.raise_for_status()
        return timing
