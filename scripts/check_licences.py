"""Licence gate: every corpus data tree must be covered by a source in data/MANIFEST.json.

Usage: python scripts/check_licences.py [--data DIR] [--fixtures DIR ...]

Checks, failing with a non-zero exit on any problem:

* the manifest parses and validates (source ids unique, licence fields present, a checked date);
* every top-level entry under ``data/`` (other than the manifest) is a record path or a
  derived path of some source;
* every record path that exists holds exactly ``document_count`` instrument files
  (``*.jsonl``), and a present record path with ``document_count: null`` is an error:
  ingest must record the count;
* every index directory given with ``--fixtures`` (default: the committed fixture index)
  names in its ``index-manifest.json`` only sources that are in the licence manifest.

Missing ``data/`` subtrees are fine: CI runs without the corpus.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, field_validator

REPO = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = (REPO / "tests" / "fixtures" / "index",)
MANIFEST_NAME = "MANIFEST.json"
INDEX_MANIFEST_NAME = "index-manifest.json"

RelPath = Annotated[str, Field(min_length=1, pattern=r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$")]


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    jurisdiction: str = Field(pattern=r"^[a-z]{2,8}$")
    url: HttpUrl
    licence: str = Field(min_length=1)
    licence_url: HttpUrl
    terms_url: HttpUrl
    date_checked: date
    attribution: str = Field(min_length=1)
    notes: str = ""
    record_paths: list[RelPath]
    derived_paths: list[RelPath] = []
    document_count: int | None = Field(default=None, ge=0)


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format_version: int = Field(ge=1, le=1)
    sources: list[Source] = Field(min_length=1)

    @field_validator("sources")
    @classmethod
    def _unique_ids(cls, sources: list[Source]) -> list[Source]:
        ids = [s.id for s in sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source ids must be unique")
        return sources


def load_manifest(path: Path) -> Manifest:
    return Manifest.model_validate_json(path.read_bytes())


def _covers(path: str, entry: str) -> bool:
    """True when manifest path ``path`` covers top-level data entry ``entry``."""
    return path == entry or path.startswith(entry + "/")


def check_data(data_dir: Path, manifest: Manifest) -> list[str]:
    problems: list[str] = []
    declared = [p for s in manifest.sources for p in (*s.record_paths, *s.derived_paths)]
    if data_dir.is_dir():
        for entry in sorted(data_dir.iterdir()):
            if entry.name == MANIFEST_NAME or entry.name.startswith("."):
                continue
            if not any(_covers(p, entry.name) for p in declared):
                problems.append(f"data/{entry.name} is not covered by any manifest source")
    for source in manifest.sources:
        present = [data_dir / p for p in source.record_paths if (data_dir / p).exists()]
        if not present:
            continue
        count = sum(1 for root in present for _ in root.rglob("*.jsonl"))
        if source.document_count is None:
            problems.append(
                f"{source.id}: record data present ({count} files) but document_count is null"
            )
        elif count != source.document_count:
            problems.append(
                f"{source.id}: document_count is {source.document_count} but {count} "
                "instrument files are present"
            )
    return problems


def check_index_sources(index_dir: Path, manifest: Manifest) -> list[str]:
    index_manifest = index_dir / INDEX_MANIFEST_NAME
    if not index_manifest.is_file():
        return []
    try:
        declared = json.loads(index_manifest.read_text(encoding="utf-8")).get("sources")
    except json.JSONDecodeError as exc:
        return [f"{index_manifest}: not valid JSON ({exc})"]
    if not isinstance(declared, list) or not declared:
        return [f"{index_manifest}: must list the sources it was built from"]
    known = {s.id for s in manifest.sources}
    return [
        f"{index_manifest}: source {name!r} is not in the licence manifest"
        for name in declared
        if name not in known
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--fixtures", type=Path, nargs="*", default=list(DEFAULT_FIXTURES))
    args = parser.parse_args(argv)

    manifest_path: Path = args.data / MANIFEST_NAME
    try:
        manifest = load_manifest(manifest_path)
    except FileNotFoundError:
        print(f"FAIL: {manifest_path} not found", file=sys.stderr)
        return 1
    except ValidationError as exc:
        print(f"FAIL: {manifest_path} is invalid:\n{exc}", file=sys.stderr)
        return 1

    problems = check_data(args.data, manifest)
    for fixture in args.fixtures:
        problems.extend(check_index_sources(fixture, manifest))
    for problem in problems:
        print(f"FAIL: {problem}", file=sys.stderr)
    if not problems:
        print(f"OK: {len(manifest.sources)} source(s); every data tree is licensed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
