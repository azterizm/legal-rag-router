"""Build the router index (``data/index/``) from normalised records, catalogue and aliases.

Deterministic: the same inputs always produce byte-identical files (sorted keys, gzip
``mtime=0``, no wall-clock timestamps; the snapshot date is an explicit argument).

Usage::

    uv run python -m ingest.build_index --data data --out data/index --snapshot 2026-09-27

The build fails (exit 1, nothing written) on any integrity problem:

* a record fails its checksum or schema;
* two coordinates collide after casefolding, unless they are case variants inside the same
  instrument (roadmap decision 7), which are recorded in ``case_variants.json``;
* an alias names a missing instrument (unless ``--allow-missing-alias-targets``, which
  marks the index ``partial`` and lists the dropped aliases in the manifest), maps one form
  to two targets, or shadows another instrument's title.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import time
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Final

from ingest.records import CatalogueEntry, InstrumentRecord, read_instrument_file
from legal_rag_router import __version__
from legal_rag_router.coordinate import Coordinate
from legal_rag_router.grammars.uk import INSTRUMENT_TYPE_WORDS, number_keys
from legal_rag_router.index import FORMAT_VERSION, INDEX_FILES, MANIFEST_NAME
from legal_rag_router.normalise import PARTICLES, fold, split_title_year, title_key, title_words
from legal_rag_router.table import encode_table

__all__ = ["BuildError", "IndexBuild", "acronym_keys", "build_index", "main", "title_variants"]

log = logging.getLogger("ingest.build_index")

GRAMMAR_VERSION: Final = 1
TYPO_MAX_EDITS: Final = 2
TYPO_MIN_WORD: Final = 3


class BuildError(ValueError):
    """Raised when the inputs cannot produce a trustworthy index."""


# ---------------------------------------------------------------------------- keys


# The source's editorial status note after a title is not part of the name: "The Immigration
# (Amendment) (EU Exit) Regulations 2019 (expired—not approved)", "… Act 1965 ( repealed
# 1.11.1996)". "(No. 2)" and other distinguishing words are kept.
_EDITORIAL_NOTE: Final = re.compile(
    r"\s*\(\s*(?:expired|repealed|revoked|lapsed|annulled|not approved)[^()]*\)\s*$",
    re.IGNORECASE,
)


def title_variants(title: str) -> tuple[str, ...]:
    """Every lookup key for a title (plan departure 1).

    Full title + year, title without the type word + year, title without the year, and
    the core words alone: ``employment rights act|1996``, ``employment rights|1996``,
    ``employment rights act``, ``employment rights``.
    """
    text, year = split_title_year(_EDITORIAL_NOTE.sub("", title))
    words = title_words(text)
    if not words:
        return ()
    core = words[:-1] if words[-1] in INSTRUMENT_TYPE_WORDS else words
    keys = [title_key(words, year), title_key(words)]
    if core != words and core and not all(w.isdigit() for w in core):
        keys += [title_key(core, year), title_key(core)]
    return tuple(dict.fromkeys(k for k in keys if k))


_SKIPPED: Final = "the of and a an at for to in on with etc from by against into under upon or"
ACRONYM_SKIP: Final = frozenset(_SKIPPED.split())
_ACRONYM_WORD: Final = re.compile(r"[^\W\d_]+|\d+")


def acronym_keys(title: str) -> tuple[str, ...]:
    """Generated acronyms of an Act title (roadmap decision 18).

    Initials with every particle kept (POCA, PACE), with only "the/of/and/a/an" skipped
    (OAPA, TCGA), and with all particles skipped (HSWA, ITEPA). Keys are
    ``form|year`` for forms of two letters or more, and the same without the "Act" initial
    when three letters remain (PACE, LASPO). Every generated form needs its year: bare
    acronyms collide with regulators (FCA, CMA) and come only from the curated aliases.
    Numbered titles ("Finance (No. 2) Act") get none, so "FA 2023" means the Finance Act.
    """
    text, year = split_title_year(title)
    words = _ACRONYM_WORD.findall(fold(text).text.replace("&", " and ").replace("'", ""))
    if year is None or len(words) < 2 or words[-1] != "act" or any(w.isdigit() for w in words):  # noqa: PLR2004
        return ()
    keys: set[str] = set()
    articles = [w for w in words if w not in PARTICLES]  # OAPA: "against" kept, "the" not
    for chosen in (words, articles, [w for w in words if w not in ACRONYM_SKIP]):
        full = "".join(w[0] for w in chosen)
        if len(full) >= 2:  # noqa: PLR2004
            keys.add(f"{full}|{year}")
        if len(full) >= 4:  # noqa: PLR2004 - without the Act initial: PACE, LASPO
            keys.add(f"{full[:-1]}|{year}")
    return tuple(sorted(keys))


def wordset_key(title: str) -> str | None:
    """Order-free key for the reordered-title tier: sorted content words + year."""
    text, year = split_title_year(title)
    words = title_words(text)
    if year is None or len(set(words)) < 2:  # noqa: PLR2004
        return None
    return " ".join(sorted(set(words))) + f"|{year}"


def deletes(word: str, max_edits: int = TYPO_MAX_EDITS) -> set[str]:
    """Symmetric-delete variants of ``word`` up to ``max_edits`` deletions (SymSpell)."""
    frontier = {word}
    out: set[str] = set()
    for _ in range(max_edits):
        nxt = {w[:i] + w[i + 1 :] for w in frontier for i in range(len(w)) if len(w) > 1}
        out |= nxt
        frontier = nxt
    return out


# ---------------------------------------------------------------------------- inputs


@dataclass(slots=True)
class _Instrument:
    record: InstrumentRecord
    coordinates: list[str]


def read_records(data_dir: Path, *, verify: bool) -> Iterator[_Instrument]:
    """Yield every instrument under ``data_dir/uk`` with its coordinates, in path order."""
    for path in sorted((data_dir / "uk").rglob("*.jsonl")):
        if verify:
            instrument, provisions = read_instrument_file(path)
            coordinates = [p.coordinate for p in provisions]
        else:
            with path.open(encoding="utf-8") as fh:
                instrument = InstrumentRecord.model_validate_json(fh.readline())
                coordinates = [json.loads(line)["coordinate"] for line in fh if line.strip()]
        yield _Instrument(instrument, [instrument.coordinate, *coordinates])


def read_catalogue(path: Path | None) -> Iterator[CatalogueEntry]:
    if path is None or not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield CatalogueEntry.model_validate_json(line)


def read_aliases(aliases_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(aliases_dir.glob("*.toml")):
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        for entry in data.get("alias", []):
            if not isinstance(entry.get("target"), str) or not entry.get("forms"):
                raise BuildError(f"{path.name}: every [[alias]] needs a target and forms")
            entries.append({**entry, "_file": path.name})
    return entries


# ---------------------------------------------------------------------------- build


@dataclass(slots=True)
class IndexBuild:
    """The built tables, before serialisation."""

    coordinates: list[str] = field(default_factory=list)
    instruments: dict[str, dict[str, Any]] = field(default_factory=dict)
    titles: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    aliases: dict[str, dict[str, Any]] = field(default_factory=dict)
    numbers: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    wordsets: dict[str, str] = field(default_factory=dict)
    words: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    typo: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    coverage: dict[str, Any] = field(default_factory=dict)
    acronyms: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    case_variants: dict[str, list[str]] = field(default_factory=dict)
    freshness: dict[str, dict[str, int]] = field(default_factory=dict)
    former_titles: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Instrument id → other titles from the source, before the decision 17 checks."""
    warnings: list[str] = field(default_factory=list)
    dropped_aliases: list[str] = field(default_factory=list)


def _instrument_part(coordinate: str) -> str:
    parsed = Coordinate.try_parse(coordinate)
    return str(parsed.instrument_coordinate) if parsed else coordinate


def _case_variants(coordinates: Iterable[str]) -> dict[str, list[str]]:
    by_key: dict[str, list[str]] = defaultdict(list)
    for coordinate in coordinates:
        by_key[coordinate.casefold()].append(coordinate)
    variants = {k: sorted(set(v)) for k, v in by_key.items() if len(set(v)) > 1}
    for key, spellings in sorted(variants.items()):
        if len({_instrument_part(s) for s in spellings}) > 1:
            raise BuildError(f"casefold collision between unrelated coordinates: {spellings}")
        log.info("case variants recorded for %s: %s", key, spellings)
    return variants


def _add_instrument(
    out: IndexBuild, item: _Instrument, wordset_ids: dict[str, set[str]], vocabulary: set[str]
) -> None:
    record = item.record
    iid = record.instrument_id
    if iid in out.instruments:
        raise BuildError(f"instrument {iid} appears in two record files")
    coordinate = Coordinate.parse(record.coordinate)
    year = coordinate.instrument[1]
    if coordinate.jurisdiction == "uk" and year.isdigit() and int(year) != record.year:
        # The router reads a UK calendar instrument's year from its id (typo._year_of).
        raise BuildError(f"instrument {iid}: year {record.year} differs from its coordinate")
    out.coordinates.extend(item.coordinates)
    out.instruments[iid] = {
        "c": record.coordinate,
        "t": record.title,
        "y": record.year,
        "n": record.number,
        "s": coordinate.series,
        "r": record.repealed,
        "st": record.structure,
        "p": record.authority_type == "PRIMARY_ACT",
        "g": {k: list(v) for k, v in record.groups.items()},
        "d": sorted(record.duplicated_provisions),
    }
    for key in title_variants(record.title):
        out.titles[key].append(iid)
    for key in number_keys(coordinate.instrument):
        out.numbers[key].append(iid)
    if len(coordinate.instrument) == 4:  # noqa: PLR2004 - regnal: also "1925 c. 20" by calendar year
        out.numbers[f"c/{record.year}/{record.number}"].append(iid)
    ws = wordset_key(record.title)
    if ws:
        wordset_ids[ws].add(iid)
    words = set(title_words(split_title_year(record.title)[0]))
    for word in words:
        out.words[word].append(iid)
    vocabulary |= words
    if record.authority_type == "PRIMARY_ACT":
        for key in acronym_keys(record.title):
            out.acronyms[key].append(iid)
        if record.other_titles:
            out.former_titles[iid] = record.other_titles
    if coordinate.instrument[1].isdigit():  # calendar-numbered: freshness per year
        series = out.freshness.setdefault(coordinate.series, {})
        year = coordinate.instrument[1]
        series[year] = max(series.get(year, 0), record.number)


def _add_coverage(out: IndexBuild, catalogue: Path | None, vocabulary: set[str]) -> None:
    """Instruments known to exist (catalogue) but not indexed: the out-of-coverage table."""
    indexed = {v["c"] for v in out.instruments.values()}
    instruments: dict[str, dict[str, Any]] = {}
    titles: dict[str, list[str]] = defaultdict(list)
    numbers: dict[str, list[str]] = defaultdict(list)
    for entry in read_catalogue(catalogue):
        if entry.coordinate in indexed or entry.coordinate in instruments:
            continue
        keys = number_keys(Coordinate.parse(entry.coordinate).instrument)
        if any(k.startswith("si/") and k in out.numbers for k in keys):
            # An SI number names one instrument: uksi/2013/2729 is indexed as wsi/2013/2729.
            # A chapter does not: 41 Geo. 3 c. 1 is both a Great Britain and a UK Act.
            continue
        instruments[entry.coordinate] = {
            "c": entry.coordinate,
            "t": entry.title,
            "y": entry.year,
            "s": entry.series,
            "r": entry.repealed,
        }
        if entry.title:
            for key in title_variants(entry.title):
                titles[key].append(entry.coordinate)
            vocabulary |= set(title_words(split_title_year(entry.title)[0]))
        for key in number_keys(Coordinate.parse(entry.coordinate).instrument):
            numbers[key].append(entry.coordinate)
    out.coverage = {
        "instruments": instruments,
        "titles": {k: sorted(set(v)) for k, v in titles.items()},
        "numbers": {k: sorted(set(v)) for k, v in numbers.items()},
        "series": sorted({v["s"] for v in instruments.values()}),
    }


_CHAPTER_SUFFIX: Final = re.compile(r"\s*\(c\.?\s*\d+\)\s*$", re.IGNORECASE)


def _former_title_key(out: IndexBuild, iid: str, other: str) -> str | None:
    """The full title key under which ``other`` may name instrument ``iid``, or ``None``.

    The source's effect titles include mapping errors (another Act's title), so a former
    title is kept only if it names the Act's own year, ends in "Act", and is not the
    current title of any other indexed or catalogued instrument. Regnal Acts also need
    half their content words shared: the source confuses sessions that share a calendar
    year and chapter (Army Act 1955, 3 & 4 Eliz. 2 c. 18, listed as the Aliens'
    Employment Act 1955, 4 & 5 Eliz. 2 c. 18).
    """
    info = out.instruments[iid]
    text, year = split_title_year(_CHAPTER_SUFFIX.sub("", other))
    cited = title_words(text)
    if year != info["y"] or not cited or cited[-1] != "act":
        return None
    regnal = not Coordinate.parse(info["c"]).instrument[1].isdigit()
    if regnal and not _shares_words(cited, info["t"]):
        out.warnings.append(f"former title {other!r} of {iid} shares no words with it")
        return None
    full = title_key(cited, year)
    owners = {*out.titles.get(full, ()), *out.coverage.get("titles", {}).get(full, ())}
    if owners - {iid}:
        out.warnings.append(f"former title {other!r} of {iid} names another instrument")
        return None
    return None if owners else full  # owners == {iid}: its own title written differently


def _add_former_titles(out: IndexBuild, vocabulary: set[str]) -> None:
    """Index an Act's former titles as titles of that Act (roadmap decision 17)."""
    claims: dict[str, set[str]] = defaultdict(set)
    accepted: list[tuple[str, str, str]] = []
    for iid, others in sorted(out.former_titles.items()):
        for other in others:
            key = _former_title_key(out, iid, other)
            if key is not None:
                claims[key].add(iid)
                accepted.append((iid, other, key))
    kept: dict[str, list[str]] = defaultdict(list)
    for iid, other, key in accepted:
        if len(claims[key]) > 1:
            continue  # two Acts claim one former title: neither may bind by it
        kept[iid].append(other)
        text, year = split_title_year(_CHAPTER_SUFFIX.sub("", other))
        for variant in title_variants(f"{text} {year}"):
            if iid not in out.titles[variant]:
                out.titles[variant].append(iid)
        new_words = set(title_words(text))
        for word in new_words:
            if iid not in out.words[word]:
                out.words[word].append(iid)
        vocabulary |= new_words
    for iid, titles in kept.items():
        out.instruments[iid]["f"] = sorted(titles)
    log.info("former titles: %d Acts", len(kept))


def _shares_words(cited: Sequence[str], title: str) -> bool:
    """At least half the content words of the shorter title appear in the other."""
    a = {w for w in cited if w not in INSTRUMENT_TYPE_WORDS}
    b = {w for w in title_words(split_title_year(title)[0]) if w not in INSTRUMENT_TYPE_WORDS}
    return bool(a and b) and 2 * len(a & b) >= min(len(a), len(b))


def build_index(
    data_dir: Path,
    *,
    catalogue: Path | None,
    aliases_dir: Path,
    allow_missing_alias_targets: bool = False,
    verify: bool = True,
) -> IndexBuild:
    """Build every table in memory. Raises :class:`BuildError` on any integrity problem."""
    out = IndexBuild()
    wordset_ids: dict[str, set[str]] = defaultdict(set)
    vocabulary: set[str] = set()
    for item in read_records(data_dir, verify=verify):
        _add_instrument(out, item, wordset_ids, vocabulary)
    if not out.instruments:
        raise BuildError(f"no instrument records under {data_dir / 'uk'}")
    out.case_variants = _case_variants(out.coordinates)
    out.wordsets = {k: next(iter(v)) for k, v in wordset_ids.items() if len(v) == 1}
    _add_coverage(out, catalogue, vocabulary)
    _add_former_titles(out, vocabulary)
    _build_aliases(out, read_aliases(aliases_dir), allow_missing=allow_missing_alias_targets)
    vocabulary |= {w for key in out.aliases for w in key.split()}
    for word in sorted(w for w in vocabulary if len(w) >= TYPO_MIN_WORD and w.isalpha()):
        for variant in deletes(word):
            out.typo[variant].append(word)
    return out


def _build_aliases(out: IndexBuild, entries: list[dict[str, Any]], *, allow_missing: bool) -> None:
    by_coordinate = {v["c"]: k for k, v in out.instruments.items()}
    for entry in entries:
        target = str(entry["target"])
        iid = by_coordinate.get(target)
        if iid is None:
            message = f"alias target {target} ({entry['_file']}) is not in the index"
            if not allow_missing:
                raise BuildError(message)
            out.dropped_aliases.append(target)
            out.warnings.append(message)
            continue
        for form in entry["forms"]:
            key = " ".join(title_words(str(form)))
            if not key:
                raise BuildError(f"alias form {form!r} folds to nothing")
            existing = out.aliases.get(key)
            if existing is not None and existing["id"] != iid:
                raise BuildError(f"alias {form!r} names two targets: {existing['id']} and {iid}")
            # Read as a full title (with or without its year), the form must not name some
            # other instrument: at runtime an exact title match wins over an alias. Core-word
            # variants ("civil procedure" for "Civil Procedure Rules") do not count.
            text, year = split_title_year(str(form))
            full = title_words(text)
            full_keys = {title_key(full, year)} if full else set()  # like for like: year or none
            shadowed = sorted({i for k in full_keys for i in out.titles.get(k, []) if i != iid})
            if shadowed:
                raise BuildError(f"alias {form!r} shadows the title of {shadowed}")
            out.aliases[key] = {
                "id": iid,
                "salient": bool(entry.get("salient", False)),
                "form": form,
            }


# ---------------------------------------------------------------------------- output


def _json_bytes(data: Any) -> bytes:
    return (
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()


def _compact(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _joined(values: Iterable[str]) -> str:
    items = sorted(set(values))
    if any("," in v for v in items):
        raise BuildError(f"list value contains a comma: {items}")
    return ",".join(items)


def _coordinate_rows(build: IndexBuild) -> Iterator[tuple[str, str]]:
    """casefolded key → "" (canonical == key), the canonical spelling, or "a|A" variants."""
    by_key: dict[str, set[str]] = defaultdict(set)
    for coordinate in build.coordinates:
        by_key[coordinate.casefold()].add(coordinate)
    for key, spellings in by_key.items():
        if len(spellings) > 1:
            yield key, "|".join(sorted(spellings))
        else:
            (only,) = spellings
            yield key, "" if only == key else only


def serialise(build: IndexBuild) -> dict[str, bytes]:
    """Every index file's bytes (manifest excluded), deterministically."""
    tables: dict[str, Iterable[tuple[str, str]]] = {
        "coordinates": _coordinate_rows(build),
        "instruments": ((k, _compact(v)) for k, v in build.instruments.items()),
        "titles": ((k, _joined(v)) for k, v in build.titles.items()),
        "numbers": ((k, _joined(v)) for k, v in build.numbers.items()),
        "wordsets": build.wordsets.items(),
        "words": ((k, _joined(v)) for k, v in build.words.items()),
        "typo": ((k, _joined(v)) for k, v in build.typo.items()),
        "coverage_instruments": (  # keyed case-insensitively; canonical spelling in "c"
            (k.casefold(), _compact(v)) for k, v in build.coverage.get("instruments", {}).items()
        ),
        "coverage_titles": ((k, _joined(v)) for k, v in build.coverage.get("titles", {}).items()),
        "coverage_numbers": ((k, _joined(v)) for k, v in build.coverage.get("numbers", {}).items()),
        "acronyms": ((k, _joined(v)) for k, v in build.acronyms.items()),
    }
    files: dict[str, bytes] = {}
    for name, rows in tables.items():
        try:
            files[f"{name}.tbl"], files[f"{name}.off"] = encode_table(rows)
        except ValueError as exc:
            raise BuildError(f"table {name}: {exc}") from exc
    files["aliases.json"] = _json_bytes(build.aliases)
    return files


def write_index(
    build: IndexBuild, out_dir: Path, *, snapshot: date, sources: Sequence[str]
) -> dict[str, Any]:
    """Write the files and a manifest carrying each file's SHA-256. Returns the manifest."""
    files = serialise(build)
    if set(files) != set(INDEX_FILES):
        raise BuildError("builder and loader disagree on the index file set")
    manifest: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "grammar_version": GRAMMAR_VERSION,
        "builder": f"legal-rag-router {__version__}",
        "snapshot": snapshot.isoformat(),
        "jurisdictions": ["uk"],
        "sources": list(sources),
        "partial": bool(build.dropped_aliases),
        "dropped_alias_targets": sorted(set(build.dropped_aliases)),
        "coverage_series": build.coverage.get("series", []),
        "counts": {
            "coordinates": len(set(build.coordinates)),
            "instruments": len(build.instruments),
            "instruments_metadata_only": sum(
                1 for v in build.instruments.values() if v["st"] == "metadata_only"
            ),
            "title_keys": len(build.titles),
            "aliases": len(build.aliases),
            "coverage_instruments": len(build.coverage.get("instruments", {})),
            "case_variant_keys": len(build.case_variants),
            "typo_variants": len(build.typo),
        },
        "freshness": {
            s: {
                "complete_through": snapshot.isoformat(),
                "max_number_by_year": dict(sorted(y.items())),
            }
            for s, y in sorted(build.freshness.items())
        },
        "files": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for name, data in sorted(files.items())
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.iterdir():  # never leave files from an older format behind
        if stale.is_file() and stale.name not in files and stale.name != MANIFEST_NAME:
            stale.unlink()
    for name, data in files.items():
        tmp = out_dir / f".{name}.tmp"
        tmp.write_bytes(data)
        tmp.replace(out_dir / name)
    (out_dir / MANIFEST_NAME).write_bytes(_json_bytes(manifest))
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the router index.")
    parser.add_argument("--data", type=Path, required=True, help="data root with uk/ records")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--snapshot", type=date.fromisoformat, required=True)
    parser.add_argument("--catalogue", type=Path, default=None)
    parser.add_argument("--aliases", type=Path, default=Path("aliases"))
    parser.add_argument("--source", action="append", default=None)
    parser.add_argument("--allow-missing-alias-targets", action="store_true")
    parser.add_argument("--no-verify", action="store_true", help="skip record checksums")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    started = time.monotonic()
    try:
        build = build_index(
            args.data,
            catalogue=args.catalogue,
            aliases_dir=args.aliases,
            allow_missing_alias_targets=args.allow_missing_alias_targets,
            verify=not args.no_verify,
        )
    except BuildError as exc:
        log.error("index build failed: %s", exc)  # noqa: TRY400 - expected; no traceback
        return 1
    for warning in build.warnings:
        log.warning("%s", warning)
    manifest = write_index(
        build, args.out, snapshot=args.snapshot, sources=args.source or ["legislation.gov.uk"]
    )
    log.info(
        "built %s in %.1fs: %s",
        args.out,
        time.monotonic() - started,
        json.dumps(manifest["counts"]),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
