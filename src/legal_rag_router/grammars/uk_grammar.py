"""UK citation grammar: the *shape* of UK citations (docs/grammar.md section 4).

Patterns run over folded text (``normalise.fold``: lower case, accents and look-alikes
folded, dashes as ``-``); every span reported points back into the original query, and
designators are read from the original so their case survives (``1ZA``, ``Part IV``).

Titles are never listed here: they are data in the index. Each pattern is tied to a row
of the surface-form table, and every pattern is linear (bounded repetition, no nested
unbounded quantifiers), which is the ReDoS guard the plan requires.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from typing import ClassVar, Final

from legal_rag_router.grammars.base import (
    Cue,
    CueKind,
    NumberMention,
    ProvisionMention,
    ProvisionRef,
)
from legal_rag_router.grammars.uk import INSTRUMENT_TYPE_WORDS, JURISDICTION, UNIT_PREFIXES
from legal_rag_router.normalise import Folded

__all__ = ["BOUNDARY_WORDS", "GRAMMAR", "UKGrammar", "int_to_roman", "roman_to_int"]

# ---------------------------------------------------------------------------- numerals

_ROMAN: Final = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
_ROMAN_TABLE: Final = (
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"),
    (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
)  # fmt: skip
_MAX_ROMAN: Final = 399


def int_to_roman(value: int) -> str:
    """``4`` -> ``"IV"`` (1 to 399)."""
    out: list[str] = []
    for number, numeral in _ROMAN_TABLE:
        while value >= number:
            out.append(numeral)
            value -= number
    return "".join(out)


def roman_to_int(text: str) -> int | None:
    """``"iv"`` -> 4; ``None`` unless ``text`` is a canonical Roman numeral (1 to 399)."""
    lowered = text.casefold()
    if not lowered or any(ch not in _ROMAN for ch in lowered):
        return None
    total = 0
    for i, ch in enumerate(lowered):
        value = _ROMAN[ch]
        following = _ROMAN[lowered[i + 1]] if i + 1 < len(lowered) else 0
        total += -value if following > value else value
    if not 0 < total <= _MAX_ROMAN or int_to_roman(total) != lowered.upper():
        return None
    return total


def numeral_variants(designator: str) -> list[str]:
    """Arabic and Roman spellings of a part number: ``"X"`` <-> ``"10"``, ``"2A"`` <-> ``"IIA"``."""
    out = [designator]
    arabic = re.fullmatch(r"(\d{1,3})([A-Za-z]?)", designator)
    if arabic and 0 < int(arabic.group(1)) <= _MAX_ROMAN:
        out.append(int_to_roman(int(arabic.group(1))) + arabic.group(2).upper())
    roman = re.fullmatch(r"([IVXLCivxlc]{1,7})([A-Za-z]?)", designator)
    if roman:
        value = roman_to_int(roman.group(1))
        if value is not None:
            out.append(f"{value}{roman.group(2).upper()}")
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------------------- patterns

# Provision-word forms (UK-P-01, 02, 10, 11, 12, 16), including fixed typo variants.
_UNIT_WORDS: Final = {
    "section": r"sections|section|secton|sectoin|setion|sction|scetion|sects\.?|sect\.?|secs\.?"
    r"|sec\.?|ss\.?|s\.?|§§|§",
    "article": r"articles|article|artcle|articel|arts\.?|art\.?",
    "regulation": r"regulations|regulation|regualtion|regulaton|regs\.?|reg\.?",
    "rule": r"rules|rule|r\.",
    "schedule": r"schedules|schedule|shedule|sched\.?|schs\.?|sch\.?",
    "part": r"parts|part|pts\.?|pt\.?",
    "chapter": r"chapters|chapter|chap\.?|ch\.?",
    "paragraph": r"paragraphs|paragraph|paras\.?|para\.?|pars\.?|par\.?",
}
_ANY_UNIT: Final = "|".join(_UNIT_WORDS.values())
# "124", "124ZA", "1A2", "3.1" … and letter-first designators: Sch. A1, Sch. B1, s. ZA1.
_NUM: Final = (
    r"(?:\d{1,4}[a-z]{0,3}(?:\d{1,2}[a-z]{0,2})?(?:\.\d{1,3}[a-z]?)?|[a-z]{1,2}\d{1,3}[a-z]{0,2})"
)
_ROMAN_D: Final = r"[ivxlc]{1,7}[a-z]?"
_DESIG: Final = rf"(?:{_NUM}|{_ROMAN_D})"
_SUB: Final = r"\(\s*[0-9a-z]{1,6}\s*\)"
_SUBS: Final = rf"(?:\s*{_SUB}){{0,6}}"
_SEP: Final = r"\s*(?:,|&|\band\b|\bor\b|\bto\b|-)\s*"
_OPEN: Final = r"\s*(?:et\s+seq\.?|onwards|ff\.?|and\s+following)"
_YEAR_RX: Final = r"(?:1[2-9]\d\d|20\d\d)"

_PROVISION_RE: Final = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(f"(?P<{u}>{p})" for u, p in _UNIT_WORDS.items()) + r")"
    r"(?![a-z])\s*"
    rf"(?P<first>{_DESIG})(?P<firstsubs>{_SUBS})"
    rf"(?P<more>(?:{_SEP}(?:(?:{_ANY_UNIT})(?![a-z])\s*)?{_DESIG}{_SUBS}){{0,20}})"
    rf"(?P<open>{_OPEN})?"
)
_MORE_ITEM_RE: Final = re.compile(
    rf"(?P<sep>{_SEP})(?:(?P<uw>{_ANY_UNIT})(?![a-z])\s*)?(?P<d>{_DESIG})(?P<subs>{_SUBS})"
)
_UNIT_WORD_RES: Final = {u: re.compile(rf"(?:{p})") for u, p in _UNIT_WORDS.items()}
_SUB_ITEM_RE: Final = re.compile(r"\(\s*([0-9a-z]{1,6})\s*\)")
# Every unit word ends at a word boundary: "Part 1" is never "par" + "t" (paragraph t).
_NESTED_RE: Final = re.compile(
    rf"\s*,?\s*(?:(?:{_UNIT_WORDS['paragraph']})(?![a-z])\s*(?P<para>{_NUM}|[a-z]{{1,2}})"
    rf"(?P<psubs>{_SUBS})"
    rf"|(?:{_UNIT_WORDS['part']})(?![a-z])\s+(?P<part>\d{{1,3}}[a-z]?|{_ROMAN_D})"
    rf"|(?:{_UNIT_WORDS['chapter']})(?![a-z])\s*(?P<chap>\d{{1,3}}[a-z]?|{_ROMAN_D})"
    rf"|(?:sub-?sections?|subs\.?)(?![a-z])\s*\(?\s*(?P<subsec>[0-9a-z]{{1,6}})\s*\)?)"
)
_OF_OUTER_RE: Final = re.compile(
    rf"\s+of\s+(?:the\s+)?(?:(?P<sch>{_UNIT_WORDS['schedule']})(?![a-z])\s*(?P<schd>{_DESIG})?"
    rf"|(?P<pt>{_UNIT_WORDS['part']})(?![a-z])\s+(?P<ptd>\d{{1,3}}[a-z]?|{_ROMAN_D}))"
)
_SUBSECTION_RE: Final = re.compile(  # UK-P-04: "subsection (2) of section 124"
    rf"(?<![a-z0-9])(?:sub-?sections?|subs\.?)\s*\(?\s*(?P<sub>[0-9a-z]{{1,6}})\s*\)?"
    rf"\s+of\s+(?:the\s+)?(?:{_UNIT_WORDS['section']})\s*(?P<d>{_NUM})(?P<subs>{_SUBS})"
)
_SOLE_SCHEDULE_RE: Final = re.compile(  # UK-P-09: "the Schedule, para 3"
    rf"(?<![a-z0-9])(?:the\s+)?(?:{_UNIT_WORDS['schedule']})\s*,?\s*"
    rf"(?:{_UNIT_WORDS['paragraph']})\s*(?P<para>{_NUM})(?P<psubs>{_SUBS})"
)
# "Regulations 2011" / "Rules 1998" is a title's type word and year, not reg. 2011.
_PLURAL_TYPE_YEAR_RE: Final = re.compile(rf"(?:regulations|rules|orders)\s+{_YEAR_RX}(?!\d)")

# Official numbers (UK-I-08, UK-I-09, UK-I-10).
_Y: Final = rf"(?P<y>{_YEAR_RX})"
_SI_RE: Final = re.compile(
    rf"(?<![a-z0-9])(?:s\s?\.?\s?i\s?\.?|statutory\s+instruments?)\s*(?:no\.?\s*)?{_Y}"
    rf"\s*(?:/|\s+no\.?\s*|\s+number\s+)(?P<n>\d{{1,5}})(?!\d)"
)
# List continuation after an SI number: "S.I. 2008/2767, 2010/641 and 2011/2425" or
# "S.I. 1988/663 and 1445" (same year). A bare continuation needs 3+ digits, so
# "S.I. 2011/3006, 2 employees" is not read as SI 2011/2.
_SI_CONTINUATION_RE: Final = re.compile(
    r"\s*(?:,|;|&|\band\b|\bor\b)\s*(?:s\s?\.?\s?i\s?\.?\s*)?"
    r"(?:(?P<y>(?:19|20)\d\d)\s*/\s*(?P<n>\d{1,5})|(?P<bare>\d{3,5}))(?![\d/])"
)
_BARE_SI_RE: Final = re.compile(rf"(?<![a-z0-9/.]){_Y}\s+no\.?\s*(?P<n>\d{{1,5}})(?!\d)")
_SSI_RE: Final = re.compile(
    rf"(?<![a-z0-9])s\s?\.?\s?s\s?\.?\s?i\s?\.?\s*{_Y}\s*/\s*(?P<n>\d{{1,5}})(?!\d)"
)
_SR_RE: Final = re.compile(
    rf"(?<![a-z0-9])s\s?\.?\s?r\s?\.?\s*(?:\(\s*n\.?\s?i\.?\s*\)\s*)?{_Y}"
    rf"\s*(?:/|\s+no\.?\s*)(?P<n>\d{{1,5}})(?!\d)"
)
_CHAPTER_RE: Final = re.compile(
    rf"(?<![a-z0-9/]){_Y}\s*,?\s*(?:c|ch|chapter)\.?\s*(?P<n>\d{{1,3}})(?![\d/])"
    rf"|(?<![a-z0-9])(?:c|ch|chapter)\.?\s*(?P<n2>\d{{1,3}})\s+of\s+(?P<y2>{_YEAR_RX})(?!\d)"
)
_REIGNS: Final = {
    "vict": "Vict", "victoria": "Vict", "geo": "Geo", "george": "Geo", "edw": "Edw",
    "edward": "Edw", "will": "Will", "william": "Will", "gul": "Will", "eliz": "Eliz",
    "elizabeth": "Eliz", "anne": "Ann", "ann": "Ann", "cha": "Cha", "car": "Cha",
    "jas": "Ja", "ja": "Ja", "jac": "Ja",
}  # fmt: skip
_REIGN_ALT: Final = "|".join(sorted(_REIGNS, key=len, reverse=True))
_ORD: Final = r"(?:\d|iii|ii|iv|vii|viii|vi|v|i)"
_REGNAL_RE: Final = re.compile(
    rf"(?<![a-z0-9])(?P<years>\d{{1,2}}(?:\s*(?:&|and|,)\s*\d{{1,2}}){{0,3}})\s+"
    rf"(?P<r1>{_REIGN_ALT})\.?\s*(?P<o1>{_ORD})?\.?"
    rf"(?:\s*(?:&|and)\s*(?P<y2>\d{{1,2}})\s+(?P<r2>{_REIGN_ALT})\.?\s*(?P<o2>{_ORD})?\.?)?"
    rf"(?:\s*,?\s*sess(?:ion)?\.?\s*(?P<sess>\d))?\s*,?\s*(?:c|ch|chapter|cap)\.?\s*"
    rf"(?P<n>\d{{1,3}})(?!\d)"
)

# Cues (UK-C-06 to UK-C-08, UK-C-19, UK-O-01 to UK-O-06).
_NEGATION_RE: Final = re.compile(
    r"(?<![a-z])(?:with\s+the\s+exception\s+of|except\s+for|except|excepting|excluding|"
    r"exclusive\s+of|other\s+than|apart\s+from|aside\s+from|save\s+for|but\s+not|rather\s+than|"
    r"instead\s+of|not)(?![a-z])"
)
_CONTEXT_REF_RE: Final = re.compile(
    rf"(?<![a-z])(?:the|that|this|said|same|such)\s+"
    rf"(?:(?:amending|principal|parent|enabling|relevant|former|latter|above(?:-mentioned)?|"
    rf"repealed|said|same)\s+)?(?:(?P<y>{_YEAR_RX})\s+)?"
    rf"(?P<t>act|order|regulations|rules|instrument|statute|measure)(?![a-z])"
    rf"(?!\s*,?\s*(?:of\s+)?\(?{_YEAR_RX})"
)
_DATE: Final = rf"(?:\d{{1,2}}\s+)?(?:[a-z]+\s+)?{_YEAR_RX}"
_TEMPORAL_RE: Final = re.compile(
    r"(?<![a-z])(?:"
    r"as\s+(?:it|they)?\s*(?:stood|was|were|in\s+force|originally\s+enacted|enacted|made|amended|"
    rf"applied|had\s+effect)(?:\s+(?:in|on|at|as\s+at|before|after|from|until))?(?:\s+{_DATE})?"
    r"|(?:original|enacted|as\s+made|point[-\s]in[-\s]time|historic(?:al)?)\s+(?:version|text|wording|form)"
    rf"|(?:in\s+force|applicable|in\s+effect|that\s+applied)\s+(?:on|at|in|as\s+at|during)\s+{_DATE}"
    rf"|(?:version|text|wording)\s+(?:of|from|as\s+at|at|in)\s+{_DATE}"
    r"|(?:before|prior\s+to|after|since|until)\s+(?:the\s+)?(?:\d{1,4}\s+)?amendments?"
    r")(?![a-z])"
)
# Dates ("1.3.2007", "1 April 1996", "6th April 2020") and territorial extents ("(E.W.)"):
# never citations, and their years are never instrument years (grammar.md UK-C-12).
_MONTHS: Final = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec"
)
_DATE_RE: Final = re.compile(
    r"(?<![\d.])\d{1,2}\s*[./]\s*\d{1,2}\s*[./]\s*(?:1[2-9]|20)\d\d(?!\d)"
    rf"|(?<![a-z\d])\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\.?,?\s+(?:1[2-9]|20)\d\d(?!\d)"
    rf"|(?<![a-z])(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+(?:1[2-9]|20)\d\d(?!\d)"
    r"|\((?:e|w|s|n\.?\s?i|e\.?\s?w|e\.?\s?w\.?\s?s|s\.?\s?w)\.?\)"
)
_OUT_OF_COVERAGE_RES: Final = (
    ("bill", re.compile(r"(?<![a-z])bill(?![a-z])")),
    (
        "case",
        re.compile(
            r"\[\s*(?:1[89]|20)\d\d\s*\]\s*(?:\d{1,3}\s+)?(?:uksc|ukhl|ukpc|ewca|ewhc|ukut|ukftt|"
            r"ukeat|ewfc|csih|csoh|hcj|nica|niqb|nich|ac|qb|kb|ch|wlr|all\s?er|icr|irlr|ecr|cmlr|"
            r"bclc)(?![a-z])"
        ),
    ),
    (
        "eu",
        re.compile(
            r"(?<![a-z])(?:uk\s+gdpr|gdpr|tfeu|teu)(?![a-z])"
            r"|(?<![a-z])(?:regulation|directive|decision)\s*\(\s*e[uc]\s*\)\s*(?:no\.?\s*)?"
            r"\d{1,4}\s*/\s*\d{1,4}"
            r"|(?<![a-z])directive\s+(?:no\.?\s*)?\d{2,4}/\d{1,4}/e[uc]c?"
        ),
    ),
    (
        "foreign",
        re.compile(
            r"(?<![a-z])(?:code\s+civil|code\s+du\s+travail|code\s+de\s+commerce|bgb|hgb|stgb|"
            r"u\.\s?s\.\s?c\.?|usc|c\.\s?f\.\s?r\.?|cfr)(?![a-z])"
        ),
    ),
    (
        "es",
        re.compile(
            r"(?<![a-z])(?:cdc|lgt|rdleg|rdl|codigo\s+(?:de\s+)?comercio|codigo\s+civil|"
            r"ley\s+(?:organica\s+)?\d{1,3}\s*/\s*\d{4}|real\s+decreto(?:-ley|\s+legislativo)?|"
            r"estatuto\s+de\s+los\s+trabajadores|ley\s+general\s+tributaria|boe-a-\d{4}-\d{1,6}|"
            r"articulo\s+\d|apartado)(?![a-z])"
        ),
    ),
)

BOUNDARY_WORDS: Final = frozenset(
    (
        "the",
        "of",
        "under",
        "in",
        "within",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "does",
        "do",
        "did",
        "how",
        "why",
        "when",
        "where",
        "per",
        "by",
        "to",
        "from",
        "for",
        "on",
        "at",
        "with",
        "about",
        "regarding",
        "re",
        "according",
        "see",
        "cf",
        "as",
        "and",
        "or",
        "but",
        "not",
        "except",
        "apart",
        "than",
        "into",
        "between",
        "applies",
        "apply",
        "say",
        "says",
        "said",
        "mean",
        "means",
        "explain",
        "describe",
        "summarise",
        "summarize",
        "show",
        "list",
        "give",
        "tell",
        "define",
        "check",
        "cite",
        "quote",
        "read",
        "find",
        "compare",
        "a",
        "an",
        "this",
        "that",
        "these",
        "those",
        "my",
        "our",
        "your",
        "their",
        "its",
        "his",
        "her",
        "please",
        "can",
        "could",
        "would",
        "should",
        "will",
        "shall",
        "may",
        "might",
        "must",
        "i",
        "we",
        "you",
        "they",
        "it",
        "there",
        "here",
        "if",
        "whether",
        "also",
        "any",
        "all",
        "some",
        "each",
        "every",
        "both",
        "s",
        "section",
        "sections",
        "art",
        "article",
        "reg",
        "regulation",
        "sch",
        "schedule",
        "part",
        "pt",
        "para",
        "paragraph",
        "rule",
        "r",
    )
)
"""Folded words at which a cited title's span stops when extended left (plan departure 1)."""

_PRIMARY_UNIT_ORDER: Final = {
    "section": ("s",),
    "article": ("s", "art"),  # an Act has sections: "art. 124" of an Act is s.124
    "regulation": ("reg", "s"),
    "rule": ("rule", "s"),
}
_SECONDARY_UNIT_ORDER: Final = {
    "section": ("art", "reg", "rule", "s"),  # an SI has articles/regulations/rules
    "article": ("art", "reg", "rule"),
    "regulation": ("reg", "art", "rule"),
    "rule": ("rule", "reg", "art"),
}


# ---------------------------------------------------------------------------- helpers


class _Reader:
    """Reads designators and spans from the original query for folded-text matches."""

    __slots__ = ("folded", "query")

    def __init__(self, query: str, folded: Folded) -> None:
        self.query = query
        self.folded = folded

    def text(self, start: int, end: int) -> str:
        o_start, o_end = self.folded.span(start, end)
        return unicodedata.normalize("NFKC", self.query[o_start:o_end]).strip()

    def group(self, match: re.Match[str], name: str, offset: int = 0) -> str:
        return self.text(offset + match.start(name), offset + match.end(name))

    def subs(self, match: re.Match[str], name: str, offset: int = 0) -> tuple[str, ...]:
        base = offset + match.start(name)
        body = match.group(name) or ""
        return tuple(
            self.text(base + s.start(1), base + s.end(1)) for s in _SUB_ITEM_RE.finditer(body)
        )


class _Claims:
    """Non-overlapping folded spans already turned into mentions."""

    __slots__ = ("_spans",)

    def __init__(self) -> None:
        self._spans: list[tuple[int, int]] = []

    def take(self, start: int, end: int) -> bool:
        if any(start < e and s < end for s, e in self._spans):
            return False
        self._spans.append((start, end))
        return True


def _unit_of(match: re.Match[str]) -> str:
    return next(u for u in _UNIT_WORDS if match.group(u) is not None)


def _is_roman(raw: str) -> bool:
    return re.fullmatch(_ROMAN_D, raw) is not None


def _ordinal(token: str | None) -> str:
    if not token:
        return ""
    return token if token.isdigit() else str(roman_to_int(token) or "")


def _regnal_key(match: re.Match[str]) -> str:
    years = re.findall(r"\d{1,2}", match.group("years"))  # the pattern starts with a year
    reign = _REIGNS[match.group("r1")] + _ordinal(match.group("o1"))
    if match.group("r2"):
        reign += f"and{match.group('y2')}{_REIGNS[match.group('r2')]}{_ordinal(match.group('o2'))}"
    if match.group("sess"):
        reign += f"Sess{match.group('sess')}"
    return f"rc/{reign.casefold()}/{'-'.join(years)}/{int(match.group('n'))}"


# ---------------------------------------------------------------------------- grammar


class UKGrammar:
    """UK citation grammar plugin (docs/grammar.md section 4)."""

    jurisdiction: ClassVar[str] = JURISDICTION
    registry: ClassVar[str | None] = "legislation.gov.uk"
    type_words: ClassVar[frozenset[str]] = INSTRUMENT_TYPE_WORDS
    boundary_words: ClassVar[frozenset[str]] = BOUNDARY_WORDS

    # ------------------------------------------------------------------ provisions

    def provisions(
        self, query: str, folded: Folded, *, limit: int | None = None
    ) -> list[ProvisionMention]:
        reader = _Reader(query, folded)
        text = folded.text
        claims = _Claims()
        found: list[ProvisionMention] = []

        # The two fixed phrasings are read first; they cannot overlap each other.
        for m in _SUBSECTION_RE.finditer(text):
            ref = ProvisionRef(
                (("section", reader.group(m, "d")),),
                (*reader.subs(m, "subs"), reader.group(m, "sub")),
            )
            claims.take(m.start(), m.end())
            found.append(self._mention(folded, m.start(), m.end(), (ref,)))

        for m in _SOLE_SCHEDULE_RE.finditer(text):
            ref = ProvisionRef(
                (("schedule", ""), ("paragraph", reader.group(m, "para"))), reader.subs(m, "psubs")
            )
            claims.take(m.start(), m.end())
            found.append(self._mention(folded, m.start(), m.end(), (ref,)))
        position = 0
        while (hit := _PROVISION_RE.search(text, position)) is not None:
            # Resume where the mention really ended: a list that stops at a different unit
            # ("s. 84, Sch. 14 para. 46") must leave "Sch. 14 ..." to be read again.
            position = hit.start() + 1
            if _PLURAL_TYPE_YEAR_RE.match(text, hit.start()):
                continue
            parsed = self._parse(reader, hit)
            if parsed is None:
                continue
            position = max(position, parsed[1])
            if claims.take(hit.start(), parsed[1]):
                found.append(parsed[0])
            if limit is not None and len(found) > limit:
                break  # the caller will refuse to route this many; stop working

        return sorted(found, key=lambda p: p.start)

    @staticmethod
    def _mention(
        folded: Folded,
        start: int,
        end: int,
        refs: tuple[ProvisionRef, ...],
        *,
        is_range: bool = False,
        open_ended: bool = False,
    ) -> ProvisionMention:
        o_start, o_end = folded.span(start, end)
        return ProvisionMention(o_start, o_end, refs, is_range=is_range, open_ended=open_ended)

    def _parse(self, reader: _Reader, m: re.Match[str]) -> tuple[ProvisionMention, int] | None:
        """One provision match -> (mention, folded end), or ``None`` if it is not a citation."""
        unit = _unit_of(m)
        first_raw = m.group("first")
        first = reader.group(m, "first")
        if _is_roman(first_raw) and (
            unit not in ("part", "chapter", "schedule") or not first.isupper()
        ):
            return None  # Roman only where used, and only in capitals: "part i think" is English
        first_ref = ProvisionRef(((unit, first),), reader.subs(m, "firstsubs"))
        refs, is_range, end = self._list(reader, m, unit, first_ref)
        if len(refs) == 1:
            units, subs, end = self._nested(
                reader, unit, list(refs[0].units), list(refs[0].subs), end
            )
            units, end = self._outer(reader, unit, units, end)
            refs = [ProvisionRef(tuple(units), tuple(subs))]
        mention = self._mention(
            reader.folded,
            m.start(),
            end,
            tuple(refs),
            is_range=is_range,
            open_ended=m.group("open") is not None,
        )
        return mention, end

    @staticmethod
    def _list(
        reader: _Reader, m: re.Match[str], unit: str, first: ProvisionRef
    ) -> tuple[list[ProvisionRef], bool, int]:
        """Lists ("ss. 94, 95 and 98") and ranges ("ss. 94-98", "sections 94 to 98").

        A list stops at a different unit word ("Part 2, Chapter 1" is one nested citation).
        Returns the refs, whether they form a range, and the folded end of the last item.
        """
        refs = [first]
        is_range = False
        offset = m.start("more")
        end = m.end("firstsubs")
        for item in _MORE_ITEM_RE.finditer(m.group("more") or ""):
            word = item.group("uw")
            if word is not None and not _UNIT_WORD_RES[unit].fullmatch(word):
                break
            designator = reader.group(item, "d", offset)
            if _is_roman(item.group("d")) and not designator.isupper():
                break
            refs.append(ProvisionRef(((unit, designator),), reader.subs(item, "subs", offset)))
            is_range = is_range or item.group("sep").strip() in ("-", "to")
            end = offset + item.end()
        if is_range and len(refs) != 2:  # noqa: PLR2004 - "ss.1-3 and 5" is read as a list
            is_range = False
        if (
            m.group("open") is not None
            and len(refs) == len(_MORE_ITEM_RE.findall(m.group("more") or "")) + 1
        ):
            end = m.end()
        return refs, is_range, end

    @staticmethod
    def _nested(
        reader: _Reader, unit: str, units: list[tuple[str, str]], subs: list[str], end: int
    ) -> tuple[list[tuple[str, str]], list[str], int]:
        """Inner units after the first unit.

        "Sch. 2 para 4(1)", "Part 2, Chapter 1", "s.124 subsection (2)".
        """
        text = reader.folded.text
        nested = _NESTED_RE.match(text, end)
        while nested is not None:
            last = units[-1][0]
            if (
                nested.group("para") is not None
                and last in ("schedule", "part")
                and unit == "schedule"
            ):
                units.append(("paragraph", reader.group(nested, "para")))
                subs = list(reader.subs(nested, "psubs"))
            elif nested.group("part") is not None and unit == "schedule" and last == "schedule":
                units.append(("part", reader.group(nested, "part")))
            elif nested.group("chap") is not None and unit == "part" and last == "part":
                units.append(("chapter", reader.group(nested, "chap")))
            elif nested.group("subsec") is not None and unit == "section" and not subs:
                subs.append(reader.group(nested, "subsec"))
            else:
                break
            end = nested.end()
            nested = _NESTED_RE.match(text, end)
        return units, subs, end

    @staticmethod
    def _outer(
        reader: _Reader, unit: str, units: list[tuple[str, str]], end: int
    ) -> tuple[list[tuple[str, str]], int]:
        """Outer unit after "of": "para 4 of Schedule 2", "Chapter 1 of Part 2"."""
        outer = _OF_OUTER_RE.match(reader.folded.text, end)
        if outer is None:
            return units, end
        if outer.group("sch") is not None and unit == "paragraph":
            schedule = reader.group(outer, "schd") if outer.group("schd") else ""
            return [("schedule", schedule), *units], outer.end()
        if outer.group("pt") is not None and unit == "chapter":
            return [("part", reader.group(outer, "ptd")), *units], outer.end()
        return units, end

    @staticmethod
    def _schedule_paths(ref: ProvisionRef) -> list[tuple[str, ...]]:
        head = ref.units[0][1]
        rest = dict(ref.units[1:])
        schedule = "sch" + head if head else "sch"
        if "paragraph" in rest:
            return [(schedule, "para" + rest["paragraph"], *ref.subs)]
        if "part" in rest:
            return [(schedule, "pt" + p) for p in numeral_variants(rest["part"])]
        return [(schedule, *ref.subs)]

    def provision_paths(self, ref: ProvisionRef, *, primary: bool) -> list[tuple[str, ...]]:
        head_unit, head = ref.units[0]
        rest = dict(ref.units[1:])
        subs = tuple(ref.subs)
        if head_unit == "schedule":
            return self._schedule_paths(ref)
        if head_unit == "part":
            chapter = (f"ch{rest['chapter']}",) if "chapter" in rest else ()
            return [("pt" + p, *chapter) for p in numeral_variants(head)]
        if head_unit == "chapter":
            return [("ch" + head,)]
        if head_unit == "paragraph":
            return [("para" + head, *subs)]
        order = _PRIMARY_UNIT_ORDER if primary else _SECONDARY_UNIT_ORDER
        prefixes = order.get(head_unit, (UNIT_PREFIXES.get(head_unit, head_unit),))
        return [(prefix + head, *subs) for prefix in prefixes]

    # ------------------------------------------------------------------ numbers

    def numbers(self, query: str, folded: Folded) -> list[NumberMention]:
        text = folded.text
        claims = _Claims()
        found: list[NumberMention] = []

        def add(m: re.Match[str], key: str, kind: str, year: str | None, number: str) -> None:
            if claims.take(m.start(), m.end()):
                o_start, o_end = folded.span(m.start(), m.end())
                found.append(
                    NumberMention(o_start, o_end, key, kind, int(year) if year else None, number)
                )

        for m in _REGNAL_RE.finditer(text):
            add(m, _regnal_key(m), "act", None, m.group("n"))
        numbered: tuple[tuple[re.Pattern[str], str, str], ...] = (
            (_SSI_RE, "ssi", "ssi"),
            (_SR_RE, "sr", "sr"),
            (_SI_RE, "si", "si"),
        )
        for pattern, prefix, kind in numbered:
            for m in pattern.finditer(text):
                year = m.group("y")
                add(m, f"{prefix}/{year}/{int(m.group('n'))}", kind, year, m.group("n"))
                for more in self._continuation(text, m.end()):
                    year = more.group("y") or year
                    number = more.group("n") or more.group("bare")
                    add(more, f"{prefix}/{year}/{int(number)}", kind, year, number)
        for m in _CHAPTER_RE.finditer(text):
            year = m.group("y") or m.group("y2")
            number = m.group("n") or m.group("n2")
            add(m, f"c/{year}/{int(number)}", "act", year, number)
        for m in _BARE_SI_RE.finditer(text):
            add(m, f"si/{m.group('y')}/{int(m.group('n'))}", "si", m.group("y"), m.group("n"))
        return sorted(found, key=lambda n: n.start)

    @staticmethod
    def _continuation(text: str, position: int) -> list[re.Match[str]]:
        """The rest of an SI number list starting at ``position`` (bounded)."""
        found: list[re.Match[str]] = []
        while len(found) < 24:  # noqa: PLR2004 - the router refuses longer lists anyway
            more = _SI_CONTINUATION_RE.match(text, position)
            if more is None:
                break
            found.append(more)
            position = more.end()
        return found

    # ------------------------------------------------------------------ cues

    def cues(self, query: str, folded: Folded) -> list[Cue]:
        text = folded.text
        cues: list[Cue] = []

        def scan(
            pattern: re.Pattern[str], kind: CueKind, detail: Callable[[re.Match[str]], str | None]
        ) -> None:
            for m in pattern.finditer(text):
                o_start, o_end = folded.span(m.start(), m.end())
                cues.append(Cue(o_start, o_end, kind, query[o_start:o_end], detail(m)))

        scan(_NEGATION_RE, "negation", lambda _: None)
        scan(_CONTEXT_REF_RE, "context_ref", lambda m: m.group("y"))
        scan(_TEMPORAL_RE, "temporal", lambda _: None)
        scan(_DATE_RE, "date", lambda _: None)
        for name, pattern in _OUT_OF_COVERAGE_RES:
            scan(pattern, "out_of_coverage", lambda _, name=name: name)  # type: ignore[misc]
        return sorted(cues, key=lambda c: c.start)


GRAMMAR: Final = UKGrammar()
