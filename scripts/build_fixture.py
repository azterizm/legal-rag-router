"""Rebuild the committed fixture index (tests/fixtures/index/) from tests/fixtures/fixture.toml.

Build machine only: needs ``uk_scrap_data/`` (raw XML) and ``data/catalogue/uk_catalogue.jsonl``.
Deterministic: re-running on the same inputs produces byte-identical files.

Usage: uv run python -m scripts.build_fixture [--source uk_scrap_data] [--catalogue …]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import tomllib
from collections import defaultdict
from datetime import date
from pathlib import Path

from ingest import build_index, uk

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"


def _coverage_sample(catalogue: Path, per_series: int, extra: list[str]) -> list[str]:
    by_series: dict[str, list[str]] = defaultdict(list)
    wanted = set(extra)
    lines: list[str] = []
    with catalogue.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            series = row["series"]
            if row["coordinate"] in wanted or len(by_series[series]) < per_series:
                by_series[series].append(row["coordinate"])
                lines.append(line.rstrip("\n"))
    missing = wanted - {json.loads(line)["coordinate"] for line in lines}
    if missing:
        raise SystemExit(f"coverage_extra entries not in the catalogue: {sorted(missing)}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--source", type=Path, default=REPO / "uk_scrap_data")
    parser.add_argument(
        "--catalogue", type=Path, default=REPO / "data/catalogue/uk_catalogue.jsonl"
    )
    parser.add_argument("--out", type=Path, default=FIXTURES / "index")
    args = parser.parse_args(argv)

    spec = tomllib.loads((FIXTURES / "fixture.toml").read_text(encoding="utf-8"))
    instruments: list[str] = spec["instruments"]
    pending = set(spec.get("pending", []))

    with tempfile.TemporaryDirectory(prefix="lrr-fixture-") as tmp:
        work = Path(tmp)
        status = uk.main(
            [
                "--source",
                str(args.source),
                "--data",
                str(work),
                "--workers",
                "4",
                "--only",
                *instruments,
            ]
        )
        if status != 0:
            print("fixture ingest reported failures; see INGEST_REPORT.json", file=sys.stderr)
            return status
        present = {p.stem for p in (work / "uk").rglob("*.jsonl")}
        missing = set(instruments) - present
        unexpected = missing - pending
        if unexpected:
            print(
                f"fixture instruments missing from the raw cache: {sorted(unexpected)}",
                file=sys.stderr,
            )
            return 1
        if missing:
            print(f"pending (not yet downloaded, skipped): {sorted(missing)}")

        catalogue = work / "catalogue.jsonl"
        sample = _coverage_sample(
            args.catalogue, spec["coverage_per_series"], spec["coverage_extra"]
        )
        catalogue.write_text("\n".join(sample) + "\n", encoding="utf-8")

        built = build_index.build_index(
            work,
            catalogue=catalogue,
            aliases_dir=REPO / "aliases",
            allow_missing_alias_targets=True,
        )
        staging = work / "index"
        manifest = build_index.write_index(
            built,
            staging,
            snapshot=date.fromisoformat(spec["snapshot"]),
            sources=["legislation.gov.uk"],
        )
        if args.out.exists():
            shutil.rmtree(args.out)
        shutil.copytree(staging, args.out)
    size = sum(p.stat().st_size for p in args.out.iterdir())
    counts = json.dumps(manifest["counts"])
    print(f"fixture index written to {args.out} ({size / 1e6:.1f} MB): {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
