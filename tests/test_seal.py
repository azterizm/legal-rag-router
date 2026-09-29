"""Battery seal (plan step 9): a sealed run refuses one changed byte."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from eval.seal import SealError, canonical, main, seal_battery, verify_battery_seal
from tests.conftest import FIXTURE_INDEX


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)  # noqa: S603, S607


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "batteries" / "uk").mkdir(parents=True)
    (root / "batteries" / "uk" / "collision.jsonl").write_text('{"id": "uk-collision-0001"}\n')
    (root / "aliases").mkdir()
    (root / "aliases" / "uk.toml").write_text("# aliases\n")
    (root / "reports").mkdir()
    (root / "reports" / "harvest-split.json").write_text('{"salt": "x"}\n')
    shutil.copytree(FIXTURE_INDEX, root / "index")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@lrr.test", "commit", "-qm", "batteries")
    return root


def _sealed(repo: Path) -> Path:
    assert main(["--repo", str(repo), "battery", "--index", str(repo / "index")]) == 0
    [path] = (repo / "seals").glob("battery-*.json")
    return path


def test_seal_round_trip(repo: Path) -> None:
    path = _sealed(repo)
    seal = json.loads(path.read_text())
    assert set(seal["contents"]["batteries"]) == {"batteries/uk/collision.jsonl"}
    assert seal["contents"]["typo_policy"]["auto_correct_edits"] == 1
    assert verify_battery_seal(path, repo, repo / "index")["git_commit"] == seal["git_commit"]
    assert main(["--repo", str(repo), "verify", str(path), "--index", str(repo / "index")]) == 0


@pytest.mark.parametrize(
    ("target", "named"),
    [
        ("batteries/uk/collision.jsonl", "batteries/batteries/uk/collision.jsonl"),
        ("index/titles.tbl", "index/files/titles.tbl"),
        ("aliases/uk.toml", "aliases/aliases/uk.toml"),
        ("reports/harvest-split.json", "harvest_split/reports/harvest-split.json"),
    ],
)
def test_one_changed_byte_is_refused(repo: Path, target: str, named: str) -> None:
    path = _sealed(repo)
    changed = repo / target
    data = bytearray(changed.read_bytes())
    data[0] ^= 1
    changed.write_bytes(bytes(data))
    with pytest.raises(SealError, match=named):
        verify_battery_seal(path, repo, repo / "index")
    assert main(["--repo", str(repo), "verify", str(path), "--index", str(repo / "index")]) == 1


def test_a_new_battery_file_is_refused(repo: Path) -> None:
    path = _sealed(repo)
    (repo / "batteries" / "uk" / "typo.jsonl").write_text("{}\n")
    with pytest.raises(SealError, match=r"typo\.jsonl: sealed None"):
        verify_battery_seal(path, repo, repo / "index")


def test_an_edited_seal_is_refused(repo: Path) -> None:
    path = _sealed(repo)
    seal = json.loads(path.read_text())
    seal["contents"]["batteries"]["batteries/uk/collision.jsonl"] = "0" * 64
    path.write_text(json.dumps(seal))
    with pytest.raises(SealError, match="has been edited"):
        verify_battery_seal(path, repo, repo / "index")


def test_only_a_battery_seal_is_accepted(repo: Path) -> None:
    path = repo / "other.json"
    path.write_text(json.dumps({"kind": "results", "seal_format": 1}))
    with pytest.raises(SealError, match="not a format-1 battery seal"):
        verify_battery_seal(path, repo, repo / "index")


def test_sealing_needs_a_committed_tree(repo: Path) -> None:
    (repo / "aliases" / "uk.toml").write_text("# changed\n")
    with pytest.raises(SealError, match="commit every tracked change"):
        seal_battery(repo, repo / "index")


def test_canonical_form_is_key_order_free() -> None:
    assert (
        canonical({"b": 1, "a": "é"}) == canonical({"a": "é", "b": 1}) == '{"a":"é","b":1}'.encode()
    )


def test_the_concept_battery_has_its_own_seal(repo: Path) -> None:
    path = _sealed(repo)
    (repo / "batteries" / "concept").mkdir()
    (repo / "batteries" / "concept" / "uk.jsonl").write_text("{}\n")
    assert verify_battery_seal(path, repo, repo / "index")["kind"] == "battery"


def test_concept_seal_pins_the_concept_battery_only(repo: Path) -> None:
    (repo / "batteries" / "concept").mkdir()
    concept = repo / "batteries" / "concept" / "uk.jsonl"
    concept.write_text('{"id": "uk-concept-0001"}\n')
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@lrr.test", "commit", "-qm", "concept")
    assert main(["--repo", str(repo), "concept", "--index", str(repo / "index")]) == 0
    [path] = (repo / "seals").glob("concept-*.json")
    seal = json.loads(path.read_text())
    assert set(seal["contents"]["batteries"]) == {"batteries/concept/uk.jsonl"}
    (repo / "batteries" / "uk" / "collision.jsonl").write_text("changed\n")  # not pinned here
    assert verify_battery_seal(path, repo, repo / "index")["kind"] == "concept"
    concept.write_text("changed\n")
    with pytest.raises(SealError, match=r"concept/uk\.jsonl"):
        verify_battery_seal(path, repo, repo / "index")
