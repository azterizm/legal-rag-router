"""Index loading and lookups against the committed fixture index (M6)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from legal_rag_router.index import (
    FORMAT_VERSION,
    INDEX_FILES,
    MANIFEST_NAME,
    IndexLoadError,
    RouterIndex,
    load_index,
)
from tests.conftest import FIXTURE_INDEX


@pytest.fixture
def index_copy(tmp_path: Path) -> Path:
    target = tmp_path / "index"
    shutil.copytree(FIXTURE_INDEX, target)
    return target


# ---------------------------------------------------------------- integrity


def test_fixture_loads_and_is_labelled(fixture_index: RouterIndex) -> None:
    manifest = fixture_index.manifest
    assert manifest["format_version"] == FORMAT_VERSION
    assert fixture_index.snapshot == "2026-09-28"
    assert manifest["sources"] == ["legislation.gov.uk"]
    assert set(manifest["files"]) == set(INDEX_FILES)


@pytest.mark.parametrize(
    "name", ["coordinates.tbl", "coordinates.off", "titles.tbl", "aliases.json"]
)
def test_tampered_file_refuses_to_load(index_copy: Path, name: str) -> None:
    path = index_copy / name
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0x01  # flip one bit
    path.write_bytes(bytes(data))
    with pytest.raises(IndexLoadError, match="hash mismatch"):
        load_index(index_copy)


def test_missing_file_refuses_to_load(index_copy: Path) -> None:
    (index_copy / "typo.tbl").unlink()
    with pytest.raises(IndexLoadError, match="missing index file"):
        load_index(index_copy)


def test_unknown_format_version_refuses_to_load(index_copy: Path) -> None:
    manifest = json.loads((index_copy / MANIFEST_NAME).read_text())
    manifest["format_version"] = FORMAT_VERSION + 1
    (index_copy / MANIFEST_NAME).write_text(json.dumps(manifest))
    with pytest.raises(IndexLoadError, match="unsupported index format version"):
        load_index(index_copy)


def test_manifest_without_hash_refuses_to_load(index_copy: Path) -> None:
    manifest = json.loads((index_copy / MANIFEST_NAME).read_text())
    del manifest["files"]["words.tbl"]
    (index_copy / MANIFEST_NAME).write_text(json.dumps(manifest))
    with pytest.raises(IndexLoadError, match=r"no hash for words\.tbl"):
        load_index(index_copy)


@pytest.mark.parametrize("content", ["", "{", "[]", '{"format_version": 1}'])
def test_bad_manifest_refuses_to_load(index_copy: Path, content: str) -> None:
    (index_copy / MANIFEST_NAME).write_text(content)
    with pytest.raises(IndexLoadError):
        load_index(index_copy)


def test_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(IndexLoadError, match=r"no index-manifest\.json"):
        load_index(tmp_path)


# ---------------------------------------------------------------- lookups


def test_coordinate_existence_and_canonical_case(fixture_index: RouterIndex) -> None:
    coords = fixture_index.coordinates
    assert "uk/ukpga/1996/18/s124/1ZA/a" in coords
    assert "UK/UKPGA/1996/18/S124/1za/A" in coords
    assert coords.canonical("uk/ukpga/1996/18/s124/1za/a") == "uk/ukpga/1996/18/s124/1ZA/a"
    assert "uk/ukpga/1996/18/s999" not in coords
    assert "uk/ukpga/1996/18/s124A" in coords
    assert 124 not in coords


def test_descendants_respect_segment_boundary(fixture_index: RouterIndex) -> None:
    coords = fixture_index.coordinates
    under = list(coords.descendants("uk/ukpga/1996/18/s124"))
    assert "uk/ukpga/1996/18/s124/1ZA/a" in under
    assert not any(c.startswith("uk/ukpga/1996/18/s124A") for c in under)
    children = list(coords.children("uk/ukpga/1996/18/s124"))
    assert "uk/ukpga/1996/18/s124/1ZA" in children
    assert "uk/ukpga/1996/18/s124/1ZA/a" not in children


def test_case_variants_bind_only_on_exact_case(fixture_index: RouterIndex) -> None:
    coords = fixture_index.coordinates
    lower, upper = "uk/uksi/1990/2145/sch1/para34/a", "uk/uksi/1990/2145/sch1/para34/A"
    assert set(coords.spellings(lower)) == {lower, upper}
    assert coords.canonical(lower) == lower
    assert coords.canonical(upper) == upper
    assert coords.canonical("UK/UKSI/1990/2145/SCH1/PARA34/A") is None  # ambiguous by case alone


def test_instrument_metadata(fixture_index: RouterIndex) -> None:
    era = fixture_index.instrument("uk_ukpga_1996_18")
    assert era is not None
    assert (era.title, era.year, era.series, era.structure) == (
        "Employment Rights Act 1996", 1996, "ukpga", "full",
    )  # fmt: skip
    assert era.primary
    assert "s124" in era.groups["ptX"]
    repealed = fixture_index.instrument("uk_ukpga_Geo3_41_63")
    assert repealed is not None
    assert repealed.repealed
    pdf_only = fixture_index.instrument("uk_uksi_1981_292")
    assert pdf_only is not None
    assert pdf_only.structure == "metadata_only"
    duplicated = fixture_index.instrument("uk_uksi_1987_50")
    assert duplicated is not None
    assert duplicated.duplicated
    assert fixture_index.instrument("uk_ukpga_1996_999") is None


def test_title_keys(fixture_index: RouterIndex) -> None:
    ids = fixture_index.ids
    assert ids("titles", "employment rights act|1996") == ("uk_ukpga_1996_18",)
    assert ids("titles", "employment rights|1996") == ("uk_ukpga_1996_18",)
    assert set(ids("titles", "employment rights act")) == {"uk_ukpga_1996_18", "uk_ukpga_2025_36"}
    assert set(ids("titles", "finance act")) == {"uk_ukpga_2024_3", "uk_ukpga_2025_8"}
    assert ids("titles", "consolidated fund act|1996") == ("uk_ukpga_1996_4",)
    assert ids("titles", "consolidated fund no 2 act|1996") == ("uk_ukpga_1996_60",)
    assert set(ids("titles", "military lands act|1897")) == {
        "uk_ukpga_Vict_60-61_6",
        "uk_ukpga_Vict_60-61_7",
    }
    assert ids("titles", "law property act|1925") == ("uk_ukpga_Geo5_15-16_20",)
    assert ids("titles", "marchwood commercial arbitration act|1996") == ()


def test_numbers_aliases_wordsets(fixture_index: RouterIndex) -> None:
    ids = fixture_index.ids
    assert ids("numbers", "c/1996/18") == ("uk_ukpga_1996_18",)
    assert ids("numbers", "si/2013/2729") == ("uk_wsi_2013_2729",)
    assert ids("numbers", "rc/geo5/15-16/20") == ("uk_ukpga_Geo5_15-16_20",)
    assert fixture_index.aliases["era 96"]["id"] == "uk_ukpga_1996_18"
    assert fixture_index.aliases["era 1988"]["id"] == "uk_ukpga_1988_40"
    assert fixture_index.aliases["ca 2006"]["id"] == "uk_ukpga_2006_46"
    assert fixture_index.manifest["partial"] is False  # every alias target is present
    assert fixture_index.manifest["dropped_alias_targets"] == []
    assert fixture_index.tables["wordsets"].get("act data protection|2018") == "uk_ukpga_2018_12"


def test_coverage(fixture_index: RouterIndex) -> None:
    asp = fixture_index.coverage("uk/asp/2010/13")
    assert asp is not None
    assert asp["t"] == "Criminal Justice and Licensing (Scotland) Act 2010"
    assert fixture_index.coverage("UK/ASP/2010/13") == asp  # case-insensitive
    assert fixture_index.coverage("uk/wsi/2012/1427") == {
        "c": "uk/wsi/2012/1427",
        "r": False,
        "s": "wsi",
        "t": None,
        "y": 2012,
    }
    assert fixture_index.ids("coverage_numbers", "asp/2010/13") == ("uk/asp/2010/13",)
    assert fixture_index.coverage("uk/ukpga/1996/18") is None  # indexed, so not coverage


def test_typo_table(fixture_index: RouterIndex) -> None:
    # "rihgts" and "rights" share the delete variant "rigts"
    assert "rights" in fixture_index.ids("typo", "rigts")


def test_aliases_that_are_not_json_refuse_to_load(index_copy: Path) -> None:
    path = index_copy / "aliases.json"
    path.write_text("{not json", encoding="utf-8")
    manifest_path = index_copy / "index-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["aliases.json"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(IndexLoadError, match="not valid JSON"):
        load_index(index_copy)


def test_info_raises_on_an_inconsistent_index(fixture_index: RouterIndex) -> None:
    assert fixture_index.info("uk_ukpga_1996_18").title == "Employment Rights Act 1996"
    with pytest.raises(IndexLoadError, match="inconsistent"):
        fixture_index.info("uk_ukpga_1996_999")


def test_coordinate_index_length(fixture_index: RouterIndex) -> None:
    assert len(fixture_index.coordinates) > 60_000
