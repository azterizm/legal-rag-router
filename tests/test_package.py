import legal_rag_router


def test_version_is_exposed() -> None:
    assert legal_rag_router.__version__
    assert legal_rag_router.__version__ != "0.0.0+unknown"
