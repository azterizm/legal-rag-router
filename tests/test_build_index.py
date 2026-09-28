"""Index build rules (M6): keys, integrity failures, determinism, round trip through the loader."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from ingest.build_index import (
    BuildError,
    _case_variants,
    acronym_keys,
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


def _instrument(
    coordinate: str, title: str, *, count: int, other_titles: tuple[str, ...] = ()
) -> InstrumentRecord:
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
        other_titles=other_titles,
        text_version="current",
        normative_tier=1,
        licence="OGL-3.0",
        source_url="https://www.legislation.gov.uk/x",
        source_sha256=SHA,
    )


def write_records(
    data: Path,
    instruments: dict[str, tuple[str, list[str]]],
    other_titles: dict[str, tuple[str, ...]] | None = None,
) -> None:
    """instruments: coordinate → (title, provision coordinates)."""
    for coordinate, (title, provisions) in instruments.items():
        others = (other_titles or {}).get(coordinate, ())
        record = _instrument(coordinate, title, count=len(provisions), other_titles=others)
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


def test_case_variants_without_variant_parents_are_recorded(tmp_path: Path) -> None:
    # SI 1994/1433 and SI 2015/596 have ids such as paragraph-5-A-i and paragraph-5-a-i
    # whose parents are never coordinates themselves: still one instrument (decision 7).
    root = tmp_path / "data"
    spellings = ["uk/uksi/1990/2145/art1/A/I", "uk/uksi/1990/2145/art1/a/i"]
    write_records(root, {"uk/uksi/1990/2145": ("X Order 1990", spellings)})
    built = build_index(root, catalogue=None, aliases_dir=write_aliases(tmp_path / "a", ""))
    assert built.case_variants == {"uk/uksi/1990/2145/art1/a/i": spellings}


def test_case_collision_across_instruments_fails() -> None:
    with pytest.raises(BuildError, match="unrelated"):
        _case_variants(["uk/ukpga/Geo3/1/1/s1", "uk/ukpga/GEO3/1/1/s1"])


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


def test_regnal_act_is_also_keyed_by_calendar_chapter(tmp_path: Path) -> None:
    root = tmp_path / "data"
    write_records(
        root,
        {"uk/ukpga/Geo5/15-16/20": ("Law of Property Act 1925", ["uk/ukpga/Geo5/15-16/20/s1"])},
    )
    built = build_index(root, catalogue=None, aliases_dir=write_aliases(tmp_path / "a", ""))
    assert built.numbers["rc/geo5/15-16/20"] == ["uk_ukpga_Geo5_15-16_20"]
    assert built.numbers["c/1925/20"] == ["uk_ukpga_Geo5_15-16_20"]


def test_catalogue_entry_already_indexed_by_number_is_not_coverage(
    tmp_path: Path, data: Path
) -> None:
    catalogue = tmp_path / "cat.jsonl"
    alias = CatalogueEntry(
        coordinate="uk/uksi/1996/18", series="uksi", year=1996, number=18, title="x", source="t"
    )
    catalogue.write_text(alias.model_dump_json() + "\n")
    built = build_index(data, catalogue=catalogue, aliases_dir=write_aliases(tmp_path / "a", ""))
    assert "uk/uksi/1996/18" in built.coverage["instruments"]  # different number space: kept


# ---------------------------------------------------------------- acronyms (decision 18)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Proceeds of Crime Act 2002", {"poca|2002", "pca|2002", "poc|2002"}),
        ("Police and Criminal Evidence Act 1984", {"pacea|1984", "pace|1984", "pcea|1984"}),
        ("Offences against the Person Act 1861", {"oapa|1861", "opa|1861"}),
        ("Health and Safety at Work etc. Act 1974", {"hswa|1974", "hsw|1974"}),
        ("Finance Act 2023", {"fa|2023"}),
    ],
)
def test_acronym_keys(title: str, expected: set[str]) -> None:
    assert expected <= set(acronym_keys(title))
    assert all(not k.endswith("|") for k in acronym_keys(title))  # never without a year


@pytest.mark.parametrize(
    "title",
    ["Finance (No. 2) Act 2023", "Entail Amendment Act", "Explosives Act 1875", "The X Order 2011"],
)
def test_no_acronym_for_numbered_yearless_single_word_or_non_act_titles(title: str) -> None:
    keys = acronym_keys(title)
    assert keys in ((), ("ea|1875",))  # a one-word Act keeps only "EA 1875"


def test_acronyms_table_lists_every_act_it_could_mean(tmp_path: Path) -> None:
    data = tmp_path / "data"
    write_records(
        data,
        {
            "uk/ukpga/2010/15": ("Equality Act 2010", []),
            "uk/ukpga/2010/27": ("Energy Act 2010", []),
            "uk/uksi/2010/1": ("The Energy Allowance Order 2010", []),
        },
    )
    built = build_index(data, catalogue=None, aliases_dir=write_aliases(tmp_path / "a", ""))
    assert sorted(built.acronyms["ea|2010"]) == ["uk_ukpga_2010_15", "uk_ukpga_2010_27"]


# ---------------------------------------------------------------- former titles (decision 17)


def test_former_titles_are_checked_before_they_bind(tmp_path: Path) -> None:
    data = tmp_path / "data"
    catalogue = tmp_path / "catalogue.jsonl"
    catalogue.write_text(
        CatalogueEntry(
            coordinate="uk/nia/2002/7", series="nia", year=2002, number=7,
            title="Budget (No. 2) Act (Northern Ireland) 2002", source="t",
        ).model_dump_json() + "\n"
    )  # fmt: skip
    write_records(
        data,
        {
            "uk/ukpga/1981/54": ("Senior Courts Act 1981", []),
            "uk/ukpga/2002/7": ("Homelessness Act 2002", []),
            "uk/ukpga/1998/38": ("Government of Wales Act 1998", []),
            "uk/ukpga/Geo5/15-16/18": ("Army Act 1925", []),
            "uk/ukpga/2001/1": ("First Act 2001", []),
            "uk/ukpga/2001/2": ("Second Act 2001", []),
        },
        {
            "uk/ukpga/1981/54": (
                "Supreme Court Act 1981",
                "Supreme Court Act 1982",
                "Senior Order 1981",
            ),
            "uk/ukpga/2002/7": ("Budget (No. 2) Act (Northern Ireland) 2002",),  # not "… Act"
            "uk/ukpga/1998/38": ("Government of Wales Act 1998 (c. 38)",),  # its own title
            "uk/ukpga/Geo5/15-16/18": ("Aliens' Employment Act 1925",),  # a session mix-up
            "uk/ukpga/2001/1": ("Shared Act 2001", "Second Act 2001"),  # another Act's title
            "uk/ukpga/2001/2": ("Shared Act 2001",),  # two Acts claim it: neither binds
        },
    )
    built = build_index(data, catalogue=catalogue, aliases_dir=write_aliases(tmp_path / "a", ""))
    formers = {k: v["f"] for k, v in built.instruments.items() if "f" in v}
    assert formers == {"uk_ukpga_1981_54": ["Supreme Court Act 1981"]}
    assert built.titles["supreme court act|1981"] == ["uk_ukpga_1981_54"]
    assert "shared act|2001" not in built.titles
    assert any("names another instrument" in w for w in built.warnings)
    assert any("shares no words" in w for w in built.warnings)
