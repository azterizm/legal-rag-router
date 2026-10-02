import hashlib
import tarfile
from pathlib import Path

import pytest

from legal_rag_router import load_index
from scripts.package_index import NOTICE, main, package

FIXTURE_INDEX = Path(__file__).resolve().parent / "fixtures" / "index"


def test_index_archive_unpacks_to_a_loadable_index(tmp_path: Path) -> None:
    assets = package(tmp_path / "out", FIXTURE_INDEX, None)
    names = [p.name for p in assets]
    snapshot = load_index(FIXTURE_INDEX).snapshot
    assert names == [f"index-uk-{snapshot}.tar.gz", "NOTICE", "SHA256SUMS"]
    unpacked = tmp_path / "data" / "index"
    unpacked.mkdir(parents=True)
    with tarfile.open(assets[0]) as tar:
        assert all("/" not in m.name for m in tar.getmembers())
        tar.extractall(unpacked, filter="data")
    assert load_index(unpacked).snapshot == snapshot
    assert sorted(p.name for p in unpacked.iterdir()) == sorted(
        p.name for p in FIXTURE_INDEX.iterdir() if p.is_file()
    )
    assert (assets[1]).read_bytes() == NOTICE.read_bytes()


def test_checksums_cover_every_asset(tmp_path: Path) -> None:
    assets = package(tmp_path, FIXTURE_INDEX, None)
    lines = assets[-1].read_text(encoding="utf-8").splitlines()
    expected = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}" for p in assets[:-1]]
    assert lines == expected


def test_archives_are_reproducible(tmp_path: Path) -> None:
    first = package(tmp_path / "a", FIXTURE_INDEX, None)[0].read_bytes()
    second = package(tmp_path / "b", FIXTURE_INDEX, None)[0].read_bytes()
    assert first == second


def test_refuses_to_overwrite(tmp_path: Path) -> None:
    package(tmp_path, FIXTURE_INDEX, None)
    with pytest.raises(FileExistsError):
        package(tmp_path, FIXTURE_INDEX, None)


def test_main_prints_sizes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path), "--index", str(FIXTURE_INDEX), "--no-concepts"]) == 0
    assert "SHA256SUMS" in capsys.readouterr().out
