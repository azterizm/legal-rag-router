"""Build the limits table from the Employment Rights (Increase of Limits) Orders as made.

    uv run python -m bench.pit.limits            # write bench/pit/limits.json
    uv run python -m bench.pit.limits --check    # rebuild and compare with the committed file

One row per (provision, Order): the sum in column 4 of the Order's Schedule, copied verbatim,
in force from the Order's commencement until the next Order's. Every figure comes from the
Order's own XML in ``bench/pit/orders/``, whose SHA-256 the row records; none is typed in.

The build refuses to write unless the Orders agree with each other:

* the commencement date in the metadata (``ukm:ComingIntoForce``) matches the date in
  article 1's text;
* each Order's column 3 ("old limit") equals the previous Order's column 4 for every
  provision, so no Order is missing from the chain;
* every Order but the newest is revoked by a later one in the set.

The table starts with SI 2010/2926 (in force 1 February 2011). Before it, s.186 and s.227 were
also raised by another instrument (SI 2009/1903, from 1 October 2009, per the Explanatory Note
to SI 2009/3274), which the chain check rejects; a date before 1 February 2011 has no row.

Identity is read from each file's ``IdURI``, never from its name (roadmap U2).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeET

__all__ = ["CAVEATS", "TARGETS", "LimitsError", "Order", "build", "load_orders", "parse_order"]

HERE: Final = Path(__file__).resolve().parent
ORDERS_DIR: Final = HERE / "orders"
LIMITS_JSON: Final = HERE / "limits.json"

TARGETS: Final = {
    "124": "uk/ukpga/1996/18/s124",
    "186": "uk/ukpga/1996/18/s186",
    "227": "uk/ukpga/1996/18/s227",
}
"""Employment Rights Act 1996 sections the table covers, by section number."""

CAVEATS: Final = {
    "uk/ukpga/1996/18/s124": (
        "2013-07-29",
        (
            "From 29 July 2013 the compensatory award is capped at the lower of this sum and 52 "
            "weeks' pay (s.124(1ZA), inserted by SI 2013/1949)."
        ),
    ),
}
"""Hand-written context returned beside a figure, never in place of one: (from, text).

Attached to rows still in force on or after ``from``. The date and SI are from the Act's own
footnote: "S. 124(1ZA) inserted (29.7.2013) by … S.I. 2013/1949"."""

_ID_PREFIX: Final = "http://www.legislation.gov.uk/id/"
_IN_FORCE_RE: Final = re.compile(
    r"comes?\s+into\s+force\s+on\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Z][a-z]+)\s+(\d{4})"
)
_SECTION_RE: Final = re.compile(r"\bsection\s+(\d+[A-Z]*)\(", re.IGNORECASE)
_ORDER_TITLE_RE: Final = re.compile(
    r"Employment Rights \((?:Increase|Revision) of Limits\) (?:\(No\. \d\) )?Order \d{4}"
)


class LimitsError(RuntimeError):
    """The Orders disagree with each other, or one cannot be read."""


@dataclass(frozen=True, slots=True)
class ScheduleRow:
    provision: str
    old: str
    new: str


@dataclass(frozen=True, slots=True)
class Order:
    si: str
    title: str
    made: str
    in_force: str
    in_force_text: str
    revokes: tuple[str, ...]
    transitional: str
    rows: tuple[ScheduleRow, ...]
    xml_sha256: str


def _text(element: Element) -> str:
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip()


def _article(body: Element, heading: str) -> Element | None:
    for group in body.findall(".//{*}P1group"):
        title = group.find("{*}Title")
        if title is not None and heading in _text(title).lower():
            return group
    return None


def parse_order(path: Path) -> Order:
    raw = path.read_bytes()
    root = SafeET.fromstring(raw)
    id_uri = root.get("IdURI") or ""
    if not id_uri.startswith(_ID_PREFIX):
        raise LimitsError(f"{path.name}: no IdURI")
    si = "uk/" + id_uri.removeprefix(_ID_PREFIX)
    title = _text(_required(root.find(".//{*}Metadata/{*}title"), path, "dc:title"))
    made = _required(root.find(".//{*}Made"), path, "ukm:Made").get("Date", "")
    meta_in_force = _required(
        root.find(".//{*}ComingIntoForce/{*}DateTime"), path, "ukm:ComingIntoForce"
    ).get("Date", "")
    body = _required(root.find(".//{*}Body"), path, "Body")

    citation = _text(_required(_article(body, "commencement"), path, "article 1"))
    match = _IN_FORCE_RE.search(citation)
    if match is None:
        raise LimitsError(f"{si}: no commencement date in article 1")
    day, month, year = match.groups()
    in_force = datetime.strptime(f"{day} {month} {year}", "%d %B %Y").date().isoformat()
    if in_force != meta_in_force:
        raise LimitsError(f"{si}: article 1 says {in_force}, metadata says {meta_in_force}")
    in_force_text = next(
        t for e in body.findall(".//{*}Text") if _IN_FORCE_RE.search(t := _text(e))
    )

    revocation = _article(body, "revocation")
    revokes = tuple(_ORDER_TITLE_RE.findall(_text(revocation))) if revocation is not None else ()
    transitional_group = _required(_article(body, "transitional"), path, "transitional article")
    first = transitional_group.find(".//{*}P2para")
    transitional = _text(first if first is not None else transitional_group)

    rows = []
    schedules = _required(root.find(".//{*}Schedules"), path, "Schedules")
    for tr in schedules.findall(".//{*}tr"):
        cells = [_text(td) for td in tr.findall("{*}td")]
        provision = next((c for c in cells if "of the 1996 Act" in c), None)
        if provision is not None and len(cells) >= 4:  # noqa: PLR2004
            rows.append(ScheduleRow(provision, cells[-2], cells[-1]))
    return Order(
        si=si,
        title=title,
        made=made,
        in_force=in_force,
        in_force_text=in_force_text,
        revokes=revokes,
        transitional=transitional,
        rows=tuple(rows),
        xml_sha256=hashlib.sha256(raw).hexdigest(),
    )


def _required(element: Element | None, path: Path, what: str) -> Element:
    if element is None:
        raise LimitsError(f"{path.name}: no {what}")
    return element


def _target_row(order: Order, section: str) -> ScheduleRow:
    found = [r for r in order.rows if (m := _SECTION_RE.search(r.provision)) and m[1] == section]
    if len(found) != 1:
        raise LimitsError(f"{order.si}: {len(found)} Schedule rows for ERA 1996 s.{section}")
    return found[0]


def _caveat(coordinate: str, valid_to: str | None) -> str | None:
    if coordinate not in CAVEATS:
        return None
    start, text = CAVEATS[coordinate]
    return text if valid_to is None or valid_to > start else None


def build(orders: list[Order]) -> list[dict[str, object]]:
    """The table rows, after checking the Orders form one unbroken chain."""
    orders = sorted(orders, key=lambda o: o.in_force)
    titles = {o.title.removeprefix("The ") for o in orders}
    revoked = {t for o in orders for t in o.revokes}
    for order in orders[:-1]:
        if order.title.removeprefix("The ") not in revoked:
            raise LimitsError(f"{order.si} is not revoked by a later Order in the set")
    for order in orders[1:]:  # the oldest Order revokes ones before the table starts
        unknown = set(order.revokes) - titles
        if unknown:
            raise LimitsError(f"{order.si} revokes Orders outside the set: {sorted(unknown)}")

    table: list[dict[str, object]] = []
    for section, coordinate in TARGETS.items():
        previous: ScheduleRow | None = None
        for i, order in enumerate(orders):
            row = _target_row(order, section)
            if previous is not None and row.old != previous.new:
                raise LimitsError(
                    f"{order.si} s.{section}: old limit {row.old} but the previous Order "
                    f"set {previous.new}; an Order is missing from the chain"
                )
            previous = row
            nxt = orders[i + 1] if i + 1 < len(orders) else None
            table.append(
                {
                    "coordinate": coordinate,
                    "amount": row.new,
                    "valid_from": order.in_force,
                    "valid_to": nxt.in_force if nxt else None,
                    "si": order.si,
                    "title": order.title,
                    "made": order.made,
                    "provision": row.provision,
                    "previous_amount": row.old,
                    "commencement": order.in_force_text,
                    "transitional": order.transitional,
                    "caveat": _caveat(coordinate, nxt.in_force if nxt else None),
                    "source_url": f"https://www.legislation.gov.uk/{order.si[3:]}/made/data.xml",
                    "xml_sha256": order.xml_sha256,
                }
            )
    return table


def render(table: list[dict[str, object]]) -> str:
    return json.dumps(table, ensure_ascii=False, indent=1) + "\n"


def load_orders(directory: Path = ORDERS_DIR) -> list[Order]:
    return [parse_order(p) for p in sorted(directory.glob("*.xml"))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="compare with the committed file")
    args = parser.parse_args(argv)
    text = render(build(load_orders()))
    if args.check:
        same = LIMITS_JSON.exists() and LIMITS_JSON.read_text(encoding="utf-8") == text
        print("limits.json matches the Orders" if same else "limits.json differs from the Orders")
        return 0 if same else 1
    LIMITS_JSON.write_text(text, encoding="utf-8")
    print(f"wrote {LIMITS_JSON.relative_to(HERE.parents[1])}: {text.count('coordinate')} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
