"""The router: one query in, exactly one :class:`~legal_rag_router.result.RouteResult` out.

Pipeline (plan, "How matching works"):

    normalise -> identifiers -> provisions / numbers / cues (grammar) -> titles (index n-grams)
    -> exclusion -> link provisions to instruments -> resolve against the index -> result

The router is a stateless function over an immutable index: no sessions, no model, no
network, no disk I/O per query. The caller owns the conversation and passes the previous
turn's coordinates as ``context``. A form the grammar does not know produces no match and
fails safe to ``ROUTE_UNRESOLVED`` (discover-then-bind); binding always needs a positive
match that exists in the index.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Final

from legal_rag_router.coordinate import Coordinate
from legal_rag_router.grammars.base import Cue, NumberMention, ProvisionMention, ProvisionRef
from legal_rag_router.grammars.uk_grammar import GRAMMAR as UK_GRAMMAR
from legal_rag_router.grammars.uk_grammar import UKGrammar
from legal_rag_router.identifiers import IdentifierMention, scan_identifiers
from legal_rag_router.index import InstrumentInfo, RouterIndex, load_index
from legal_rag_router.normalise import (
    MAX_QUERY_CHARS,
    PARTICLES,
    Folded,
    Token,
    fold,
    title_key,
    title_words,
    title_words_folded,
    tokenise,
)
from legal_rag_router.result import (
    Candidate,
    NextAction,
    ParsedCitation,
    Resolution,
    RouteContext,
    RouteResult,
    RouteStatus,
    Source,
)
from legal_rag_router.typo import TitleVerdict, TypoPolicy, analyse_title, damerau

__all__ = ["Router"]

log = logging.getLogger("legal_rag_router")
miss_log = logging.getLogger("legal_rag_router.misses")

MAX_ANCHORS: Final = 16
MAX_MENTIONS: Final = 24
MAX_TITLE_WORDS: Final = 28
MAX_CUES: Final = 64
MAX_TITLE_LOOKUPS: Final = 320
"""Work cap per query. Past it the query is too complex to route safely: it fails safe to
``ROUTE_UNRESOLVED`` rather than binding on a partial reading (DoS and misroute guard)."""
MAX_CITED_WORDS: Final = 20
MAX_RANGE: Final = 20
MAX_CANDIDATES_SHOWN: Final = 8
MAX_BEFORE_GAP: Final = 2
MAX_AFTER_GAP: Final = 4
_CAPS_SHARE: Final = 0.6

_STOP_PUNCT: Final = frozenset(",;:?!")
_AFTER_CONNECTORS: Final = frozenset(
    {
        "of",
        "under",
        "in",
        "within",
        "to",
        "from",
        "the",
        "said",
        "this",
        "that",
        "for",
        "per",
        "by",
        "at",
    }
)
_BEFORE_CONNECTORS: Final = frozenset({"s", "at", "in", "under"})
_LIST_JOINERS: Final = frozenset({"and", "or", "nor", "&"})
_CLAUSE_BREAK_RE: Final = re.compile(r"[;?!]|(?P<word>\w*)\.\s+(?=[A-Z(\u201c\"])")
# A full stop after these ends an abbreviation, not a sentence: "Sch. B1", "Pt. II", "art. A1".
_ABBREVIATED: Final = (
    "s ss sec sect sch schs sched para paras par pars art arts reg regs r pt pts ch chap "
    "no nos c apdo núm num"
)
_ABBREVIATIONS: Final = frozenset(_ABBREVIATED.split())
_NEGATION_FILLERS: Final = frozenset({"the", "a", "an", "in", "under", "any", "of", "for", "to"})
_YEAR_RE: Final = re.compile(r"1[2-9]\d\d|20\d\d")
# "Housing and Planning Act 2016 (c. 22)", "(c.42, SIF 81:1, 2)": a chapter number in brackets
# right after a cited title belongs to that citation.
_CHAPTER_NOTE_RE: Final = re.compile(
    r"\s*\(\s*c\s*\.?\s*(?P<n>\d{1,3})\b[^()]{0,40}\)", re.IGNORECASE
)
# Words that can start a citation without a digit: unit words (with Roman numbers),
# context references, and out-of-coverage cues ("Bill", "GDPR", "CdC", "código", "ley" …).
_TRIGGER_WORDS: Final = frozenset(
    {
        "part", "parts", "pt", "chapter", "ch", "schedule", "sch", "the schedule", "bill",
        "gdpr", "tfeu", "teu", "cdc", "lgt", "lec", "rdl", "rdleg", "codigo", "ley", "real",
        "estatuto", "articulo", "apartado", "bgb", "hgb", "stgb", "usc", "cfr", "code",
        "statute", "instrument",
    }
)  # fmt: skip
# Words that occur inside titles ("Rights of Employment", "Offences against the Person",
# "Health and Safety at Work"). Extending a cited title left crosses one only when a
# content word follows it; otherwise it is a boundary.
_SOFT_PARTICLES: Final = frozenset(
    {"of", "and", "the", "for", "from", "against", "to", "on", "with", "at", "&"}
)

_PRIORITY: Final = (
    RouteStatus.INSTRUMENT_NOT_FOUND,
    RouteStatus.PROVISION_NOT_FOUND,
    RouteStatus.AMBIGUOUS,
    RouteStatus.OUT_OF_COVERAGE,
    RouteStatus.BOUNDED,
    RouteStatus.UNRESOLVED,
)
_NEXT_ACTION: Final = {
    RouteStatus.BOUNDED: NextAction.RETRIEVE_BOUNDED,
    RouteStatus.AMBIGUOUS: NextAction.ASK_USER,
    RouteStatus.INSTRUMENT_NOT_FOUND: NextAction.REFUSE,
    RouteStatus.PROVISION_NOT_FOUND: NextAction.REFUSE,
    RouteStatus.OUT_OF_COVERAGE: NextAction.DECLARE_OUT_OF_COVERAGE,
    RouteStatus.UNRESOLVED: NextAction.DISCOVER_THEN_BIND,
}
_OOC_LABELS: Final = {
    "bill": "a Bill (not legislation until enacted)",
    "case": "case law",
    "eu": "EU or retained EU law",
    "foreign": "another legal system",
    "es": "Spanish law (not yet indexed)",
    "series": "a series not indexed",
}


# ---------------------------------------------------------------------------- mentions


@dataclass(slots=True)
class _Instrument:
    """An instrument mention and everything known about it before resolution."""

    start: int
    end: int
    kind: str  # identifier number title alias acronym anchor context_ref out_of_coverage
    verdict: str  # resolved | ambiguous | not_found | out_of_coverage | context
    ids: tuple[str, ...] = ()
    coverage: tuple[str, ...] = ()
    title_as_cited: str | None = None
    year: int | None = None
    number: str | None = None
    instrument_type: str | None = None
    corrections: tuple[tuple[str, str], ...] = ()
    suggestions: tuple[str, ...] = ()
    reason: str | None = None
    identifier_key: str | None = None
    clear_claim: bool = False
    jurisdiction: str | None = "uk"
    excluded: bool = False
    narrow_by_provision: bool = False
    note: str | None = None
    """A line for ``messages`` when the mention binds (e.g. cited by a former title)."""
    provisions: list[ProvisionMention] = field(default_factory=list)


@dataclass(slots=True)
class _Outcome:
    status: RouteStatus
    coordinates: list[Coordinate] = field(default_factory=list)
    excluded: list[Coordinate] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    suggestions: list[Candidate] = field(default_factory=list)
    corrections: tuple[tuple[str, str], ...] = ()
    clarification: str | None = None
    message: str | None = None
    reason: str | None = None
    repealed: bool = False
    source: Source = "grammar"
    citation: ParsedCitation | None = None
    live_checkable: bool = False


@dataclass(slots=True)
class _Scan:
    query: str
    tokens: list[Token]
    identifiers: list[IdentifierMention]
    provisions: list[ProvisionMention]
    numbers: list[NumberMention]
    cues: list[Cue]
    blocked: list[tuple[int, int]]
    lookups: int = 0
    _blocked_starts: list[int] = field(default_factory=list)
    _blocked_ends: list[int] = field(default_factory=list)
    _token_starts: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        merged: list[list[int]] = []
        for start, end in sorted(self.blocked):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        self._blocked_starts = [m[0] for m in merged]
        self._blocked_ends = [m[1] for m in merged]
        self._token_starts = [t.start for t in self.tokens]

    def is_blocked(self, position: int) -> bool:
        """True when ``position`` lies inside an identifier, number, provision or cue span."""
        i = bisect_right(self._blocked_starts, position) - 1
        return i >= 0 and position < self._blocked_ends[i]

    def gap_words(self, start: int, end: int) -> list[str]:
        """Token texts lying wholly within ``[start, end)``."""
        i = bisect_left(self._token_starts, start)
        out: list[str] = []
        while i < len(self.tokens) and self.tokens[i].end <= end:
            out.append(self.tokens[i].text)
            i += 1
        return out

    def words(self, start: int, end: int) -> tuple[str, ...]:
        """``title_words`` of the text from token ``start`` to token ``end`` (inclusive).

        Rebuilt from the already-folded tokens (adjacent tokens touch, others are separated
        by a space) and passed through the same function the index build uses.
        """
        parts: list[str] = []
        previous_end: int | None = None
        for token in self.tokens[start : end + 1]:
            if previous_end is not None and token.start != previous_end:
                parts.append(" ")
            parts.append(token.text)
            previous_end = token.end
        return title_words_folded("".join(parts))


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


# ---------------------------------------------------------------------------- router


class Router:
    """Deterministic citation pre-router over a verified, immutable index.

    Thread-safe: ``route`` reads only immutable state.
    """

    def __init__(
        self,
        index: RouterIndex,
        *,
        log_misses: bool = False,
        redact: Callable[[str], str] | None = None,
        typo_policy: TypoPolicy | None = None,
    ) -> None:
        """
        Args:
            index: a loaded index (:func:`legal_rag_router.index.load_index`).
            log_misses: emit a structured ``legal_rag_router.misses`` event when a query has a
                citation signal but routes ``ROUTE_UNRESOLVED`` (plan, "Missed patterns" 3).
                Off by default.
            redact: turns a query into loggable text for that event. Without it the event
                carries only a hash and the length: query text is never logged by default.
            typo_policy: typo-tier thresholds (tuned on the dev slice; frozen with the seal).
        """
        self._index = index
        self._grammar: UKGrammar = UK_GRAMMAR
        self._log_misses = log_misses
        self._redact = redact
        self._policy = typo_policy or TypoPolicy()
        self._alias_last_words = frozenset(key.split()[-1] for key in index.aliases)
        self._alias_words = {tuple(key.split()) for key in index.aliases}
        self._alias_max_words = max((len(k) for k in self._alias_words), default=0)
        self._salient = tuple(
            dict.fromkeys(str(v["id"]) for v in index.aliases.values() if v.get("salient"))
        )
        self._snapshot_year = date.fromisoformat(index.snapshot).year
        # Prefilter (plan pipeline): text with none of these cannot hold a citation.
        triggers = sorted(
            {*self._grammar.type_words, *self._alias_last_words, *_TRIGGER_WORDS},
            key=len,
            reverse=True,
        )
        self._prefilter = re.compile(
            r"[0-9/_\u00a7]|(?<![a-z])(?:" + "|".join(map(re.escape, triggers)) + r")(?![a-z])"
        )

    @classmethod
    def from_path(cls, path: str | Path, **options: object) -> Router:
        """Load and verify the index at ``path`` (hashes, format version), then build a router."""
        return cls(load_index(path), **options)  # type: ignore[arg-type]

    @property
    def index(self) -> RouterIndex:
        return self._index

    # ------------------------------------------------------------------ public

    def route(
        self,
        query: str,
        *,
        context: RouteContext | Sequence[Coordinate | str] | None = None,
        jurisdictions: Iterable[str] | None = None,
    ) -> RouteResult:
        """Route one query. Never raises for any string input."""
        started = time.perf_counter_ns()
        try:
            result = self._route(query, context, jurisdictions)
        except Exception:  # a bug or a corrupt index must fail safe, never crash the caller
            log.exception("router error; failing safe to ROUTE_UNRESOLVED")
            result = self._result(RouteStatus.UNRESOLVED, reason="internal_error")
        result = replace(result, latency_ns=time.perf_counter_ns() - started)
        if self._log_misses and result.status is RouteStatus.UNRESOLVED and result.citation_signal:
            self._emit_miss(query, result)
        return result

    # ------------------------------------------------------------------ pipeline

    def _result(self, status: RouteStatus, **fields: object) -> RouteResult:
        return RouteResult(
            status=status,
            next_action=_NEXT_ACTION[status],
            index_snapshot=self._index.snapshot,
            **fields,  # type: ignore[arg-type]
        )

    def _route(
        self,
        query: object,
        context: RouteContext | Sequence[Coordinate | str] | None,
        jurisdictions: Iterable[str] | None,
    ) -> RouteResult:
        rejected = self._precheck(query, jurisdictions)
        if rejected is not None:
            return rejected
        assert isinstance(query, str)  # noqa: S101 - established by _precheck
        folded = fold(query)
        if not self._prefilter.search(folded.text):
            return self._result(RouteStatus.UNRESOLVED)
        scan = self._scan(query, folded)
        too_big = self._too_big(scan)
        if too_big is not None:
            return too_big
        instruments = self._instruments(scan)
        if scan.lookups > MAX_TITLE_LOOKUPS:
            return self._result(RouteStatus.UNRESOLVED, reason="too_complex", citation_signal=True)
        if len(instruments) + len(scan.provisions) > MAX_MENTIONS:
            return self._result(
                RouteStatus.UNRESOLVED, reason="too_many_citations", citation_signal=True
            )
        excluded_provisions = self._apply_exclusions(scan, instruments)
        context_instrument = self._context_instrument(context)
        unlinked = self._link(scan, instruments)
        outcomes = [
            self._resolve_instrument(m, excluded_provisions, context_instrument)
            for m in instruments
        ]
        outcomes += [
            self._resolve_unlinked(p, instruments, context_instrument, excluded_provisions)
            for p in unlinked
        ]
        temporal = next((c.text for c in scan.cues if c.kind == "temporal"), None)
        signal = (
            bool(scan.identifiers or scan.numbers or scan.provisions or instruments)
            or any(c.kind == "out_of_coverage" for c in scan.cues)
            or any(t.text in self._grammar.type_words for t in scan.tokens)
            or "legislation.gov.uk" in scan.query.casefold()
        )
        return self._assemble(scan, outcomes, temporal=temporal, signal=signal)

    # ------------------------------------------------------------------ scanning

    def _too_big(self, scan: _Scan) -> RouteResult | None:
        """Caps checked before any pairwise work, so every later loop is bounded and routing
        stays linear in the query length. Past a cap the query fails safe (DoS guard)."""
        if max(len(scan.provisions), len(scan.numbers), len(scan.identifiers)) > MAX_MENTIONS:
            return self._result(
                RouteStatus.UNRESOLVED, reason="too_many_citations", citation_signal=True
            )
        if len(scan.cues) > MAX_CUES:
            return self._result(RouteStatus.UNRESOLVED, reason="too_complex", citation_signal=True)
        return None

    def _precheck(self, query: object, jurisdictions: Iterable[str] | None) -> RouteResult | None:
        """Queries the router declines before scanning, failing safe to ROUTE_UNRESOLVED."""
        if not isinstance(query, str):
            return self._result(RouteStatus.UNRESOLVED, reason="not_a_string")
        if len(query) > MAX_QUERY_CHARS:
            return self._result(
                RouteStatus.UNRESOLVED, reason="query_too_long", citation_signal=True
            )
        if jurisdictions is not None and "uk" not in set(jurisdictions):
            return self._result(RouteStatus.UNRESOLVED, reason="no_jurisdiction_in_scope")
        return None

    def _scan(self, query: str, folded: Folded) -> _Scan:
        tokens = tokenise(query, folded)
        identifiers = scan_identifiers(query)
        id_spans = [(m.start, m.end) for m in identifiers]
        provisions = [
            p
            for p in self._grammar.provisions(query, folded, limit=MAX_MENTIONS)
            if not any(_overlaps((p.start, p.end), s) for s in id_spans)
        ]
        numbers = [
            n
            for n in self._grammar.numbers(query, folded)
            if not any(_overlaps((n.start, n.end), s) for s in id_spans)
        ]
        cues = self._grammar.cues(query, folded)
        blocked: list[tuple[int, int]] = [
            *id_spans,
            *((p.start, p.end) for p in provisions),
            *((n.start, n.end) for n in numbers),
        ]
        blocked += [
            (c.start, c.end) for c in cues if c.kind in ("temporal", "date", "out_of_coverage")
        ]
        return _Scan(query, tokens, identifiers, provisions, numbers, cues, blocked)

    def _instruments(self, scan: _Scan) -> list[_Instrument]:
        found: list[_Instrument] = []
        found += [self._identifier_mention(m) for m in scan.identifiers]
        found += [self._number_mention(n) for n in scan.numbers]
        found += self._title_mentions(scan)
        found += self._cue_mentions(scan, found)
        found.sort(key=lambda m: m.start)
        # Drop overlaps: earlier-listed kinds win (identifier > number > title > cue).
        kept: list[_Instrument] = []
        for mention in found:
            if not any(_overlaps((mention.start, mention.end), (k.start, k.end)) for k in kept):
                kept.append(mention)
        return self._refer_back(scan, self._merge_title_numbers(scan, kept))

    def _merge_title_numbers(self, scan: _Scan, mentions: list[_Instrument]) -> list[_Instrument]:
        """ "Health Act 2009 c. 21": a title followed by its own official number is one citation."""
        merged: list[_Instrument] = []
        for mention in mentions:
            last = merged[-1] if merged else None
            if (
                last is not None
                and last.kind in ("title", "alias", "acronym", "anchor")
                and mention.kind == "number"
                and mention.verdict == "resolved"
                and mention.ids[0] in last.ids
                and not scan.query[last.end : mention.start].strip(" ,(")
            ):
                merged[-1] = replace(
                    mention, start=last.start, title_as_cited=last.title_as_cited, kind="number"
                )
                continue
            merged.append(mention)
        return merged

    def _antecedent(self, mention: _Instrument, earlier_mentions: list[_Instrument]) -> _Instrument:
        """Resolve "that Act" to the nearest earlier resolved instrument of the same kind."""
        wants_act = (mention.title_as_cited or "").casefold().rstrip().endswith(("act", "statute"))
        for earlier in reversed(earlier_mentions):
            if earlier.kind in ("context_ref", "out_of_coverage") or earlier.verdict != "resolved":
                continue
            info = self._index.info(earlier.ids[0])
            if info.primary != wants_act:
                continue
            if mention.year is not None and info.year != mention.year:
                continue
            return replace(mention, kind="anaphora", verdict="resolved", ids=earlier.ids)
        return mention

    def _refer_back(self, scan: _Scan, mentions: list[_Instrument]) -> list[_Instrument]:
        """ "that Act", "the said Act", "(the 1990 Act)" name the Act cited just before them."""
        out: list[_Instrument] = []
        for mention in mentions:
            out.append(self._antecedent(mention, out) if mention.kind == "context_ref" else mention)
        return out

    # --- identifiers and numbers

    def _identifier_mention(self, m: IdentifierMention) -> _Instrument:
        index = self._index
        canonical = index.coordinates.canonical(m.instrument_key)
        if canonical is not None:
            coordinate = Coordinate.parse(canonical)
            return _Instrument(
                m.start, m.end, "identifier", "resolved", ids=(coordinate.instrument_id,),
                identifier_key=m.typed_key, clear_claim=True,
            )  # fmt: skip
        covered = index.coverage(m.instrument_key)
        if covered is not None:
            return _Instrument(
                m.start, m.end, "identifier", "out_of_coverage", coverage=(str(covered["c"]),),
                reason="series", identifier_key=m.key, clear_claim=True,
            )  # fmt: skip
        return _Instrument(
            m.start, m.end, "identifier", "not_found", identifier_key=m.key, clear_claim=True,
            title_as_cited=m.instrument_key, reason="identifier_not_in_index",
        )  # fmt: skip

    def _number_mention(self, n: NumberMention) -> _Instrument:
        ids = self._index.ids("numbers", n.key)
        base = {
            "year": n.year,
            "number": n.number,
            "instrument_type": n.instrument_type,
            "clear_claim": True,
        }
        if ids:
            verdict = "resolved" if len(ids) == 1 else "ambiguous"
            return _Instrument(n.start, n.end, "number", verdict, ids=ids, **base)  # type: ignore[arg-type]
        coverage = self._index.ids("coverage_numbers", n.key)
        if coverage:
            return _Instrument(
                n.start,
                n.end,
                "number",
                "out_of_coverage",
                coverage=coverage,
                reason="series",
                **base,  # type: ignore[arg-type]
            )
        if n.key.startswith(("ssi/", "sr/")):  # series not indexed at all: out of coverage
            return _Instrument(n.start, n.end, "number", "out_of_coverage", reason="series", **base)  # type: ignore[arg-type]
        return _Instrument(
            n.start,
            n.end,
            "number",
            "not_found",
            title_as_cited=self._scan_text(n),
            reason="number_not_in_index",
            **base,  # type: ignore[arg-type]
        )

    @staticmethod
    def _scan_text(n: NumberMention) -> str:
        return n.key

    # --- titles

    def _title_mentions(self, scan: _Scan) -> list[_Instrument]:
        tokens = scan.tokens
        grammar = self._grammar
        claimed: set[int] = set()
        found: list[_Instrument] = []
        anchors: list[tuple[int, str]] = []
        for pos, token in enumerate(tokens):
            if token.kind == "punct":
                continue
            if token.kind == "number" and len(token.text) == 4 and _YEAR_RE.fullmatch(token.text):  # noqa: PLR2004
                kind = "year"
            elif token.text in grammar.type_words:
                kind = "type"
            elif token.text in self._alias_last_words and self._completes_alias(scan, pos):
                kind = "alias"
            else:
                continue
            if not scan.is_blocked(token.start):
                anchors.append((pos, kind))
        for pos, kind in reversed(anchors[-MAX_ANCHORS:]):  # right to left: longest titles win
            if pos in claimed:
                continue
            mention = (
                self._match_title(scan, pos, claimed)
                or self._acronym(scan, pos, kind, claimed)
                or self._unknown_title(scan, pos, kind, claimed)
            )
            if mention is not None:
                found.append(mention)
        return found

    def _acronym(self, scan: _Scan, pos: int, kind: str, claimed: set[int]) -> _Instrument | None:
        """A generated Act acronym with its year: "TCGA 1992", "PACE 1984" (decision 18).

        Curated aliases were tried first (in :meth:`_match_title`) and always win. One Act
        binds; several ask. Bare acronyms ("FCA") are never generated.
        """
        tokens = scan.tokens
        if kind != "year" or pos == 0 or tokens[pos - 1].kind != "word":
            return None
        first = pos - 1
        token = tokens[first]
        typed = scan.query[token.start : token.end]
        if first in claimed or scan.is_blocked(token.start):
            return None
        if not (typed.isupper() or self._lower_case_acronym(token.text)):
            return None
        ids = self._index.ids("acronyms", f"{token.text}|{tokens[pos].text}")
        if not ids:
            return None
        claimed.update(range(first, pos + 1))
        text = scan.query[token.start : tokens[pos].end]
        info = self._index.info(ids[0]) if len(ids) == 1 else None
        mention = _Instrument(
            token.start,
            tokens[pos].end,
            "acronym",
            "resolved" if info is not None else "ambiguous",
            ids=ids,
            title_as_cited=text,
            year=int(tokens[pos].text),
            instrument_type="act",
            reason=None if info is not None else "acronym",
            note=f"“{text}” read as the {info.title}." if info is not None else None,
        )
        return self._absorb_chapter(scan, mention)

    def _lower_case_acronym(self, word: str) -> bool:
        """ "tcga 1992" counts; "in 2006" never does: not a title word or a boundary word."""
        return (
            len(word) >= 3  # noqa: PLR2004
            and word.isalpha()
            and word not in self._grammar.boundary_words
            and self._index.tables["words"].get(word) is None
        )

    def _completes_alias(self, scan: _Scan, pos: int) -> bool:
        """True when the words ending at token ``pos`` spell a whole alias ("TULR(C)A 1992")."""
        first = max(0, pos - 3 * self._alias_max_words)
        for start in range(pos, first - 1, -1):
            words = scan.words(start, pos)
            if words in self._alias_words:
                return True
            if len(words) > self._alias_max_words:
                return False
        return False

    def _window(self, scan: _Scan, anchor: int, claimed: set[int], limit: int) -> list[int]:
        """Word-token positions left of ``anchor`` a title may start at, nearest first."""
        tokens = scan.tokens
        starts = [anchor]
        pos = anchor - 1
        words = 0
        while pos >= 0 and words < limit:
            token = tokens[pos]
            if pos in claimed or scan.is_blocked(token.start):
                break
            if token.kind == "punct":
                if token.text in _STOP_PUNCT and token.text not in ",:":  # both occur in titles
                    break
            else:
                starts.append(pos)
                words += 1
            pos -= 1
        return starts

    def _key_for(self, text: str) -> tuple[tuple[str, ...], int | None, tuple[str, ...]]:
        """(content words without year, year, all words) for a candidate title span."""
        return self._split_year(title_words(text))

    @staticmethod
    def _split_year(words: tuple[str, ...]) -> tuple[tuple[str, ...], int | None, tuple[str, ...]]:
        if len(words) > 1 and _YEAR_RE.fullmatch(words[-1]):
            return words[:-1], int(words[-1]), words
        if len(words) > 1 and _YEAR_RE.fullmatch(words[0]):
            return words[1:], int(words[0]), words
        return words, None, words

    def _match_title(self, scan: _Scan, anchor: int, claimed: set[int]) -> _Instrument | None:
        tokens = scan.tokens
        query = scan.query
        index = self._index
        for start in reversed(self._window(scan, anchor, claimed, MAX_TITLE_WORDS)):
            if tokens[start].text in PARTICLES:
                continue  # "and Equality Act 2010" must not swallow the "and" joining two citations
            text = query[tokens[start].start : tokens[anchor].end]
            content, year, words = self._split_year(scan.words(start, anchor))
            key = title_key(content, year)  # never empty: the window starts on a content word
            scan.lookups += 1
            if scan.lookups > MAX_TITLE_LOOKUPS:
                return None
            ids = index.ids("titles", key)
            alias = index.aliases.get(" ".join(words))
            kind = "title"
            if not ids and alias is not None:
                ids, kind = (str(alias["id"]),), "alias"
            coverage = () if ids else index.ids("coverage_titles", key)
            if not ids and not coverage:
                continue
            claimed.update(range(start, anchor + 1))
            verdict = "resolved" if len(ids) == 1 else ("ambiguous" if ids else "out_of_coverage")
            note = self._former_title_note(text, content, ids) if verdict == "resolved" else None
            mention = _Instrument(
                tokens[start].start,
                tokens[anchor].end,
                kind,
                verdict,
                ids=ids,
                coverage=coverage,
                title_as_cited=text,
                year=year,
                instrument_type=self._type_word(content),
                clear_claim=self._clear_claim(content, year),
                reason="series" if coverage else ("title_without_year" if len(ids) > 1 else None),
                narrow_by_provision=len(ids) > 1,
                note=note,
            )
            return self._absorb_chapter(scan, self._check_embedded(scan, start, mention, claimed))
        return None

    def _former_title_note(
        self, cited: str, content: Sequence[str], ids: tuple[str, ...]
    ) -> str | None:
        """ "Supreme Court Act 1981" names the Senior Courts Act 1981 (decision 17)."""
        info = self._index.info(ids[0])
        if not info.former_titles:
            return None
        current = set(title_words(info.title))
        if all(w in current for w in content):
            return None
        return f"“{cited}” is a former title of the {info.title}."

    def _absorb_chapter(self, scan: _Scan, mention: _Instrument) -> _Instrument:
        """Extend a title mention over a following "(c. N)" and check N against the Act."""
        note = _CHAPTER_NOTE_RE.match(scan.query, mention.end)
        if note is None:
            return mention
        mention = replace(mention, end=note.end(), number=note.group("n"))
        if mention.verdict == "not_found" and mention.year is not None:
            # "Water Act 1980 (c. 45)": the official number names a real Act, the title does
            # not. The number is the stronger identity: ask, never refuse.
            numbered = self._index.ids("numbers", f"c/{mention.year}/{note.group('n')}")
            if numbered:
                return replace(
                    mention, verdict="ambiguous", ids=numbered, reason="title_number_conflict"
                )
        if mention.verdict == "resolved" and mention.ids:
            info = self._index.info(mention.ids[0])
            if info.series == "ukpga" and str(info.number) != note.group("n"):
                other = self._index.ids("numbers", f"c/{info.year}/{note.group('n')}")
                return replace(
                    mention,
                    verdict="ambiguous",
                    reason="chapter_mismatch",
                    ids=tuple(dict.fromkeys([*mention.ids, *other])),
                )
        return mention

    def _type_word(self, content: Sequence[str]) -> str | None:
        return next((w for w in reversed(content) if w in self._grammar.type_words), None)

    def _clear_claim(self, content: Sequence[str], year: int | None) -> bool:
        """A type word plus a year: enough to refuse if the instrument does not exist."""
        return year is not None and self._type_word(content) is not None

    def _cited_start(self, scan: _Scan, first: int, claimed: set[int]) -> int:
        """Extend left from ``first`` to a boundary: stopword, stop punctuation, claimed text.

        Particles that occur inside titles are crossed when a content word lies beyond them.
        """
        tokens = scan.tokens
        pos = first - 1
        start = first
        words = 0
        while pos >= 0 and words < MAX_CITED_WORDS:
            token = tokens[pos]
            if pos in claimed or scan.is_blocked(token.start):
                break
            if token.kind == "punct":
                if token.text in _STOP_PUNCT:
                    break
            elif token.text in _SOFT_PARTICLES:
                if not self._content_word_at(scan, pos - 1, claimed):
                    break
            elif token.text in self._grammar.boundary_words:
                break
            elif token.kind == "word":
                start = pos
                words += 1
            pos -= 1
        return start

    def _content_word_at(self, scan: _Scan, pos: int, claimed: set[int]) -> bool:
        if pos < 0 or pos in claimed:
            return False
        token = scan.tokens[pos]
        return (
            token.kind == "word"
            and token.text not in self._grammar.boundary_words
            and not scan.is_blocked(token.start)
        )

    def _check_embedded(
        self, scan: _Scan, start: int, mention: _Instrument, claimed: set[int]
    ) -> _Instrument:
        """A known title with extra words in front of it (plan departure 1)."""
        cited = self._cited_start(scan, start, claimed)
        if cited >= start:
            return mention
        extras = [t for t in scan.tokens[cited:start] if t.kind == "word"]  # cited is a word
        query = scan.query
        if (
            not _mostly_capitals(query)
            and query[scan.tokens[start].start].isupper()
            and not query[extras[-1].start].isupper()
        ):
            return mention  # "by virtue of Northern Ireland ... Act": the capitals start the title
        claimed.update(range(cited, start))
        whole = self._reordered(scan, cited, mention)
        if whole is not None:
            return whole
        capitalised = not _mostly_capitals(query) and all(query[t.start].isupper() for t in extras)
        cited_start = scan.tokens[cited].start
        cited_text = query[cited_start : mention.end]
        if capitalised and mention.clear_claim:
            # "Marchwood Commercial Arbitration Act 1996": longer than any real title.
            return replace(
                mention,
                start=cited_start,
                kind="anchor",
                verdict="not_found",
                title_as_cited=cited_text,
                suggestions=mention.ids,
                ids=(),
                reason="embedded_title",
            )
        return replace(
            mention,
            start=cited_start,
            verdict="ambiguous",
            title_as_cited=cited_text,
            reason="embedded_title",
            narrow_by_provision=False,
        )

    def _reordered(self, scan: _Scan, cited: int, mention: _Instrument) -> _Instrument | None:
        """Extra words that make the cited span a real title reordered, e.g.
        "Rights of Employment Act 1990" around the real "Employment Act 1990": the words are
        those of the Employment Rights Act, so the span is read as that title (typo tiers)."""
        text = scan.query[scan.tokens[cited].start : mention.end]
        content, year, _ = self._key_for(text)
        type_words = self._grammar.type_words
        verdict = analyse_title(
            self._index, content, year, type_words=type_words, policy=self._policy
        )
        start = scan.tokens[cited].start
        if verdict.verdict == "bound" and verdict.reason == "reordered":
            return replace(
                mention,
                start=start,
                title_as_cited=text,
                kind="anchor",
                verdict="resolved",
                ids=verdict.ids,
                corrections=verdict.corrections,
                reason="reordered",
            )
        cited_set = {w for w in content if w not in type_words}
        same_words = [i for i in verdict.suggestions if self._content_words(i) == cited_set]
        if same_words and mention.clear_claim:
            return replace(
                mention,
                start=start,
                title_as_cited=text,
                kind="anchor",
                verdict="not_found",
                ids=(),
                reason="wrong_year",
                suggestions=tuple(dict.fromkeys([*same_words, *verdict.suggestions, *mention.ids])),
            )
        return None

    def _content_words(self, instrument_id: str) -> set[str]:
        info = self._index.info(instrument_id)
        type_words = self._grammar.type_words
        return {w for w in title_words(info.title) if w not in type_words and not w.isdigit()}

    def _unknown_title(
        self, scan: _Scan, anchor: int, kind: str, claimed: set[int]
    ) -> _Instrument | None:
        """An anchor no known title ends on: typo tiers, wrong year, or invented law."""
        if kind == "alias":
            return None
        tokens = scan.tokens
        start = self._cited_start(scan, anchor, claimed)
        text = scan.query[tokens[start].start : tokens[anchor].end]
        content, year, _ = self._key_for(text)
        type_words = self._grammar.type_words
        core = [w for w in content if w not in type_words and not w.isdigit()]
        if not core:
            return None
        has_type = any(w in type_words for w in content)
        words_cited = sum(1 for t in tokens[start : anchor + 1] if t.kind == "word")
        truncated = words_cited >= MAX_CITED_WORDS  # the real title may start further left
        clear = has_type and year is not None and not truncated
        known_core = sum(self._index.tables["words"].get(w) is not None for w in core)
        if not clear and (known_core == 0 or (not has_type and known_core < 2)):  # noqa: PLR2004
            return None  # a year after one ordinary word ("substituted 2007") is no claim
        verdict: TitleVerdict = analyse_title(
            self._index, content, year, type_words=type_words, policy=self._policy
        )
        if verdict.verdict in ("bound", "ambiguous"):
            state, ids = ("resolved" if verdict.verdict == "bound" else "ambiguous"), verdict.ids
        elif clear:
            state, ids = "not_found", ()
        elif verdict.suggestions and year is not None:
            state, ids = "ambiguous", verdict.suggestions  # "employment rights 1990"
        else:
            return None  # "of the amending Act": a type word alone claims nothing
        claimed.update(range(start, anchor + 1))
        mention = _Instrument(
            tokens[start].start,
            tokens[anchor].end,
            "anchor",
            state,
            ids=ids,
            corrections=verdict.corrections,
            suggestions=verdict.suggestions if state == "not_found" else (),
            title_as_cited=text,
            year=year,
            clear_claim=clear,
            reason=verdict.reason,
            instrument_type=self._type_word(content),
        )
        return self._absorb_chapter(scan, mention)

    # --- cue mentions (out of coverage, context references)

    def _cue_mentions(self, scan: _Scan, found: list[_Instrument]) -> list[_Instrument]:
        mentions: list[_Instrument] = []
        taken = [(m.start, m.end) for m in found]
        for cue in scan.cues:
            if any(_overlaps((cue.start, cue.end), t) for t in taken):
                continue
            if cue.kind == "out_of_coverage":
                start = cue.start
                if cue.detail == "bill":
                    start = self._cue_title_start(scan, cue)
                jurisdiction = {"es": "es", "eu": "eu", "foreign": None, "case": None}.get(
                    cue.detail or "", "uk"
                )
                mentions.append(
                    _Instrument(
                        start,
                        cue.end,
                        "out_of_coverage",
                        "out_of_coverage",
                        title_as_cited=scan.query[start : cue.end],
                        reason=cue.detail,
                        jurisdiction=jurisdiction,
                        clear_claim=True,
                    )
                )
                taken.append((start, cue.end))
            elif cue.kind == "context_ref":
                mentions.append(
                    _Instrument(
                        cue.start,
                        cue.end,
                        "context_ref",
                        "context",
                        title_as_cited=cue.text,
                        year=int(cue.detail) if cue.detail else None,
                    )
                )
        return mentions

    def _cue_title_start(self, scan: _Scan, cue: Cue) -> int:
        anchor = next(i for i, t in enumerate(scan.tokens) if t.start >= cue.start)  # "bill"
        return scan.tokens[self._cited_start(scan, anchor, set())].start

    # ------------------------------------------------------------------ exclusion and linking

    @staticmethod
    def _gap_words(scan: _Scan, start: int, end: int) -> list[str]:
        return scan.gap_words(start, end)

    def _apply_exclusions(self, scan: _Scan, instruments: list[_Instrument]) -> set[int]:
        """Mark mentions right after a negation cue (and lists joined to them) as excluded.

        Returns the ids (``id()``) of excluded provision mentions.
        """
        excluded: set[int] = set()
        mentions: list[tuple[int, int, object]] = sorted(
            [(m.start, m.end, m) for m in instruments]
            + [(p.start, p.end, p) for p in scan.provisions],
            key=lambda item: item[0],
        )
        for cue in (c for c in scan.cues if c.kind == "negation"):
            allowed = 1 if cue.text.strip().casefold() == "not" else 3
            following = [item for item in mentions if item[0] >= cue.end]
            if not following:
                continue
            gap = self._gap_words(scan, cue.end, following[0][0])
            if len(gap) > allowed or any(w not in _NEGATION_FILLERS for w in gap):
                continue
            previous_end = None
            for start, end, mention in following:
                if previous_end is not None:
                    joiners = self._gap_words(scan, previous_end, start)
                    if not joiners or any(w not in _LIST_JOINERS and w != "," for w in joiners):
                        break
                self._exclude(mention, excluded)
                previous_end = end
        return excluded

    @staticmethod
    def _exclude(mention: object, excluded: set[int]) -> None:
        if isinstance(mention, _Instrument):
            mention.excluded = True
        else:
            excluded.add(id(mention))

    def _link(self, scan: _Scan, instruments: list[_Instrument]) -> list[ProvisionMention]:
        """Attach provisions to instruments; return the provisions left unlinked."""
        # An unresolved "the 1996 Act" still takes its provisions: its year narrows the question.
        targets = [
            m
            for m in instruments
            if m.kind != "context_ref" or m.verdict != "context" or m.year is not None
        ]
        named = [m for m in targets if m.kind != "context_ref"]
        unlinked: list[ProvisionMention] = []
        previous: tuple[ProvisionMention, _Instrument] | None = None
        for provision in scan.provisions:
            target = self._nearest_link(scan, provision, targets)
            if target is None and previous is not None:
                target = self._chained(scan, previous, provision)
            if target is None:
                live = [m for m in named if not m.excluded]
                distinct = {m.ids[0] if m.ids else id(m) for m in live}
                lone = live[0] if len(distinct) == 1 else None  # decision 15
                if lone is not None and self._same_clause(scan, provision, lone):
                    target = lone
            if target is None:
                unlinked.append(provision)
                previous = None
            else:
                target.provisions.append(provision)
                previous = (provision, target)
        return unlinked

    @staticmethod
    def _chained(
        scan: _Scan, previous: tuple[ProvisionMention, _Instrument], provision: ProvisionMention
    ) -> _Instrument | None:
        """A provision listed straight after one already linked belongs to the same
        instrument: "Act 2003 (c. 32), ss. 91(1), 94, Sch. 5 para. 26(a)"."""
        before, instrument = previous  # provisions are sorted and never overlap
        gap = scan.gap_words(before.end, provision.start)
        return instrument if all(w in _LIST_JOINERS or w == "," for w in gap) else None

    def _same_clause(self, scan: _Scan, provision: ProvisionMention, lone: _Instrument) -> bool:
        """Decision 15 applies within one clause, and not across an agentive "by"."""
        start, end = sorted(((provision.start, provision.end), (lone.start, lone.end)))
        between = scan.query[start[1] : end[0]]
        if any(
            m.group("word") is None or m.group("word").casefold() not in _ABBREVIATIONS
            for m in _CLAUSE_BREAK_RE.finditer(between)
        ):
            return False
        return not self._agentive(scan, provision, lone)

    def _agentive(self, scan: _Scan, p: ProvisionMention, instrument: _Instrument) -> bool:
        """True for "s. 79 amended by <Act>": the instrument is the agent acting on the
        provision, which belongs to something else, so it must not be linked by default."""
        if p.end > instrument.start:
            return False
        return "by" in self._gap_words(scan, p.end, instrument.start)

    def _nearest_link(
        self, scan: _Scan, p: ProvisionMention, targets: list[_Instrument]
    ) -> _Instrument | None:
        """Link to the instrument after ("s. 124 of <Act>") or before ("<SI>, reg. 5").

        When both are possible the one joined by a connector word wins; with no word on
        either side ("SI 2019/627, reg. 5(2) 2020 c. 1"), the instrument before does.
        """
        after = self._linked_after(scan, p, targets)
        before = self._linked_before(scan, p, targets)
        if after is None or before is None:
            return after or before
        after_gap = self._gap_words(scan, p.end, after.start)
        return after if any(w in _AFTER_CONNECTORS for w in after_gap) else before

    def _linked_after(
        self, scan: _Scan, p: ProvisionMention, targets: list[_Instrument]
    ) -> _Instrument | None:
        after = [m for m in targets if m.start >= p.end]
        if not after:
            return None
        target = min(after, key=lambda m: m.start)
        gap = self._gap_words(scan, p.end, target.start)
        if len(gap) <= MAX_AFTER_GAP and all(w in _AFTER_CONNECTORS or w in ",()" for w in gap):
            return target
        return None

    def _linked_before(
        self, scan: _Scan, p: ProvisionMention, targets: list[_Instrument]
    ) -> _Instrument | None:
        before = [m for m in targets if m.end <= p.start]
        if not before:
            return None
        target = max(before, key=lambda m: m.end)
        gap = self._gap_words(scan, target.end, p.start)
        if len(gap) <= MAX_BEFORE_GAP and all(
            w in _BEFORE_CONNECTORS or w in ",':-()" for w in gap
        ):
            return target
        return None

    def _context_instrument(
        self, context: RouteContext | Sequence[Coordinate | str] | None
    ) -> InstrumentInfo | None:
        """The one instrument the validated context coordinates belong to, if any."""
        if context is None:
            return None
        raw = context.coordinates if isinstance(context, RouteContext) else tuple(context)
        found: set[str] = set()
        for item in raw:
            canonical = self._index.coordinates.canonical(str(item))
            if canonical is None:
                continue  # context cannot smuggle in unverified law
            found.add(Coordinate.parse(canonical).instrument_id)  # the index holds valid ones
        if len(found) != 1:
            return None
        return self._index.info(next(iter(found)))

    # ------------------------------------------------------------------ resolution

    def _candidate(
        self, coordinate: Coordinate, info: InstrumentInfo | None = None, label: str | None = None
    ) -> Candidate:
        title = (info or self._index.info(coordinate.instrument_id)).title
        return Candidate(coordinate, f"{title} {label}".strip() if label else title)

    def _instrument_candidate(self, instrument_id: str) -> Candidate:
        info = self._index.info(instrument_id)
        return Candidate(Coordinate.parse(info.coordinate), info.title)

    def _labelled(self, candidates: list[Candidate]) -> list[Candidate]:
        """Add the official number where two candidates would otherwise read the same."""
        counts: dict[str, int] = {}
        for candidate in candidates:
            counts[candidate.label] = counts.get(candidate.label, 0) + 1
        return [
            Candidate(c.coordinate, f"{c.label} ({_official_number(c.coordinate)})")
            if counts[c.label] > 1
            else c
            for c in candidates
        ]

    def _lookup(self, info: InstrumentInfo, path: tuple[str, ...]) -> tuple[str, ...]:
        """Canonical spellings of ``info.coordinate/path`` (several: case variants)."""
        typed = "/".join((info.coordinate, *path))
        spellings = self._index.coordinates.spellings(typed)
        if typed in spellings:
            return (typed,)
        return spellings

    @staticmethod
    def _sub_kind(segment: str) -> str:
        if segment[:1].isdigit():
            return "n"
        return "r" if re.fullmatch(r"[ivxl]+", segment) else "a"

    def _sibling_paths(self, path: tuple[str, ...], n_subs: int) -> list[tuple[str, ...]]:
        """Editorial lists read as siblings when the nested path does not exist.

        legislation.gov.uk notes write "s. 108(4)(6)(7)" for subsections (4), (6) and (7),
        and "s. 10(2)(a)(ii)(7)" for (2)(a)(ii) and (7). UK drafting never nests a number
        below a letter or another number, so each later number restarts at the first
        level; a trailing run of letters ("(2)(a)(b)") lists siblings at its own level.
        """
        if n_subs < 2 or n_subs >= len(path):  # noqa: PLR2004
            return []
        unit, subs = path[: len(path) - n_subs], path[len(path) - n_subs :]
        groups: list[list[str]] = [[subs[0]]]
        for segment in subs[1:]:
            if self._sub_kind(segment) == "n":
                groups.append([segment])
            else:
                groups[-1].append(segment)
        out: list[tuple[str, ...]] = []
        for group in groups:
            tail = group[-1]
            run = 1
            while (
                run < len(group) and self._sub_kind(group[-run - 1]) == self._sub_kind(tail) != "n"
            ):
                run += 1
            if run > 1:  # "(2)(a)(b)": (2)(a) and (2)(b)
                out.extend((*unit, *group[:-run], item) for item in group[-run:])
            else:
                out.append((*unit, *group))
        return out if len(out) > 1 else []

    def _resolve_ref(
        self, info: InstrumentInfo, ref: ProvisionRef
    ) -> tuple[str, list[Coordinate], str | None]:
        """("bound" | "ambiguous" | "missing", coordinates, reason) for one provision ref."""
        paths = self._grammar.provision_paths(ref, primary=info.primary)
        for path in paths:
            spellings = self._lookup(info, path)
            if not spellings:
                continue
            coordinates = [Coordinate.parse(s) for s in spellings]
            if len(coordinates) > 1:
                return "ambiguous", coordinates, "case_variants"
            coordinate = coordinates[0]
            if str(coordinate) in info.duplicated:
                return "ambiguous", coordinates, "duplicated_in_source"  # decision 13
            tail = "/".join(coordinate.provision)
            if ref.unit == "part" and tail in info.groups:  # a part binds to its sections
                return (
                    "bound",
                    [Coordinate.parse(f"{info.coordinate}/{t}") for t in info.groups[tail]],
                    None,
                )
            return "bound", coordinates, None
        for path in paths:  # nested reading absent: try "(1)(2)" as siblings (1) and (2)
            siblings = self._sibling_paths(path, len(ref.subs))
            found = [self._lookup(info, sibling) for sibling in siblings]
            if siblings and all(len(f) == 1 for f in found):
                return "bound", [Coordinate.parse(f[0]) for f in found], None
        return "missing", [], None

    def _resolve_range(
        self, info: InstrumentInfo, mention: ProvisionMention
    ) -> tuple[str, list[Coordinate]]:
        first, last = mention.refs
        ends = [self._resolve_ref(info, first), self._resolve_ref(info, last)]
        if any(e[0] != "bound" or len(e[1]) != 1 for e in ends):
            return "missing" if any(e[0] == "missing" for e in ends) else "ambiguous", []
        a, b = ends[0][1][0], ends[1][1][0]
        if a.provision[:-1] != b.provision[:-1] or len(a.provision) != 1:
            return "ambiguous", []
        unit = re.sub(r"[^a-z].*$", "", a.provision[0])  # "s124A" → "s", "schA1" → "sch"
        lo, hi = _order_key(a.provision[0][len(unit) :]), _order_key(b.provision[0][len(unit) :])
        if hi < lo or hi[0] - lo[0] > MAX_RANGE:
            return "ambiguous", []
        inside: list[str] = []
        for number in range(lo[0], hi[0] + 1):
            inside.extend(
                c
                for c in self._top_level(info, unit, number)
                if lo <= _order_key(c.rsplit("/", 1)[-1][len(unit) :]) <= hi
            )
        if not inside or len(inside) > MAX_RANGE:
            return "ambiguous", []
        inside.sort(key=lambda c: _order_key(c.rsplit("/", 1)[-1][len(unit) :]))
        return "bound", [Coordinate.parse(c) for c in inside]

    def _top_level(self, info: InstrumentInfo, unit: str, number: int) -> list[str]:
        """Top-level provisions ``unit{number}``, ``unit{number}A``, ``unit{number}ZA`` …"""
        prefix = f"{info.coordinate}/{unit}{number}"
        pattern = re.compile(rf"{re.escape(unit)}{number}[A-Za-z]{{0,3}}")
        found = []
        for key, value in self._index.tables["coordinates"].prefix(prefix.casefold()):
            if key.count("/") != prefix.count("/"):
                continue
            canonical = value.split("|")[0] if value else key
            if pattern.fullmatch(canonical.rsplit("/", 1)[-1]):
                found.append(canonical)
        return found

    def _resolve_provisions(
        self, info: InstrumentInfo, provisions: list[ProvisionMention], excluded_ids: set[int]
    ) -> _Outcome:
        """Resolve the provisions cited against one known instrument."""
        outcome = _Outcome(RouteStatus.BOUNDED, repealed=info.repealed)
        wanted = [p for p in provisions if id(p) not in excluded_ids]
        for provision in (p for p in provisions if id(p) in excluded_ids):
            for ref in provision.refs:
                state, coords, _ = self._resolve_ref(info, ref)
                if state == "bound":
                    outcome.excluded.extend(coords)
        if not wanted:
            outcome.coordinates.append(Coordinate.parse(info.coordinate))
            return outcome
        if info.structure == "metadata_only":
            outcome.status = RouteStatus.OUT_OF_COVERAGE
            outcome.reason = "provision_structure_unavailable"
            outcome.message = (
                f"{info.title} is held by the official source only as a PDF: its provisions "
                "cannot be verified offline."
            )
            return outcome
        for provision in wanted:
            if provision.open_ended:
                outcome.status = RouteStatus.AMBIGUOUS
                outcome.reason = "open_range"
                after = provision.refs[0].label()
                outcome.clarification = f"Which provisions of the {info.title} after {after}?"
                return outcome
            if provision.is_range:
                state, coords = self._resolve_range(info, provision)
                if state != "bound":
                    return self._provision_problem(
                        outcome, info, provision.refs[0], state=state, coords=coords, reason="range"
                    )
                outcome.coordinates.extend(coords)
                continue
            for ref in provision.refs:
                state, coords, reason = self._resolve_ref(info, ref)
                if state != "bound":
                    return self._provision_problem(
                        outcome, info, ref, state=state, coords=coords, reason=reason
                    )
                outcome.coordinates.extend(coords)
        return outcome

    def _provision_problem(
        self,
        outcome: _Outcome,
        info: InstrumentInfo,
        ref: ProvisionRef,
        *,
        state: str,
        coords: list[Coordinate],
        reason: str | None,
    ) -> _Outcome:
        if state == "missing":
            outcome.status = RouteStatus.PROVISION_NOT_FOUND
            outcome.reason = "provision_not_in_instrument"
            outcome.message = (
                f"{info.title} has no {ref.label()} (index snapshot {self._index.snapshot})."
            )
            return outcome
        outcome.status = RouteStatus.AMBIGUOUS
        outcome.reason = reason
        outcome.candidates = [self._candidate(c, info, "/".join(c.provision)) for c in coords]
        if reason == "duplicated_in_source":
            outcome.clarification = (
                f"The {info.title} publishes {ref.label()} more than once (its Parts restart the "
                "numbering). Which Part do you mean?"
            )
        elif reason == "case_variants":
            both = " and ".join("/".join(c.provision) for c in coords)
            outcome.clarification = f"The {info.title} has both {both}. Which do you mean?"
        else:
            outcome.clarification = f"Which provisions of the {info.title} do you mean?"
        return outcome

    def _resolve_instrument(
        self, mention: _Instrument, excluded_ids: set[int], context: InstrumentInfo | None
    ) -> _Outcome:
        outcome = self._resolve_instrument_status(mention, excluded_ids, context)
        outcome.live_checkable = self._live_checkable(mention)
        outcome.citation = self._citation(mention, outcome)
        return outcome

    def _resolve_instrument_status(
        self, mention: _Instrument, excluded_ids: set[int], context: InstrumentInfo | None
    ) -> _Outcome:
        if mention.excluded and not mention.provisions:
            return _Outcome(RouteStatus.UNRESOLVED, reason="excluded")
        if mention.kind == "context_ref":
            return self._resolve_context_ref(mention, excluded_ids, context)
        terminal = self._terminal(mention)
        if terminal is not None:
            return terminal
        chosen = self._choose(mention, excluded_ids)
        if isinstance(chosen, _Outcome):
            return chosen
        if (
            mention.identifier_key
            and mention.identifier_key.casefold() != chosen.coordinate.casefold()
        ):
            return self._resolve_identifier_provision(mention, chosen)
        outcome = self._resolve_provisions(chosen, mention.provisions, excluded_ids)
        if mention.excluded:
            outcome.excluded.append(Coordinate.parse(chosen.coordinate))
            outcome.coordinates = []  # every coordinate resolved here is inside the excluded Act
            outcome.status, outcome.reason = RouteStatus.UNRESOLVED, "excluded"
        outcome.corrections = mention.corrections
        outcome.source = "identifier" if mention.kind == "identifier" else "grammar"
        if mention.note is not None:
            outcome.message = " ".join(filter(None, (mention.note, outcome.message)))
        return outcome

    def _terminal(self, mention: _Instrument) -> _Outcome | None:
        """The outcome for a mention that never reaches the index: invented, or uncovered."""
        if mention.verdict == "not_found":
            return self._not_found(mention)
        if mention.verdict == "out_of_coverage":
            label = _OOC_LABELS.get(mention.reason or "series", _OOC_LABELS["series"])
            cited = mention.title_as_cited or ""
            return _Outcome(
                RouteStatus.OUT_OF_COVERAGE,
                reason=mention.reason or "series",
                message=f"“{cited}” is {label}: outside the indexed corpus.",
            )
        return None

    def _not_found(self, mention: _Instrument) -> _Outcome:
        cited = mention.title_as_cited or "the cited instrument"
        return _Outcome(
            RouteStatus.INSTRUMENT_NOT_FOUND,
            reason=mention.reason,
            suggestions=[self._instrument_candidate(i) for i in mention.suggestions],
            message=(
                f"No instrument “{cited}” is in the UK statute book as of the index snapshot "
                f"{self._index.snapshot}."
            ),
        )

    def _choose(self, mention: _Instrument, excluded_ids: set[int]) -> InstrumentInfo | _Outcome:
        """The one instrument a mention names, or the clarifying outcome if it names several.

        A title that fits several instruments (no year) is narrowed by the cited provisions:
        exactly one instrument containing them is bound (grammar.md UK-I-06, UK-I-07).
        """
        ids = list(mention.ids)
        if mention.verdict == "ambiguous":
            if not (mention.narrow_by_provision and mention.provisions):
                return self._ambiguous_instruments(mention, ids)
            fitting = [i for i in ids if self._fits(i, mention.provisions, excluded_ids)]
            if len(fitting) != 1:
                return self._ambiguous_instruments(mention, fitting or ids)
            ids = fitting
        return self._index.info(ids[0])

    def _fits(
        self, instrument_id: str, provisions: list[ProvisionMention], excluded_ids: set[int]
    ) -> bool:
        info = self._index.info(instrument_id)
        wanted = [p for p in provisions if id(p) not in excluded_ids] or provisions
        return all(self._resolve_ref(info, ref)[0] == "bound" for p in wanted for ref in p.refs)

    def _ambiguous_instruments(self, mention: _Instrument, ids: list[str]) -> _Outcome:
        candidates = self._labelled([self._instrument_candidate(i) for i in ids])
        outcome = _Outcome(
            RouteStatus.AMBIGUOUS,
            candidates=candidates,
            reason=mention.reason,
            corrections=mention.corrections,
        )
        names = ", ".join(c.label for c in candidates[:MAX_CANDIDATES_SHOWN])
        if mention.reason == "title_number_conflict":
            outcome.clarification = (
                f"No instrument is titled “{mention.title_as_cited}”, but its chapter number "
                f"is that of the {names}. Did you mean that?"
            )
        elif mention.reason == "chapter_mismatch":
            outcome.clarification = (
                f"“{mention.title_as_cited}”: the chapter number does not match that title. "
                f"Which do you mean: {names}?"
            )
        elif mention.reason in ("typo", "embedded_title", "reordered", "no_such_title"):
            outcome.clarification = (
                f"Did you mean the {names}?"
                if len(candidates) == 1
                else f"Did you mean one of: {names}?"
            )
        else:
            cited = mention.title_as_cited
            outcome.clarification = f"“{cited}” fits more than one instrument: {names}. Which?"
        return outcome

    def _resolve_identifier_provision(self, mention: _Instrument, info: InstrumentInfo) -> _Outcome:
        key = mention.identifier_key or ""
        canonical = self._index.coordinates.canonical(key)
        outcome = _Outcome(RouteStatus.BOUNDED, repealed=info.repealed, source="identifier")
        if canonical is None:
            if self._index.coordinates.spellings(key):
                outcome.status = RouteStatus.AMBIGUOUS
                outcome.reason = "case_variants"
                outcome.candidates = [
                    self._candidate(Coordinate.parse(s), info)
                    for s in self._index.coordinates.spellings(key)
                ]
                outcome.clarification = (
                    "That identifier matches provisions that differ only by case. Which one?"
                )
                return outcome
            if info.structure == "metadata_only":
                outcome.status = RouteStatus.OUT_OF_COVERAGE
                outcome.reason = "provision_structure_unavailable"
                return outcome
            outcome.status = RouteStatus.PROVISION_NOT_FOUND
            outcome.reason = "provision_not_in_instrument"
            provision = key[len(info.coordinate) + 1 :]
            outcome.message = (
                f"{info.title} has no provision {provision} "
                f"(index snapshot {self._index.snapshot})."
            )
            return outcome
        coordinate = Coordinate.parse(canonical)
        if canonical in info.duplicated:
            outcome.status = RouteStatus.AMBIGUOUS
            outcome.reason = "duplicated_in_source"
            outcome.candidates = [self._candidate(coordinate, info)]
            outcome.clarification = (
                f"The {info.title} publishes that provision more than once. Which Part do you mean?"
            )
            return outcome
        outcome.coordinates.append(coordinate)
        return outcome

    def _resolve_context_ref(
        self, mention: _Instrument, excluded_ids: set[int], context: InstrumentInfo | None
    ) -> _Outcome:
        year = mention.year
        if context is not None and (year is None or context.year == year):
            outcome = self._resolve_provisions(context, mention.provisions, excluded_ids)
            outcome.source = "context"
            return outcome
        if year is not None:
            ids = [
                i
                for _, i in self._index.tables["numbers"].prefix(f"c/{year}/")
                for i in i.split(",")
            ]
            # The only Act of that year binds only if the catalogue knows no other one either.
            others = next(self._index.tables["coverage_numbers"].prefix(f"c/{year}/"), None)
            if len(ids) == 1 and others is None:
                info = self._index.info(ids[0])
                return self._resolve_provisions(info, mention.provisions, excluded_ids)
            if mention.provisions:
                fitting = [i for i in ids if self._fits(i, mention.provisions, excluded_ids)]
                ids = fitting or ids
            return self._ambiguous_instruments(replace(mention, reason="year_only"), ids)
        return _Outcome(
            RouteStatus.AMBIGUOUS,
            reason="context_needed",
            clarification=f"Which instrument do you mean by “{mention.title_as_cited}”?",
        )

    def _resolve_unlinked(
        self,
        provision: ProvisionMention,
        instruments: list[_Instrument],
        context: InstrumentInfo | None,
        excluded_ids: set[int],
    ) -> _Outcome:
        label = "; ".join(r.label() for r in provision.refs)
        citation = ParsedCitation(
            span=(provision.start, provision.end),
            jurisdiction_hint=None,
            instrument_type=None,
            title_as_cited=None,
            year=None,
            number=None,
            provision=label,
            resolution="unlinked",
            live_checkable=False,
        )
        if context is not None and not any(
            not m.excluded for m in instruments if m.kind != "context_ref"
        ):
            outcome = self._resolve_provisions(context, [provision], excluded_ids)
            outcome.source = "context"
            outcome.citation = replace(citation, resolution="resolved")
            return outcome
        if id(provision) in excluded_ids:
            return _Outcome(
                RouteStatus.UNRESOLVED,
                reason="excluded",
                citation=replace(citation, resolution="excluded"),
            )
        pool = [i for m in instruments if not m.excluded and m.kind != "context_ref" for i in m.ids]
        pool = pool or list(self._salient)
        candidates: list[Candidate] = []
        for iid in dict.fromkeys(pool):
            info = self._index.info(iid)
            for ref in provision.refs:
                state, coords, _ = self._resolve_ref(info, ref)
                if state == "bound":
                    candidates.extend(self._candidate(c, info, ref.label()) for c in coords[:1])
        if not candidates:
            return _Outcome(
                RouteStatus.UNRESOLVED, reason="provision_without_instrument", citation=citation
            )
        names = ", ".join(c.label for c in candidates[:MAX_CANDIDATES_SHOWN])
        return _Outcome(
            RouteStatus.AMBIGUOUS,
            candidates=candidates,
            reason="provision_without_instrument",
            clarification=f"{label} appears in more than one instrument: {names}. Which one?",
            citation=citation,
        )

    # ------------------------------------------------------------------ live checks and citations

    def _live_checkable(self, mention: _Instrument) -> bool:
        """Registry known, enough identity, and inside the freshness window (plan contract).

        A covered series is a closed period before the snapshot year and below the highest
        number indexed for its year: "Marchwood Order 2022" or "SI 2011/9999" are refused
        offline even in confirm mode. Uncovered series are always checkable.
        """
        registry = mention.jurisdiction == "uk" and self._grammar.registry is not None
        identified = mention.kind in ("identifier", "number") or (
            mention.title_as_cited is not None and mention.year is not None
        )
        if not registry or not identified or mention.verdict in ("resolved", "context"):
            return False
        if mention.verdict == "out_of_coverage" or mention.year is None:
            return True
        series = "uksi" if mention.instrument_type == "si" else "ukpga"
        window = self._index.manifest.get("freshness", {}).get(series)
        if window is None or mention.year >= self._snapshot_year:
            return True
        highest = window.get("max_number_by_year", {}).get(str(mention.year))
        return bool(mention.number and highest is not None and int(mention.number) > int(highest))

    def _citation(self, mention: _Instrument, outcome: _Outcome) -> ParsedCitation:
        resolution: Resolution
        if mention.excluded:
            resolution = "excluded"
        elif outcome.status is RouteStatus.OUT_OF_COVERAGE:
            resolution = "out_of_coverage"
        elif mention.verdict == "not_found":
            resolution = "not_in_index"
        elif outcome.status in (RouteStatus.BOUNDED, RouteStatus.PROVISION_NOT_FOUND):
            resolution = "resolved"
        else:
            resolution = "unlinked"
        spans = [(mention.start, mention.end), *((p.start, p.end) for p in mention.provisions)]
        labels = [r.label() for p in mention.provisions for r in p.refs]
        return ParsedCitation(
            span=(min(s for s, _ in spans), max(e for _, e in spans)),
            jurisdiction_hint=mention.jurisdiction,
            instrument_type=mention.instrument_type,
            title_as_cited=mention.title_as_cited,
            year=mention.year,
            number=mention.number,
            provision="; ".join(labels) or None,
            resolution=resolution,
            live_checkable=outcome.live_checkable,
        )

    # ------------------------------------------------------------------ assembly

    def _assemble(
        self, scan: _Scan, outcomes: list[_Outcome], *, temporal: str | None, signal: bool
    ) -> RouteResult:
        outcomes = [
            o
            for o in outcomes
            if not (o.status is RouteStatus.UNRESOLVED and o.reason == "excluded")
        ] or outcomes
        citations = tuple(o.citation for o in outcomes if o.citation is not None)
        if not outcomes:
            return self._result(
                RouteStatus.UNRESOLVED, temporal_hint=temporal, citation_signal=signal
            )
        status = min((o.status for o in outcomes), key=_PRIORITY.index)
        deciding = [o for o in outcomes if o.status is status]
        coordinates: tuple[Coordinate, ...] = ()
        excluded = tuple(dict.fromkeys(c for o in outcomes for c in o.excluded))
        if status is RouteStatus.BOUNDED:
            coordinates = tuple(dict.fromkeys(c for o in outcomes for c in o.coordinates))
        next_action = _NEXT_ACTION[status]
        if status is RouteStatus.OUT_OF_COVERAGE and any(o.live_checkable for o in deciding):
            next_action = NextAction.VERIFY_LIVE
        spans = [c.span for c in citations]
        sources = {o.source for o in outcomes if o.status is RouteStatus.BOUNDED}
        source: Source = (
            "context"
            if "context" in sources
            else "identifier"
            if sources == {"identifier"}
            else "grammar"
        )
        return RouteResult(
            status=status,
            next_action=next_action,
            coordinates=coordinates,
            excluded=excluded if status is RouteStatus.BOUNDED else (),
            candidates=tuple(c for o in deciding for c in o.candidates),
            clarification=next((o.clarification for o in deciding if o.clarification), None),
            citations=citations,
            citation_span=(min(s for s, _ in spans), max(e for _, e in spans)) if spans else None,
            corrections=tuple(
                dict.fromkeys(
                    c for o in outcomes if o.status is RouteStatus.BOUNDED for c in o.corrections
                )
            ),
            suggestions=tuple(dict.fromkeys(c for o in deciding for c in o.suggestions)),
            repealed=status is RouteStatus.BOUNDED and any(o.repealed for o in deciding),
            temporal_hint=temporal,
            citation_signal=signal or bool(citations),
            source=source,
            index_snapshot=self._index.snapshot,
            reason=next((o.reason for o in deciding if o.reason), None),
            messages=tuple(dict.fromkeys(o.message for o in deciding if o.message)),
        )

    def _emit_miss(self, query: str, result: RouteResult) -> None:
        miss_log.info(
            "unresolved query with a citation signal",
            extra={
                "event": "unresolved_with_signal",
                "query_sha256": hashlib.sha256(query.encode("utf-8", "replace")).hexdigest(),
                "query_length": len(query),
                "query": self._redact(query) if self._redact is not None else None,
                "reason": result.reason,
                "index_snapshot": result.index_snapshot,
            },
        )


def _official_number(coordinate: Coordinate) -> str:
    """``c. 18`` for an Act, ``SI 2011/3006`` for an instrument."""
    if coordinate.series == "ukpga":
        return f"c. {coordinate.instrument[-1]}"
    return f"SI {coordinate.instrument[1]}/{coordinate.instrument[-1]}"


def _mostly_capitals(text: str) -> bool:
    """ALL-CAPS queries carry no capitalisation signal (grammar.md UK-C-15)."""
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > _CAPS_SHARE


def _order_key(designator: str) -> tuple[int, int, str]:
    """Statutory ordering: 98 < 98ZA < 98ZB < 98A < 98B < 99."""
    match = re.match(r"(\d+)(.*)", designator)
    if match is None:
        return (0, 0, designator)
    number, suffix = int(match.group(1)), match.group(2).upper()
    rank = 0 if not suffix else 1 if suffix.startswith("Z") else 2
    return (number, rank, suffix)


_ = damerau  # re-exported for tests that measure typo distance through the router module
