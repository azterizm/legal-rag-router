"""The jurisdiction plugin protocol and the mention types grammars produce.

A grammar covers only the *shape* of citations in one legal system: provision markers,
official-number formats, instrument-type words, boundary words and cue phrases. Titles are
always data (the index), never patterns. Adding a jurisdiction means adding a plugin that
satisfies :class:`Grammar`; the router, index format, typo tiers and seal stay unchanged.

All spans are character offsets into the caller's original query.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from legal_rag_router.normalise import Folded

__all__ = [
    "Cue",
    "CueKind",
    "Grammar",
    "NumberMention",
    "ProvisionMention",
    "ProvisionRef",
]

CueKind = Literal["negation", "context_ref", "temporal", "out_of_coverage", "open_range"]


@dataclass(frozen=True, slots=True)
class ProvisionRef:
    """One cited provision: its unit chain and sub-divisions, as written.

    ``units`` pairs a unit word with its designator, outermost first:
    ``(("section", "124"),)`` or ``(("schedule", "2"), ("paragraph", "4"))``.
    ``subs`` are the bracketed sub-divisions: ``("1ZA", "a")``.
    """

    units: tuple[tuple[str, str], ...]
    subs: tuple[str, ...] = ()

    @property
    def unit(self) -> str:
        return self.units[0][0]

    def label(self) -> str:
        """Readable form: ``s.124(1ZA)(a)``, ``Sch. 2 para. 4(1)``."""
        short = {
            "section": "s.", "article": "art. ", "regulation": "reg. ", "rule": "r. ",
            "schedule": "Sch. ", "paragraph": "para. ", "part": "Part ", "chapter": "Ch. ",
        }  # fmt: skip
        head = " ".join(f"{short.get(u, u + ' ')}{d}".strip() for u, d in self.units)
        return head + "".join(f"({s})" for s in self.subs)


@dataclass(frozen=True, slots=True)
class ProvisionMention:
    """A provision citation found in the query, possibly a list or range."""

    start: int
    end: int
    refs: tuple[ProvisionRef, ...]
    is_range: bool = False
    """``refs`` holds exactly two endpoints of an inclusive range."""
    open_ended: bool = False
    """``et seq.`` / ``onwards``: never expanded, always a clarifying question."""


@dataclass(frozen=True, slots=True)
class NumberMention:
    """An official-number citation: ``SI 2011/3006``, ``1996 c. 18``, ``8 & 9 Eliz. 2 c. 69``."""

    start: int
    end: int
    key: str
    """Index lookup key (``si/2011/3006``, ``c/1996/18``, ``rc/eliz2/8-9/69``)."""
    instrument_type: str
    year: int | None
    number: str


@dataclass(frozen=True, slots=True)
class Cue:
    """A phrase that changes how nearby mentions are read."""

    start: int
    end: int
    kind: CueKind
    text: str
    detail: str | None = None


class Grammar(Protocol):
    """What each jurisdiction plugin supplies (plan step 7; frozen for Stage C)."""

    jurisdiction: str
    registry: str | None
    """Official registry for live checks (``VERIFY_LIVE``), or ``None``."""
    type_words: frozenset[str]
    """Folded words that name an instrument type ("act", "order", "ley" …)."""
    boundary_words: frozenset[str]
    """Folded words at which a cited title's span stops when extended left."""

    def provisions(self, query: str, folded: Folded) -> list[ProvisionMention]: ...

    def numbers(self, query: str, folded: Folded) -> list[NumberMention]: ...

    def cues(self, query: str, folded: Folded) -> list[Cue]: ...

    def provision_paths(self, ref: ProvisionRef, *, primary: bool) -> Sequence[tuple[str, ...]]:
        """Candidate coordinate provision paths for ``ref``, most literal first.

        ``primary`` is true for primary legislation, where mixed-up provision words are
        read as that system's own unit (UK: ``art.`` of an Act → ``s``).
        """
        ...
