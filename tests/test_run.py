"""The sealed run (roadmap M10): it refuses a changed battery, and seals what it writes."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from batteries.schema import BATTERIES, BatteryRow, write_battery
from eval.run import main
from eval.seal import SealError, seal_battery, verify_results_seal
from tests.conftest import FIXTURE_INDEX

ERA = "uk/ukpga/1996/18"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)  # noqa: S603, S607


def _row(battery: str) -> BatteryRow:
    row: dict[str, object] = {
        "id": f"uk-{battery}-0001",
        "query": "section 124 of the Employment Rights Act 1996",
        "lang": "en",
        "domain": "uk_legislation",
        "expected_status": "ROUTE_BOUNDED",
        "expected_coordinates": [f"{ERA}/s124"],
        "source": "real_document" if battery == "misroute" else "hand",
    }
    if battery == "typo":
        row["split"] = "test"
    if battery == "invented":
        row |= {"query": "section 999 of the Employment Rights Act 1996",
                "expected_status": "EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND",
                "expected_coordinates": []}  # fmt: skip
    return BatteryRow.model_validate(row)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for battery in BATTERIES:
        write_battery(root / "batteries" / "uk" / f"{battery}.jsonl", [_row(battery)])
    (root / "aliases").mkdir()
    (root / "aliases" / "uk.toml").write_text("# aliases\n")
    (root / "reports").mkdir()
    (root / "reports" / "harvest-split.json").write_text('{"salt": "x"}\n')
    shutil.copytree(FIXTURE_INDEX, root / "index")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@lrr.test", "commit", "-qm", "batteries")
    seal = seal_battery(root, root / "index")
    (root / "seals").mkdir()
    (root / "seals" / "battery.json").write_text(json.dumps(seal))
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@lrr.test", "commit", "-qm", "seal")
    return root


def _run(repo: Path) -> int:
    return main(["--repo", str(repo), "--seal", str(repo / "seals" / "battery.json"),
                 "--index", str(repo / "index")])  # fmt: skip


def test_a_sealed_run_writes_and_seals_its_results(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(repo) == 0
    [results] = (repo / "results").glob("uk-run-*.json")
    payload = json.loads(results.read_text())
    metrics = payload["metrics"]["uk_legislation"]
    assert metrics["collision"]["count"] == 0
    assert metrics["bound_on_invented"] == {"count": 0, "total": 1, "rate": 0.0,
                                            "upper_95": pytest.approx(0.95)}  # fmt: skip
    assert len(payload["rows"]) == len(BATTERIES)
    assert all(row["met"] for row in payload["rows"] if row["expected_status"] == "ROUTE_BOUNDED")
    [seal] = (repo / "seals").glob("results-*.json")
    verified = verify_results_seal(seal, repo)
    assert verified["contents"]["battery_seal"]["file"] == "seals/battery.json"
    assert "| Bound on invented law | 0 | 1 |" in capsys.readouterr().out
    results.write_text(results.read_text().replace('"met": true', '"met": false', 1))
    with pytest.raises(SealError, match="the sealed results changed"):
        verify_results_seal(seal, repo)


def test_one_changed_battery_byte_refuses_the_run(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    battery = repo / "batteries" / "uk" / "collision.jsonl"
    data = bytearray(battery.read_bytes())
    data[-2] ^= 1
    battery.write_bytes(bytes(data))
    assert _run(repo) == 1
    assert "REFUSED" in capsys.readouterr().out
    assert not (repo / "results").exists()


def test_uncommitted_code_refuses_the_run(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "seals" / "battery.json").write_text(
        (repo / "seals" / "battery.json").read_text() + "\n"
    )  # a tracked file changed, the sealed inputs did not
    assert _run(repo) == 1
    assert "commit every tracked change" in capsys.readouterr().out


def test_only_the_battery_seal_starts_a_run(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    concept = seal_battery(repo, repo / "index", kind="concept")
    (repo / "seals" / "battery.json").write_text(json.dumps(concept))
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@lrr.test", "commit", "-qm", "concept")
    assert _run(repo) == 1
    assert "not the battery seal" in capsys.readouterr().out


def test_a_results_seal_is_checked(repo: Path) -> None:
    other = repo / "other.json"
    other.write_text(json.dumps({"kind": "battery", "seal_format": 1}))
    with pytest.raises(SealError, match="not a format-1 results seal"):
        verify_results_seal(other, repo)
    assert _run(repo) == 0
    [seal] = (repo / "seals").glob("results-*.json")
    edited = json.loads(seal.read_text())
    edited["contents"]["package_version"] = "9"
    seal.write_text(json.dumps(edited))
    with pytest.raises(SealError, match="has been edited"):
        verify_results_seal(seal, repo)
