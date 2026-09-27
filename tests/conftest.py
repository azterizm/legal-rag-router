from __future__ import annotations

from pathlib import Path

import pytest

from legal_rag_router.index import RouterIndex, load_index

FIXTURE_INDEX = Path(__file__).resolve().parent / "fixtures" / "index"


@pytest.fixture(scope="session")
def fixture_index() -> RouterIndex:
    """The committed real UK fixture index (tests/fixtures/fixture.toml)."""
    return load_index(FIXTURE_INDEX)
