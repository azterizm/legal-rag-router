"""UK catalogue: feed parsing, import and harvest (offline)."""

from __future__ import annotations

import json
import random
from pathlib import Path

import httpx
import pytest

from ingest.cache import Fetcher, FetchPolicy
from ingest.records import CatalogueEntry
from ingest.uk_catalogue import harvest, import_listing, main, parse_feed, write_catalogue

UA = "legal-rag-router-ingest/0.1 (abdullah@memonsystems.com)"


def feed(entries: list[tuple[str, str, str, str]], next_href: str | None = None) -> bytes:
    """entries: (id path, title, year, number)."""
    items = "".join(
        f"<entry><id>http://www.legislation.gov.uk/id/{path}</id><title>{title}</title>"
        f'<ukm:Year Value="{year}"/><ukm:Number Value="{number}"/></entry>'
        for path, title, year, number in entries
    )
    link = f'<link rel="next" href="{next_href}"/>' if next_href else ""
    return (
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata">'
        f"{link}{items}</feed>"
    ).encode()


def test_parse_feed_uses_entry_id_including_regnal() -> None:
    entries, next_url, skipped = parse_feed(
        feed(
            [
                ("asp/2010/13", "Crofting Reform (Scotland) Act 2010", "2010", "13"),
                ("aep/Hen3/52/23", "Statute of Marlborough 1267 (repealed)", "1267", "23"),
                ("asp/2010", "broken", "2010", "x"),
            ],
            next_href="https://www.legislation.gov.uk/asp/data.feed?page=2",
        ),
        series_hint="asp",
    )
    assert [e.coordinate for e in entries] == ["uk/asp/2010/13", "uk/aep/Hen3/52/23"]
    assert entries[1].title == "Statute of Marlborough 1267"
    assert entries[1].repealed
    assert next_url == "https://www.legislation.gov.uk/asp/data.feed?page=2"
    assert skipped == 1


def test_import_listing() -> None:
    rows = [
        {"coordinate": "uk/asp/1999/1", "series": "asp", "year": 1999, "number": "1",
         "title": "Mental Health (Public Safety and Appeals) (Scotland) Act 1999 (repealed)"},
        {"coordinate": "uk/asp/1999", "series": "asp", "year": 1999, "number": "", "title": "x"},
        {"coordinate": "uk/wsi/2012/1427", "series": "wsi", "year": 2012, "number": "1427",
         "title": ""},
    ]  # fmt: skip
    entries = list(import_listing((json.dumps(r) for r in rows), source="import:test"))
    assert [e.coordinate for e in entries] == ["uk/asp/1999/1", "uk/wsi/2012/1427"]
    assert entries[0].title == "Mental Health (Public Safety and Appeals) (Scotland) Act 1999"
    assert entries[0].repealed
    assert entries[1].title is None  # untitled rows are kept: the instrument still exists


def test_write_catalogue_dedupes_and_sorts(tmp_path: Path) -> None:
    def entry(coordinate: str, title: str) -> CatalogueEntry:
        c = coordinate.split("/")
        return CatalogueEntry(
            coordinate=coordinate, series=c[1], year=int(c[2]), number=int(c[3]),
            title=title, title_as_published=title, source="t",
        )  # fmt: skip

    out = tmp_path / "cat.jsonl"
    count = write_catalogue(
        [entry("uk/ssi/2001/2", "B"), entry("uk/asp/2001/1", "A"), entry("uk/ssi/2001/2", "dup")],
        out,
    )
    lines = [json.loads(line) for line in out.read_text().splitlines()]
    assert count == 2
    assert [r["coordinate"] for r in lines] == ["uk/asp/2001/1", "uk/ssi/2001/2"]
    assert lines[1]["title"] == "B"


def test_harvest_follows_next_links_politely(tmp_path: Path) -> None:
    pages = {
        "https://www.legislation.gov.uk/asp/data.feed": feed(
            [("asp/2010/13", "A (Scotland) Act 2010", "2010", "13")],
            next_href="https://www.legislation.gov.uk/asp/data.feed?page=2",
        ),
        "https://www.legislation.gov.uk/asp/data.feed?page=2": feed(
            [("asp/2011/1", "B (Scotland) Act 2011", "2011", "1")]
        ),
    }
    seen: list[str] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        body = pages.get(str(request.url))
        return httpx.Response(200, content=body) if body else httpx.Response(404)

    now = [0.0]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    with Fetcher(
        tmp_path / "cache", UA, FetchPolicy(min_interval=5.0),
        transport=httpx.MockTransport(handler), clock=lambda: now[0], wall_clock=lambda: now[0],
        sleep=sleep, rng=random.Random(0),
    ) as fetcher:  # fmt: skip
        entries = list(harvest(fetcher, ["asp", "zz"]))
    assert [e.coordinate for e in entries] == ["uk/asp/2010/13", "uk/asp/2011/1"]
    assert seen[-1] == "https://www.legislation.gov.uk/zz/data.feed"
    assert sleeps == [5.0, 5.0]


def test_cli_import(tmp_path: Path) -> None:
    listing = tmp_path / "router_other_series.jsonl"
    listing.write_text(
        json.dumps({"coordinate": "uk/nia/2000/5", "series": "nia", "year": 2000, "number": "5",
                    "title": "Some Act (Northern Ireland) 2000"}) + "\n"
    )  # fmt: skip
    out = tmp_path / "out" / "uk_catalogue.jsonl"
    assert main(["import", "--listing", str(listing), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["source"] == "import:router_other_series.jsonl"


def test_cli_harvest_refuses_placeholder_contact(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="real contact"):
        main(["harvest", "--out", str(tmp_path / "x"), "--contact", "me@example.com"])


def _entry(coordinate: str, title: str = "T", year: int = 1807) -> CatalogueEntry:
    parts = coordinate.split("/")
    return CatalogueEntry(
        coordinate=coordinate, series=parts[1], year=int(parts[2]) if parts[2].isdigit() else year,
        number=int(parts[-1]), title=title, source="t",
    )  # fmt: skip


def test_missing_lists_what_the_index_lacks(tmp_path: Path) -> None:
    from ingest.uk_catalogue import missing  # noqa: PLC0415
    from legal_rag_router.index import load_index  # noqa: PLC0415
    from tests.conftest import FIXTURE_INDEX  # noqa: PLC0415

    raw = tmp_path / "raw_xml"
    (raw / "uksi" / "2011").mkdir(parents=True)
    (raw / "uksi" / "2011" / "9999.xml.gz").write_bytes(b"")  # holds another instrument (U2)
    entries = [
        _entry("uk/ukpga/1996/18"),  # indexed
        _entry("uk/uksi/2013/2729"),  # indexed as uk/wsi/2013/2729, found by its number
        _entry("uk/ukpga/Geo3/47/78", "Lost Act 1807"),  # regnal, lost to a calendar key
        _entry("uk/uksi/2011/9999"),
        _entry("uk/asp/2010/13"),  # other series: never ingested
    ]
    rows = list(missing(entries, load_index(FIXTURE_INDEX), raw))
    assert rows == [
        (
            "uk/ukpga/Geo3/47/78",
            "https://www.legislation.gov.uk/ukpga/Geo3/47/78/data.xml",
            "ukpga/Geo3-47/78.xml.gz",
            "Lost Act 1807",
        ),
        (
            "uk/uksi/2011/9999",
            "https://www.legislation.gov.uk/uksi/2011/9999/data.xml",
            "uksi/refetch-2011/9999.xml.gz",
            "T",
        ),
    ]


def test_cli_missing_writes_a_tsv(tmp_path: Path) -> None:
    from tests.conftest import FIXTURE_INDEX  # noqa: PLC0415

    catalogue = tmp_path / "catalogue.jsonl"
    write_catalogue([_entry("uk/ukpga/Geo3/47/78", "Lost Act 1807")], catalogue)
    out = tmp_path / "missing.tsv"
    args = ["missing", "--catalogue", str(catalogue), "--index", str(FIXTURE_INDEX)]
    assert main([*args, "--raw-xml", str(tmp_path / "raw"), "--out", str(out)]) == 0
    lines = out.read_text().splitlines()
    assert lines[0] == "coordinate\turl\tsave_path\ttitle"
    assert lines[1].startswith("uk/ukpga/Geo3/47/78\thttps://www.legislation.gov.uk/ukpga/")


def test_cli_harvest_merges_into_the_catalogue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ingest.uk_catalogue as catalogue_module  # noqa: PLC0415

    out = tmp_path / "uk_catalogue.jsonl"
    write_catalogue([_entry("uk/wsi/2012/1427", ""), _entry("uk/asp/2010/13", "Kept")], out)
    fed = [_entry("uk/wsi/2012/1427", "Titled Welsh Order 2012")]
    monkeypatch.setattr(catalogue_module, "harvest", lambda fetcher, series: iter(fed))
    args = ["harvest", "--out", str(out), "--contact", "abdullah@memonsystems.com"]
    assert main([*args, "--cache", str(tmp_path / "cache")]) == 0
    titles = {e["coordinate"]: e["title"] for e in map(json.loads, out.read_text().splitlines())}
    assert titles == {"uk/wsi/2012/1427": "Titled Welsh Order 2012", "uk/asp/2010/13": "Kept"}
