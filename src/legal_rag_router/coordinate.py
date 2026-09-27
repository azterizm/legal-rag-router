"""Canonical legal coordinates.

A coordinate names one legal unit as a ``/``-separated path::

    uk/ukpga/1996/18                    an instrument (calendar-numbered)
    uk/ukpga/1996/18/s124/1ZA/a         a provision inside it
    uk/ukpga/Eliz2/8-9/69/s1            a pre-1963 Act, keyed on its regnal identifier

The path is ``jurisdiction / instrument segments / provision segments``. How many
segments make up the instrument part (its *arity*) is declared per jurisdiction by a
:class:`CoordinateScheme`, because not every legal system numbers by year. The
``instrument_id`` used as a vector-store partition key is the jurisdiction plus the
instrument segments joined with ``_`` (``uk_ukpga_1996_18``).

The canonical string keeps the source's case (``1ZA``, ``ptI``). Lookups use
:attr:`Coordinate.key`, the casefolded string. The full grammar is in ``docs/grammar.md``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

__all__ = [
    "MAX_COORDINATE_LENGTH",
    "MAX_PROVISION_DEPTH",
    "Coordinate",
    "CoordinateError",
    "CoordinateScheme",
    "register_scheme",
    "scheme_for",
]

MAX_COORDINATE_LENGTH: Final = 256
"""Upper bound on the length of a coordinate string; longer input is rejected unparsed."""

MAX_PROVISION_DEPTH: Final = 16
"""Upper bound on the number of provision segments."""

# One provision segment: letters and digits, optionally dotted (``rule3.1``), no empty parts.
# Deliberately narrow: no quotes, spaces, slashes or wildcards can ever appear in a segment,
# which is what makes coordinates safe to interpolate into a filter expression (filters.py).
_SEGMENT: Final = re.compile(r"[0-9A-Za-z]{1,24}(?:\.[0-9A-Za-z]{1,24}){0,3}")


class CoordinateError(ValueError):
    """Raised when a string is not a well-formed coordinate."""


@dataclass(frozen=True, slots=True)
class CoordinateScheme:
    """How one jurisdiction lays out its coordinates.

    Attributes:
        jurisdiction: The first path segment, e.g. ``"uk"``.
        instrument_arity: Given the path segments after the jurisdiction, returns how many
            of them form the instrument part, or ``None`` if they cannot start a valid
            instrument. It may inspect the segments, so one jurisdiction can mix layouts
            (UK: 3 for ``ukpga/1996/18``, 4 for ``ukpga/Eliz2/8-9/69``).
        instrument_pattern: Full-match pattern for the instrument segments joined by ``/``.
        first_provision_pattern: Full-match pattern for the first provision segment, which
            must name a unit (``s124``, ``sch2``, ``art42``); later segments are free-form.
    """

    jurisdiction: str
    instrument_arity: Callable[[tuple[str, ...]], int | None]
    instrument_pattern: re.Pattern[str]
    first_provision_pattern: re.Pattern[str]


_SCHEMES: dict[str, CoordinateScheme] = {}


def register_scheme(scheme: CoordinateScheme) -> None:
    """Register a jurisdiction's coordinate scheme. Re-registering the same code is an error."""
    if scheme.jurisdiction in _SCHEMES:
        raise ValueError(f"coordinate scheme already registered for {scheme.jurisdiction!r}")
    if not re.fullmatch(r"[a-z]{2,8}", scheme.jurisdiction):
        raise ValueError(f"invalid jurisdiction code {scheme.jurisdiction!r}")
    _SCHEMES[scheme.jurisdiction] = scheme


def scheme_for(jurisdiction: str) -> CoordinateScheme:
    """Return the registered scheme for ``jurisdiction``.

    Raises:
        CoordinateError: if no scheme is registered for it.
    """
    try:
        return _SCHEMES[jurisdiction]
    except KeyError:
        raise CoordinateError(f"unknown jurisdiction {jurisdiction!r}") from None


@dataclass(frozen=True, slots=True, order=True)
class Coordinate:
    """An immutable, validated legal coordinate.

    Build one with :meth:`parse` (from a canonical string) or :meth:`of` (from parts);
    both validate against the jurisdiction's :class:`CoordinateScheme`.

    Attributes:
        jurisdiction: ``"uk"``, ``"es"``, …
        instrument: The instrument segments after the jurisdiction,
            e.g. ``("ukpga", "1996", "18")``.
        provision: The provision segments, e.g. ``("s124", "1ZA", "a")``; empty for an
            instrument-level coordinate.
    """

    jurisdiction: str
    instrument: tuple[str, ...]
    provision: tuple[str, ...] = ()
    _text: str = field(default="", init=False, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        scheme = scheme_for(self.jurisdiction)
        arity = scheme.instrument_arity(self.instrument)
        if arity is None or arity != len(self.instrument):
            raise CoordinateError(f"invalid instrument path {'/'.join(self.instrument)!r}")
        if not scheme.instrument_pattern.fullmatch("/".join(self.instrument)):
            raise CoordinateError(f"invalid instrument path {'/'.join(self.instrument)!r}")
        if len(self.provision) > MAX_PROVISION_DEPTH:
            raise CoordinateError("provision path too deep")
        for i, segment in enumerate(self.provision):
            if not _SEGMENT.fullmatch(segment):
                raise CoordinateError(f"invalid provision segment {segment!r}")
            if i == 0 and not scheme.first_provision_pattern.fullmatch(segment):
                raise CoordinateError(f"first provision segment must name a unit: {segment!r}")
        text = "/".join((self.jurisdiction, *self.instrument, *self.provision))
        if len(text) > MAX_COORDINATE_LENGTH:
            raise CoordinateError("coordinate too long")
        object.__setattr__(self, "_text", text)

    # ------------------------------------------------------------------ construction

    @classmethod
    def of(
        cls, jurisdiction: str, instrument: tuple[str, ...], provision: tuple[str, ...] = ()
    ) -> Coordinate:
        """Build and validate a coordinate from its parts."""
        return cls(jurisdiction, tuple(instrument), tuple(provision))

    @classmethod
    def parse(cls, text: str) -> Coordinate:
        """Parse a canonical coordinate string.

        Parsing is exact: case is significant and no normalisation is applied. Use the
        index's casefolded lookup to resolve user-typed coordinates to canonical form.

        Raises:
            CoordinateError: if ``text`` is not a well-formed coordinate.
        """
        if not isinstance(text, str):
            raise CoordinateError("coordinate must be a string")
        if len(text) > MAX_COORDINATE_LENGTH:
            raise CoordinateError("coordinate too long")
        parts = text.split("/")
        if len(parts) < 2 or any(p == "" for p in parts):  # noqa: PLR2004
            raise CoordinateError(f"malformed coordinate {text!r}")
        jurisdiction, rest = parts[0], tuple(parts[1:])
        scheme = scheme_for(jurisdiction)
        arity = scheme.instrument_arity(rest)
        if arity is None or arity > len(rest):
            raise CoordinateError(f"incomplete or invalid instrument in {text!r}")
        return cls(jurisdiction, rest[:arity], rest[arity:])

    @classmethod
    def try_parse(cls, text: str) -> Coordinate | None:
        """Like :meth:`parse` but returns ``None`` instead of raising."""
        try:
            return cls.parse(text)
        except CoordinateError:
            return None

    # ------------------------------------------------------------------ views

    def __str__(self) -> str:
        return self._text

    @property
    def key(self) -> str:
        """Casefolded lookup key. Two distinct canonical coordinates never share a key
        (the index build enforces this)."""
        return self._text.casefold()

    @property
    def instrument_id(self) -> str:
        """Partition key: jurisdiction and instrument segments joined with ``_``."""
        return "_".join((self.jurisdiction, *self.instrument))

    @property
    def instrument_coordinate(self) -> Coordinate:
        """The instrument-level coordinate this one belongs to."""
        return self if self.is_instrument else Coordinate(self.jurisdiction, self.instrument)

    @property
    def is_instrument(self) -> bool:
        """True when this coordinate names a whole instrument (no provision segments)."""
        return not self.provision

    @property
    def parent(self) -> Coordinate | None:
        """The enclosing coordinate, or ``None`` for an instrument."""
        if self.is_instrument:
            return None
        return Coordinate(self.jurisdiction, self.instrument, self.provision[:-1])

    @property
    def series(self) -> str:
        """The first instrument segment (``ukpga``, ``uksi``, ``boe`` …)."""
        return self.instrument[0]

    def child(self, *segments: str) -> Coordinate:
        """Return the coordinate for ``segments`` under this one."""
        return Coordinate(self.jurisdiction, self.instrument, (*self.provision, *segments))

    def is_ancestor_of(self, other: Coordinate) -> bool:
        """True when ``other`` lies strictly beneath this coordinate."""
        return (
            other.jurisdiction == self.jurisdiction
            and other.instrument == self.instrument
            and len(other.provision) > len(self.provision)
            and other.provision[: len(self.provision)] == self.provision
        )
