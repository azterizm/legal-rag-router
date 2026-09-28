import json
import shutil
from pathlib import Path

import pytest

from scripts.check_licences import (
    REPO,
    check_data,
    check_index_sources,
    load_manifest,
    main,
)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(REPO / "data" / "MANIFEST.json", data / "MANIFEST.json")
    return data


def _set_count(data: Path, count: int | None) -> None:
    raw = json.loads((data / "MANIFEST.json").read_text())
    raw["sources"][0]["document_count"] = count
    (data / "MANIFEST.json").write_text(json.dumps(raw))


def _records(data: Path, n: int) -> None:
    year = data / "uk" / "ukpga" / "1996"
    year.mkdir(parents=True)
    for i in range(n):
        (year / f"uk_ukpga_1996_{i + 1}.jsonl").write_text("{}\n")


def test_committed_manifest_is_valid() -> None:
    manifest = load_manifest(REPO / "data" / "MANIFEST.json")
    assert {s.id for s in manifest.sources} == {"legislation.gov.uk"}


def test_empty_data_tree_passes(data_dir: Path) -> None:
    assert check_data(data_dir, load_manifest(data_dir / "MANIFEST.json")) == []


def test_matching_count_passes(data_dir: Path) -> None:
    _records(data_dir, 3)
    _set_count(data_dir, 3)
    assert check_data(data_dir, load_manifest(data_dir / "MANIFEST.json")) == []


def test_count_mismatch_fails(data_dir: Path) -> None:
    _records(data_dir, 3)
    _set_count(data_dir, 2)
    [problem] = check_data(data_dir, load_manifest(data_dir / "MANIFEST.json"))
    assert "document_count is 2 but 3" in problem


def test_null_count_with_records_fails(data_dir: Path) -> None:
    _records(data_dir, 1)
    _set_count(data_dir, None)
    [problem] = check_data(data_dir, load_manifest(data_dir / "MANIFEST.json"))
    assert "document_count is null" in problem


def test_unlicensed_tree_fails(data_dir: Path) -> None:
    (data_dir / "fr").mkdir()
    [problem] = check_data(data_dir, load_manifest(data_dir / "MANIFEST.json"))
    assert "data/fr is not covered" in problem


def test_derived_paths_are_covered(data_dir: Path) -> None:
    (data_dir / "index").mkdir()
    (data_dir / "harvest").mkdir()
    assert check_data(data_dir, load_manifest(data_dir / "MANIFEST.json")) == []


def test_invalid_manifest_fails(data_dir: Path, tmp_path: Path) -> None:
    raw = json.loads((data_dir / "MANIFEST.json").read_text())
    raw["sources"].append(raw["sources"][0])
    (data_dir / "MANIFEST.json").write_text(json.dumps(raw))
    assert main(["--data", str(data_dir), "--fixtures"]) == 1


def test_missing_manifest_fails(tmp_path: Path) -> None:
    assert main(["--data", str(tmp_path), "--fixtures"]) == 1


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ({"sources": ["legislation.gov.uk"]}, []),
        ({"sources": ["unknown-source"]}, ["not in the licence manifest"]),
        ({}, ["must list the sources"]),
    ],
)
def test_fixture_index_sources(
    data_dir: Path, tmp_path: Path, content: dict[str, list[str]], expected: list[str]
) -> None:
    index = tmp_path / "index"
    index.mkdir()
    (index / "index-manifest.json").write_text(json.dumps(content))
    problems = check_index_sources(index, load_manifest(data_dir / "MANIFEST.json"))
    assert len(problems) == len(expected)
    for problem, fragment in zip(problems, expected, strict=True):
        assert fragment in problem


def test_fixture_index_bad_json(data_dir: Path, tmp_path: Path) -> None:
    index = tmp_path / "index"
    index.mkdir()
    (index / "index-manifest.json").write_text("{")
    [problem] = check_index_sources(index, load_manifest(data_dir / "MANIFEST.json"))
    assert "not valid JSON" in problem


def test_main_passes_on_repo(data_dir: Path) -> None:
    assert main(["--data", str(data_dir)]) == 0
