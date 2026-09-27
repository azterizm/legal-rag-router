"""Deterministic coordinate pre-routing and epistemic abstention for legal RAG.

The router takes a query string and returns exactly one routing decision: a bound
coordinate, a clarifying question, a refusal because the cited law does not exist,
an out-of-coverage notice, or "no citation found". It uses no model, no network and
no disk I/O per query.

    >>> from legal_rag_router import Router, RouteStatus, partition_filter
    >>> router = Router.from_path("data/index")                    # doctest: +SKIP
    >>> result = router.route("section 124 of the Employment Rights Act 1996")  # doctest: +SKIP
    >>> result.status is RouteStatus.BOUNDED                         # doctest: +SKIP
    True
    >>> partition_filter(result)                                     # doctest: +SKIP
    'instrument_id in ["uk_ukpga_1996_18"] and (coordinate == ... )'
"""

from importlib.metadata import PackageNotFoundError, version

from legal_rag_router import grammars as _grammars  # registers bundled coordinate schemes
from legal_rag_router.coordinate import Coordinate, CoordinateError
from legal_rag_router.filters import FilterError, partition_filter
from legal_rag_router.index import IndexLoadError, RouterIndex, load_index
from legal_rag_router.result import (
    Candidate,
    NextAction,
    ParsedCitation,
    RouteContext,
    RouteResult,
    RouteStatus,
)
from legal_rag_router.router import Router

try:
    __version__ = version("legal-rag-router")
except PackageNotFoundError:  # pragma: no cover - only when run from a bare source tree
    __version__ = "0.0.0+unknown"

del _grammars

__all__ = [
    "Candidate",
    "Coordinate",
    "CoordinateError",
    "FilterError",
    "IndexLoadError",
    "NextAction",
    "ParsedCitation",
    "RouteContext",
    "RouteResult",
    "RouteStatus",
    "Router",
    "RouterIndex",
    "__version__",
    "load_index",
    "partition_filter",
]
