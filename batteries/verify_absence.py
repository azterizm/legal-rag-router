"""Confirm invented instruments with the source's own search (plan step 8, ``invented``).

You run this: it fetches from legislation.gov.uk under your contact details, through the
repo's fetch layer (one request per 5 s, cached, resumable). About one request per row.

    uv run python -m batteries.verify_absence --contact you@example.org [--dry-run]

For each row whose ``absence_verified_via.searched`` is empty it reads the search as an
Atom feed (``/all/data.feed?title=…&year=…``). The site matches titles by containment, so
a result only counts when its title has the invented title's exact key. A number-cited row
(``https://www.legislation.gov.uk/uksi/2011/9999``) is absent when the source answers 400,
404 or 410. Absent rows get the response's date in ``searched`` and are saved at once;
anything found is reported and left empty. ``--from-cache`` confirms from responses already
fetched, without any request (and without a contact).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from defusedxml import ElementTree

from batteries.schema import BATTERY_DIR, BatteryRow, read_battery, write_battery
from ingest.build_index import title_variants
from ingest.cache import Fetcher, FetchError, FetchPolicy, FetchResult, read_cached

log = logging.getLogger("batteries.verify_absence")
_ATOM = "{http://www.w3.org/2005/Atom}"


def feed_url(search_url: str) -> str:
    """The Atom form of a legislation.gov.uk search URL."""
    return search_url.replace("/all?", "/all/data.feed?", 1)


def found_titles(feed: bytes) -> list[str]:
    root = ElementTree.fromstring(feed)
    if root.tag != f"{_ATOM}feed":
        raise ValueError(f"not an Atom feed: <{root.tag}>")
    return [(entry.findtext(f"{_ATOM}title") or "").strip() for entry in root.iter(f"{_ATOM}entry")]


def same_title(search_url: str, titles: list[str]) -> list[str]:
    """The results whose title is the searched one (by the index's own full-title key)."""
    query = parse_qs(urlsplit(search_url).query)
    wanted = title_variants(f"{query['title'][0]} {query['year'][0]}")[0]
    return [t for t in titles if title_variants(t)[:1] == (wanted,)]


Get = Callable[[str], FetchResult | None]
"""``Fetcher.get``, or a cache-only lookup that answers ``None`` for an uncached URL."""


def verify(get: Get, row: BatteryRow) -> tuple[bool | None, str, date | None]:
    """(absent?, what was seen, when) for one invented row; ``None`` when nothing is cached.

    A number-cited row is absent when the source answers 404 or 410, or 400: legislation.gov.uk
    rejects an SI number it has no record of (seen for ``uksi/2011/9999``, 29 Sept 2026).
    """
    check = row.absence_verified_via
    if check is None:
        raise ValueError(f"{row.id} has no absence check")
    by_number = "/all?" not in check.search_url
    try:
        result = get(check.search_url if by_number else feed_url(check.search_url))
    except FetchError as exc:
        if by_number and exc.status == 400:  # noqa: PLR2004
            return True, "HTTP 400", datetime.now(UTC).date()
        raise
    if result is None:
        return None, "not cached", None
    when = datetime.fromisoformat(result.fetched_at).date()
    if by_number:
        return result.status in {404, 410}, f"HTTP {result.status}", when
    if result.status != 200:  # noqa: PLR2004
        return False, f"HTTP {result.status}", when
    titles = found_titles(result.read())
    matches = same_title(check.search_url, titles)
    return not matches, f"{len(titles)} result(s); same title: {matches or 'none'}", when


def _confirm(get: Get, battery: Path, rows: list[BatteryRow]) -> tuple[int, int]:
    """Check every unconfirmed row, saving after each one; (confirmed, found)."""
    confirmed = found = 0
    for i, row in enumerate(rows):
        check = row.absence_verified_via
        if check is None or check.searched is not None:
            continue
        absent, seen, when = verify(get, row)
        log.info(
            "%s %s: %s", row.id, {True: "absent", False: "FOUND", None: "skipped"}[absent], seen
        )
        if absent:
            dated = check.model_copy(update={"searched": when})
            rows[i] = row.model_copy(update={"absence_verified_via": dated})
            write_battery(battery, rows)
            confirmed += 1
        elif absent is False:
            found += 1
    return confirmed, found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--battery", type=Path, default=BATTERY_DIR / "uk" / "invented.jsonl")
    parser.add_argument("--contact", help="your e-mail or URL for the User-Agent")
    parser.add_argument("--cache", type=Path, default=Path(".cache/http"))
    parser.add_argument("--dry-run", action="store_true", help="list the URLs; fetch nothing")
    parser.add_argument(
        "--from-cache", action="store_true", help="confirm from cached responses only; no request"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rows = read_battery(args.battery)
    todo = [r for r in rows if r.absence_verified_via and r.absence_verified_via.searched is None]
    if args.dry_run or not todo:
        for row in todo:
            url = row.absence_verified_via.search_url  # type: ignore[union-attr]
            print(row.id, feed_url(url))
        print(f"{len(todo)} row(s) to confirm")
        return 0
    if args.from_cache:
        confirmed, found = _confirm(lambda url: read_cached(args.cache, url), args.battery, rows)
    else:
        if not args.contact:
            parser.error("--contact is required to fetch (or use --from-cache)")
        user_agent = f"legal-rag-router-batteries/0.1 ({args.contact})"
        with Fetcher(args.cache, user_agent, FetchPolicy()) as fetcher:
            confirmed, found = _confirm(fetcher.get, args.battery, rows)
    left = sum(
        1 for r in rows if r.absence_verified_via and r.absence_verified_via.searched is None
    )
    print(f"confirmed {confirmed}, found {found}, still unconfirmed {left}")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
