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
import math
import re
import shutil
import time
import tomllib
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
    PRIOR_FLAGS,
    pack_tf,
    terms,
)
from legal_rag_router.coordinate import Coordinate
from legal_rag_router.table import encode_table

log = logging.getLogger("ingest.build_concept_index")

STEMMER: Final = "lrr-light-v1"
_UNIT_RE: Final = re.compile(r"^(?:s|reg|art|rule|para)[A-Z]{0,2}\d+[A-Za-z0-9]*(?:\.\d+)?$")
_SCHEDULE_RE: Final = re.compile(r"^sch[0-9A-Za-z]*$")
_U16_MAX: Final = 0xFFFF
_OPENING_CHARS: Final = 300
# A provision whose opening words amend another enactment ("In section 7 of the Inheritance
# Tax Act 1984 ... substitute") is where the change was made, not where the law now lives.
_AMENDING_RE: Final = re.compile(
    r"\b(?:is|are) (?:further )?amended\b|\bamended as follows\b|\bthere (?:is|are) "
    r"(?:inserted|substituted)\b|\b(?:insert|substitute|omit)\b|\b(?:is|are) repealed\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class _Doc:
    coordinate: str
    heading: str | None
    kind: str
    fields: dict[str, list[str]] = field(default_factory=lambda: {f: [] for f in FIELDS})
    flags: int = 0
    instrument: str = ""


_NI_SERIES: Final = frozenset({"nisi", "nisr", "nisro", "apni", "nia", "mnia"})
_SCOTLAND_SERIES: Final = frozenset({"ssi", "asp", "aosp"})


def instrument_flags(instrument: dict[str, Any]) -> int:
    """The source facts every document of an instrument shares (:data:`PRIOR_FLAGS`)."""
    title = str(instrument["title"]).casefold()
    series = str(instrument["coordinate"]).split("/")[1]
    facts = {
        "repealed": bool(instrument.get("repealed")),
        "northern_ireland": series in _NI_SERIES or "northern ireland" in title,
        "scotland": series in _SCOTLAND_SERIES or "(scotland)" in title,
        "amending": "amendment" in title,
        "commencement": "commencement" in title,
        "secondary": instrument.get("authority_type") == "SECONDARY_INSTRUMENT",
    }
    return sum(1 << i for i, name in enumerate(PRIOR_FLAGS) if facts[name])


@dataclass(slots=True)
class ConceptBuild:
    docs: list[tuple[str, str | None, str]] = field(default_factory=list)
    lengths: array[int] = field(default_factory=lambda: array("H"))
    flags: bytearray = field(default_factory=bytearray)
    instruments: list[str] = field(default_factory=list)
    postings: dict[str, tuple[array[int], array[int]]] = field(default_factory=dict)
    totals: list[int] = field(default_factory=lambda: [0] * len(FIELDS))

    def add(self, doc: _Doc) -> None:
        doc_id = len(self.docs)
        self.docs.append((doc.coordinate, doc.heading, doc.kind))
        self.flags.append(doc.flags)
        self.instruments.append(doc.instrument)
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
    flags = instrument_flags(instrument)
    repealed_bit = 1 << PRIOR_FLAGS.index("repealed")
    title_words = terms(" ".join(filter(None, (instrument["title"], instrument.get("long_title")))))
    whole = _Doc(base, instrument["title"], "i", flags=flags, instrument=base)
    whole.fields["title"] = title_words
    yield whole
    rel = {r["coordinate"]: r["coordinate"][len(base) + 1 :] for r in provisions}
    titles = {rel[r["coordinate"]]: r.get("title") or "" for r in provisions}
    groups_of: dict[str, list[str]] = {}
    for group, members in (instrument.get("groups") or {}).items():
        for member in members:
            groups_of.setdefault(member, []).append(group)
    units: dict[str, _Doc] = {}
    opening: dict[str, str] = {}
    for record in provisions:
        path = rel[record["coordinate"]]
        if _SCHEDULE_RE.match(path):
            schedule = _Doc(record["coordinate"], record.get("title"), "p", flags=flags,
                            instrument=base)  # fmt: skip
            schedule.fields["heading"] = terms(record.get("title") or "")
            schedule.fields["title"] = title_words
            units[path] = schedule
            continue
        unit = unit_of(path)
        if unit is None:
            continue
        doc = units.get(unit)
        if doc is None:
            own = flags | (repealed_bit if record.get("repealed") else 0)
            doc = _Doc(f"{base}/{unit}", record.get("title"), "p", flags=own, instrument=base)
            doc.fields["heading"] = terms(record.get("title") or "")
            doc.fields["crossheading"] = terms(record.get("crossheading") or "")
            structure = " ".join(titles.get(g, "") for g in groups_of.get(unit, ()))
            top = unit.split("/")[0]
            if top != unit and _SCHEDULE_RE.match(top):
                structure = f"{titles.get(top, '')} {structure}"
            doc.fields["structure"] = terms(structure)
            doc.fields["title"] = title_words
            units[unit] = doc
        text = f"{record.get('text') or ''} {record.get('text_after') or ''}"
        if len(opening.get(unit, "")) < _OPENING_CHARS:
            opening[unit] = f"{opening.get(unit, '')} {text}"
        room = BODY_TERMS - len(doc.fields["body"])
        if room > 0:
            doc.fields["body"] += terms(text)[:room]
    amending_bit = 1 << PRIOR_FLAGS.index("amending")
    for unit, text in opening.items():
        if _AMENDING_RE.search(text[:_OPENING_CHARS]):
            units[unit].flags |= amending_bit
    yield from units.values()


def _files(data_dir: Path) -> list[Path]:
    return sorted((data_dir / "uk").glob("*/*/uk_*.jsonl"))


def build_concepts(data_dir: Path) -> ConceptBuild:
    """Provision documents first, then every instrument document, so a document's kind
    follows from its id (``first_instrument_doc`` in the manifest)."""
    out = ConceptBuild()
    files = _files(data_dir)
    instruments: list[_Doc] = []
    for n, path in enumerate(files, start=1):
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        for doc in instrument_docs(records):
            if doc.kind == "i":
                instruments.append(doc)
            else:
                out.add(doc)
        if n % 20000 == 0:
            log.info("%d / %d files, %d documents", n, len(files), len(out.docs))
    for doc in instruments:
        out.add(doc)
    return out


def compile_thesaurus(path: Path | None) -> dict[str, list[str]]:
    """``thesaurus/{jurisdiction}.toml`` → stemmed term → stemmed expansions.

    Query expansion only: a synonym never outweighs the word the user typed.
    """
    if path is None or not path.is_file():
        return {}
    raw = tomllib.loads(path.read_text(encoding="utf-8")).get("synonyms", {})
    out: dict[str, list[str]] = {}
    for word, expansions in sorted(raw.items()):
        keys = terms(word)
        if len(keys) != 1:
            raise ValueError(f"{path.name}: thesaurus key {word!r} must be one indexable word")
        found = [t for e in expansions for t in terms(e) if t != keys[0]]
        out[keys[0]] = sorted(set(out.get(keys[0], [])) | set(found))
    return out


def citation_in_degree(harvest: Path | None) -> Counter[str]:
    """Citations to each instrument from the text of legislation (not editorial notes)."""
    counts: Counter[str] = Counter()
    if harvest is None or not harvest.is_file():
        return counts
    with harvest.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            target = row.get("target_coordinate")
            if not target or row.get("in_commentary") or row.get("in_amendment"):
                continue
            coordinate = Coordinate.try_parse(str(target))
            if coordinate is not None:
                counts[str(coordinate.instrument_coordinate)] += 1
    return counts


def _degree_byte(count: int) -> int:
    return min(255, round(16 * math.log2(1 + count)))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_concepts(
    build: ConceptBuild,
    out_dir: Path,
    *,
    snapshot: str,
    thesaurus: dict[str, list[str]] | None = None,
    in_degree: Counter[str] | None = None,
) -> dict[str, Any]:
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
    degrees = in_degree or Counter()
    priors = bytearray()
    for flags, instrument in zip(build.flags, build.instruments, strict=True):
        priors += bytes((flags, _degree_byte(degrees.get(instrument, 0))))
    (staging / "priors.bin").write_bytes(bytes(priors))
    (staging / "thesaurus.json").write_text(
        json.dumps(thesaurus or {}, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    count = len(build.docs)
    instrument_docs = sum(1 for _, _, k in build.docs if k == "i")
    manifest = {
        "format_version": CONCEPTS_FORMAT_VERSION,
        "snapshot": snapshot,
        "fields": list(FIELDS),
        "body_terms": BODY_TERMS,
        "stemmer": STEMMER,
        "first_instrument_doc": count - instrument_docs,
        "counts": {
            "docs": count,
            "instrument_docs": instrument_docs,
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
    parser.add_argument("--thesaurus", type=Path, default=Path("thesaurus/uk.toml"))
    parser.add_argument("--harvest", type=Path, default=None, help="for citation in-degree")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start = time.monotonic()
    manifest = write_concepts(
        build_concepts(args.data),
        args.out,
        snapshot=args.snapshot,
        thesaurus=compile_thesaurus(args.thesaurus),
        in_degree=citation_in_degree(args.harvest),
    )
    log.info("built %s in %.1fs: %s", args.out, time.monotonic() - start, manifest["counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
