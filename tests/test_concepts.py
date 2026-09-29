"""Concept index (roadmap D3): terms, packing, the build and the verified load."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest.build_concept_index import build_concepts, main, unit_of, write_concepts
from legal_rag_router.concepts import (
    CONCEPTS_MANIFEST,
    FIELDS,
    ConceptIndexError,
    load_concepts,
    pack_tf,
    stem,
    terms,
    unpack_tf,
)

ERA = "uk/ukpga/1996/18"


@pytest.mark.parametrize(
    ("word", "stemmed"),
    [
        ("compensation", "compens"),
        ("compensatory", "compens"),
        ("dismissed", "dismiss"),
        ("rights", "right"),
        ("act", "act"),  # too short to strip
        ("1996", "1996"),
    ],
)
def test_stem(word: str, stemmed: str) -> None:
    assert stem(word) == stemmed


def test_terms_fold_and_drop_stop_words() -> None:
    assert terms("The Limit of COMPENSATORY award, etc.") == ["limit", "compens", "award", "etc"]
    assert terms("\uff25\uff32\uff21 1996") == ["era", "1996"]  # NFKC


def test_tf_packing_round_trips_and_caps() -> None:
    assert unpack_tf(pack_tf((1, 0, 3, 63, 2))) == (1, 0, 3, 63, 2)
    assert unpack_tf(pack_tf((100, 0, 0, 0, 0)))[0] == 63


@pytest.mark.parametrize(
    ("path", "unit"),
    [
        ("s124", "s124"),
        ("s124/1ZA/a", "s124"),
        ("sch2/para3/1", "sch2/para3"),
        ("sch2/pt1/para3", "sch2/pt1/para3"),
        ("rule3.1/2", "rule3.1"),
        ("sA1", "sA1"),
        ("ptX", None),
        ("ptX/chII", None),
    ],
)
def test_unit_of(path: str, unit: str | None) -> None:
    assert unit_of(path) == unit


def _records(data: Path) -> None:
    lines = [
        {"record_type": "instrument", "coordinate": ERA, "title": "Employment Rights Act 1996",
         "long_title": "An Act to consolidate enactments relating to employment rights.",
         "groups": {"ptX": ["s124"], "ptX/chII": ["s124"]}},
        {"coordinate": f"{ERA}/ptX", "title": "Unfair dismissal"},
        {"coordinate": f"{ERA}/ptX/chII", "title": "Remedies for unfair dismissal"},
        {"coordinate": f"{ERA}/s124", "title": "Limit of compensatory award etc.",
         "crossheading": "Compensation", "text": ""},
        {"coordinate": f"{ERA}/s124/1", "text": "The amount of a compensatory award",
         "text_after": "shall not exceed the limit."},
        {"coordinate": f"{ERA}/sch1", "title": "Enactments"},
        {"coordinate": f"{ERA}/sch1/para1", "title": None, "text": "Consequential amendments."},
    ]  # fmt: skip
    path = data / "uk" / "ukpga" / "1996" / "uk_ukpga_1996_18.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    _records(tmp_path / "data")
    out = tmp_path / "concepts"
    args = ["--data", str(tmp_path / "data"), "--out", str(out), "--snapshot", "2026-09-28"]
    assert main(args) == 0
    return out


def test_documents_and_their_fields(index_dir: Path) -> None:
    index = load_concepts(index_dir)
    assert index.doc_count == 4  # the Act, s124, Schedule 1, Sch. 1 para. 1
    assert len(index.average_lengths) == len(FIELDS)
    by_coordinate = {index.doc(i).coordinate: i for i in range(index.doc_count)}
    s124 = by_coordinate[f"{ERA}/s124"]
    assert index.doc(s124).heading == "Limit of compensatory award etc."
    assert index.doc(by_coordinate[ERA]).kind == "i"
    docs, tfs = index.postings("compens")
    counts = dict(zip(docs, (unpack_tf(t) for t in tfs), strict=True))
    heading, crossheading, structure, title, body = counts[s124]
    assert (heading, crossheading, structure, title, body) == (1, 1, 0, 0, 1)
    docs, tfs = index.postings("unfair")
    assert unpack_tf(dict(zip(docs, tfs, strict=True))[s124])[2] == 2  # Part and Chapter titles
    assert index.document_frequency(stem("employment")) == 4  # the long title, in every document
    assert index.field_lengths(s124)[1] == 1
    assert index.document_frequency("nowhere") == 0
    assert len(index.postings("nowhere")[0]) == 0
    para = by_coordinate[f"{ERA}/sch1/para1"]
    assert index.field_lengths(para)[2] == 1  # the schedule's title as structure
    with pytest.raises(ConceptIndexError, match="no document"):
        index.doc(99)


def test_an_empty_build_loads(tmp_path: Path) -> None:
    (tmp_path / "data" / "uk").mkdir(parents=True)
    write_concepts(build_concepts(tmp_path / "data"), tmp_path / "c", snapshot="2026-09-28")
    index = load_concepts(tmp_path / "c")
    assert index.doc_count == 0
    assert index.average_lengths == (0.0,) * len(FIELDS)


def _manifest(index_dir: Path) -> dict[str, object]:
    manifest: dict[str, object] = json.loads((index_dir / CONCEPTS_MANIFEST).read_text())
    return manifest


@pytest.mark.parametrize(
    ("damage", "message"),
    [
        (lambda d: (d / CONCEPTS_MANIFEST).unlink(), "no concepts-manifest.json"),
        (lambda d: (d / CONCEPTS_MANIFEST).write_text("{"), "not valid JSON"),
        (
            lambda d: (d / CONCEPTS_MANIFEST).write_text(
                json.dumps({**_manifest(d), "format_version": 99})
            ),
            "unsupported concept index format",
        ),
        (
            lambda d: (d / CONCEPTS_MANIFEST).write_text(
                json.dumps({**_manifest(d), "fields": ["heading"]})
            ),
            "fields",
        ),
        (lambda d: (d / "postings.tf").unlink(), "missing concept index file postings.tf"),
        (lambda d: (d / "lengths.bin").write_bytes(b"\x00\x00"), "hash mismatch for lengths.bin"),
    ],
)
def test_load_refuses_a_damaged_index(index_dir: Path, damage: object, message: str) -> None:
    damage(index_dir)  # type: ignore[operator]
    with pytest.raises(ConceptIndexError, match=message):
        load_concepts(index_dir)
