"""Polite, resumable HTTP fetch layer with a content-addressed disk cache.

Every network read made by ingest goes through :class:`Fetcher`, which enforces the
source's fair-use terms (roadmap U7) rather than leaving them to each caller:

* **Identification:** a User-Agent with contact details is mandatory; placeholder
  contacts (``example.com`` …) are rejected.
* **Rate:** at most one request per ``min_interval`` seconds (default 5 s, the
  legislation.gov.uk ``Crawl-delay``), process-wide for this fetcher.
* **Back-off:** 429 and 5xx responses and transport errors are retried with exponential
  back-off and jitter; ``Retry-After`` (seconds or HTTP date) is honoured and raises the
  interval for the rest of the run.
* **Resumable and idempotent:** responses are cached on disk, keyed by URL; bodies are
  stored once per content hash. A re-run serves from the cache; ``revalidate=True`` sends
  a conditional GET (``If-None-Match`` / ``If-Modified-Since``).
* **Bounded:** bodies are streamed to disk with a size cap, never held twice in memory.

Cache layout under ``cache_dir``::

    meta/{aa}/{sha256(url)}.json     status, validators, body hash, fetch time
    blobs/{bb}/{sha256(body)}.gz     response body, gzip-compressed

The cache is build-machine state (``.cache/``): git-ignored, never published.
"""

from __future__ import annotations

import email.utils
import gzip
import hashlib
import json
import logging
import os
import random
import re
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import httpx

__all__ = ["FetchError", "FetchPolicy", "FetchResult", "Fetcher"]

log = logging.getLogger("ingest.cache")

_RETRY_STATUSES: Final = frozenset({429, 500, 502, 503, 504})
_CACHEABLE_STATUSES: Final = frozenset({200, 404, 410})
_CONTACT: Final = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|https?://\S+")
_PLACEHOLDER: Final = re.compile(r"example\.(com|org|net)|localhost|your(domain|email)", re.I)


class FetchError(RuntimeError):
    """Raised when a URL cannot be fetched after all retries."""


@dataclass(frozen=True, slots=True)
class FetchPolicy:
    min_interval: float = 5.0
    """Seconds between request starts. legislation.gov.uk robots.txt: Crawl-delay 5."""
    max_retries: int = 6
    backoff_base: float = 5.0
    backoff_max: float = 600.0
    timeout: float = 120.0
    max_body_bytes: int = 1 << 30


@dataclass(frozen=True, slots=True)
class FetchResult:
    url: str
    status: int
    body_path: Path | None
    from_cache: bool
    fetched_at: str
    etag: str | None = None
    last_modified: str | None = None

    def read(self) -> bytes:
        """The response body (empty for bodiless statuses)."""
        if self.body_path is None:
            return b""
        return gzip.decompress(self.body_path.read_bytes())


def _sha(text: str | bytes) -> str:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()


def validate_user_agent(user_agent: str) -> str:
    """Return ``user_agent`` if it identifies the client with real contact details."""
    if not _CONTACT.search(user_agent) or _PLACEHOLDER.search(user_agent):
        raise ValueError(
            "User-Agent must identify the client with a real contact e-mail or URL, "
            'e.g. "legal-rag-router-ingest/0.1 (you@yourcompany.com)"'
        )
    return user_agent


def parse_retry_after(value: str | None, *, now: float) -> float | None:
    """Seconds to wait from a ``Retry-After`` header (delta-seconds or HTTP date)."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - now)


class Fetcher:
    """Rate-limited, retrying, caching HTTP GET. Not thread-safe; use one per process."""

    def __init__(
        self,
        cache_dir: Path,
        user_agent: str,
        policy: FetchPolicy | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
    ) -> None:
        self.cache_dir = cache_dir
        self.policy = policy or FetchPolicy()
        self._interval = self.policy.min_interval
        self._clock, self._wall, self._sleep = clock, wall_clock, sleep
        self._rng = rng or random.Random()  # noqa: S311 - jitter, not security
        self._last_start: float | None = None
        self.requests_made = 0
        self._client = httpx.Client(
            headers={"User-Agent": validate_user_agent(user_agent), "Accept-Encoding": "gzip"},
            timeout=self.policy.timeout,
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------ public

    def get(self, url: str, *, revalidate: bool = False) -> FetchResult:
        """Fetch ``url``, from the cache when possible.

        Raises:
            FetchError: when the request keeps failing or the body exceeds the size cap.
        """
        meta = self._load_meta(url)
        if meta is not None and not revalidate:
            return self._result(meta, from_cache=True)
        headers: dict[str, str] = {}
        if meta is not None:
            if meta.get("etag"):
                headers["If-None-Match"] = str(meta["etag"])
            if meta.get("last_modified"):
                headers["If-Modified-Since"] = str(meta["last_modified"])
        return self._fetch(url, headers, meta)

    # ------------------------------------------------------------------ internals

    def _throttle(self) -> None:
        now = self._clock()
        if self._last_start is not None:
            wait = self._last_start + self._interval - now
            if wait > 0:
                self._sleep(wait)
                now = self._clock()
        self._last_start = now

    def _fetch(
        self, url: str, headers: dict[str, str], meta: dict[str, object] | None
    ) -> FetchResult:
        last_error = "no attempt made"
        for attempt in range(self.policy.max_retries + 1):
            self._throttle()
            self.requests_made += 1
            try:
                with self._client.stream("GET", url, headers=headers) as response:
                    if response.status_code == 304 and meta is not None:  # noqa: PLR2004
                        return self._result(meta, from_cache=True)
                    if response.status_code in _RETRY_STATUSES:
                        last_error = f"HTTP {response.status_code}"
                        self._back_off(attempt, response.headers.get("Retry-After"), url)
                        continue
                    return self._store(url, response)
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                self._back_off(attempt, None, url)
        raise FetchError(
            f"{url}: giving up after {self.policy.max_retries + 1} attempts ({last_error})"
        )

    def _back_off(self, attempt: int, retry_after: str | None, url: str) -> None:
        if attempt >= self.policy.max_retries:
            return
        hinted = parse_retry_after(retry_after, now=self._wall())
        if hinted is not None:
            # The server asked us to slow down: honour it now and for the rest of the run.
            self._interval = max(self._interval, min(hinted, self.policy.backoff_max))
            delay = min(hinted, self.policy.backoff_max)
        else:
            delay = min(self.policy.backoff_max, self.policy.backoff_base * 2**attempt)
            delay += self._rng.uniform(0, delay / 4)
        log.warning("retrying %s in %.1fs (attempt %d)", url, delay, attempt + 1)
        self._sleep(delay)

    def _store(self, url: str, response: httpx.Response) -> FetchResult:
        status = response.status_code
        if status not in _CACHEABLE_STATUSES:
            raise FetchError(f"{url}: unexpected HTTP {status}")
        body_sha: str | None = None
        if status == 200:  # noqa: PLR2004
            body_sha = self._write_blob(url, response)
        meta: dict[str, object] = {
            "url": url,
            "status": status,
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "body_sha256": body_sha,
            "fetched_at": datetime.fromtimestamp(self._wall(), tz=UTC).isoformat(),
        }
        self._atomic_write(self._meta_path(url), json.dumps(meta, sort_keys=True).encode())
        return self._result(meta, from_cache=False)

    def _write_blob(self, url: str, response: httpx.Response) -> str:
        blob_dir = self.cache_dir / "blobs"
        blob_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=blob_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
                sha = self._copy_capped(url, response, gz)
            target = self._blob_path(sha)
            target.parent.mkdir(parents=True, exist_ok=True)
            Path(tmp).replace(target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return sha

    def _copy_capped(self, url: str, response: httpx.Response, sink: gzip.GzipFile) -> str:
        """Stream the body into ``sink`` under the size cap; return its SHA-256."""
        digest = hashlib.sha256()
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > self.policy.max_body_bytes:
                raise FetchError(f"{url}: body exceeds {self.policy.max_body_bytes} bytes")
            digest.update(chunk)
            sink.write(chunk)
        return digest.hexdigest()

    def _result(self, meta: dict[str, object], *, from_cache: bool) -> FetchResult:
        body_sha = meta.get("body_sha256")
        return FetchResult(
            url=str(meta["url"]),
            status=int(str(meta["status"])),
            body_path=self._blob_path(str(body_sha)) if body_sha else None,
            from_cache=from_cache,
            fetched_at=str(meta["fetched_at"]),
            etag=str(meta["etag"]) if meta.get("etag") else None,
            last_modified=str(meta["last_modified"]) if meta.get("last_modified") else None,
        )

    def _meta_path(self, url: str) -> Path:
        key = _sha(url)
        return self.cache_dir / "meta" / key[:2] / f"{key}.json"

    def _blob_path(self, sha: str) -> Path:
        return self.cache_dir / "blobs" / sha[:2] / f"{sha}.gz"

    def _load_meta(self, url: str) -> dict[str, object] | None:
        path = self._meta_path(url)
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(meta, dict):
            return None
        body_sha = meta.get("body_sha256")
        if body_sha and not self._blob_path(str(body_sha)).exists():
            return None  # body evicted or incomplete: refetch
        return meta

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            Path(tmp).replace(path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
