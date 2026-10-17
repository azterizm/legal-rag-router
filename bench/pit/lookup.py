"""Point-in-time lookup over the limits table: CS2 §7 Control 3, run as it is written there.

The router binds the provision and passes the date phrase through as ``temporal_hint``; this
module reads a date out of that hint and runs one SQL range query over ``limits.json`` loaded
into in-memory SQLite. It answers with exactly one row or says why it cannot, and never
guesses: no date, a date without a day ("as at 2012"), a provision the table does not hold,
or a date before the table starts each get their own status and no figure.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final, Literal

from bench.pit.limits import LIMITS_JSON
from legal_rag_router import RouteResult, RouteStatus

__all__ = ["SQL", "Answer", "Limits", "parse_date", "render", "resolve"]

SQL: Final = (
    "SELECT amount, si, title, valid_from, valid_to, provision, caveat, transitional FROM limits "
    "WHERE coordinate = ? AND valid_from <= ? AND (valid_to IS NULL OR ? < valid_to)"
)
"""CS2 §7: ``valid_from <= :date AND :date < valid_to``, with an open end for the newest row."""

Status = Literal[
    "FOUND", "NOT_BOUND", "NO_DATE", "IMPRECISE_DATE", "NOT_COVERED", "NO_ROW", "AMBIGUOUS"
]

_MONTHS: Final = {
    m: i
    for i, names in enumerate(
        (
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sept", "sep"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ),
        start=1,
    )
    for m in names
}
_MONTH_RX: Final = "|".join(sorted(_MONTHS, key=len, reverse=True))
_FULL_DATE_RES: Final = (
    re.compile(rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_RX})\.?,?\s+(\d{{4}})(?!\d)", re.I),
    re.compile(
        rf"(?<![a-z])({_MONTH_RX})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})(?!\d)", re.I
    ),
    re.compile(r"(?<![\d.])(\d{1,2})\s*[./]\s*(\d{1,2})\s*[./]\s*(\d{4})(?!\d)"),
    re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)"),
)
_YEAR_RE: Final = re.compile(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)")


@dataclass(frozen=True, slots=True)
class Answer:
    status: Status
    coordinate: str | None = None
    on: str | None = None
    amount: str | None = None
    si: str | None = None
    title: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    provision: str | None = None
    caveat: str | None = None
    transitional: str | None = None
    """The Order's own transitional clause: it applies by the "appropriate date"."""


def parse_date(hint: str | None) -> tuple[date | None, Status | None]:
    """The one calendar date in ``hint``, or the status that says why there is none."""
    if not hint:
        return None, "NO_DATE"
    found: set[date] = set()
    for i, pattern in enumerate(_FULL_DATE_RES):
        for m in pattern.finditer(hint):
            a, b, c = m.groups()
            try:
                if i == 0:
                    found.add(date(int(c), _MONTHS[b.lower()], int(a)))
                elif i == 1:
                    found.add(date(int(c), _MONTHS[a.lower()], int(b)))
                elif i == 2:  # noqa: PLR2004 - UK order: day, month, year
                    found.add(date(int(c), int(b), int(a)))
                else:
                    found.add(date(int(a), int(b), int(c)))
            except ValueError:
                continue
    if len(found) == 1:
        return found.pop(), None
    if len(found) > 1:
        return None, "AMBIGUOUS"
    return None, "IMPRECISE_DATE" if _YEAR_RE.search(hint) else "NO_DATE"


class Limits:
    """``limits.json`` in an in-memory SQLite table, queried with :data:`SQL`."""

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._db = sqlite3.connect(":memory:")
        self._db.execute(
            "CREATE TABLE limits (coordinate TEXT NOT NULL, valid_from TEXT NOT NULL, "
            "valid_to TEXT, amount TEXT NOT NULL, si TEXT NOT NULL, title TEXT NOT NULL, "
            "provision TEXT NOT NULL, caveat TEXT, transitional TEXT NOT NULL)"
        )
        self._db.execute("CREATE INDEX limits_at ON limits (coordinate, valid_from)")
        self._db.executemany(
            "INSERT INTO limits VALUES (:coordinate, :valid_from, :valid_to, :amount, :si, "
            ":title, :provision, :caveat, :transitional)",
            rows,
        )
        self.coordinates = frozenset(str(r["coordinate"]) for r in rows)

    @classmethod
    def from_path(cls, path: Path = LIMITS_JSON) -> Limits:
        rows: list[dict[str, object]] = json.loads(path.read_text(encoding="utf-8"))
        return cls(rows)

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> Limits:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def at(self, coordinate: str, on: date) -> Answer:
        if coordinate not in self.coordinates:
            return Answer("NOT_COVERED", coordinate, on.isoformat())
        day = on.isoformat()
        rows = self._db.execute(SQL, (coordinate, day, day)).fetchall()
        if not rows:
            return Answer("NO_ROW", coordinate, day)
        if len(rows) > 1:
            return Answer("AMBIGUOUS", coordinate, day)
        return Answer("FOUND", coordinate, day, *rows[0])


def resolve(route: RouteResult, limits: Limits) -> Answer:
    """Router output to an answer: the one bound coordinate, the hint's date, one row."""
    if route.status is not RouteStatus.BOUNDED or len(route.coordinates) != 1:
        return Answer("NOT_BOUND")
    coordinate = str(route.coordinates[0])
    on, problem = parse_date(route.temporal_hint)
    if on is None:
        return Answer(problem or "NO_DATE", coordinate)
    return limits.at(coordinate, on)


def render(answer: Answer) -> str:
    """The answer as text: a figure only when the table returned exactly one row."""
    if answer.status != "FOUND":
        return f"No figure: {answer.status} ({answer.coordinate or 'no single provision bound'})."
    assert answer.valid_from is not None  # noqa: S101 - FOUND always carries a row
    until = "until replaced" if answer.valid_to is None else "to " + _day_before(answer.valid_to)
    text = (
        f"{answer.amount}. {answer.provision} (Employment Rights Act 1996), as at {answer.on}: "
        f"set by {answer.title} ({answer.si}), in force {answer.valid_from} {until}."
    )
    return f"{text} {answer.caveat}" if answer.caveat else text


def _day_before(iso: str) -> str:
    return (datetime.strptime(iso, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
