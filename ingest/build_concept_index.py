"""Build the concept index (``data/concepts/``, roadmap D3) from the normalised records.

    uv run python -m ingest.build_concept_index --data data --out data/concepts \
        --snapshot 2026-09-28

Deterministic: files are read in sorted order and documents numbered in that order. Format
and fields: :mod:`legal_rag_router.concepts`. The router index is not read or changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import shutil
import time
from array import array
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from legal_rag_router.concepts import (
    BODY_TERMS,
    CONCEPT_FILES,
    CONCEPTS_FORMAT_VERSION,
    CONCEPTS_MANIFEST,
    FIELDS,
    pack_tf,
    terms,
)
from legal_rag_router.table import encode_table

log = logging.getLogger("ingest.build_concept_index")

STEMMER: Final = "lrr-light-v1"
_UNIT_RE: Final = re.compile(r"^(?:s|reg|art|rule|para)[A-Z]{0,2}\d+[A-Za-z0-9]*(?:\.\d+)?$")
_SCHEDULE_RE: Final = re.compile(r"^sch[0-9A-Za-z]*$")
_U16_MAX: Final = 0xFFFF


@dataclass(slots=True)
class _Doc:
    coordinate: str
    heading: str | None
    kind: str
    fields: dict[str, list[str]] = field(default_factory=lambda: {f: [] for f in FIELDS})


@dataclass(slots=True)
class ConceptBuild:
    docs: list[tuple[str, str | None, str]] = field(default_factory=list)
    lengths: array[int] = field(default_factory=lambda: array("H"))
    postings: dict[str, tuple[array[int], array[int]]] = field(default_factory=dict)
    totals: list[int] = field(default_factory=lambda: [0] * len(FIELDS))

    def add(self, doc: _Doc) -> None:
        doc_id = len(self.docs)
        self.docs.append((doc.coordinate, doc.heading, doc.kind))
        per_term: dict[str, list[int]] = {}
        for i, name in enumerate(FIELDS):
            words = doc.fields[name]
            self.lengths.append(min(len(words), _U16_MAX))
            self.totals[i] += len(words)
            for word, count in Counter(words).items():
                per_term.setdefault(word, [0] * len(FIELDS))[i] = count
        for word, counts in per_term.items():
            docs, tfs = self.postings.setdefault(word, (array("I"), array("I")))
            docs.append(doc_id)
            tfs.append(pack_tf(tuple(counts)))


def unit_of(relative: str) -> str | None:
    """The document a provision path belongs to: its top-most section-level unit."""
    parts = relative.split("/")
    for i, part in enumerate(parts):
        if _UNIT_RE.match(part):
            return "/".join(parts[: i + 1])
    return None


def instrument_docs(records: Sequence[dict[str, Any]]) -> Iterator[_Doc]:
    """The documents of one instrument file: the instrument, its schedules and its units."""
    instrument, provisions = records[0], records[1:]
    base = instrument["coordinate"]
    title_words = terms(" ".join(filter(None, (instrument["title"], instrument.get("long_title")))))
    whole = _Doc(base, instrument["title"], "i")
    whole.fields["title"] = title_words
    yield whole
    rel = {r["coordinate"]: r["coordinate"][len(base) + 1 :] for r in provisions}
    titles = {rel[r["coordinate"]]: r.get("title") or "" for r in provisions}
    groups_of: dict[str, list[str]] = {}
    for group, members in (instrument.get("groups") or {}).items():
        for member in members:
            groups_of.setdefault(member, []).append(group)
    units: dict[str, _Doc] = {}
    for record in provisions:
        path = rel[record["coordinate"]]
        if _SCHEDULE_RE.match(path):
            schedule = _Doc(record["coordinate"], record.get("title"), "p")
            schedule.fields["heading"] = terms(record.get("title") or "")
            schedule.fields["title"] = title_words
            units[path] = schedule
            continue
        unit = unit_of(path)
        if unit is None:
            continue
        doc = units.get(unit)
        if doc is None:
            doc = _Doc(f"{base}/{unit}", record.get("title"), "p")
            doc.fields["heading"] = terms(record.get("title") or "")
            doc.fields["crossheading"] = terms(record.get("crossheading") or "")
            structure = " ".join(titles.get(g, "") for g in groups_of.get(unit, ()))
            top = unit.split("/")[0]
            if top != unit and _SCHEDULE_RE.match(top):
                structure = f"{titles.get(top, '')} {structure}"
            doc.fields["structure"] = terms(structure)
            doc.fields["title"] = title_words
            units[unit] = doc
        room = BODY_TERMS - len(doc.fields["body"])
        if room > 0:
            text = f"{record.get('text') or ''} {record.get('text_after') or ''}"
            doc.fields["body"] += terms(text)[:room]
    yield from units.values()


def _files(data_dir: Path) -> list[Path]:
    return sorted((data_dir / "uk").glob("*/*/uk_*.jsonl"))


def build_concepts(data_dir: Path) -> ConceptBuild:
    out = ConceptBuild()
    files = _files(data_dir)
    for n, path in enumerate(files, start=1):
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        for doc in instrument_docs(records):
            out.add(doc)
        if n % 20000 == 0:
            log.info("%d / %d files, %d documents", n, len(files), len(out.docs))
    return out


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_concepts(build: ConceptBuild, out_dir: Path, *, snapshot: str) -> dict[str, Any]:
    """Write the index files and manifest into ``out_dir`` (replaced atomically)."""
    staging = out_dir.with_name(out_dir.name + ".tmp")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    doc_ids, tfs, term_items = array("I"), array("I"), []
    for word in sorted(build.postings, key=lambda w: w.encode()):
        docs, counts = build.postings[word]
        term_items.append((word, f"{len(doc_ids)},{len(docs)}"))
        doc_ids.extend(docs)
        tfs.extend(counts)
    tbl, off = encode_table(term_items)
    (staging / "terms.tbl").write_bytes(tbl)
    (staging / "terms.off").write_bytes(off)
    (staging / "postings.doc").write_bytes(doc_ids.tobytes())
    (staging / "postings.tf").write_bytes(tfs.tobytes())
    doc_items = (
        (f"{i:08d}", json.dumps({"c": c, "h": h, "k": k}, ensure_ascii=False, sort_keys=True))
        for i, (c, h, k) in enumerate(build.docs)
    )
    tbl, off = encode_table(doc_items)
    (staging / "docs.tbl").write_bytes(tbl)
    (staging / "docs.off").write_bytes(off)
    (staging / "lengths.bin").write_bytes(build.lengths.tobytes())
    count = len(build.docs)
    manifest = {
        "format_version": CONCEPTS_FORMAT_VERSION,
        "snapshot": snapshot,
        "fields": list(FIELDS),
        "body_terms": BODY_TERMS,
        "stemmer": STEMMER,
        "counts": {
            "docs": count,
            "instrument_docs": sum(1 for _, _, k in build.docs if k == "i"),
            "terms": len(term_items),
            "postings": len(doc_ids),
        },
        "average_lengths": [round(t / count, 4) if count else 0.0 for t in build.totals],
        "files": {name: {"sha256": _sha256(staging / name)} for name in CONCEPT_FILES},
    }
    (staging / CONCEPTS_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    shutil.rmtree(out_dir, ignore_errors=True)
    staging.replace(out_dir)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--snapshot", required=True, help="the router index snapshot date")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start = time.monotonic()
    manifest = write_concepts(build_concepts(args.data), args.out, snapshot=args.snapshot)
    log.info("built %s in %.1fs: %s", args.out, time.monotonic() - start, manifest["counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
