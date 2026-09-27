"""Every concrete UK coordinate written in docs/grammar.md is well-formed and round-trips."""

import re
from pathlib import Path

import pytest

from legal_rag_router import Coordinate

GRAMMAR = Path(__file__).resolve().parents[1] / "docs" / "grammar.md"
# Examples the document deliberately shows as invalid or partial.
DOCUMENTED_NON_COORDINATES = {"uk/ukpga/1996"}


def _doc_coordinates() -> list[str]:
    found = re.findall(r"`(uk/[^`\s]+)`", GRAMMAR.read_text(encoding="utf-8"))
    return sorted({c for c in found if not re.search(r"[…{'\[]", c)} - DOCUMENTED_NON_COORDINATES)


def test_document_has_examples() -> None:
    assert len(_doc_coordinates()) >= 5


@pytest.mark.parametrize("text", _doc_coordinates())
def test_doc_coordinate_round_trips(text: str) -> None:
    assert str(Coordinate.parse(text)) == text
