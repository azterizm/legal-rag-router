"""UK CLML ingest (M3-UK). Synthetic documents pin each rule; golden tests use real files."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from ingest.records import InstrumentRecord, ProvisionRecord, read_instrument_file
from ingest.uk import IngestError, coordinate_from_uri, main, parse_clml

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "uk_scrap_data" / "raw_xml"
ID = "http://www.legislation.gov.uk/id/"
EQA = "http://www.legislation.gov.uk/id/ukpga/2010/15/section/26"


def clml(
    id_path: str,
    body: str,
    *,
    title: str = "Test Act 2020",
    category: str = "primary",
    year: str = "2020",
    number: str = "5",
    status: str = "revised",
    extra_meta: str = "",
    tail: str = "",
) -> bytes:
    kind = "PrimaryMetadata" if category == "primary" else "SecondaryMetadata"
    main_type = (
        "UnitedKingdomPublicGeneralAct"
        if category == "primary"
        else "UnitedKingdomStatutoryInstrument"
    )
    wrapper = "Primary" if category == "primary" else "Secondary"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
  IdURI="{ID}{id_path}" NumberOfProvisions="1">
 <ukm:Metadata xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
   xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dct="http://purl.org/dc/terms/">
  <dc:title>{title}</dc:title><dct:valid>2026-07-29</dct:valid>
  <ukm:{kind}>
   <ukm:DocumentClassification>
    <ukm:DocumentCategory Value="{category}"/><ukm:DocumentMainType Value="{main_type}"/>
    <ukm:DocumentStatus Value="{status}"/>
   </ukm:DocumentClassification>
   <ukm:Year Value="{year}"/><ukm:Number Value="{number}"/>{extra_meta}
  </ukm:{kind}>
 </ukm:Metadata>
 <{wrapper}><Body>{body}</Body></{wrapper}>{tail}
</Legislation>""".encode()


def p1(path: str, num: str, inner: str, heading: str = "Heading") -> str:
    return (
        f'<P1group><Title>{heading}</Title><P1 IdURI="{ID}{path}" id="x">'
        f"<Pnumber>{num}</Pnumber><P1para>{inner}</P1para></P1></P1group>"
    )


def p2(path: str, num: str, inner: str) -> str:
    return f'<P2 IdURI="{ID}{path}"><Pnumber>{num}</Pnumber><P2para>{inner}</P2para></P2>'


def by_coordinate(provisions: list[ProvisionRecord]) -> dict[str, ProvisionRecord]:
    return {p.coordinate: p for p in provisions}


# ---------------------------------------------------------------- identity


def test_identity_comes_from_iduri_including_regnal() -> None:
    doc = clml(
        "ukpga/Geo3/41/63",
        p1("ukpga/Geo3/41/63/section/1", "1", "<Text>No person shall sit.</Text>"),
        title="House of Commons (Clergy Disqualification) Act 1801 (repealed)",
        year="1801",
        number="63",
        extra_meta='<ukm:AlternativeNumber Category="Regnal" Value="41_Geo_3"/>',
    )
    parsed = parse_clml(doc)
    record = parsed.instrument
    assert record.coordinate == "uk/ukpga/Geo3/41/63"
    assert record.instrument_id == "uk_ukpga_Geo3_41_63"
    assert record.title == "House of Commons (Clergy Disqualification) Act 1801"
    assert record.repealed is True
    assert record.year == 1801
    assert record.alternative_numbers[0].value == "41_Geo_3"
    assert [p.coordinate for p in parsed.provisions] == ["uk/ukpga/Geo3/41/63/s1"]


def test_welsh_si_keeps_canonical_series() -> None:
    doc = clml(
        "wsi/2013/2729", "", category="secondary", year="2013", number="2729", title="The X Order"
    )
    record = parse_clml(doc).instrument
    assert record.coordinate == "uk/wsi/2013/2729"
    assert record.authority_type == "SECONDARY_INSTRUMENT"
    assert record.normative_tier == 2


@pytest.mark.parametrize(
    ("doc", "message"),
    [
        (b"<not-xml", "parse error"),
        (
            b'<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"/>',
            "no IdURI",
        ),
        (clml("ukpga/1996", ""), "not a UK instrument"),
        (clml("ukpga/1996/18/section/1", ""), "not a UK instrument"),
        (clml("ukpga/1996/18/s1", ""), "names a provision"),
        (clml("ukpga/2020/5", "", year="twenty"), "numeric Year"),
    ],
)
def test_unusable_documents_raise(doc: bytes, message: str) -> None:
    with pytest.raises(IngestError, match=message):
        parse_clml(doc)


def test_dtd_entities_are_refused() -> None:
    evil = b'<!DOCTYPE x [<!ENTITY a "aaaa">]><Legislation IdURI="x">&a;</Legislation>'
    with pytest.raises(Exception):  # noqa: B017, PT011 - defusedxml raises its own error types
        parse_clml(evil)


# ---------------------------------------------------------------- structure


def test_metadata_only_instrument() -> None:
    record = parse_clml(clml("uksi/2013/76", "", category="secondary")).instrument
    assert record.structure == "metadata_only"
    assert record.provision_count == 0
    assert record.text_version == "current"


def test_provision_tree_text_split_and_labels() -> None:
    inner = p2(
        "ukpga/2020/5/section/1/1",
        "1",
        "<Text>The amount of—</Text>"
        '<P3 IdURI="' + ID + 'ukpga/2020/5/section/1/1/a"><Pnumber>a</Pnumber>'
        "<P3para><Text>any award, or</Text></P3para></P3>" + "<Text>shall not exceed £100.</Text>",
    )
    parsed = parse_clml(clml("ukpga/2020/5", p1("ukpga/2020/5/section/1", "1", inner, "Limit")))
    records = by_coordinate(parsed.provisions)
    s1 = records["uk/ukpga/2020/5/s1"]
    assert (s1.title, s1.number_label, s1.parent) == ("Limit", "1", "uk/ukpga/2020/5")
    sub = records["uk/ukpga/2020/5/s1/1"]
    assert (sub.text, sub.text_after) == ("The amount of—", "shall not exceed £100.")
    assert sub.parent == "uk/ukpga/2020/5/s1"
    assert records["uk/ukpga/2020/5/s1/1/a"].text == "any award, or"
    assert [p.order for p in parsed.provisions] == [0, 1, 2]


def test_block_amendment_internal_link_and_crossheading_are_not_provisions() -> None:
    quoted = (
        '<BlockAmendment><P1 IdURI="' + ID + 'ukpga/1996/18/section/124A" id="p00001">'
        "<Pnumber>124A</Pnumber><P1para><Text>Inserted text.</Text></P1para></P1></BlockAmendment>"
    )
    link = (
        '<Text>See <InternalLink IdURI="' + ID + 'ukpga/2020/5/section/2/1">'
        "subsection (1)</InternalLink>.</Text>"
    )
    body = (
        '<Pblock IdURI="'
        + ID
        + 'ukpga/2020/5/crossheading/general"><Title>General</Title>'
        + p1("ukpga/2020/5/section/1", "1", "<Text>After section 124 insert—</Text>" + quoted)
        + p1("ukpga/2020/5/section/3", "3", link)
        + "</Pblock>"
    )
    parsed = parse_clml(clml("ukpga/2020/5", body))
    records = by_coordinate(parsed.provisions)
    assert list(records) == ["uk/ukpga/2020/5/s1", "uk/ukpga/2020/5/s3"]
    assert "Inserted text." in records["uk/ukpga/2020/5/s1"].text
    assert records["uk/ukpga/2020/5/s3"].text == "See subsection (1)."


def test_versions_are_skipped_and_counted() -> None:
    main_text = p1("ukpga/2020/5/section/1", "1", "<Text>E+W text.</Text>")
    versions = (
        '<Versions><Version id="v1">'
        + p1("ukpga/2020/5/section/1", "1", "<Text>N.I. text.</Text>")
        + "</Version></Versions>"
    )
    parsed = parse_clml(clml("ukpga/2020/5", main_text, tail=versions))
    assert [p.text for p in parsed.provisions] == ["E+W text."]
    assert parsed.instrument.alternative_versions == 1
    assert parsed.warnings == []


def test_duplicates_are_recorded_and_first_kept() -> None:
    body = p1("ukpga/2020/5/section/6", "6", "<Text>first</Text>") + p1(
        "ukpga/2020/5/section/6", "6", "<Text>second</Text>"
    )
    parsed = parse_clml(clml("ukpga/2020/5", body))
    assert [p.text for p in parsed.provisions] == ["first"]
    assert parsed.instrument.duplicated_provisions == ("uk/ukpga/2020/5/s6",)
    assert parsed.warnings[0].startswith("duplicate provision")


def test_parts_group_their_top_level_provisions_and_status_inherits() -> None:
    body = (
        '<Part IdURI="'
        + ID
        + 'ukpga/2020/5/part/I"><Number>Part I</Number><Title>Intro</Title>'
        + p1("ukpga/2020/5/section/1", "1", "<Text>a</Text>")
        + '<Chapter IdURI="'
        + ID
        + 'ukpga/2020/5/part/I/chapter/1"><Number>Chapter 1</Number>'
        + '<P1group Status="Repealed"><Title>Gone</Title><P1 IdURI="'
        + ID
        + 'ukpga/2020/5/section/2"><Pnumber>2</Pnumber><P1para>'
        + p2("ukpga/2020/5/section/2/1", "1", "<Text>. . .</Text>")
        + "</P1para></P1></P1group></Chapter></Part>"
    )
    parsed = parse_clml(clml("ukpga/2020/5", body))
    # A part maps to the sections it contains (chapters are coordinates in their own right).
    assert parsed.instrument.groups == {"ptI": ("s1", "s2"), "ptI/ch1": ("s2",)}
    records = by_coordinate(parsed.provisions)
    assert records["uk/ukpga/2020/5/ptI"].title == "Intro"
    assert records["uk/ukpga/2020/5/ptI"].number_label == "Part I"
    assert records["uk/ukpga/2020/5/s2"].repealed
    assert records["uk/ukpga/2020/5/s2/1"].repealed
    assert not records["uk/ukpga/2020/5/s1"].repealed


# ---------------------------------------------------------------- citations


def test_citations_are_harvested_with_context_and_span() -> None:
    text = (
        f'<Text>as defined in <Citation URI="{EQA}" '
        'Class="UnitedKingdomPublicGeneralAct" id="c1">section 26</Citation>'
        f'<CitationSubRef URI="{EQA}/2" '
        'CitationRef="c1" id="c2">(2)</CitationSubRef> of the Equality Act 2010.</Text>'
    )
    commentary = (
        '<Commentaries><Commentary id="k1"><Para><Text>S. 1 amended by '
        f'<Citation URI="{ID}uksi/2011/3006" id="c9">S.I. 2011/3006</Citation>'
        "</Text></Para></Commentary></Commentaries>"
    )
    parsed = parse_clml(
        clml("ukpga/2020/5", p1("ukpga/2020/5/section/1", "1", text), tail=commentary)
    )
    first, sub, editorial = parsed.citations
    assert first.text == "section 26"
    assert first.context[first.span[0] : first.span[1]] == "section 26"
    assert first.target_coordinate == "uk/ukpga/2010/15/s26"
    assert first.source_coordinate == "uk/ukpga/2020/5/s1"
    assert (sub.kind, sub.citation_ref, sub.target_coordinate) == (
        "subref",
        "c1",
        "uk/ukpga/2010/15/s26/2",
    )
    assert sub.context[sub.span[0] : sub.span[1]] == "(2)"
    assert editorial.in_commentary
    assert editorial.source_coordinate == "uk/ukpga/2020/5"
    assert editorial.target_coordinate == "uk/uksi/2011/3006"


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("http://www.legislation.gov.uk/id/ukpga/1996/18", "uk/ukpga/1996/18"),
        (
            "https://www.legislation.gov.uk/ukpga/1996/18/section/124/1ZA/a",
            "uk/ukpga/1996/18/s124/1ZA/a",
        ),
        ("https://www.legislation.gov.uk/ukpga/1996/18/contents", "uk/ukpga/1996/18"),
        (
            "https://www.legislation.gov.uk/ukpga/1996/18/section/124/2020-01-01",
            "uk/ukpga/1996/18/s124",
        ),
        ("https://www.legislation.gov.uk/uksi/2011/3006/made", "uk/uksi/2011/3006"),
        (
            "http://www.legislation.gov.uk/id/ukpga/Eliz2/8-9/69/section/1",
            "uk/ukpga/Eliz2/8-9/69/s1",
        ),
        (
            "https://www.legislation.gov.uk/ukpga/1996/18/schedule/2/paragraph/4",
            "uk/ukpga/1996/18/sch2/para4",
        ),
        ("https://www.legislation.gov.uk/ukpga/1996/18/crossheading/general", None),
        ("https://www.legislation.gov.uk/ukpga/1996", None),
        ("https://example.com/ukpga/1996/18", None),
        ("", None),
        (None, None),
    ],
)
def test_coordinate_from_uri(uri: str | None, expected: str | None) -> None:
    result = coordinate_from_uri(uri)
    assert (str(result) if result is not None else None) == expected


# ---------------------------------------------------------------- CLI round trip


def test_cli_writes_verified_records_and_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "src" / "raw_xml" / "ukpga" / "2020"
    source.mkdir(parents=True)
    body = p1("ukpga/2020/5/section/1", "1", "<Text>Hello.</Text>")
    (source / "5.xml.gz").write_bytes(gzip.compress(clml("ukpga/2020/5", body)))
    (source / "6.xml.gz").write_bytes(b"not gzip")
    out = tmp_path / "data"

    assert main(["--source", str(tmp_path / "src"), "--data", str(out), "--workers", "1"]) == 1
    report = json.loads((out / "uk" / "INGEST_REPORT.json").read_text())
    assert report["status"] == {"ok": 1, "failed": 1}

    instrument, provisions = read_instrument_file(
        out / "uk" / "ukpga" / "2020" / "uk_ukpga_2020_5.jsonl"
    )
    assert isinstance(instrument, InstrumentRecord)
    assert [p.coordinate for p in provisions] == ["uk/ukpga/2020/5/s1"]

    (source / "6.xml.gz").unlink()
    assert main(["--source", str(tmp_path / "src"), "--data", str(out), "--workers", "1"]) == 0
    report = json.loads((out / "uk" / "INGEST_REPORT.json").read_text())
    assert report["status"] == {"skipped": 1}


def test_cli_only_filters_by_instrument_id(tmp_path: Path) -> None:
    source = tmp_path / "src" / "raw_xml" / "ukpga" / "2020"
    source.mkdir(parents=True)
    for n in ("5", "6"):
        (source / f"{n}.xml.gz").write_bytes(gzip.compress(clml(f"ukpga/2020/{n}", "", number=n)))
    out = tmp_path / "data"
    args = ["--source", str(tmp_path / "src"), "--data", str(out), "--workers", "1"]
    assert main([*args, "--only", "uk_ukpga_2020_6", "uk_ukpga_1999_1"]) == 0
    assert sorted(p.name for p in (out / "uk").rglob("*.jsonl")) == ["uk_ukpga_2020_6.jsonl"]


# ---------------------------------------------------------------- golden (real data)

needs_raw = pytest.mark.skipif(not RAW.is_dir(), reason="uk_scrap_data not present")


@needs_raw
def test_golden_era_1996_s124() -> None:
    parsed = parse_clml(gzip.decompress((RAW / "ukpga" / "1996" / "18.xml.gz").read_bytes()))
    assert parsed.instrument.title == "Employment Rights Act 1996"
    records = by_coordinate(parsed.provisions)
    assert records["uk/ukpga/1996/18/s124"].title == "Limit of compensatory award etc."
    assert records["uk/ukpga/1996/18/s124/1ZA/a"].text.startswith("£")
    assert "s124" in parsed.instrument.groups["ptX"]
    assert parsed.instrument.structure == "full"


@needs_raw
def test_golden_regnal_session_with_three_years() -> None:
    parsed = parse_clml(gzip.decompress((RAW / "ukpga" / "1948" / "1.xml.gz").read_bytes()))
    assert parsed.instrument.coordinate.startswith("uk/ukpga/Geo6/12-13-14/")
