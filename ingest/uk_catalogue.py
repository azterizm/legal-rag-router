"""UK catalogue: every instrument legislation.gov.uk lists, in every series (roadmap U4).

The catalogue records title, year and number for instruments whose provisions are *not*
ingested (devolved legislation, local Acts, pre-1801 parliaments, retained EU law …), so
the router can answer "out of coverage" instead of falsely refusing them. It also gives a
regnal-correct list of ``ukpga``/``uksi`` to measure what the XML download still lacks.

Two sources write the same :class:`~ingest.records.CatalogueEntry` JSONL:

``import``
    Converts an existing listing (``router_other_series.jsonl``) offline. Stage A.
``harvest``
    Reads the Atom feeds through :class:`~ingest.cache.Fetcher` (1 request / 5 s, cached,
    resumable). Stage B only, after the XML download finishes, so two clients never share
    the rate budget (roadmap decision 9).

Usage::

    uv run python -m ingest.uk_catalogue import --listing uk_scrap_data/router_other_series.jsonl \\
        --out data/catalogue/uk_catalogue.jsonl
    uv run python -m ingest.uk_catalogue harvest --out data/catalogue/uk_catalogue.jsonl \\
        --contact you@yourcompany.com [--series asp ssi …]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Final
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeET
from pydantic import ValidationError

from ingest.cache import Fetcher, FetchPolicy
from ingest.records import CatalogueEntry, canonical_json
from ingest.uk import clean_title, coordinate_from_uri
from legal_rag_router.coordinate import Coordinate

__all__ = ["ALL_SERIES", "harvest", "import_listing", "main", "parse_feed"]

log = logging.getLogger("ingest.uk_catalogue")

SITE: Final = "https://www.legislation.gov.uk"
ATOM: Final = "{http://www.w3.org/2005/Atom}"
UKM: Final = "{http://www.legislation.gov.uk/namespaces/metadata}"

# Every series legislation.gov.uk publishes (robots.txt sitemaps, checked 27 Sept 2026),
# plus the pre-1948/draft series that have no sitemap.
ALL_SERIES: Final = (
    "ukpga", "ukla", "ukppa", "gbppa", "gbla", "apgb", "aep", "aosp", "asp", "aip",
    "apni", "mnia", "nia", "ukcm", "mwa", "anaw", "asc", "uksi", "ssi", "wsi", "nisr",
    "ukci", "nisi", "ukmo", "eudn", "eudr", "eur", "eut",
    "uksro", "nisro", "ukdsi", "sdsi", "wdsi", "nidsr", "ukmd",
)  # fmt: skip
MAX_PAGES_PER_FEED: Final = 20_000


# ---------------------------------------------------------------------------- parsing


def _entry(entry: Element, series_hint: str | None, source: str) -> CatalogueEntry | None:
    coordinate = coordinate_from_uri((entry.findtext(f"{ATOM}id") or "").strip())
    published = (entry.findtext(f"{ATOM}title") or "").strip()
    year = entry.find(f".//{UKM}Year")
    number = entry.find(f".//{UKM}Number")
    if coordinate is None and series_hint and year is not None and number is not None:
        coordinate = Coordinate.try_parse(
            f"uk/{series_hint}/{year.get('Value', '')}/{number.get('Value', '')}"
        )
    if coordinate is None or not coordinate.is_instrument:
        return None
    year_value = year.get("Value") if year is not None else coordinate.instrument[1]
    number_value = number.get("Value") if number is not None else coordinate.instrument[-1]
    title, repealed = clean_title(published) if published else (None, False)
    try:
        return CatalogueEntry(
            coordinate=str(coordinate),
            series=coordinate.series,
            year=int(year_value or 0),
            number=int(number_value or 0),
            title=title,
            title_as_published=published or None,
            repealed=repealed,
            source=source,
        )
    except (ValidationError, ValueError):
        return None


def parse_feed(
    data: bytes, *, series_hint: str | None = None, source: str = "atom-feed"
) -> tuple[list[CatalogueEntry], str | None, int]:
    """Parse one Atom feed page.

    Returns ``(entries, next_page_url, skipped)``: the catalogue entries it lists, the
    ``rel="next"`` link (``None`` on the last page), and how many entries were unusable.
    """
    root = SafeET.fromstring(data)
    entries: list[CatalogueEntry] = []
    skipped = 0
    for node in root.findall(f"{ATOM}entry"):
        parsed = _entry(node, series_hint, source)
        if parsed is None:
            skipped += 1
        else:
            entries.append(parsed)
    next_url = None
    for link in root.findall(f"{ATOM}link"):
        if link.get("rel") == "next" and link.get("href"):
            next_url = link.get("href")
    return entries, next_url, skipped


# ---------------------------------------------------------------------------- sources


def import_listing(lines: Iterable[str], *, source: str) -> Iterator[CatalogueEntry]:
    """Convert ``router_other_series.jsonl`` rows (coordinate, series, year, number, title).

    Rows without a title are kept (``title=None``): the instrument is still known to
    exist, which is what an out-of-coverage answer by number needs.
    """
    untitled = unusable = 0
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        published = str(row.get("title") or "").strip()
        coordinate = Coordinate.try_parse(str(row.get("coordinate", "")))
        if coordinate is None or not coordinate.is_instrument:
            unusable += 1
            log.debug("skipping unusable listing row: %s", line.strip()[:200])
            continue
        title, repealed = clean_title(published) if published else (None, False)
        untitled += title is None
        yield CatalogueEntry(
            coordinate=str(coordinate),
            series=coordinate.series,
            year=int(row["year"]),
            number=int(row["number"]),
            title=title,
            title_as_published=published or None,
            repealed=repealed,
            source=source,
        )
    if untitled or unusable:
        log.warning(
            "listing: %d rows without a title kept, %d unusable rows skipped", untitled, unusable
        )


def harvest(fetcher: Fetcher, series: Sequence[str]) -> Iterator[CatalogueEntry]:
    """Walk each series' Atom feed by its ``rel="next"`` links."""
    for name in series:
        url: str | None = f"{SITE}/{name}/data.feed"
        pages = 0
        while url is not None and pages < MAX_PAGES_PER_FEED:
            result = fetcher.get(url)
            pages += 1
            if result.status != 200:  # noqa: PLR2004
                log.warning("%s: HTTP %d, stopping this series", url, result.status)
                break
            entries, url, skipped = parse_feed(result.read(), series_hint=name)
            if skipped:
                log.warning("%s: %d unusable entries", result.url, skipped)
            yield from entries
        log.info("%s: %d pages", name, pages)


def write_catalogue(entries: Iterable[CatalogueEntry], out: Path) -> int:
    """Write entries de-duplicated by coordinate (first wins), sorted, atomically."""
    unique: dict[str, CatalogueEntry] = {}
    for entry in entries:
        unique.setdefault(entry.coordinate, entry)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for key in sorted(unique):
            fh.write(canonical_json(unique[key].model_dump(mode="json")) + "\n")
    tmp.replace(out)
    return len(unique)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import", help="convert an existing listing (offline)")
    imp.add_argument("--listing", type=Path, required=True)
    imp.add_argument("--out", type=Path, required=True)
    har = sub.add_parser("harvest", help="read the Atom feeds (network; Stage B)")
    har.add_argument("--out", type=Path, required=True)
    har.add_argument("--contact", required=True, help="e-mail or URL for the User-Agent")
    har.add_argument("--cache", type=Path, default=Path(".cache/http"))
    har.add_argument("--series", nargs="*", default=list(ALL_SERIES))
    har.add_argument("--interval", type=float, default=FetchPolicy().min_interval)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.command == "import":
        with args.listing.open(encoding="utf-8") as fh:
            count = write_catalogue(
                import_listing(fh, source=f"import:{args.listing.name}"), args.out
            )
    else:
        user_agent = f"legal-rag-router-ingest/0.1 ({args.contact})"
        policy = FetchPolicy(min_interval=max(args.interval, FetchPolicy().min_interval))
        with Fetcher(args.cache, user_agent, policy) as fetcher:
            count = write_catalogue(harvest(fetcher, args.series), args.out)
    log.info("wrote %d catalogue entries to %s", count, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
