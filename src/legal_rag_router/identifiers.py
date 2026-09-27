"""Structured identifiers: the strongest citations there are, read before any grammar.

Accepted (case-insensitive, never typo-corrected, docs/grammar.md UK-X-01 to UK-X-05):

* canonical coordinates: ``uk/ukpga/1996/18/s124/1ZA/a``;
* instrument ids: ``uk_ukpga_1996_18``;
* legislation.gov.uk URLs: ``https://www.legislation.gov.uk/ukpga/1996/18/section/124``
  (also ``/id/``, ``/contents``, ``/enacted``, ``/made``, ``/data.xml``, point-in-time dates,
  no scheme).

A scanner result is only a *lookup key* (lower case). Nothing here decides existence: the
router confirms every key against the index, so an identifier binds only if the index
holds it, and the alphabet of a key (``[0-9a-z./_-]``) cannot carry anything into a filter
expression. A partial path (``uk/ukpga/1996``) is not an identifier.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from legal_rag_router.grammars.uk import SCHEME as UK_SCHEME
from legal_rag_router.grammars.uk import UNIT_PREFIXES

__all__ = ["IdentifierMention", "scan_identifiers"]

_SEGMENT: Final = r"[0-9A-Za-z][0-9A-Za-z.\-]{0,23}"
_COORDINATE_RE: Final = re.compile(
    rf"(?<![\w/.])(?P<j>uk)/(?P<rest>{_SEGMENT}(?:/{_SEGMENT}){{2,19}})", re.I
)
_INSTRUMENT_ID_RE: Final = re.compile(
    rf"(?<![\w/])(?P<j>uk)_(?P<rest>[a-z]{{2,6}}_{_SEGMENT}(?:_{_SEGMENT}){{1,2}})(?![\w])", re.I
)
_URL_RE: Final = re.compile(
    r"(?<![\w.])(?:https?://)?(?:www\.)?legislation\.gov\.uk/(?:id/)?(?P<path>[0-9A-Za-z.\-/+]{3,300})",
    re.I,
)
_VIEW_SUFFIXES: Final = frozenset(
    {"contents", "enacted", "made", "created", "adopted", "data.xml", "data.htm", "data.html",
     "england", "wales", "scotland", "ni", "england+wales", "introduction", "body", "schedules"}
)  # fmt: skip
_DATE_SEGMENT: Final = re.compile(r"\d{4}-\d{2}-\d{2}")
_KEY_SEGMENT: Final = re.compile(r"[0-9a-z][0-9a-z.\-]{0,23}")


@dataclass(frozen=True, slots=True)
class IdentifierMention:
    start: int
    end: int
    kind: Literal["coordinate", "instrument_id", "url"]
    key: str
    """Lower-case coordinate key: instrument segments plus any provision segments."""
    instrument_key: str
    """Lower-case key of the instrument part alone."""


def _split(parts: Sequence[str]) -> tuple[list[str], list[str]] | None:
    """Split lower-case path segments after ``uk`` into (instrument, provision)."""
    if len(parts) < 3 or not all(_KEY_SEGMENT.fullmatch(p) for p in parts):  # noqa: PLR2004
        return None
    arity = UK_SCHEME.instrument_arity(
        tuple(p if i != 1 else p[:1].upper() + p[1:] for i, p in enumerate(parts))
    )
    if arity is None or arity > len(parts):
        return None
    return list(parts[:arity]), list(parts[arity:])


def _url_provision(tokens: list[str]) -> list[str] | None:
    """legislation.gov.uk URL tokens (lower case) → provision key segments, leniently.

    Leniency is safe: the key must still be found in the index to bind.
    """
    segments: list[str] = []
    i = 0
    while i < len(tokens):
        prefix = UNIT_PREFIXES.get(tokens[i])
        if prefix is not None:
            if i + 1 < len(tokens) and tokens[i + 1] not in UNIT_PREFIXES:
                segments.append(prefix + tokens[i + 1])
                i += 2
                continue
            if prefix != "sch":
                return None
            segments.append(prefix)
            i += 1
            continue
        if not segments:
            return None
        segments.append(tokens[i])
        i += 1
    return segments


def scan_identifiers(query: str) -> list[IdentifierMention]:
    """Every structured identifier in ``query``, left to right, non-overlapping."""
    found: list[IdentifierMention] = []

    def add(
        start: int, end: int, kind: Literal["coordinate", "instrument_id", "url"], parts: list[str]
    ) -> None:
        if any(start < m.end and m.start < end for m in found):
            return
        split = _split([p.casefold() for p in parts])
        if split is None:
            return
        instrument, provision = split
        instrument_key = "/".join(("uk", *instrument))
        key = "/".join((instrument_key, *provision)) if provision else instrument_key
        found.append(IdentifierMention(start, end, kind, key, instrument_key))

    for m in _URL_RE.finditer(query):
        tokens = [t for t in m.group("path").casefold().rstrip("/.").split("/") if t]
        while tokens and (tokens[-1] in _VIEW_SUFFIXES or _DATE_SEGMENT.fullmatch(tokens[-1])):
            tokens.pop()
        instrument_split = _split(tokens)
        if instrument_split is None:
            continue
        instrument, rest = instrument_split
        provision = _url_provision(rest) if rest else []
        if provision is None:
            continue
        add(m.start(), m.end(), "url", [*instrument, *provision])
    for m in _COORDINATE_RE.finditer(query):
        add(m.start(), m.end(), "coordinate", m.group("rest").rstrip(".").split("/"))
    for m in _INSTRUMENT_ID_RE.finditer(query):
        add(m.start(), m.end(), "instrument_id", m.group("rest").split("_"))
    return sorted(found, key=lambda m: m.start)
