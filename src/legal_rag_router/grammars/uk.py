"""United Kingdom: coordinate scheme and legislation.gov.uk path mapping.

Coordinates mirror legislation.gov.uk's identifier URIs (``IdURI``):

* calendar-numbered instruments (all SIs; Acts from 1963):
  ``uk/{series}/{year}/{number}`` — e.g. ``uk/ukpga/1996/18``;
* regnal-numbered Acts (before 1963), whose chapter numbers restart every session:
  ``uk/{series}/{regnal}/{session}/{number}`` — e.g. ``uk/ukpga/Eliz2/8-9/69``.

Provision segments are derived from legislation.gov.uk element ids and URL paths, which
share one token sequence (``section-124-1ZA-a`` ≡ ``section/124/1ZA/a`` → ``s124/1ZA/a``).
See ``docs/grammar.md`` §UK for the grammar and the full mapping table.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final

from legal_rag_router.coordinate import CoordinateScheme, register_scheme

__all__ = [
    "INSTRUMENT_TYPE_WORDS",
    "JURISDICTION",
    "SCHEME",
    "UNIT_PREFIXES",
    "legislation_path",
    "number_keys",
    "provision_from_legislation_tokens",
]

JURISDICTION: Final = "uk"

_SERIES: Final = r"[a-z]{2,6}"
_YEAR: Final = r"[12][0-9]{3}"
# Reign tokens as used by legislation.gov.uk: Vict, Geo3, Geo3Sess2, Will4and1Vict,
# Edw7and1Geo5, Geo6and1Eliz2, VictSess2, WillandMar …
_REIGN: Final = r"[A-Z][a-z]{1,5}[0-9]{0,2}"
_REGNAL: Final = rf"{_REIGN}(?:and[0-9]{{0,2}}{_REIGN})*(?:Sess[0-9])?"
_SESSION: Final = r"[0-9]{1,3}(?:-[0-9]{1,3}){0,3}"  # 47, 8-9, 12-13-14
_NUMBER: Final = r"[1-9][0-9]{0,5}"

_YEAR_RE: Final = re.compile(_YEAR)
_REGNAL_RE: Final = re.compile(_REGNAL)
_SERIES_RE: Final = re.compile(_SERIES)

UNIT_PREFIXES: Final[dict[str, str]] = {
    "section": "s",
    "article": "art",
    "regulation": "reg",
    "rule": "rule",
    "schedule": "sch",
    "paragraph": "para",
    "part": "pt",
    "chapter": "ch",
    "group": "grp",
    "appendix": "app",
}
"""legislation.gov.uk unit word → coordinate segment prefix."""

_UNIT_WORDS: Final = {prefix: word for word, prefix in UNIT_PREFIXES.items()}

INSTRUMENT_TYPE_WORDS: Final = frozenset(
    {
        "act", "acts", "order", "orders", "regulations", "regulation", "rules", "rule",
        "measure", "scheme", "schemes", "directions", "direction", "byelaws", "bylaws",
        "code", "declaration", "determination", "instrument", "warrant", "resolution",
        "statute", "sederunt", "adjournal",
    }
)  # fmt: skip
"""Folded words that name a kind of UK instrument when they end a title ("… Act 1996",
"… Order 2011"). A title is also indexed without its type word ("employment rights|1996").
"""

# A unit designator: 124, 124A, 1ZA, A1, I, IV, 2A, 3.1 (CPR-style rule numbers).
_DESIGNATOR: Final = re.compile(r"[0-9A-Z][0-9A-Za-z]{0,11}(?:\.[0-9A-Za-z]{1,6}){0,2}")
# Schedules and schedule paragraphs may also be lettered in lower case in older Acts
# ("Schedule 13, paragraph (b)" → ``sch13/parab``). Only these two units allow it: a
# lower-case designator on ``s``/``pt``/… would collide with bare sub-divisions (``sa``).
_LOWER_OK_UNITS: Final = frozenset({"sch", "para"})
_DESIGNATOR_ANY_CASE: Final = re.compile(
    r"[0-9A-Z][0-9A-Za-z]{0,11}(?:\.[0-9A-Za-z]{1,6}){0,2}|[a-z]{1,2}[0-9]{0,2}"
)


def _is_designator(prefix: str, token: str) -> bool:
    pattern = _DESIGNATOR_ANY_CASE if prefix in _LOWER_OK_UNITS else _DESIGNATOR
    return pattern.fullmatch(token) is not None


# A bare sub-division below a unit: (1), (1ZA), (a), (aa), (aza), (i), (iv), (iia) …
_SUBDIVISION: Final = re.compile(
    r"[0-9]{1,4}[A-Z]{0,3}[0-9]{0,2}"  # 1, 1A, 1ZA, 2B1
    r"|[A-Z]{1,3}[0-9]{0,3}"  # A, A1, ZA1
    r"|[ivxlc]{1,7}[a-z]?"  # i, iv, xxvii, iia
    r"|[a-z]{1,3}"  # a, aa, aza
)
# Words that can appear in odd ids but never name a sub-division, plus "sch", which would
# make the unnumbered-schedule segment ambiguous on the way back to a URL path.
_NOT_SUBDIVISIONS: Final = frozenset({"and", "the", "for", "of", "to", "sch"})

_FIRST_PROVISION: Final = re.compile(
    r"(?:s|art|reg|rule|pt|ch|grp|app)"
    r"[0-9A-Z][0-9A-Za-z]{0,11}(?:\.[0-9A-Za-z]{1,6}){0,2}"
    r"|(?:para|sch)(?:[0-9A-Z][0-9A-Za-z]{0,11}(?:\.[0-9A-Za-z]{1,6}){0,2}|[a-z]{1,2}[0-9]{0,2})"
    r"|sch"
)


def _instrument_arity(segments: tuple[str, ...]) -> int | None:
    """3 for ``series/year/number``, 4 for ``series/regnal/session/number``."""
    if len(segments) < 2 or not _SERIES_RE.fullmatch(segments[0]):  # noqa: PLR2004
        return None
    if _YEAR_RE.fullmatch(segments[1]):
        return 3
    if _REGNAL_RE.fullmatch(segments[1]):
        return 4
    return None


SCHEME: Final = CoordinateScheme(
    jurisdiction=JURISDICTION,
    instrument_arity=_instrument_arity,
    instrument_pattern=re.compile(
        rf"{_SERIES}/(?:{_YEAR}|{_REGNAL}/{_SESSION})/{_NUMBER}",
    ),
    first_provision_pattern=_FIRST_PROVISION,
)

register_scheme(SCHEME)


def provision_from_legislation_tokens(tokens: Sequence[str]) -> tuple[str, ...] | None:
    """Map a legislation.gov.uk element-id or URL token sequence to provision segments.

    ``["section", "124", "1ZA", "a"]`` → ``("s124", "1ZA", "a")``;
    ``["schedule", "paragraph", "3"]`` → ``("sch", "para3")`` (a sole, unnumbered schedule);
    ``["part", "2A", "chapter", "1"]`` → ``("pt2A", "ch1")``.

    Returns ``None`` for anything that is not a citable provision: cross-headings, ids with
    unknown words, empty input, or a first token that is not a unit word.
    """
    segments: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        token = tokens[i]
        prefix = UNIT_PREFIXES.get(token)
        if prefix is not None:
            nxt = tokens[i + 1] if i + 1 < n else None
            if nxt is not None and nxt not in UNIT_PREFIXES and _is_designator(prefix, nxt):
                segments.append(prefix + nxt)
                i += 2
                continue
            if prefix != "sch":  # only a schedule may be unnumbered ("The Schedule")
                return None
            segments.append(prefix)
            i += 1
            continue
        if not segments or token in _NOT_SUBDIVISIONS or not _SUBDIVISION.fullmatch(token):
            return None
        segments.append(token)
        i += 1
    return tuple(segments) if segments else None


def _split_segment(segment: str) -> tuple[str, str] | None:
    """Split a unit segment ``s124A`` into (``section``, ``124A``); ``None`` if not a unit."""
    for prefix in sorted(_UNIT_WORDS, key=len, reverse=True):
        if segment.startswith(prefix):
            rest = segment[len(prefix) :]
            if rest == "" and prefix == "sch":
                return _UNIT_WORDS[prefix], ""
            if rest and _is_designator(prefix, rest):
                return _UNIT_WORDS[prefix], rest
    return None


def legislation_path(provision: Sequence[str]) -> str:
    """Inverse of :func:`provision_from_legislation_tokens`, as a URL path fragment.

    ``("s124", "1ZA", "a")`` → ``"section/124/1ZA/a"``.
    """
    parts: list[str] = []
    for segment in provision:
        unit = _split_segment(segment)
        if unit is not None:
            word, designator = unit
            parts.append(word)
            if designator:
                parts.append(designator)
        else:
            parts.append(segment)
    return "/".join(parts)


# Series whose official number is a UK SI number ("SI 2013/2729" may be canonically wsi).
_UK_SI_SERIES: Final = frozenset({"uksi", "wsi", "nisi"})
_NUMBERED_SERIES_KEYS: Final = {
    "ssi": "ssi",  # Scottish SI: "SSI 2003/623"
    "nisr": "sr",  # Northern Ireland Statutory Rules: "SR 1996/123"
    "asp": "asp",
    "nia": "nia",
    "anaw": "anaw",
    "asc": "asc",
    "eur": "eur",
}


def number_keys(instrument: Sequence[str]) -> tuple[str, ...]:
    """Official-number lookup keys for an instrument (its segments after ``uk``).

    ``("uksi", "2011", "3006")`` → ``("si/2011/3006",)``;
    ``("ukpga", "1996", "18")`` → ``("c/1996/18",)`` (chapter 18 of 1996);
    ``("ukpga", "Eliz2", "8-9", "69")`` → ``("rc/eliz2/8-9/69",)`` (8 & 9 Eliz. 2 c. 69).
    The router builds the same keys from a parsed citation.
    """
    series = instrument[0]
    if len(instrument) == 4:  # noqa: PLR2004 - regnal
        return (f"rc/{instrument[1].casefold()}/{instrument[2]}/{instrument[3]}",)
    year, number = instrument[1], instrument[2]
    if series in _UK_SI_SERIES:
        return (f"si/{year}/{number}",)
    if series == "ukpga":
        return (f"c/{year}/{number}",)
    prefix = _NUMBERED_SERIES_KEYS.get(series)
    return (f"{prefix}/{year}/{number}",) if prefix else ()
