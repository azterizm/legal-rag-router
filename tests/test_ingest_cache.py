"""Fetch layer (offline: every request goes to an httpx.MockTransport)."""

from __future__ import annotations

import random
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path

import httpx
import pytest

from ingest.cache import (
    Fetcher,
    FetchError,
    FetchPolicy,
    parse_retry_after,
    validate_user_agent,
)

UA = "legal-rag-router-ingest/0.1 (abdullah@memonsystems.com)"
URL = "https://www.legislation.gov.uk/ukpga/1996/18/data.xml"


class FakeTime:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make(
    tmp_path: Path,
    handler: Callable[[httpx.Request], httpx.Response],
    fake: FakeTime,
    policy: FetchPolicy | None = None,
) -> Fetcher:
    return Fetcher(
        tmp_path / "cache",
        UA,
        policy or FetchPolicy(min_interval=5.0, max_retries=3, backoff_base=1.0),
        transport=httpx.MockTransport(handler),
        clock=fake.clock,
        wall_clock=fake.clock,
        sleep=fake.sleep,
        rng=random.Random(0),
    )


@pytest.mark.parametrize(
    "agent",
    [
        "python-httpx/0.28",
        "LegalRAGScraper/1.0 (+mailto:data-team@example.com)",
        "bot (contact: yourdomain)",
    ],
)
def test_user_agent_needs_real_contact(agent: str) -> None:
    with pytest.raises(ValueError, match="real contact"):
        validate_user_agent(agent)


def test_valid_user_agents() -> None:
    assert validate_user_agent(UA) == UA
    assert validate_user_agent("bot/1 (https://memonsystems.com/bot)")


def test_fetch_caches_and_serves_from_cache(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"<xml/>", headers={"ETag": '"v1"'})

    fake = FakeTime()
    with make(tmp_path, handler, fake) as fetcher:
        first = fetcher.get(URL)
        second = fetcher.get(URL)
    assert (first.from_cache, second.from_cache) == (False, True)
    assert first.read() == second.read() == b"<xml/>"
    assert len(calls) == 1
    assert calls[0].headers["User-Agent"] == UA
    assert first.etag == '"v1"'


def test_cache_survives_a_new_fetcher(tmp_path: Path) -> None:
    fake = FakeTime()
    with make(tmp_path, lambda _: httpx.Response(200, content=b"x"), fake) as fetcher:
        fetcher.get(URL)

    def fail(_: httpx.Request) -> httpx.Response:
        raise AssertionError("network used on resume")

    with make(tmp_path, fail, fake) as fetcher:
        assert fetcher.get(URL).read() == b"x"


def test_rate_limit_spaces_requests(tmp_path: Path) -> None:
    fake = FakeTime()
    with make(tmp_path, lambda _: httpx.Response(200, content=b"x"), fake) as fetcher:
        for n in range(3):
            fetcher.get(f"{URL}?n={n}")
    assert fake.sleeps == [5.0, 5.0]


def test_conditional_get_uses_validators_and_304(tmp_path: Path) -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.headers))
        if "if-none-match" in request.headers:
            return httpx.Response(304)
        return httpx.Response(
            200,
            content=b"body",
            headers={"ETag": '"v1"', "Last-Modified": "Mon, 01 Sep 2026 00:00:00 GMT"},
        )

    fake = FakeTime()
    with make(tmp_path, handler, fake) as fetcher:
        fetcher.get(URL)
        again = fetcher.get(URL, revalidate=True)
    assert again.from_cache
    assert again.read() == b"body"
    assert seen[1]["if-none-match"] == '"v1"'
    assert seen[1]["if-modified-since"] == "Mon, 01 Sep 2026 00:00:00 GMT"


def test_retry_after_is_honoured_and_slows_the_run(tmp_path: Path) -> None:
    fake = FakeTime()
    starts: list[float] = []
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "30"}),
            httpx.Response(200, content=b"ok"),
            httpx.Response(200, content=b"next"),
        ]
    )

    def handler(_: httpx.Request) -> httpx.Response:
        starts.append(fake.now)
        return next(responses)

    with make(tmp_path, handler, fake) as fetcher:
        assert fetcher.get(URL).read() == b"ok"
        assert fetcher.get(URL + "?next").read() == b"next"
    gaps = [b - a for a, b in pairwise(starts)]
    assert gaps == [30.0, 30.0]  # waited as asked, and kept the slower pace afterwards


def test_exponential_backoff_then_give_up(tmp_path: Path) -> None:
    fake = FakeTime()
    starts: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        starts.append(fake.now)
        return httpx.Response(503)

    policy = FetchPolicy(min_interval=5.0, max_retries=3, backoff_base=10.0)
    with (
        make(tmp_path, handler, fake, policy) as fetcher,
        pytest.raises(FetchError, match="giving up after 4 attempts"),
    ):
        fetcher.get(URL)
    gaps = [b - a for a, b in pairwise(starts)]
    assert len(starts) == 4
    assert all(g >= 10.0 for g in gaps)
    assert gaps[0] < gaps[1] < gaps[2]


def test_backoff_never_undercuts_the_interval(tmp_path: Path) -> None:
    fake = FakeTime()
    starts: list[float] = []
    responses = iter([httpx.Response(503), httpx.Response(200, content=b"ok")])

    def handler(_: httpx.Request) -> httpx.Response:
        starts.append(fake.now)
        return next(responses)

    with make(tmp_path, handler, fake) as fetcher:  # backoff_base 1 s < 5 s interval
        fetcher.get(URL)
    assert starts[1] - starts[0] == pytest.approx(5.0)


def test_transport_errors_are_retried(tmp_path: Path) -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, content=b"ok")

    fake = FakeTime()
    with make(tmp_path, handler, fake) as fetcher:
        assert fetcher.get(URL).read() == b"ok"
    assert attempts["n"] == 3


def test_404_is_cached_without_body(tmp_path: Path) -> None:
    fake = FakeTime()
    with make(tmp_path, lambda _: httpx.Response(404), fake) as fetcher:
        result = fetcher.get(URL)
        assert (result.status, result.read()) == (404, b"")
        assert fetcher.get(URL).from_cache


def test_unexpected_status_raises(tmp_path: Path) -> None:
    fake = FakeTime()
    with (
        make(tmp_path, lambda _: httpx.Response(403), fake) as fetcher,
        pytest.raises(FetchError, match="unexpected HTTP 403"),
    ):
        fetcher.get(URL)


def test_body_size_cap(tmp_path: Path) -> None:
    fake = FakeTime()
    policy = FetchPolicy(min_interval=0, max_body_bytes=10)
    with (
        make(tmp_path, lambda _: httpx.Response(200, content=b"x" * 11), fake, policy) as fetcher,
        pytest.raises(FetchError, match="exceeds"),
    ):
        fetcher.get(URL)
    assert not list((tmp_path / "cache" / "blobs").rglob("*.tmp"))


def test_identical_bodies_share_one_blob(tmp_path: Path) -> None:
    fake = FakeTime()
    with make(tmp_path, lambda _: httpx.Response(200, content=b"same"), fake) as fetcher:
        a = fetcher.get(URL)
        b = fetcher.get(URL + "?other")
    assert a.body_path == b.body_path
    assert len(list((tmp_path / "cache" / "blobs").rglob("*.gz"))) == 1


def test_missing_blob_forces_refetch(tmp_path: Path) -> None:
    fake = FakeTime()
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, content=b"x")

    with make(tmp_path, handler, fake) as fetcher:
        first = fetcher.get(URL)
        assert first.body_path is not None
        first.body_path.unlink()
        fetcher.get(URL)
    assert calls["n"] == 2


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("120", 120.0),
        (" 5 ", 5.0),
        ("Thu, 01 Jan 1970 00:17:40 GMT", 60.0),  # 1060 s epoch, "now" is 1000
        ("garbage", None),
        (None, None),
        ("", None),
    ],
)
def test_parse_retry_after(value: str | None, expected: float | None) -> None:
    assert parse_retry_after(value, now=1000.0) == expected
