"""Title typo tiers and suggestions (plan departure 7, grammar.md UK-I-15 to UK-I-20).

Small typos are corrected, bigger ones get a question, invented titles are still refused:

========================================================  ===================================
Title as cited (year / number match exactly)              Verdict
========================================================  ===================================
1 edit (Damerau) in **one** word of >= 5 letters; exactly  ``bound``, correction recorded
one real title fits and no other within 2 edits
2 edits, more than one misspelled word, several titles    ``ambiguous`` ("did you mean ...?")
same words, different order, exactly one real title       ``bound``, reordering recorded
reordered and a typo, or several reordered titles         ``ambiguous``
right title, wrong year                                   ``not_found`` + suggestions
nothing close                                             ``not_found`` (suggestions only if a
                                                          real title shares >= 50 % of words)
========================================================  ===================================

Years, numbers, provisions and identifiers are never corrected; words shorter than five
letters are never corrected. Every threshold lives in :class:`TypoPolicy`, tuned on the
typo *dev* slice only (roadmap decision D2) and frozen with the battery seal.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from itertools import product
from typing import Final, Literal

from legal_rag_router.index import RouterIndex
from legal_rag_router.normalise import title_key

__all__ = ["TitleVerdict", "TypoPolicy", "analyse_title", "damerau"]

Verdict = Literal["bound", "ambiguous", "not_found", "none"]


@dataclass(frozen=True, slots=True)
class TypoPolicy:
    """Every threshold of the typo tiers, in one place (frozen with the battery seal)."""

    min_correctable_length: int = 5
    auto_correct_edits: int = 1
    clarify_edits: int = 2
    max_unknown_words: int = 3
    max_candidates_per_word: int = 4
    max_suggestions: int = 3
    suggestion_min_shared: float = 0.5
    common_word_value_chars: int = 40_000
    """Skip words whose title list is huge ("act", "order"): they carry no signal."""


DEFAULT_POLICY: Final = TypoPolicy()


@dataclass(frozen=True, slots=True)
class TitleVerdict:
    verdict: Verdict
    ids: tuple[str, ...] = ()
    """``bound``: the one instrument; ``ambiguous``: candidates, best first."""
    corrections: tuple[tuple[str, str], ...] = ()
    suggestions: tuple[str, ...] = ()
    """Instrument ids offered with a refusal, best first."""
    reason: str | None = None
    notes: tuple[str, ...] = field(default=())


def damerau(a: str, b: str, limit: int = 3) -> int:
    """Optimal-string-alignment Damerau-Levenshtein distance, capped at ``limit + 1``."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous2: list[int] = []
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i] + [0] * len(b)
        best = current[0]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            value = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                value = min(value, previous2[j - 2] + 1)
            current[j] = value
            best = min(best, value)
        if best > limit:
            return limit + 1
        previous2, previous = previous, current
    return previous[-1]


def _deletes(word: str, depth: int) -> set[str]:
    frontier = {word}
    out: set[str] = set()
    for _ in range(depth):
        frontier = {w[:i] + w[i + 1 :] for w in frontier for i in range(len(w)) if len(w) > 1}
        out |= frontier
    return out


class _Vocabulary:
    """Title-word lookups against the index's ``words`` and ``typo`` tables."""

    __slots__ = ("_index", "_known")

    def __init__(self, index: RouterIndex) -> None:
        self._index = index
        self._known: dict[str, bool] = {}

    def known(self, word: str) -> bool:
        if word not in self._known:
            self._known[word] = self._index.tables["words"].get(word) is not None or (
                self._index.tables["typo"].get(word) is not None
                and word in self._index.ids("typo", word)
            )
        return self._known[word]

    def near(self, word: str, max_edits: int) -> list[tuple[int, str]]:
        """Vocabulary words within ``max_edits`` of ``word``: (distance, word), nearest first."""
        variants = {word, *_deletes(word, max_edits)}
        found: set[str] = set()
        for variant in variants:
            found.update(self._index.ids("typo", variant))
            if self._index.tables["words"].get(variant) is not None:
                found.add(variant)
        scored = [(damerau(word, w, max_edits), w) for w in found if w != word]
        return sorted((d, w) for d, w in scored if d <= max_edits)


def _title_ids(index: RouterIndex, words: Sequence[str], year: int | None) -> tuple[str, ...]:
    return index.ids("titles", title_key(tuple(words), year)) if words else ()


def _wordset_id(index: RouterIndex, words: Sequence[str], year: int | None) -> str | None:
    if year is None or len(set(words)) < 2:  # noqa: PLR2004
        return None
    value = index.tables["wordsets"].get(" ".join(sorted(set(words))) + f"|{year}")
    return value or None


def suggestions(
    index: RouterIndex,
    words: Sequence[str],
    year: int | None,
    *,
    type_words: frozenset[str],
    policy: TypoPolicy = DEFAULT_POLICY,
    extra: Iterable[str] = (),
) -> tuple[str, ...]:
    """Real instruments sharing >= 50 % of the cited content words, best first.

    Ranked by shared content words, then distance from the cited year, then edit distance
    between titles (plan departure 7). ``extra`` ids are always considered.
    """
    content = [w for w in dict.fromkeys(words) if w not in type_words and not w.isdigit()]
    if not content:
        return tuple(extra)[: policy.max_suggestions]
    shared: dict[str, int] = dict.fromkeys(extra, len(content))
    for word in content:
        raw = index.tables["words"].get(word)
        if raw is None or len(raw) > policy.common_word_value_chars:
            continue
        for iid in raw.split(","):
            shared[iid] = shared.get(iid, 0) + 1
    cited = " ".join(content)
    scored = []
    for iid, count in shared.items():
        if count / len(content) < policy.suggestion_min_shared:
            continue
        info = index.instrument(iid)
        if info is None:
            continue
        year_gap = abs(info.year - year) if year is not None else 0
        scored.append((-count, year_gap, damerau(cited, info.title.casefold(), 30), iid))
    return tuple(iid for *_, iid in sorted(scored)[: policy.max_suggestions])


def analyse_title(
    index: RouterIndex,
    words: Sequence[str],
    year: int | None,
    *,
    type_words: frozenset[str],
    policy: TypoPolicy = DEFAULT_POLICY,
) -> TitleVerdict:
    """Verdict for a cited title (content words incl. any type word, folded) that did not
    match exactly. The caller decides what the verdict means for the route status."""
    vocabulary = _Vocabulary(index)
    words = list(words)

    reordered = _wordset_id(index, words, year)
    if reordered is not None:
        info = index.instrument(reordered)
        title = info.title if info is not None else reordered
        return TitleVerdict("bound", (reordered,), (("reordered", title),), reason="reordered")

    if year is not None:
        other_years = [i for i in _title_ids(index, words, None) if _year_of(index, i) != year]
        if other_years:
            ranked = sorted(other_years, key=lambda i: abs(_year_of(index, i) - year))
            return TitleVerdict(
                "not_found",
                suggestions=tuple(ranked[: policy.max_suggestions]),
                reason="wrong_year",
            )

    unknown = [w for w in dict.fromkeys(words) if not w.isdigit() and not vocabulary.known(w)]
    if 0 < len(unknown) <= policy.max_unknown_words:
        verdict = _typo_verdict(index, vocabulary, words, unknown, year=year, policy=policy)
        if verdict is not None:
            return verdict

    offered = suggestions(index, words, year, type_words=type_words, policy=policy)
    return TitleVerdict("not_found", suggestions=offered, reason="no_such_title")


def _year_of(index: RouterIndex, instrument_id: str) -> int:
    info = index.instrument(instrument_id)
    return info.year if info is not None else 0


def _typo_verdict(
    index: RouterIndex,
    vocabulary: _Vocabulary,
    words: list[str],
    unknown: list[str],
    *,
    year: int | None,
    policy: TypoPolicy,
) -> TitleVerdict | None:
    options: list[list[tuple[int, str]]] = []
    for word in unknown:
        if len(word) < policy.min_correctable_length:
            return None  # short words are never corrected
        near = vocabulary.near(word, policy.clarify_edits)[: policy.max_candidates_per_word]
        if not near:
            return None
        options.append(near)
    hits: dict[str, tuple[int, tuple[tuple[str, str], ...]]] = {}
    for combo in product(*options):
        replacement = dict(zip(unknown, (w for _, w in combo), strict=True))
        corrected = [replacement.get(w, w) for w in words]
        distance = sum(d for d, _ in combo)
        corrections = tuple((u, replacement[u]) for u in unknown)
        ids = _title_ids(index, corrected, year) or tuple(
            filter(None, [_wordset_id(index, corrected, year)])
        )
        for iid in ids:
            if iid not in hits or distance < hits[iid][0]:
                hits[iid] = (distance, corrections)
    if not hits:
        return None
    ranked = sorted(hits, key=lambda i: hits[i][0])
    best = ranked[0]
    distance, corrections = hits[best]
    single_small = len(unknown) == 1 and distance <= policy.auto_correct_edits and len(hits) == 1
    if single_small:
        return TitleVerdict("bound", (best,), corrections, reason="typo")
    return TitleVerdict("ambiguous", tuple(ranked), corrections, reason="typo")
