import zipfile
from pathlib import Path

from scripts.check_wheel import check_wheel

METADATA = "Metadata-Version: 2.4\nName: legal-rag-router\nVersion: 0.1.0\n"


def _wheel(tmp_path: Path, files: dict[str, str]) -> Path:
    path = tmp_path / "legal_rag_router-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return path


def _clean_files() -> dict[str, str]:
    return {
        "legal_rag_router/__init__.py": "",
        "legal_rag_router/py.typed": "",
        "legal_rag_router-0.1.0.dist-info/METADATA": METADATA,
    }


def test_clean_wheel_passes(tmp_path: Path) -> None:
    assert check_wheel(_wheel(tmp_path, _clean_files())) == []


def test_stray_package_is_rejected(tmp_path: Path) -> None:
    files = _clean_files() | {"ingest/uk.py": ""}
    assert check_wheel(_wheel(tmp_path, files)) == ["unexpected file in wheel: ingest/uk.py"]


def test_runtime_dependency_is_rejected(tmp_path: Path) -> None:
    files = _clean_files()
    files["legal_rag_router-0.1.0.dist-info/METADATA"] = METADATA + "Requires-Dist: pydantic\n"
    assert check_wheel(_wheel(tmp_path, files)) == ["runtime dependency declared: pydantic"]


def test_missing_py_typed_is_rejected(tmp_path: Path) -> None:
    files = _clean_files()
    del files["legal_rag_router/py.typed"]
    assert check_wheel(_wheel(tmp_path, files)) == ["py.typed marker missing"]
