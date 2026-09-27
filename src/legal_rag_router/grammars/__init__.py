"""Jurisdiction plugins: coordinate schemes and citation grammars.

Importing this package registers every bundled jurisdiction's coordinate scheme.
"""

from legal_rag_router.grammars import uk as uk
from legal_rag_router.grammars import uk_grammar as uk_grammar

__all__ = ["uk", "uk_grammar"]
