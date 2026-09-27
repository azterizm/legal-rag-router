"""Index build rules (M6): keys, integrity failures, determinism, round trip through the loader."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from ingest.build_index import (
    BuildError,
    build_index,
    deletes,
    main,
    serialise,
    title_variants,
    wordset_key,
    write_index,
)
from ingest.records import CatalogueEntry, InstrumentRecord, ProvisionRecord, write_instrument_file
from legal_rag_router.index import load_index

SHA = "0" * 64


def _instrument(coordinate: str, title: str, *, count: int) -> InstrumentRecord:
    parts = coordinate.split("/")
    return InstrumentRecord(
        coordinate=coordinate,
        instrument_id="_".join(parts),
        domain="uk_legislation",
        jurisdiction="UK",
        authority_type="PRIMARY_ACT" if parts[1] == "ukpga" else "SECONDARY_INSTRUMENT",
        document_type="x",
        title=title,
        title_as_published=title,
        year=int(parts[2]) if parts[2].isdigit() else 1925,
        number=int(parts[-1]),
        repealed=False,
        structure="full" if count else "metadata_only",
        provision_count=count,
        text_version="current",
        normative_tier=1,
        licence="OGL-3.0",
        source_url="https://www.legislation.gov.uk/x",
        source_sha256=SHA,
    )


def write_records(data: Path, instruments: dict[str, tuple[str, list[str]]]) -> None:
    """instruments: coordinate → (title, provision coordinates)."""
    for coordinate, (title, provisions) in instruments.items():
        record = _instrument(coordinate, title, count=len(provisions))
        path = (
            data
            / "uk"
            / coordinate.split("/")[1]
            / str(record.year)
            / f"{record.instrument_id}.jsonl"
        )
        write_instrument_file(
            path,
            record,
            [
                ProvisionRecord(
                    coordinate=p,
                    instrument_id=record.instrument_id,
                    parent=p.rsplit("/", 1)[0],
                    order=i,
                    source_url="https://www.legislation.gov.uk/x",
                )
                for i, p in enumerate(provisions)
            ],
        )


def write_aliases(directory: Path, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "uk.toml").write_text(body)
    return directory


TWO_TARGETS = (
    '[[alias]]\ntarget = "uk/ukpga/1996/18"\nforms = ["EA"]\n'
    '[[alias]]\ntarget = "uk/ukpga/2010/15"\nforms = ["EA"]\n'
)

BASE = {
    "uk/ukpga/1996/18": (
        "Employment Rights Act 1996",
        ["uk/ukpga/1996/18/s124", "uk/ukpga/1996/18/s124/1ZA"],
    ),
    "uk/ukpga/2010/15": ("Equality Act 2010", ["uk/ukpga/2010/15/s124"]),
}


@pytest.fixture
def data(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    write_records(root, BASE)
    return root


def test_title_variants() -> None:
    assert title_variants("Employment Rights Act 1996") == (
        "employment rights act|1996",
        "employment rights act",
        "employment rights|1996",
        "employment rights",
    )
    assert title_variants("The Civil Procedure Rules 1998")[:2] == (
        "civil procedure rules|1998",
        "civil procedure rules",
    )
    assert title_variants("Finance (No. 2) Act 2024")[0] == "finance no 2 act|2024"
    assert title_variants("An Act for the relief of the poor") == ("act for relief poor",)
    assert title_variants("Act 1996") == ("act|1996", "act")  # the core is empty: no core keys
    assert title_variants("...") == ()


def test_wordset_key_and_deletes() -> None:
    assert wordset_key("Rights of Employment Act 1996") == wordset_key("Employment Rights Act 1996")
    assert wordset_key("Civil Procedure Rules") is None
    assert "rigts" in deletes("rights")
    assert "rgts" in deletes("rights")  # two deletes
    assert "rts" not in deletes("rights")  # three deletes


def test_build_and_load_round_trip(tmp_path: Path, data: Path) -> None:
    aliases = write_aliases(
        tmp_path / "aliases",
        '[[alias]]\ntarget = "uk/ukpga/1996/18"\nforms = ["ERA 1996", "ERA 96"]\nsalient = true\n',
    )
    catalogue = tmp_path / "catalogue.jsonl"
    entry = CatalogueEntry(
        coordinate="uk/asp/2010/13", series="asp", year=2010, number=13,
        title="Criminal Justice and Licensing (Scotland) Act 2010",
        title_as_published="Criminal Justice and Licensing (Scotland) Act 2010", source="t",
    )  # fmt: skip
    indexed = CatalogueEntry(
        coordinate="uk/ukpga/1996/18", series="ukpga", year=1996, number=18, title="x", source="t"
    )
    catalogue.write_text(entry.model_dump_json() + "\n" + indexed.model_dump_json() + "\n")
    built = build_index(data, catalogue=catalogue, aliases_dir=aliases)
    out = tmp_path / "index"
    write_index(built, out, snapshot=date(2026, 9, 27), sources=["legislation.gov.uk"])
    index = load_index(out)
    assert "uk/ukpga/1996/18/s124/1ZA" in index.coordinates
    assert index.ids("titles", "employment rights|1996") == ("uk_ukpga_1996_18",)
    assert index.aliases["era 96"] == {"form": "ERA 96", "id": "uk_ukpga_1996_18", "salient": True}
    assert index.coverage("uk/asp/2010/13") is not None
    assert index.coverage("uk/ukpga/1996/18") is None  # indexed wins over catalogue
    assert index.manifest["partial"] is False
    assert index.manifest["freshness"]["ukpga"]["max_number_by_year"] == {"1996": 18, "2010": 15}


def test_build_is_deterministic(tmp_path: Path, data: Path) -> None:
    aliases = write_aliases(tmp_path / "aliases", "")
    first = serialise(build_index(data, catalogue=None, aliases_dir=aliases))
    second = serialise(build_index(data, catalogue=None, aliases_dir=aliases))
    assert first == second


def test_same_parent_case_variants_are_recorded(tmp_path: Path) -> None:
    root = tmp_path / "data"
    art1 = "uk/uksi/1990/2145/art1"
    write_records(root, {"uk/uksi/1990/2145": ("X Order 1990", [art1, f"{art1}/a", f"{art1}/A"])})
    built = build_index(root, catalogue=None, aliases_dir=write_aliases(tmp_path / "a", ""))
    assert built.case_variants == {
        "uk/uksi/1990/2145/art1/a": ["uk/uksi/1990/2145/art1/A", "uk/uksi/1990/2145/art1/a"]
    }


def test_unrelated_case_collision_fails(tmp_path: Path) -> None:
    root = tmp_path / "data"
    write_records(
        root,
        {
            "uk/uksi/1990/2145": (
                "X Order 1990",
                ["uk/uksi/1990/2145/art1/a/i", "uk/uksi/1990/2145/art1/A/I"],
            )
        },
    )
    with pytest.raises(BuildError, match="unrelated"):
        build_index(root, catalogue=None, aliases_dir=write_aliases(tmp_path / "a", ""))


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        ('[[alias]]\ntarget = "uk/ukpga/2006/46"\nforms = ["CA 2006"]\n', "not in the index"),
        (
            TWO_TARGETS,
            "names two targets",
        ),
        (
            '[[alias]]\ntarget = "uk/ukpga/2010/15"\nforms = ["Employment Rights Act 1996"]\n',
            "shadows",
        ),
        ('[[alias]]\ntarget = "uk/ukpga/2010/15"\nforms = ["..."]\n', "folds to nothing"),
        ('[[alias]]\nforms = ["x"]\n', "needs a target"),
    ],
)
def test_alias_integrity(tmp_path: Path, data: Path, toml: str, message: str) -> None:
    with pytest.raises(BuildError, match=message):
        build_index(data, catalogue=None, aliases_dir=write_aliases(tmp_path / "aliases", toml))


def test_alias_may_share_core_words_with_other_titles(tmp_path: Path, data: Path) -> None:
    # "Employment Rights" is the core of ERA 1996's title, but the alias's full form names
    # EqA 2010 only: allowed (an exact title match wins at runtime anyway).
    toml = '[[alias]]\ntarget = "uk/ukpga/2010/15"\nforms = ["Employment Rights Act 2010"]\n'
    built = build_index(data, catalogue=None, aliases_dir=write_aliases(tmp_path / "a", toml))
    assert built.aliases["employment rights act 2010"]["id"] == "uk_ukpga_2010_15"


def test_missing_alias_target_can_be_allowed_and_is_recorded(tmp_path: Path, data: Path) -> None:
    aliases = write_aliases(
        tmp_path / "aliases", '[[alias]]\ntarget = "uk/ukpga/2006/46"\nforms = ["CA 2006"]\n'
    )
    built = build_index(data, catalogue=None, aliases_dir=aliases, allow_missing_alias_targets=True)
    manifest = write_index(built, tmp_path / "index", snapshot=date(2026, 9, 27), sources=["x"])
    assert manifest["partial"] is True
    assert manifest["dropped_alias_targets"] == ["uk/ukpga/2006/46"]


def test_empty_input_fails(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="no instrument records"):
        build_index(tmp_path, catalogue=None, aliases_dir=write_aliases(tmp_path / "a", ""))


def test_write_index_removes_stale_files(tmp_path: Path, data: Path) -> None:
    out = tmp_path / "index"
    out.mkdir()
    (out / "titles.json").write_text("{}")  # left over from an older format
    built = build_index(data, catalogue=None, aliases_dir=write_aliases(tmp_path / "a", ""))
    write_index(built, out, snapshot=date(2026, 9, 27), sources=["x"])
    assert not (out / "titles.json").exists()


def test_cli(tmp_path: Path, data: Path) -> None:
    aliases = write_aliases(tmp_path / "aliases", "")
    out = tmp_path / "index"
    args = [
        "--data",
        str(data),
        "--out",
        str(out),
        "--snapshot",
        "2026-09-27",
        "--aliases",
        str(aliases),
    ]
    assert main(args) == 0
    assert json.loads((out / "index-manifest.json").read_text())["snapshot"] == "2026-09-27"
    bad = write_aliases(
        tmp_path / "bad", '[[alias]]\ntarget = "uk/ukpga/2006/46"\nforms = ["CA 2006"]\n'
    )
    assert main([*args[:-1], str(bad)]) == 1
