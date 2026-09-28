"""Harvest split (roadmap D3) and coverage-sweep classification (M7k)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from eval.sweep import HELDOUT_PERCENT, bucket, classify, main, replay_query, split_manifest
from ingest.uk_catalogue import import_queue
from legal_rag_router import Router
from tests.conftest import FIXTURE_INDEX


def citation(text: str, context: str, target: str, **extra: object) -> dict[str, object]:
    start = context.index(text)
    return {
        "source_coordinate": "uk/ukpga/2000/1/s1",
        "kind": "citation",
        "citation_id": "c1",
        "text": text,
        "context": context,
        "span": [start, start + len(text)],
        "target_uri": f"http://www.legislation.gov.uk/id/{target.removeprefix('uk/')}",
        "target_coordinate": target,
        **extra,
    }


def test_split_is_deterministic_and_about_the_stated_share() -> None:
    rows = [
        citation("Theft Act 1968", "see Theft Act 1968", "uk/ukpga/1968/60", citation_id=str(i))
        for i in range(4000)
    ]
    first = [bucket(r) for r in rows]
    assert first == [bucket(r) for r in rows]
    share = first.count("heldout") / len(first)
    assert abs(share - HELDOUT_PERCENT / 100) < 0.03


def test_split_manifest_records_the_rule() -> None:
    manifest = split_manifest()
    assert manifest["heldout_percent"] == HELDOUT_PERCENT
    assert manifest["salt"] == "lrr-harvest-split-v1"


def test_replay_starts_at_the_citation_clause() -> None:
    context = (
        "Words in s. 109(1) inserted (11.10.2004) by Theft Act 1968 (c. 60), s. 1; "
        "S.I. 2004/2624, art. 2"
    )
    assert replay_query(citation("Theft Act 1968", context, "uk/ukpga/1968/60")) == (
        "Theft Act 1968 (c. 60), s. 1"
    )


@pytest.fixture(scope="module")
def router() -> Router:
    return Router.from_path(FIXTURE_INDEX)


ERA = "Employment Rights Act 1996"
S124 = "uk/ukpga/1996/18/s124"
CLASSIFY_CASES = [
    ("Theft Act 1968", "by Theft Act 1968 (c. 60), s. 1", "uk/ukpga/1968/60", "correct"),
    ("section 124", f"section 124 of the {ERA}", S124, "correct"),
    ("section 124", "section 124 of the Equality Act 2010", S124, "misroute"),
    ("the other statute", "Theft Act 1968 and the other statute", S124, "dropped"),
    ("section 125", f"section 125 of the {ERA}", S124, "wrong_provision"),
    ("s. 999", f"{ERA}, s. 999", "uk/ukpga/1996/18", "false_abstention"),
    ("this", "in subsection (4), omit this", "uk/ukpga/1996/18", "miss"),
]


@pytest.mark.parametrize(("text", "context", "target", "outcome"), CLASSIFY_CASES)
def test_classify(router: Router, text: str, context: str, target: str, outcome: str) -> None:
    assert classify(router, citation(text, context, target))[0] == outcome


def test_cli(tmp_path: Path) -> None:
    rows = [
        citation(
            "Theft Act 1968",
            "by Theft Act 1968 (c. 60), s. 1",
            "uk/ukpga/1968/60",
            citation_id=str(i),
        )
        for i in range(30)
    ]
    harvest = tmp_path / "h.jsonl"
    harvest.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    out = tmp_path / "report.md"
    assert (
        main(["run", "--harvest", str(harvest), "--index", str(FIXTURE_INDEX), "--out", str(out)])
        == 0
    )
    report = out.read_text()
    assert "| correct |" in report
    assert main(["split-manifest", "--out", str(tmp_path / "split.json")]) == 0


def test_import_queue(tmp_path: Path) -> None:
    db = tmp_path / "q.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE download_queue (doc_id TEXT, series TEXT, year TEXT, number TEXT, "
            "title TEXT, xml_url TEXT, status TEXT)"
        )
        connection.executemany(
            "INSERT INTO download_queue VALUES (?, ?, ?, ?, ?, '', 'pending')",
            [
                ("uk/uksi/2011/3006", "uksi", "2011", "3006", "The X Order 2011 (revoked)"),
                ("uk/ukpga/1807/78", "ukpga", "1807", "78", "An Act (regnal key: skipped)"),
                ("uk/ukpga/2006/46", "ukpga", "2006", "46", "Companies Act 2006"),
                ("uk/asp/2000/1", "asp", "2000", "1", "Not a queue series"),
            ],
        )
    entries = list(import_queue(db, source="q"))
    assert [(e.coordinate, e.repealed) for e in entries] == [
        ("uk/uksi/2011/3006", True),
        ("uk/ukpga/2006/46", False),
    ]
