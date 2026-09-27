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
from typing import Final

__all__ = [
    "MAX_QUERY_CHARS",
    "PARTICLES",
    "Folded",
    "Token",
    "fold",
    "split_title_year",
    "title_key",
    "title_words",
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
    """Folded text plus, for each folded character, its index in the original string."""

    text: str
    origin: tuple[int, ...]

    def span(self, start: int, end: int) -> tuple[int, int]:
        """Map a ``[start, end)`` span of folded text back to the original string."""
        if start >= end:
            anchor = self.origin[start] if start < len(self.origin) else self._end()
            return anchor, anchor
        return self.origin[start], self.origin[end - 1] + 1

    def _end(self) -> int:
        return self.origin[-1] + 1 if self.origin else 0


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

    NFKC, casefold, accent folding (``artículo`` → ``articulo``), look-alike letters,
    Unicode dashes → ``-``, curly quotes → straight, any whitespace → one space.
    """
    chars: list[str] = []
    origin: list[int] = []
    for index, ch in enumerate(text):
        folded = _fold_char(ch)
        if folded == " " and chars and chars[-1] == " ":
            continue  # collapse whitespace runs
        for c in folded:
            chars.append(c)
            origin.append(index)
    return Folded("".join(chars), tuple(origin))


@dataclass(frozen=True, slots=True)
class Token:
    """One token of a query: folded text, kind, and its span in the original query."""

    text: str
    kind: str  # "word" | "number" | "punct"
    start: int
    end: int


def tokenise(text: str) -> list[Token]:
    """Split ``text`` into tokens (words, digit runs, single punctuation characters)."""
    folded = fold(text)
    tokens: list[Token] = []
    for match in _TOKEN.finditer(folded.text):
        value = match.group()
        kind = "number" if value.isdigit() else "word" if value.isalpha() else "punct"
        start, end = folded.span(match.start(), match.end())
        tokens.append(Token(value, kind, start, end))
    return tokens


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
    folded = fold(title).text.replace("&", " and ").replace("'", "")
    words = [t.group() for t in _TOKEN.finditer(folded) if t.group().isalnum()]
    return tuple(w for w in words if w not in PARTICLES)


def title_key(words: tuple[str, ...] | list[str], year: int | None = None) -> str:
    """Canonical lookup key for a title: ``"employment rights act|1996"``."""
    base = " ".join(words)
    return f"{base}|{year}" if year is not None else base
