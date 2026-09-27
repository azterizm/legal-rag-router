"""Public result types: the six statuses, the next action they require, and ``RouteResult``.

Every result names the caller's next action (``docs/contract.md``). The rule for callers
and later layers: **text reaches generation only through a bound coordinate.**
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from legal_rag_router.coordinate import Coordinate

__all__ = [
    "Candidate",
    "NextAction",
    "ParsedCitation",
    "Resolution",
    "RouteContext",
    "RouteResult",
    "RouteStatus",
    "Source",
]


class RouteStatus(StrEnum):
    BOUNDED = "ROUTE_BOUNDED"
    AMBIGUOUS = "ROUTE_AMBIGUOUS"
    INSTRUMENT_NOT_FOUND = "EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND"
    PROVISION_NOT_FOUND = "EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND"
    OUT_OF_COVERAGE = "ROUTE_OUT_OF_COVERAGE"
    UNRESOLVED = "ROUTE_UNRESOLVED"

    @property
    def is_abstention(self) -> bool:
        return self in (RouteStatus.INSTRUMENT_NOT_FOUND, RouteStatus.PROVISION_NOT_FOUND)


class NextAction(StrEnum):
    """What the caller must do next (``docs/contract.md``)."""

    RETRIEVE_BOUNDED = "RETRIEVE_BOUNDED"
    """Retrieve only within ``partition_filter(result)``; never widen it."""
    ASK_USER = "ASK_USER"
    """Show ``clarification`` and ``candidates``; never pick one silently."""
    REFUSE = "REFUSE"
    """Refuse, with the message, suggestions and snapshot date; never retry retrieval."""
    VERIFY_LIVE = "VERIFY_LIVE"
    """Ask the official registry (Phase 4 adapters); never answer from other law."""
    DECLARE_OUT_OF_COVERAGE = "DECLARE_OUT_OF_COVERAGE"
    """Say the citation is outside the indexed corpus."""
    DISCOVER_THEN_BIND = "DISCOVER_THEN_BIND"
    """Discover candidate coordinates, bind one through the router; never generate freely."""


Resolution = Literal["resolved", "not_in_index", "out_of_coverage", "unlinked", "excluded"]
Source = Literal["grammar", "identifier", "context"]


@dataclass(frozen=True, slots=True)
class Candidate:
    """A coordinate offered for clarification or as a suggestion, with a readable label."""

    coordinate: Coordinate
    label: str


@dataclass(frozen=True, slots=True)
class ParsedCitation:
    """What was extracted from the query, whether or not it resolved (Unit 1, 07 §2)."""

    span: tuple[int, int]
    jurisdiction_hint: str | None
    instrument_type: str | None
    title_as_cited: str | None
    year: int | None
    number: str | None
    provision: str | None
    resolution: Resolution
    live_checkable: bool


@dataclass(frozen=True, slots=True)
class RouteContext:
    """The previous turn's bound coordinates, passed by the caller for follow-ups.

    The router re-validates every coordinate against the index; an instrument named in
    the query always beats context.
    """

    coordinates: tuple[Coordinate | str, ...] = ()


@dataclass(frozen=True, slots=True)
class RouteResult:
    """The single routing decision for one query."""

    status: RouteStatus
    next_action: NextAction
    coordinates: tuple[Coordinate, ...] = ()
    """Bound coordinates (``ROUTE_BOUNDED`` only)."""
    excluded: tuple[Coordinate, ...] = ()
    """Coordinates the query explicitly excludes; the partition filter removes them."""
    candidates: tuple[Candidate, ...] = ()
    clarification: str | None = None
    citations: tuple[ParsedCitation, ...] = ()
    citation_span: tuple[int, int] | None = None
    corrections: tuple[tuple[str, str], ...] = ()
    suggestions: tuple[Candidate, ...] = ()
    repealed: bool = False
    temporal_hint: str | None = None
    citation_signal: bool = False
    source: Source = "grammar"
    index_snapshot: str = ""
    latency_ns: int = 0
    reason: str | None = None
    """Machine-readable detail for non-bound outcomes (e.g. ``provision_structure_unavailable``)."""
    messages: tuple[str, ...] = field(default=())
    """Human-readable explanation lines (refusal wording, coverage notes)."""
