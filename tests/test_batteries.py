"""Battery files (roadmap M8): schema, sizes, the typo split and grammar coverage."""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from batteries.schema import BATTERIES, BATTERY_DIR, BatteryRow, read_battery, write_battery
from batteries.verify_absence import feed_url, found_titles, main, verify
from ingest.cache import Fetcher, FetchPolicy

REPO = Path(__file__).resolve().parents[1]
UK = BATTERY_DIR / "uk"
NOT_A_QUERY = {"UK-C-17": "jurisdictions= is an API argument, not query text"}


@pytest.fixture(scope="module")
def uk() -> dict[str, list[BatteryRow]]:
    return {path.stem: read_battery(path) for path in sorted(UK.glob("*.jsonl"))}


def test_every_battery_exists_and_validates(uk: dict[str, list[BatteryRow]]) -> None:
    assert set(uk) == set(BATTERIES)


@pytest.mark.parametrize("battery", ["misroute", "false_abstention"])
def test_sampled_batteries_are_large_enough(uk: dict[str, list[BatteryRow]], battery: str) -> None:
    # Zero errors in 600 rows bounds the rate below 0.5 % at 95 % (rule of three).
    assert len(uk[battery]) >= 600


def test_misroute_rows_are_real_text_with_the_source_answer(
    uk: dict[str, list[BatteryRow]],
) -> None:
    counts = Counter(row.source for row in uk["misroute"])
    assert counts["real_document"] >= 600
    assert all(row.notes.startswith("harvest ") for row in uk["misroute"] if row.source != "hand")


def test_invented_battery_has_its_instruments_and_their_checks(
    uk: dict[str, list[BatteryRow]],
) -> None:
    instruments = [
        row
        for row in uk["invented"]
        if row.expected_status == "EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND"
    ]
    assert len(instruments) >= 50
    assert any("Marchwood" in row.query for row in instruments)
    assert all(row.absence_verified_via is not None for row in instruments)


def test_typo_rows_are_split_and_near_misses_are_never_bound(
    uk: dict[str, list[BatteryRow]],
) -> None:
    rows = uk["typo"]
    assert {row.split for row in rows} == {"dev", "test"}
    near_misses = [row for row in rows if not row.expected_coordinates]
    assert near_misses
    assert all(row.expected_status != "ROUTE_BOUNDED" for row in near_misses)


def test_every_grammar_row_is_exercised(uk: dict[str, list[BatteryRow]]) -> None:
    grammar = (REPO / "docs" / "grammar.md").read_text(encoding="utf-8")
    ids = set(re.findall(r"^\| (UK-[A-Z]+-[0-9]+a?) ", grammar, re.MULTILINE))
    used = {form for rows in uk.values() for row in rows for form in row.surface_form_ids}
    assert used <= ids, f"rows cite unknown grammar ids: {sorted(used - ids)}"
    assert ids - used == set(NOT_A_QUERY), f"grammar rows without a battery row: {ids - used}"


def test_files_are_in_canonical_form(tmp_path: Path) -> None:
    for path in UK.glob("*.jsonl"):
        again = tmp_path / "uk" / path.name
        write_battery(again, read_battery(path))
        assert again.read_bytes() == path.read_bytes(), path.name


# ---------------------------------------------------------------- the schema itself


def _row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "uk-collision-0001",
        "query": "section 124 of the Employment Rights Act 1996",
        "lang": "en",
        "domain": "uk_legislation",
        "expected_status": "ROUTE_BOUNDED",
        "expected_coordinates": ["uk/ukpga/1996/18/s124"],
        "source": "hand",
    }
    return {**row, **changes}


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"expected_coordinates": []}, "names the coordinates"),
        ({"expected_status": "ROUTE_UNRESOLVED"}, "binds nothing"),
        ({"expected_coordinates": ["uk/ukpga/1996/18/s 124"]}, "Value error"),
        ({"context": ["not a coordinate"]}, "Value error"),
        ({"surface_form_ids": ["ES-P-01"]}, "not a uk grammar row"),
        ({"expected_status": "ROUTE_MAYBE"}, "expected_status"),
        ({"id": "uk-collision-1"}, "id"),
        ({"surprise": 1}, "surprise"),
    ],
)
def test_schema_rejects(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        BatteryRow.model_validate(_row(**changes))


def _write(tmp_path: Path, battery: str, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "uk" / f"{battery}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("battery", "rows", "message"),
    [
        ("typo", [_row(id="uk-typo-0001")], "`split` is for typo rows only"),
        ("collision", [_row(split="dev")], "`split` is for typo rows only"),
        ("misroute", [_row()], "does not start with uk-misroute-"),
        ("collision", [_row(), _row()], "duplicate row ids"),
        (
            "collision",
            [_row(absence_verified_via={"catalogue": "x", "search_url": "https://x"})],
            "absence checks are for invented rows",
        ),
        (
            "invented",
            [
                _row(
                    id="uk-invented-0001",
                    expected_status="EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND",
                    expected_coordinates=[],
                )
            ],
            "needs its check",
        ),
    ],
)
def test_battery_rules(
    tmp_path: Path, battery: str, rows: list[dict[str, object]], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        read_battery(_write(tmp_path, battery, rows))


# ---------------------------------------------------------------- absence confirmation


def _feed(*titles: str) -> bytes:
    entries = "".join(f"<entry><title>{t}</title></entry>" for t in titles)
    return f'<feed xmlns="http://www.w3.org/2005/Atom">{entries}</feed>'.encode()


SEARCH = "https://www.legislation.gov.uk/all?title=Moon+Mining+%28Licensing%29+Act&year=2016"


def _invented(url: str) -> BatteryRow:
    return BatteryRow.model_validate(
        _row(
            id="uk-invented-0001",
            query="Moon Mining (Licensing) Act 2016",
            expected_status="EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND",
            expected_coordinates=[],
            absence_verified_via={"catalogue": "offline", "search_url": url},
        )
    )


@pytest.mark.parametrize(
    ("url", "status", "body", "absent"),
    [
        (SEARCH, 200, _feed(), True),
        (SEARCH, 200, _feed("The Moon (Mining) Order 2016"), True),  # containment only
        (SEARCH, 200, _feed("Moon Mining (Licensing) Act 2016"), False),
        (SEARCH, 503, b"", False),
        ("https://www.legislation.gov.uk/uksi/2011/9999", 404, b"", True),
        ("https://www.legislation.gov.uk/uksi/2011/9999", 400, b"", True),  # rejected number
        (SEARCH, 400, b"", False),  # a rejected search is never an absence
        ("https://www.legislation.gov.uk/uksi/2011/3006", 200, b"<x/>", False),
    ],
)
def test_verify_absence(tmp_path: Path, url: str, status: int, body: bytes, absent: bool) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(status, content=body)

    policy = FetchPolicy(min_interval=0.0, max_retries=0)
    with Fetcher(
        tmp_path, "test (you@lrr.test)", policy, transport=httpx.MockTransport(handler),
        sleep=lambda _: None, rng=random.Random(0),
    ) as fetcher:  # fmt: skip
        try:
            result = verify(fetcher.get, _invented(url))[0]
        except Exception:  # noqa: BLE001 - a failed fetch must never count as absent
            result = False
    assert result is absent
    assert seen[0] == httpx.URL(feed_url(url))


def test_verify_absence_rejects_a_page_that_is_not_a_feed() -> None:
    with pytest.raises(ValueError, match="not an Atom feed"):
        found_titles(b"<html/>")


def test_verify_absence_dry_run_fetches_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "uk" / "invented.jsonl"
    write_battery(path, [_invented(SEARCH)])
    assert main(["--battery", str(path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "/all/data.feed?title=Moon" in out
    assert "1 row(s) to confirm" in out


def test_verify_absence_from_cache_needs_no_request(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = tmp_path / "cache"
    policy = FetchPolicy(min_interval=0.0, max_retries=0)
    with Fetcher(
        cache, "test (you@lrr.test)", policy,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=_feed())),
        sleep=lambda _: None, rng=random.Random(0),
    ) as fetcher:  # fmt: skip
        fetched_on = fetcher.get(feed_url(SEARCH)).fetched_at[:10]
    other = SEARCH.replace("Moon", "Sun")
    rows = [_invented(SEARCH), _invented(other).model_copy(update={"id": "uk-invented-0002"})]
    path = tmp_path / "uk" / "invented.jsonl"
    write_battery(path, rows)
    assert main(["--battery", str(path), "--cache", str(cache), "--from-cache"]) == 0
    assert "confirmed 1, found 0, still unconfirmed 1" in capsys.readouterr().out
    first, second = read_battery(path)
    assert first.absence_verified_via is not None
    assert str(first.absence_verified_via.searched) == fetched_on  # the response's own date
    assert second.absence_verified_via is not None
    assert second.absence_verified_via.searched is None  # not cached: left for a real search
