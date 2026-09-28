"""Confirm invented instruments with the source's own search (plan step 8, ``invented``).

You run this: it fetches from legislation.gov.uk under your contact details, through the
repo's fetch layer (one request per 5 s, cached, resumable). About one request per row.

    uv run python -m batteries.verify_absence --contact you@example.org [--dry-run]

For each row whose ``absence_verified_via.searched`` is empty it reads the search as an
Atom feed (``/all/data.feed?title=…&year=…``). The site matches titles by containment, so
a result only counts when its title has the invented title's exact key. A number-cited row
(``https://www.legislation.gov.uk/uksi/2011/9999``) is absent when the source answers 404.
Absent rows get today's date in ``searched``; anything found is reported and left empty.
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from defusedxml import ElementTree

from batteries.schema import BATTERY_DIR, BatteryRow, read_battery, write_battery
from ingest.build_index import title_variants
from ingest.cache import Fetcher, FetchPolicy

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


def verify(fetcher: Fetcher, row: BatteryRow) -> tuple[bool, str]:
    """(absent?, what was seen) for one invented row."""
    check = row.absence_verified_via
    if check is None:
        raise ValueError(f"{row.id} has no absence check")
    if "/all?" not in check.search_url:
        result = fetcher.get(check.search_url)
        return result.status in {404, 410}, f"HTTP {result.status}"
    result = fetcher.get(feed_url(check.search_url))
    if result.status != 200:  # noqa: PLR2004
        return False, f"HTTP {result.status}"
    titles = found_titles(result.read())
    matches = same_title(check.search_url, titles)
    return not matches, f"{len(titles)} result(s); same title: {matches or 'none'}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--battery", type=Path, default=BATTERY_DIR / "uk" / "invented.jsonl")
    parser.add_argument("--contact", help="your e-mail or URL for the User-Agent")
    parser.add_argument("--cache", type=Path, default=Path(".cache/http"))
    parser.add_argument("--dry-run", action="store_true", help="list the URLs; fetch nothing")
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
    if not args.contact:
        parser.error("--contact is required to fetch")
    today = datetime.now(UTC).date()
    user_agent = f"legal-rag-router-batteries/0.1 ({args.contact})"
    confirmed: dict[str, BatteryRow] = {}
    found = 0
    with Fetcher(args.cache, user_agent, FetchPolicy()) as fetcher:
        for row in todo:
            absent, seen = verify(fetcher, row)
            log.info("%s %s: %s", row.id, "absent" if absent else "FOUND", seen)
            if absent:
                check = row.absence_verified_via.model_copy(update={"searched": today})  # type: ignore[union-attr]
                confirmed[row.id] = row.model_copy(update={"absence_verified_via": check})
            else:
                found += 1
    write_battery(args.battery, [confirmed.get(r.id, r) for r in rows])
    print(f"confirmed {len(confirmed)}, found {found}: see the log for any FOUND rows")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
