"""Deterministic text normalisation shared by the index build and the router.

Two layers:

* :func:`fold` maps text to a comparison form character by character (NFKC, casefold,
  accent folding, look-alike letters, dashes and quotes) while keeping a map from every
  output character back to its position in the input, so every token and span the router
  reports points at the user's original query.
* :func:`tokenise` splits folded text into word/number/punctuation tokens with offsets
  into the *original* string.

Title keys (:func:`title_words`, :func:`title_key`) are built from the same functions,
so a title indexed at build time and the same title typed in a query always meet.
Nothing here depends on a model or on data: the same input always gives the same output.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, NamedTuple

__all__ = [
    "MAX_QUERY_CHARS",
    "PARTICLES",
    "Folded",
    "Token",
    "fold",
    "split_title_year",
    "title_key",
    "title_words",
    "title_words_folded",
    "tokenise",
]

MAX_QUERY_CHARS: Final = 4096
"""Hard cap on query length. Longer queries return ``ROUTE_UNRESOLVED``, flagged."""

# Look-alike letters (Cyrillic, Greek) mapped to the Latin letter they imitate, applied
# after casefolding: "Act" spelled with a Cyrillic A (U+0410) must never differ from "Act".
# Written as escapes so the table itself is unambiguous to read.
_CONFUSABLES: Final = str.maketrans(
    {
        "\u0430": "a", "\u0432": "b", "\u0435": "e", "\u043a": "k", "\u043c": "m", "\u043d": "h",
        "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0442": "t", "\u0443": "y", "\u0445": "x",
        "\u0456": "i", "\u0458": "j", "\u0455": "s", "\u0501": "d", "\u0261": "g", "\u04bb": "h",
        "\u04cf": "l", "\u03b1": "a", "\u03bf": "o", "\u03c1": "p", "\u03b5": "e", "\u03b9": "i",
        "\u03ba": "k", "\u03bd": "v", "\u03c4": "t", "\u03c5": "u", "\u03c7": "x",
    }
)  # fmt: skip
_DASHES: Final = frozenset("\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d")
_QUOTES: Final = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u201c": '"', "”": '"', "\u201e": '"', "‟": '"', "\u2033": '"',
}  # fmt: skip

PARTICLES: Final = frozenset({"the", "of", "and", "a", "an", "de", "del", "la", "los", "y"})
"""Words dropped from title keys ("Código de Comercio" = "codigo comercio")."""

_TOKEN: Final = re.compile(r"[^\W\d_]+|\d+|\u00a7|\S", re.UNICODE)
_YEAR_SUFFIX: Final = re.compile(r"^(?P<title>.*?)[\s,]*\(?(?P<year>1[2-9]\d\d|20\d\d)\)?\s*$")


@dataclass(frozen=True, slots=True)
class Folded:
    """Folded text plus a map from each folded character to its index in the original.

    ``origin`` is ``None`` when folding kept every character in place (all-ASCII input),
    so the common case pays nothing for the map.
    """

    text: str
    origin: tuple[int, ...] | None

    def span(self, start: int, end: int) -> tuple[int, int]:
        """Map a ``[start, end)`` span of folded text back to the original string."""
        if self.origin is None:
            return start, end
        if start >= end:  # an empty span: anchor it where it starts
            if start < len(self.origin):
                anchor = self.origin[start]
            else:
                anchor = self.origin[-1] + 1 if self.origin else 0
            return anchor, anchor
        return self.origin[start], self.origin[end - 1] + 1


_ASCII_WHITESPACE: Final = str.maketrans("\t\n\r\x0b\x0c", "     ")


@lru_cache(maxsize=8192)
def _fold_char(ch: str) -> str:
    if ch in _DASHES:
        return "-"
    if ch in _QUOTES:
        return _QUOTES[ch]
    if ch.isspace():
        return " "
    out = []
    for c in unicodedata.normalize("NFKC", ch).casefold():
        decomposed = unicodedata.normalize("NFD", c)
        base = "".join(d for d in decomposed if not unicodedata.combining(d))
        out.append(base.translate(_CONFUSABLES))
    return "".join(out)


def fold(text: str) -> Folded:
    """Fold ``text`` for matching, keeping an offset map back to ``text``.

    NFKC, casefold, accent folding (``artículo`` -> ``articulo``), look-alike letters,
    Unicode dashes -> ``-``, curly quotes -> straight, any whitespace character -> a space.
    Whitespace is mapped one to one (not collapsed); patterns match runs with ``\\s+``.
    """
    if text.isascii():  # fast path: lower-casing keeps every offset
        return Folded(text.lower().translate(_ASCII_WHITESPACE), None)
    pieces = list(map(_fold_char, text))
    folded = "".join(pieces)
    if len(folded) == len(text) and all(pieces):
        return Folded(folded, None)  # every character folded to exactly one: offsets kept
    origin = tuple(index for index, piece in enumerate(pieces) for _ in piece)
    return Folded(folded, origin)


class Token(NamedTuple):
    """One token of a query: folded text, kind, and its span in the original query."""

    text: str
    kind: str  # "word" | "number" | "punct"
    start: int
    end: int


_KINDED_TOKEN: Final = re.compile(r"(?P<word>[^\W\d_]+)|(?P<number>\d+)|(?P<punct>\u00a7|\S)")


def tokenise(text: str, folded: Folded | None = None) -> list[Token]:
    """Split ``text`` into tokens (words, digit runs, single punctuation characters).

    Pass ``folded`` (``fold(text)``) when it is already at hand, to fold only once.
    """
    folded = folded if folded is not None else fold(text)
    matches = _KINDED_TOKEN.finditer(folded.text)
    if folded.origin is None:  # offsets unchanged by folding: no mapping needed
        return [Token(m.group(), m.lastgroup or "punct", m.start(), m.end()) for m in matches]
    span = folded.span
    return [Token(m.group(), m.lastgroup or "punct", *span(m.start(), m.end())) for m in matches]


def split_title_year(title: str) -> tuple[str, int | None]:
    """Split a trailing year off a title: ``"Employment Rights Act 1996"`` → (…, 1996)."""
    match = _YEAR_SUFFIX.match(title)
    if match is None or not match.group("title").strip():
        return title.strip(), None
    return match.group("title").strip(), int(match.group("year"))


def title_words(title: str) -> tuple[str, ...]:
    """Content words of a title, folded, in order, with particles and punctuation dropped.

    Numbers are kept (``"(No. 2)"`` → ``("no", "2")``): they distinguish real instruments.
    ``&`` reads as ``and`` (a particle); apostrophes join (``workers'`` → ``workers``);
    hyphens split (``anti-social`` → ``anti``, ``social``).
    """
    return title_words_folded(fold(title).text)


def title_words_folded(folded: str) -> tuple[str, ...]:
    """:func:`title_words` for text that is already folded."""
    cleaned = folded.replace("&", " and ").replace("'", "")
    words = [t.group() for t in _TOKEN.finditer(cleaned) if t.group().isalnum()]
    return tuple(w for w in words if w not in PARTICLES)


def title_key(words: tuple[str, ...] | list[str], year: int | None = None) -> str:
    """Canonical lookup key for a title: ``"employment rights act|1996"``."""
    base = " ".join(words)
    return f"{base}|{year}" if year is not None else base
