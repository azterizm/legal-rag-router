"""The discovery evaluation harness (roadmap D4/D5): hit rule and the test-slice guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from eval.discovery import hit_rank, main

ERA = "uk/ukpga/1996/18"


@pytest.mark.parametrize(
    ("gold", "found", "rank"),
    [
        ((f"{ERA}/s124",), [f"{ERA}/s98", f"{ERA}/s124"], 2),
        ((f"{ERA}/s124",), [f"{ERA}/s124/1ZA"], 1),  # beneath a gold coordinate
        ((f"{ERA}/s124/1ZA",), [f"{ERA}/s124"], None),  # above it is not a hit
        ((f"{ERA}/s124",), [f"{ERA}/s1245"], None),
        ((f"{ERA}/s86", f"{ERA}/s23"), [f"{ERA}/s1", f"{ERA}/s23"], 2),
    ],
)
def test_hit_rank(gold: tuple[str, ...], found: list[str], rank: int | None) -> None:
    assert hit_rank(gold, found) == rank


def test_the_test_slice_needs_a_seal(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--split", "test"])
    assert "verified concept seal" in capsys.readouterr().err


def test_misses_are_listed_for_dev_only(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--split", "test", "--misses", "--seal", "x.json"])
    assert "dev slice only" in capsys.readouterr().err


def test_a_changed_battery_fails_the_seal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seal = tmp_path / "seal.json"
    seal.write_text('{"kind": "concept", "seal_format": 1, "contents": {}, "seal_sha256": "0"}')
    assert main(["--split", "test", "--seal", str(seal)]) == 1
    assert "SEAL ERROR" in capsys.readouterr().out
