"""Concept discovery for citation-less queries: the *discover* half of discover-then-bind.

``route()`` binds what a query cites. A research query usually cites nothing ("unfair
dismissal compensatory award statutory cap") and routes ``ROUTE_UNRESOLVED`` with
``next_action = DISCOVER_THEN_BIND``. :func:`discover` then ranks the provisions of the
concept index (:mod:`legal_rag_router.concepts`) and returns candidate **coordinates** for
the user, or an orchestrating agent, to confirm. It never binds and never returns
provision text. A confirmed candidate is routed like any identifier (``route(coordinate)``),
so text reaches a caller only through a bound coordinate (``docs/contract.md`` §5).

Ranking is BM25F over the five fields. Each field's term count is normalised by the
field's length, weighted, summed, then saturated. Query words are stemmed like the index;
thesaurus expansions count at ``synonym_weight``. Every candidate is checked against the
router index before it is offered.

A result is ``confident`` when its top candidate matches at least ``min_share`` of the
query's weight (the summed inverse document frequency of the query words the index knows).
Below that, the candidates are still listed, but a caller should present them as weak
leads, not as the answer.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Final

from legal_rag_router.concepts import FIELDS, PRIOR_FLAGS, ConceptIndex, terms
from legal_rag_router.coordinate import Coordinate
from legal_rag_router.index import RouterIndex
from legal_rag_router.result import NextAction

__all__ = ["DEFAULT_DISCOVERY", "Discovered", "DiscoveryPolicy", "DiscoveryResult", "discover"]

MAX_DISCOVERY_QUERY: Final = 4096
_UNIT_LABELS: Final = {"s": "s.", "reg": "reg.", "art": "art.", "rule": "r.", "para": "para."}


@dataclass(frozen=True, slots=True)
class DiscoveryPolicy:
    """Every ranking parameter in one place.

    The defaults were tuned on the concept battery's dev slice only (29 Sept 2026: a
    coordinate search maximising MRR; docs/discovery.md, D4) and are frozen for the D5 run.
    """

    field_weights: tuple[float, ...] = (2.0, 1.0, 0.5, 0.5, 0.3)
    """heading, cross-heading, structure, title, body."""
    field_b: tuple[float, ...] = (0.6, 0.3, 0.9, 0.3, 0.3)
    """Length normalisation per field (0: none, 1: full)."""
    k1: float = 0.6
    synonym_weight: float = 1.0
    """At most 1: a synonym never outweighs the word typed."""
    max_df_share: float = 0.1
    """Words in more than this share of documents carry no signal and are not scored."""
    instruments: bool = False
    """Also rank whole instruments (their titles and long titles)."""
    prior_penalties: tuple[float, ...] = (0.3, 0.4, 0.4, 0.5, 0.3, 0.6)
    """Score multiplier for each source flag (``PRIOR_FLAGS`` order: repealed, Northern
    Ireland, Scotland, amending, commencement, secondary). A query naming Northern Ireland
    or Scotland lifts that penalty."""
    in_degree_weight: float = 0.6
    """Boost up to ``1 + in_degree_weight`` for the most-cited instruments."""
    rerank_pool: int = 300
    """Candidates re-ranked with the priors (the rest are cut on the text score alone)."""
    min_share: float = 0.5
    """Set by rule on dev: the largest value keeping 90 % of dev hits (gold in the top 10)
    confident."""
    limit: int = 10


DEFAULT_DISCOVERY: Final = DiscoveryPolicy()


@dataclass(frozen=True, slots=True)
class Discovered:
    """A candidate coordinate, with the evidence for it. Never text."""

    coordinate: Coordinate
    label: str
    """"Employment Rights Act 1996, s. 124: Limit of compensatory award etc." """
    heading: str | None
    score: float
    matched: tuple[str, ...]
    """The query terms (stemmed, as indexed) this candidate matched, directly or through
    a thesaurus expansion."""


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    query: str
    candidates: tuple[Discovered, ...]
    confident: bool
    reason: str | None
    """``no_concept_index``, ``not_a_string``, ``query_too_long``, ``no_terms``,
    ``no_match``, ``low_confidence``, or ``None`` for a confident result."""
    index_snapshot: str | None
    next_action: NextAction = field(default=NextAction.ASK_USER)
    """Confirm one candidate, then route it; never retrieve from a candidate unconfirmed."""


def provision_label(coordinate: Coordinate) -> str:
    """``s124`` → ``s. 124``; ``sch2/para3`` → ``Sch. 2 para. 3``; ``sch`` → ``Schedule``."""
    parts = []
    for segment in coordinate.provision:
        if segment.startswith("sch"):
            parts.append(f"Sch. {segment[3:]}" if segment[3:] else "Schedule")
            continue
        for prefix in ("rule", "reg", "art", "para", "pt", "ch", "s"):
            if segment.startswith(prefix):
                label = _UNIT_LABELS.get(prefix, f"{prefix}.")
                parts.append(f"{label} {segment[len(prefix) :]}")
                break
        else:
            parts.append(segment)
    return " ".join(parts)


def _query_terms(
    concepts: ConceptIndex, words: list[str], policy: DiscoveryPolicy
) -> dict[str, tuple[float, int]]:
    """Index term → (weight, index of the query word it came from)."""
    out: dict[str, tuple[float, int]] = {}
    for i, word in enumerate(words):
        out[word] = (1.0, i)
    for i, word in enumerate(words):
        for synonym in concepts.thesaurus.get(word, ()):
            out.setdefault(synonym, (policy.synonym_weight, i))
    return out


def discover(
    concepts: ConceptIndex | None,
    index: RouterIndex,
    query: object,
    policy: DiscoveryPolicy = DEFAULT_DISCOVERY,
) -> DiscoveryResult:
    """Rank candidate coordinates for a citation-less query. Never raises for any input."""
    snapshot = index.snapshot
    if not isinstance(query, str) or concepts is None or len(query) > MAX_DISCOVERY_QUERY:
        reason = (
            "not_a_string"
            if not isinstance(query, str)
            else "no_concept_index"
            if concepts is None
            else "query_too_long"
        )
        return _empty(query if isinstance(query, str) else "", reason, snapshot)
    typed = list(dict.fromkeys(terms(query)))
    candidates: list[Discovered] = []
    share = 0.0
    if typed:
        scores, matched, total = _score(concepts, typed, policy)
        candidates = _candidates(concepts, index, typed, scores, matched, policy=policy)
        share = _share(concepts, candidates[0].matched, total) if candidates else 0.0
    if not candidates:
        return _empty(query, "no_match" if typed else "no_terms", snapshot)
    confident = share >= policy.min_share
    return DiscoveryResult(
        query,
        tuple(candidates),
        confident=confident,
        reason=None if confident else "low_confidence",
        index_snapshot=snapshot,
    )


def _empty(query: str, reason: str, snapshot: str) -> DiscoveryResult:
    return DiscoveryResult(query, (), confident=False, reason=reason, index_snapshot=snapshot)


def _score(
    concepts: ConceptIndex, typed: list[str], policy: DiscoveryPolicy
) -> tuple[dict[int, float], dict[int, int], float]:
    """BM25F scores, the query words each document matched (a bit per word), and the
    query's total weight (the idf of the typed words the index knows)."""
    n = concepts.doc_count
    cutoff = max(1.0, policy.max_df_share * n)
    first_instrument = concepts.first_instrument_doc
    width = len(FIELDS)
    weights, bs, avg = policy.field_weights, policy.field_b, concepts.average_lengths
    lengths, k1 = concepts.lengths, policy.k1
    # Per field: tf~ = w * tf / (1 - b + b * len / avg) = tf * w / (c0 + c1 * len)
    c0 = [1.0 - b for b in bs]
    c1 = [b / a if a else 0.0 for b, a in zip(bs, avg, strict=True)]
    scores: dict[int, float] = {}
    matched: dict[int, int] = {}
    total = 0.0
    query_terms = _query_terms(concepts, typed, policy)
    dfs = {t: concepts.document_frequency(t) for t in query_terms}
    rarest = sorted(dfs[t] for t in typed if dfs[t])
    if rarest and rarest[0] > cutoff:
        # Every word the user typed is common: score the two rarest rather than nothing.
        cutoff = float(rarest[min(1, len(rarest) - 1)])
    for term, (qweight, origin) in query_terms.items():
        df = dfs[term]
        if df == 0:
            continue
        idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
        if term == typed[origin]:  # a word the user typed, not an expansion
            total += idf
        if df > cutoff:
            continue
        gain, bit = qweight * idf, 1 << origin
        docs, tfs = concepts.postings(term)
        for doc, packed in zip(docs, tfs, strict=True):
            if doc >= first_instrument and not policy.instruments:
                continue
            base = doc * width
            tf = 0.0
            for f in range(width):
                count = (packed >> (6 * f)) & 63
                if count:
                    tf += count * weights[f] / (c0[f] + c1[f] * lengths[base + f])
            scores[doc] = scores.get(doc, 0.0) + gain * tf / (k1 + tf)
            matched[doc] = matched.get(doc, 0) | bit
    return scores, matched, total


def _candidates(
    concepts: ConceptIndex,
    index: RouterIndex,
    typed: list[str],
    scores: dict[int, float],
    matched: dict[int, int],
    *,
    policy: DiscoveryPolicy,
) -> list[Discovered]:
    penalties = list(policy.prior_penalties)
    if {"northern", "ireland"} <= set(typed):
        penalties[PRIOR_FLAGS.index("northern_ireland")] = 1.0
    if {"scotland", "scottish"} & set(typed):
        penalties[PRIOR_FLAGS.index("scotland")] = 1.0
    pool = heapq.nlargest(policy.rerank_pool, scores, key=lambda d: (scores[d], -d))
    adjusted = {d: scores[d] * _prior(concepts, d, penalties, policy) for d in pool}
    out: list[Discovered] = []
    for doc_id in sorted(pool, key=lambda d: (-adjusted[d], d)):
        doc = concepts.doc(doc_id)
        canonical = index.coordinates.canonical(doc.coordinate)
        coordinate = Coordinate.try_parse(canonical) if canonical else None
        if coordinate is None or index.instrument(coordinate.instrument_id) is None:
            continue  # never offer what the router cannot bind
        info = index.info(coordinate.instrument_id)
        label = info.title
        if coordinate.provision:
            label = f"{label}, {provision_label(coordinate)}"
            if doc.heading:
                label = f"{label}: {doc.heading}"
        words = tuple(typed[i] for i in range(len(typed)) if matched[doc_id] >> i & 1)
        out.append(Discovered(coordinate, label, doc.heading, round(adjusted[doc_id], 4), words))
        if len(out) == policy.limit:
            break
    return out


def _prior(
    concepts: ConceptIndex, doc_id: int, penalties: list[float], policy: DiscoveryPolicy
) -> float:
    flags, degree = concepts.prior(doc_id)
    factor = 1.0 + policy.in_degree_weight * degree / 255
    for i, penalty in enumerate(penalties):
        if flags >> i & 1:
            factor *= penalty
    return factor


def _share(concepts: ConceptIndex, words: tuple[str, ...], total: float) -> float:
    """The share of the query's weight that the words in ``words`` carry."""
    if total <= 0:
        return 0.0
    n = concepts.doc_count
    got = 0.0
    for word in words:
        df = concepts.document_frequency(word)
        got += math.log(1.0 + (n - df + 0.5) / (df + 0.5))
    return got / total
