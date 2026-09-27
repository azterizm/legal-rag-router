"""Partition-bound filter expression for the vector store (02 section 4).

A pure function with no vector-store dependency. It turns a ``ROUTE_BOUNDED`` result into
a boolean expression over two fields every stored chunk carries: ``instrument_id`` (the
partition key) and ``coordinate``::

    instrument_id in ["uk_ukpga_1996_18"]
      and (coordinate == "uk/ukpga/1996/18/s124" or coordinate like "uk/ukpga/1996/18/s124/%")
      and not (coordinate == "uk/ukpga/1996/18/s98" or coordinate like "uk/ukpga/1996/18/s98/%")

* ``like "p/%"`` includes every sub-provision and keeps ``s124`` from matching ``s124A``.
* An instrument-level coordinate binds the whole instrument; several citations bind every
  cited instrument and nothing else.
* Excluded coordinates (roadmap decision 15) are removed with ``and not (...)``.

Only a bound result produces a filter, and every value is re-checked against the coordinate
grammar and a closed alphabet before it is interpolated, so nothing taken from a query can
inject into the expression.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from legal_rag_router.coordinate import Coordinate
from legal_rag_router.result import RouteResult, RouteStatus

__all__ = ["FilterError", "partition_filter"]

_SAFE: Final = re.compile(r"[0-9A-Za-z./_\-]{1,256}")


class FilterError(ValueError):
    """Raised when a filter is requested for a result that must not be retrieved from."""


def _checked(coordinate: Coordinate) -> str:
    text = str(Coordinate.parse(str(coordinate)))  # re-validate against the grammar
    if not _SAFE.fullmatch(text) or not _SAFE.fullmatch(coordinate.instrument_id):
        raise FilterError(f"coordinate outside the safe alphabet: {text!r}")
    return text


def _scope(coordinates: Iterable[Coordinate]) -> list[str]:
    return [f'(coordinate == "{c}" or coordinate like "{c}/%")' for c in map(_checked, coordinates)]


def partition_filter(result: RouteResult) -> str:
    """The retrieval filter for a bound result.

    Raises:
        FilterError: if ``result`` is not ``ROUTE_BOUNDED`` (text reaches generation only
            through a bound coordinate), has no coordinates, or holds an unsafe value.
    """
    if result.status is not RouteStatus.BOUNDED:
        raise FilterError(f"no retrieval filter for {result.status}: follow result.next_action")
    if not result.coordinates:
        raise FilterError("a bound result without coordinates")
    for coordinate in (*result.coordinates, *result.excluded):
        _checked(coordinate)
    ids = sorted({c.instrument_id for c in result.coordinates})
    expression = "instrument_id in [" + ", ".join(f'"{i}"' for i in ids) + "]"
    provisions = [c for c in result.coordinates if not c.is_instrument]
    whole = {c.instrument_id for c in result.coordinates if c.is_instrument}
    # A provision of an instrument that is also bound whole adds nothing to the scope.
    provisions = [c for c in provisions if c.instrument_id not in whole]
    if provisions:
        scopes = _scope(provisions)
        scopes += [f'instrument_id == "{i}"' for i in sorted(whole)]
        expression += " and (" + " or ".join(scopes) + ")"
    if result.excluded:
        expression += " and not (" + " or ".join(_scope(result.excluded)) + ")"
    return expression
