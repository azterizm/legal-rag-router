"""The router index: plain data files, verified on load, held immutable in memory.

The index is a release asset that third parties download, so it is stored as data (a
sorted, gzipped coordinate list plus JSON tables), never as a pickle, and every file is
checked against the SHA-256 in ``index-manifest.json`` before use. Loading refuses a
manifest with an unknown format version.

Files (format version 1):

``coordinates.txt.gz``   every indexed coordinate, one per line, sorted by casefolded key
``instruments.json``     instrument_id → metadata (title, year, series, repealed, structure …)
``titles.json``          title key → instrument_ids (several key variants per title)
``aliases.json``         alias key → {id, salient}
``numbers.json``         official-number key (``si/2011/3006``, ``c/1996/18`` …) → instrument_ids
``wordsets.json``        sorted content words|year → instrument_id (unique word sets only)
``words.json``           content word → instrument_ids (for ranking suggestions)
``typo.json``            symmetric-delete variant → title vocabulary words
``coverage.json``        instruments known to exist but not indexed (out of coverage)
``case_variants.json``   casefolded key → the canonical coordinates that share it

Queries never touch the disk: everything is loaded once; routing is lock-free and
thread-safe because nothing is mutated after :func:`load_index` returns.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from bisect import bisect_left
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from legal_rag_router.coordinate import Coordinate

__all__ = [
    "FORMAT_VERSION",
    "INDEX_FILES",
    "MANIFEST_NAME",
    "CoordinateIndex",
    "IndexLoadError",
    "InstrumentInfo",
    "RouterIndex",
    "load_index",
]

FORMAT_VERSION: Final = 1
MANIFEST_NAME: Final = "index-manifest.json"
INDEX_FILES: Final = (
    "coordinates.txt.gz",
    "instruments.json",
    "titles.json",
    "aliases.json",
    "numbers.json",
    "wordsets.json",
    "words.json",
    "typo.json",
    "coverage.json",
    "case_variants.json",
)
_MAX_FILE_BYTES: Final = 2 << 30


class IndexLoadError(RuntimeError):
    """Raised when an index cannot be loaded: missing file, bad hash, unknown format."""


class CoordinateIndex:
    """Exact existence and prefix lookups over an immutable, sorted coordinate list.

    Lookups are by casefolded key; :meth:`canonical` returns the stored spelling.
    ``descendants`` uses a ``/`` boundary so ``s124`` never matches ``s124A``.
    """

    __slots__ = ("_canonical", "_exists", "_sorted")

    def __init__(self, coordinates: list[str]) -> None:
        keys = [c.casefold() for c in coordinates]
        self._sorted: list[str] = sorted(set(keys))
        self._exists: frozenset[str] = frozenset(self._sorted)
        # Only store canonical spellings that differ from their key (source case: "1ZA").
        self._canonical: dict[str, str] = {
            k: c for k, c in zip(keys, coordinates, strict=True) if k != c
        }

    def __len__(self) -> int:
        return len(self._sorted)

    def __contains__(self, coordinate: object) -> bool:
        if isinstance(coordinate, Coordinate):
            return coordinate.key in self._exists
        return isinstance(coordinate, str) and coordinate.casefold() in self._exists

    def canonical(self, coordinate: str) -> str | None:
        """The stored spelling of ``coordinate`` (any case), or ``None`` if absent."""
        key = coordinate.casefold()
        if key not in self._exists:
            return None
        return self._canonical.get(key, key)

    def descendants(self, coordinate: str) -> Iterator[str]:
        """Every coordinate strictly beneath ``coordinate``, canonical, in key order."""
        prefix = coordinate.casefold() + "/"
        i = bisect_left(self._sorted, prefix)
        while i < len(self._sorted) and self._sorted[i].startswith(prefix):
            key = self._sorted[i]
            yield self._canonical.get(key, key)
            i += 1

    def children(self, coordinate: str) -> Iterator[str]:
        """Direct children of ``coordinate``."""
        depth = coordinate.count("/") + 1
        return (c for c in self.descendants(coordinate) if c.count("/") == depth)


@dataclass(frozen=True, slots=True)
class InstrumentInfo:
    """What the router needs to know about one indexed instrument."""

    instrument_id: str
    coordinate: str
    title: str
    year: int
    number: int
    series: str
    repealed: bool
    structure: str  # "full" | "metadata_only"
    primary: bool
    groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    duplicated: frozenset[str] = frozenset()

    @classmethod
    def from_json(cls, instrument_id: str, raw: Mapping[str, Any]) -> InstrumentInfo:
        return cls(
            instrument_id=instrument_id,
            coordinate=str(raw["c"]),
            title=str(raw["t"]),
            year=int(raw["y"]),
            number=int(raw["n"]),
            series=str(raw["s"]),
            repealed=bool(raw.get("r", False)),
            structure=str(raw.get("st", "full")),
            primary=bool(raw.get("p", False)),
            groups={k: tuple(v) for k, v in raw.get("g", {}).items()},
            duplicated=frozenset(raw.get("d", ())),
        )


@dataclass(frozen=True, slots=True)
class RouterIndex:
    """Everything the router looks up, loaded once and never mutated."""

    manifest: Mapping[str, Any]
    coordinates: CoordinateIndex
    instruments: Mapping[str, InstrumentInfo]
    titles: Mapping[str, tuple[str, ...]]
    aliases: Mapping[str, Mapping[str, Any]]
    numbers: Mapping[str, tuple[str, ...]]
    wordsets: Mapping[str, str]
    words: Mapping[str, tuple[str, ...]]
    typo: Mapping[str, tuple[str, ...]]
    coverage: Mapping[str, Any]
    case_variants: Mapping[str, tuple[str, ...]]

    @property
    def snapshot(self) -> str:
        """Date the index is complete through ("not in the statute book as of …")."""
        return str(self.manifest["snapshot"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_verified(directory: Path, name: str, expected: Mapping[str, Any]) -> bytes:
    entry = expected.get(name)
    if not isinstance(entry, Mapping) or "sha256" not in entry:
        raise IndexLoadError(f"{MANIFEST_NAME} has no hash for {name}")
    path = directory / name
    if not path.is_file():
        raise IndexLoadError(f"missing index file {name}")
    if path.stat().st_size > _MAX_FILE_BYTES:
        raise IndexLoadError(f"index file {name} is implausibly large")
    if _sha256(path) != entry["sha256"]:
        raise IndexLoadError(f"hash mismatch for {name}: the index is corrupt or was modified")
    return path.read_bytes()


def _json(data: bytes, name: str) -> Any:
    try:
        return json.loads(data)
    except ValueError as exc:
        raise IndexLoadError(f"{name} is not valid JSON") from exc


def load_index(directory: str | Path) -> RouterIndex:
    """Load and verify an index directory.

    Raises:
        IndexLoadError: if the manifest is missing or has an unsupported format version, or
            any file is missing or does not match its SHA-256.
    """
    root = Path(directory)
    try:
        manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise IndexLoadError(f"no {MANIFEST_NAME} in {root}") from None
    except ValueError as exc:
        raise IndexLoadError(f"{MANIFEST_NAME} is not valid JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("format_version") != FORMAT_VERSION:
        found = manifest.get("format_version") if isinstance(manifest, dict) else None
        raise IndexLoadError(
            f"unsupported index format version {found!r}; this router reads {FORMAT_VERSION}"
        )
    files = manifest.get("files", {})
    raw = {name: _read_verified(root, name, files) for name in INDEX_FILES}

    coordinates = gzip.decompress(raw["coordinates.txt.gz"]).decode("utf-8").split("\n")
    instruments_raw = _json(raw["instruments.json"], "instruments.json")
    return RouterIndex(
        manifest=manifest,
        coordinates=CoordinateIndex([c for c in coordinates if c]),
        instruments={k: InstrumentInfo.from_json(k, v) for k, v in instruments_raw.items()},
        titles={k: tuple(v) for k, v in _json(raw["titles.json"], "titles.json").items()},
        aliases=_json(raw["aliases.json"], "aliases.json"),
        numbers={k: tuple(v) for k, v in _json(raw["numbers.json"], "numbers.json").items()},
        wordsets=_json(raw["wordsets.json"], "wordsets.json"),
        words={k: tuple(v) for k, v in _json(raw["words.json"], "words.json").items()},
        typo={k: tuple(v) for k, v in _json(raw["typo.json"], "typo.json").items()},
        coverage=_json(raw["coverage.json"], "coverage.json"),
        case_variants={
            k: tuple(v) for k, v in _json(raw["case_variants.json"], "case_variants.json").items()
        },
    )
