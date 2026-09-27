"""Deterministic coordinate pre-routing and epistemic abstention for legal RAG.

The router takes a query string and returns exactly one routing decision: a bound
coordinate, a clarifying question, a refusal because the cited law does not exist,
an out-of-coverage notice, or "no citation found". It uses no model, no network and
no disk I/O per query.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("legal-rag-router")
except PackageNotFoundError:  # pragma: no cover - only when run from a bare source tree
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
