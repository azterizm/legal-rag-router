"""The Jev and Gemini clients (roadmap M11), against mock servers: no call leaves the machine."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from bench.clients.gemini import GeminiClient, GeminiError
from bench.clients.jev import JevClient, JevError


def _jev_server(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/api/v1/key":
            return httpx.Response(200, json={"data": {}})
        if request.url.path == "/api/v1/generation":
            latency = 381.0 if request.url.params["id"] == "gen-1" else None
            return httpx.Response(
                200, json={"data": {"provider_responses": [{"latency": latency}]}}
            )
        body = json.loads(request.content)
        if body["state"] == "fail":
            return httpx.Response(402, text="payment required")
        return httpx.Response(
            200,
            json={
                "id": "gen-1",
                "model": "typesafe/jev-1.13-20260917",
                "answers": {"instrument": {"type": "choice", "choice": "option_0"}},
                "usage": {"input_tokens": 453, "output_tokens": 0, "cost": 0.000019},
            },
        )

    return httpx.MockTransport(handle)


def test_jev_sends_the_original_payload_and_headers() -> None:
    seen: list[httpx.Request] = []
    questions = {"instrument": {"type": "choice", "instructions": "Which?", "criteria": {"a": "A"}}}
    with JevClient("sk-test", transport=_jev_server(seen)) as jev:
        decision = jev.decide("ERA 1996 s.124", questions)
        floor = jev.floor()
        assert jev.upstream_latency("gen-1") == 381.0
        assert jev.upstream_latency("gen-2") is None
    sent = seen[0]
    assert sent.url == "https://openrouter.ai/api/alpha/decisions"
    assert sent.headers["Authorization"] == "Bearer sk-test"
    assert sent.headers["HTTP-Referer"] == "https://memonsystems.com"
    assert json.loads(sent.content) == {
        "model": "typesafe/jev-1.13",
        "state": "ERA 1996 s.124",
        "questions": questions,
    }
    assert decision.model == "typesafe/jev-1.13-20260917"
    assert decision.answers["instrument"]["choice"] == "option_0"
    assert (decision.input_tokens, decision.cost) == (453, 0.000019)
    assert decision.timing.total_ns > 0
    assert floor.total_ns > 0


def test_jev_refuses_without_a_key_and_reports_api_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(JevError, match="OPENROUTER_API_KEY"):
        JevClient()
    with (
        JevClient("sk-test", transport=_jev_server([])) as jev,
        pytest.raises(JevError, match="HTTP 402"),
    ):
        jev.decide("fail", {})


def _gemini_server(seen: list[httpx.Request], reply: dict[str, Any]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"name": "models/gemini-flash"})
        return httpx.Response(200, json=reply)

    return httpx.MockTransport(handle)


def test_gemini_asks_for_schema_json_and_parses_it() -> None:
    seen: list[httpx.Request] = []
    reply = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "plan", "thought": True}, {"text": '{"citations": []}'}]
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 120,
            "candidatesTokenCount": 8,
            "thoughtsTokenCount": 30,
        },
        "modelVersion": "gemini-flash-001",
        "responseId": "r-1",
    }
    schema = {"type": "OBJECT", "properties": {"citations": {"type": "ARRAY"}}}
    with GeminiClient("gemini-flash", "key-test", transport=_gemini_server(seen, reply)) as gemini:
        out = gemini.generate("ERA 1996 s.124", schema, system="Extract.", thinking_budget=0)
        gemini.floor()
    sent = seen[0]
    assert sent.url.path == "/v1beta/models/gemini-flash:generateContent"
    assert sent.headers["x-goog-api-key"] == "key-test"
    body = json.loads(sent.content)
    assert body["generationConfig"] == {
        "temperature": 0.0,
        "responseMimeType": "application/json",
        "responseSchema": schema,
        "thinkingConfig": {"thinkingBudget": 0},
    }
    assert body["systemInstruction"] == {"parts": [{"text": "Extract."}]}
    assert out.output == {"citations": []}  # the thought part is not part of the answer
    assert (out.prompt_tokens, out.output_tokens, out.thinking_tokens) == (120, 8, 30)
    assert (out.model_version, out.response_id, out.finish_reason) == (
        "gemini-flash-001",
        "r-1",
        "STOP",
    )
    assert seen[1].url.path == "/v1beta/models/gemini-flash"


def test_gemini_keeps_bad_json_as_text_and_reports_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(GeminiError, match="GEMINI_API_KEY"):
        GeminiClient("m")
    reply = {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
    with GeminiClient("m", "k", transport=_gemini_server([], reply)) as gemini:
        out = gemini.generate("q", {})
        assert out.output is None
        assert out.text == "not json"
    with (
        GeminiClient("m", "k", transport=_gemini_server([], {"candidates": []})) as gemini,
        pytest.raises(GeminiError, match="no candidates"),
    ):
        gemini.generate("q", {})

    def refuse(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="quota")

    with (
        GeminiClient("m", "k", transport=httpx.MockTransport(refuse)) as gemini,
        pytest.raises(GeminiError, match="HTTP 429"),
    ):
        gemini.generate("q", {})


def test_the_proxy_client_sends_a_json_schema_and_reads_openai_usage() -> None:
    from bench.clients.gemini_proxy import GeminiProxyClient, json_schema  # noqa: PLC0415

    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(
            200,
            json={
                "id": "v_1",
                "model": "gemini-3.8-flash-n",
                "choices": [
                    {"message": {"content": '{"outcome": "BOUND"}'}, "finish_reason": "stop"}
                ],
                "usage": {
                    "prompt_tokens": 18,
                    "completion_tokens": 874,
                    "completion_tokens_details": {"reasoning_tokens": 851},
                },
            },
        )

    schema = {
        "type": "OBJECT",
        "properties": {
            "outcome": {"type": "STRING", "enum": ["BOUND"]},
            "list": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
        "required": ["outcome"],
        "propertyOrdering": ["outcome"],
    }
    assert json_schema(schema) == {
        "type": "object",
        "properties": {
            "outcome": {"type": "string", "enum": ["BOUND"]},
            "list": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["outcome"],
        "additionalProperties": False,
    }
    with GeminiProxyClient(api_key="k", transport=httpx.MockTransport(handle)) as gemini:
        out = gemini.generate("q", schema, system="Extract.")
        gemini.floor()
    body = json.loads(seen[0].content)
    assert seen[0].url == "http://localhost:8317/v1/chat/completions"
    assert seen[0].headers["Authorization"] == "Bearer k"
    assert body["model"] == "gemini-3.8-flash-high"
    assert body["messages"][0] == {"role": "system", "content": "Extract."}
    assert "temperature" not in body  # the model's default
    assert body["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert out.output == {"outcome": "BOUND"}
    assert (out.prompt_tokens, out.output_tokens, out.thinking_tokens) == (18, 23, 851)
    assert out.model_version == "gemini-3.8-flash-n"


def test_the_proxy_client_needs_its_key_and_reports_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from bench.clients.gemini_proxy import GeminiProxyClient  # noqa: PLC0415

    monkeypatch.delenv("LRR_GEMINI_PROXY_KEY", raising=False)
    with pytest.raises(GeminiError, match="LRR_GEMINI_PROXY_KEY"):
        GeminiProxyClient()

    def reply(status: int, payload: dict[str, Any]) -> httpx.MockTransport:
        return httpx.MockTransport(lambda _r: httpx.Response(status, json=payload))

    with (
        GeminiProxyClient(api_key="k", transport=reply(429, {"error": "busy"})) as g,
        pytest.raises(GeminiError, match="HTTP 429"),
    ):
        g.generate("q", {}, temperature=0.5)
    with (
        GeminiProxyClient(api_key="k", transport=reply(200, {"choices": []})) as g,
        pytest.raises(GeminiError, match="no candidates"),
    ):
        g.generate("q", {})
    with GeminiProxyClient(
        api_key="k", transport=reply(200, {"choices": [{"message": {"content": "x"}}]})
    ) as g:
        assert g.generate("q", {}).output is None
