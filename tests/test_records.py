from pathlib import Path

import pytest
from pydantic import ValidationError

from ingest.records import (
    HarvestedCitation,
    InstrumentRecord,
    ProvisionRecord,
    read_instrument_file,
    write_instrument_file,
)

SHA = "0" * 64


def instrument(**overrides: object) -> InstrumentRecord:
    fields: dict[str, object] = {
        "coordinate": "uk/ukpga/1996/18",
        "instrument_id": "uk_ukpga_1996_18",
        "domain": "uk_legislation",
        "jurisdiction": "UK",
        "authority_type": "PRIMARY_ACT",
        "document_type": "UnitedKingdomPublicGeneralAct",
        "title": "Employment Rights Act 1996",
        "title_as_published": "Employment Rights Act 1996",
        "year": 1996,
        "number": 18,
        "repealed": False,
        "structure": "full",
        "provision_count": 1,
        "text_version": "current",
        "normative_tier": 1,
        "licence": "OGL-3.0",
        "source_url": "https://www.legislation.gov.uk/ukpga/1996/18",
        "source_sha256": SHA,
    }
    fields.update(overrides)
    return InstrumentRecord.model_validate(fields)


def provision(**overrides: object) -> ProvisionRecord:
    fields: dict[str, object] = {
        "coordinate": "uk/ukpga/1996/18/s124",
        "instrument_id": "uk_ukpga_1996_18",
        "parent": "uk/ukpga/1996/18",
        "order": 0,
        "text": "Limit",
        "source_url": "https://www.legislation.gov.uk/ukpga/1996/18/section/124",
    }
    fields.update(overrides)
    return ProvisionRecord.model_validate(fields)


def test_seal_and_verify() -> None:
    sealed = provision().sealed()
    assert sealed.checksum_sha256 is not None
    assert sealed.verify()
    tampered = sealed.model_copy(update={"text": "Limit (edited)"})
    assert not tampered.verify()


def test_round_trip_file(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    write_instrument_file(path, instrument(), [provision()])
    head, rest = read_instrument_file(path)
    assert head.title == "Employment Rights Act 1996"
    assert [p.coordinate for p in rest] == ["uk/ukpga/1996/18/s124"]
    assert not list(tmp_path.glob(".*.tmp"))


def test_tampered_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    write_instrument_file(path, instrument(), [provision()])
    path.write_text(path.read_text().replace('"text":"Limit"', '"text":"Limitless"'))
    _, rest = read_instrument_file(path)
    with pytest.raises(ValueError, match="checksum mismatch"):
        list(rest)


def test_tampered_instrument_line_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    write_instrument_file(path, instrument(), [])
    path.write_text(path.read_text().replace("Employment Rights", "Employment Wrongs"))
    with pytest.raises(ValueError, match="checksum mismatch"):
        read_instrument_file(path)


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    path.write_text("")
    with pytest.raises(ValueError, match="empty"):
        read_instrument_file(path)


def test_foreign_provision_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    other = provision(
        coordinate="uk/ukpga/2006/46/s124",
        instrument_id="uk_ukpga_2006_46",
        parent="uk/ukpga/2006/46",
    )
    write_instrument_file(path, instrument(), [other])
    _, rest = read_instrument_file(path)
    with pytest.raises(ValueError, match="another instrument"):
        list(rest)


@pytest.mark.parametrize(
    "overrides",
    [
        {"coordinate": "uk/ukpga/1996"},
        {"instrument_id": "uk_ukpga_2006_46"},
        {"coordinate": "uk/ukpga/1996/18/s124", "structure": "full"},
        {"structure": "metadata_only", "provision_count": 3},
        {"structure": "full", "provision_count": 0},
        {"unknown_field": 1},
    ],
)
def test_invalid_instrument_records(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        instrument(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"coordinate": "uk/ukpga/1996/18"},
        {"parent": "uk/ukpga/1996/18/s125"},
        {"parent": "uk/ukpga/1996/18/s124"},
        {"parent": "not a coordinate"},
        {"order": -1},
    ],
)
def test_invalid_provision_records(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        provision(**overrides)


def test_citation_span_must_lie_in_context() -> None:
    fields: dict[str, object] = {
        "source_coordinate": "uk/ukpga/1996/18/s1",
        "kind": "citation",
        "text": "s. 1",
        "context": "see s. 1",
        "span": (4, 8),
        "target_uri": "http://www.legislation.gov.uk/id/ukpga/1996/18/section/1",
        "target_coordinate": "uk/ukpga/1996/18/s1",
    }
    assert HarvestedCitation.model_validate(fields).span == (4, 8)
    with pytest.raises(ValidationError):
        HarvestedCitation.model_validate({**fields, "span": (4, 99)})
