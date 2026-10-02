"""The router index: plain data files, verified on load, memory-mapped, immutable.

The index is a release asset that third parties download, so it is stored as data, never
as a pickle, and every file is checked against the SHA-256 in ``index-manifest.json``
before use. Loading refuses a manifest with an unknown format version.

Large tables are memory-mapped :class:`~legal_rag_router.table.SortedTable` files (roadmap
decision Q-M6-1): load time does not grow with the index and memory is only the pages
touched. Format version 1:

=========================  ================================================================
``coordinates``            casefolded coordinate → canonical spelling(s) (``|``-joined when
                           siblings differ only by case, roadmap decision 7)
``instruments``            instrument_id → JSON metadata (title, year, series, structure,
                           former titles …)
``titles``                 title key → instrument_ids (several key variants per title)
``numbers``                official-number key (``si/2011/3006``, ``c/1996/18``) → ids
``wordsets``               sorted content words|year → instrument_id (unique sets only)
``words``                  content word → instrument_ids (ranking suggestions)
``typo``                   symmetric-delete variant → title vocabulary words
``coverage_instruments``   casefolded out-of-coverage coordinate → JSON (canonical, title …)
``coverage_titles``        title key → out-of-coverage coordinates
``coverage_numbers``       official-number key → out-of-coverage coordinates
``acronyms``               generated Act acronym + year ``tcga|1992`` → instrument_ids
                           (roadmap decision 18; curated aliases take precedence)
``aliases.json``           alias key → {id, salient, form} (small; plain JSON)
=========================  ================================================================

List values are comma-joined (ids, words and coordinates never contain commas).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from legal_rag_router.table import SortedTable

__all__ = [
    "FORMAT_VERSION",
    "INDEX_FILES",
    "JSON_FILES",
    "MANIFEST_NAME",
    "TABLES",
    "CoordinateIndex",
    "IndexLoadError",
    "InstrumentInfo",
    "RouterIndex",
    "load_index",
    "split_list",
]

FORMAT_VERSION: Final = 1
MANIFEST_NAME: Final = "index-manifest.json"
TABLES: Final = (
    "coordinates",
    "instruments",
    "titles",
    "numbers",
    "wordsets",
    "words",
    "typo",
    "coverage_instruments",
    "coverage_titles",
    "coverage_numbers",
    "acronyms",
)
JSON_FILES: Final = ("aliases.json",)
INDEX_FILES: Final = (*(f"{t}.{ext}" for t in TABLES for ext in ("tbl", "off")), *JSON_FILES)


class IndexLoadError(RuntimeError):
    """Raised when an index cannot be loaded: missing file, bad hash, unknown format."""


def split_list(value: str | None) -> tuple[str, ...]:
    """Decode a comma-joined table value."""
    return tuple(value.split(",")) if value else ()


class CoordinateIndex:
    """Exact existence and prefix lookups over the sorted coordinate table.

    Lookups are case-insensitive; :meth:`spellings` returns the canonical spelling(s).
    ``descendants`` uses a ``/`` boundary so ``s124`` never matches ``s124A``.
    """

    __slots__ = ("_table",)

    def __init__(self, table: SortedTable) -> None:
        self._table = table

    def __len__(self) -> int:
        return len(self._table)

    def __contains__(self, coordinate: object) -> bool:
        return isinstance(coordinate, str) and self._table.get(coordinate.casefold()) is not None

    @staticmethod
    def _decode(key: str, value: str) -> tuple[str, ...]:
        return tuple(value.split("|")) if value else (key,)

    def spellings(self, coordinate: str) -> tuple[str, ...]:
        """Every canonical spelling for ``coordinate`` (case-insensitive); ``()`` if absent.

        More than one spelling means siblings differ only by case (``…/a`` and ``…/A``).
        """
        key = coordinate.casefold()
        value = self._table.get(key)
        return () if value is None else self._decode(key, value)

    def canonical(self, coordinate: str) -> str | None:
        """The canonical spelling, or ``None`` if absent or ambiguous by case alone.

        An exact-case match always wins (decision 7: bind only on an exact-case match).
        """
        spellings = self.spellings(coordinate)
        if coordinate in spellings:
            return coordinate
        return spellings[0] if len(spellings) == 1 else None

    def descendants(self, coordinate: str) -> Iterator[str]:
        """Every coordinate strictly beneath ``coordinate``, canonical, in key order."""
        for key, value in self._table.prefix(coordinate.casefold() + "/"):
            yield from self._decode(key, value)

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
    former_titles: tuple[str, ...] = ()
    """Titles the instrument had before a rename (roadmap decision 17)."""

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
            former_titles=tuple(raw.get("f", ())),
        )


@dataclass(frozen=True, slots=True)
class RouterIndex:
    """Everything the router looks up. Immutable; safe to share between threads."""

    manifest: Mapping[str, Any]
    coordinates: CoordinateIndex
    tables: Mapping[str, SortedTable]
    aliases: Mapping[str, Mapping[str, Any]]

    @property
    def snapshot(self) -> str:
        """Date the index is complete through ("not in the statute book as of …")."""
        return str(self.manifest["snapshot"])

    def instrument(self, instrument_id: str) -> InstrumentInfo | None:
        """The instrument with this id (``uk_ukpga_1996_18``), or ``None`` if it is not indexed."""
        raw = self.tables["instruments"].get(instrument_id)
        return None if raw is None else InstrumentInfo.from_json(instrument_id, json.loads(raw))

    def info(self, instrument_id: str) -> InstrumentInfo:
        """:meth:`instrument` for an id taken from the index's own tables.

        The build keeps every table consistent with ``instruments``, so a miss means the
        index is corrupt: it raises, and ``Router.route`` fails safe to ``ROUTE_UNRESOLVED``.
        """
        found = self.instrument(instrument_id)
        if found is None:
            raise IndexLoadError(f"index inconsistent: no instrument {instrument_id!r}")
        return found

    def ids(self, table: str, key: str) -> tuple[str, ...]:
        """Decode a comma-joined list value (titles, numbers, words, typo, coverage …)."""
        return split_list(self.tables[table].get(key))

    def coverage(self, coordinate: str) -> Mapping[str, Any] | None:
        """Out-of-coverage instrument metadata (case-insensitive), or ``None``."""
        raw = self.tables["coverage_instruments"].get(coordinate.casefold())
        return None if raw is None else json.loads(raw)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(root: Path, manifest: Mapping[str, Any]) -> None:
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise IndexLoadError(f"{MANIFEST_NAME} lists no files")
    for name in INDEX_FILES:
        entry = files.get(name)
        if not isinstance(entry, Mapping) or "sha256" not in entry:
            raise IndexLoadError(f"{MANIFEST_NAME} has no hash for {name}")
        path = root / name
        if not path.is_file():
            raise IndexLoadError(f"missing index file {name}")
        if _sha256(path) != entry["sha256"]:
            raise IndexLoadError(f"hash mismatch for {name}: the index is corrupt or was modified")


def load_index(directory: str | Path) -> RouterIndex:
    """Load, verify and map an index directory.

    Raises:
        IndexLoadError: if the manifest is missing or has an unsupported format version,
            or any file is missing or does not match its SHA-256.
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
    _verify(root, manifest)
    tables = {t: SortedTable.open(root / f"{t}.tbl", root / f"{t}.off") for t in TABLES}
    try:
        aliases = json.loads((root / "aliases.json").read_text(encoding="utf-8"))
    except ValueError as exc:
        raise IndexLoadError("aliases.json is not valid JSON") from exc
    return RouterIndex(
        manifest=manifest,
        coordinates=CoordinateIndex(tables["coordinates"]),
        tables=tables,
        aliases=aliases,
    )
