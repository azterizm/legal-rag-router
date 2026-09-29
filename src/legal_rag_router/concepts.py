"""The concept index (roadmap stage D, docs/discovery.md): what ``discover()`` searches.

A separate directory from the router index (``data/concepts/``), with its own manifest and
SHA-256 check. One *document* per section-level provision (sections, regulations, articles,
rules, schedules and schedule paragraphs) and one per instrument. Each document has five
fields, kept apart so the ranker can weight them (BM25F):

==============  ==========================================================================
``heading``     the provision's own heading ("Limit of compensatory award etc.")
``crossheading`` the cross-heading above it ("Compensation")
``structure``   the titles of the Parts and Chapters holding it ("Unfair dismissal")
``title``       the instrument's title and long title
``body``        the provision's text with its subdivisions, first :data:`BODY_TERMS` terms
==============  ==========================================================================

Files:

``terms.tbl/.off``   term → ``start,count`` into the postings arrays (a sorted table)
``postings.doc``     uint32 document ids, ascending within each term
``postings.tf``      uint32 per posting: the term's count in each field, 6 bits a field
``docs.tbl/.off``    ``{doc id:08d}`` → JSON ``{"c": coordinate, "h": heading, "k": kind}``
``lengths.bin``      uint16 x fields per document: each field's length in terms
``concepts-manifest.json``  format, fields, counts, average lengths, SHA-256 of each file

Terms come from :func:`terms`: NFKC, casefold, letters and digits, stop words dropped, and a
light suffix stemmer (``compensation`` and ``compensatory`` both give ``compens``). The
same function reads the documents at build time and the query at search time.
"""

from __future__ import annotations

import hashlib
import json
import mmap
import re
import sys
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from legal_rag_router.table import SortedTable

__all__ = [
    "BODY_TERMS",
    "CONCEPTS_FORMAT_VERSION",
    "CONCEPTS_MANIFEST",
    "CONCEPT_FILES",
    "FIELDS",
    "ConceptDoc",
    "ConceptIndex",
    "ConceptIndexError",
    "load_concepts",
    "pack_tf",
    "stem",
    "terms",
    "unpack_tf",
]

CONCEPTS_FORMAT_VERSION: Final = 1
CONCEPTS_MANIFEST: Final = "concepts-manifest.json"
FIELDS: Final = ("heading", "crossheading", "structure", "title", "body")
BODY_TERMS: Final = 200
"""Terms of provision text indexed per document: the opening, where the rule is stated."""
_TF_BITS: Final = 6
_TF_MAX: Final = (1 << _TF_BITS) - 1
CONCEPT_FILES: Final = (
    "terms.tbl",
    "terms.off",
    "postings.doc",
    "postings.tf",
    "docs.tbl",
    "docs.off",
    "lengths.bin",
)

_STOP: Final = frozenset(
    "a an and any are as at be been being but by can for from has have if in into is it its "  # noqa: SIM905
    "may must not of on or shall should such than that the their them then there these they "
    "this those to under upon was were what when where which who whom why will with would "
    "does do did how".split()
)
_SUFFIXES: Final = (
    "ational", "ations", "ation", "atory", "ments", "ment", "ions", "ion", "ings", "ing",
    "ies", "ied", "ed", "es", "ory", "ive", "s", "y",
)  # fmt: skip
_WORD_RE: Final = re.compile(r"[a-z0-9]+")


class ConceptIndexError(RuntimeError):
    """The concept index is missing, of another format, or does not match its manifest."""


def stem(word: str) -> str:
    """A light suffix stemmer: the first listed suffix that leaves at least four letters."""
    if word.isdigit():
        return word
    for suffix in _SUFFIXES:
        if len(word) - len(suffix) >= 4 and word.endswith(suffix):  # noqa: PLR2004
            return word[: -len(suffix)]
    return word


def terms(text: str) -> list[str]:
    """Index terms of ``text``, in order (duplicates kept, for term counts)."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return [stem(w) for w in _WORD_RE.findall(folded) if w not in _STOP]


def pack_tf(counts: tuple[int, ...]) -> int:
    """Per-field term counts in one uint32, 6 bits each (a count above 63 is capped)."""
    packed = 0
    for i, count in enumerate(counts):
        packed |= min(count, _TF_MAX) << (_TF_BITS * i)
    return packed


def unpack_tf(packed: int) -> tuple[int, ...]:
    return tuple((packed >> (_TF_BITS * i)) & _TF_MAX for i in range(len(FIELDS)))


@dataclass(frozen=True, slots=True)
class ConceptDoc:
    """A document: a provision (``kind`` ``p``) or a whole instrument (``i``)."""

    doc_id: int
    coordinate: str
    heading: str | None
    kind: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _map_uint(path: Path, typecode: Literal["I", "H"]) -> memoryview:
    if path.stat().st_size == 0:
        return memoryview(b"").cast(typecode)
    with path.open("rb") as fh:
        mapped = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
    return memoryview(mapped).cast(typecode)


@dataclass(frozen=True, slots=True)
class ConceptIndex:
    """A loaded concept index. Immutable; safe to share between threads."""

    manifest: Mapping[str, Any]
    term_table: SortedTable
    doc_table: SortedTable
    doc_ids: memoryview
    tfs: memoryview
    lengths: memoryview

    @property
    def doc_count(self) -> int:
        return int(self.manifest["counts"]["docs"])

    @property
    def average_lengths(self) -> tuple[float, ...]:
        return tuple(float(x) for x in self.manifest["average_lengths"])

    def postings(self, term: str) -> tuple[memoryview, memoryview]:
        """The documents holding ``term`` and its packed per-field counts in each."""
        raw = self.term_table.get(term)
        if raw is None:
            empty = memoryview(b"").cast("I")
            return empty, empty
        start, count = (int(x) for x in raw.split(","))
        return self.doc_ids[start : start + count], self.tfs[start : start + count]

    def document_frequency(self, term: str) -> int:
        raw = self.term_table.get(term)
        return 0 if raw is None else int(raw.split(",")[1])

    def field_lengths(self, doc_id: int) -> tuple[int, ...]:
        width = len(FIELDS)
        return tuple(self.lengths[doc_id * width : (doc_id + 1) * width])

    def doc(self, doc_id: int) -> ConceptDoc:
        raw = self.doc_table.get(f"{doc_id:08d}")
        if raw is None:
            raise ConceptIndexError(f"concept index inconsistent: no document {doc_id}")
        value = json.loads(raw)
        return ConceptDoc(doc_id, value["c"], value.get("h"), value["k"])


def load_concepts(directory: str | Path) -> ConceptIndex:
    """Load, verify and map a concept index directory.

    Raises:
        ConceptIndexError: if the manifest is missing or of another format version, or any
            file is missing or does not match its SHA-256.
    """
    root = Path(directory)
    try:
        manifest = json.loads((root / CONCEPTS_MANIFEST).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConceptIndexError(f"no {CONCEPTS_MANIFEST} in {root}") from None
    except ValueError as exc:
        raise ConceptIndexError(f"{CONCEPTS_MANIFEST} is not valid JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("format_version") != CONCEPTS_FORMAT_VERSION:
        raise ConceptIndexError(f"unsupported concept index format in {root}")
    if tuple(manifest.get("fields", ())) != FIELDS:
        raise ConceptIndexError(f"concept index fields {manifest.get('fields')} are not {FIELDS}")
    files = manifest.get("files", {})
    for name in CONCEPT_FILES:
        path = root / name
        expected = files.get(name, {}).get("sha256") if isinstance(files, Mapping) else None
        if not path.is_file() or expected is None:
            raise ConceptIndexError(f"missing concept index file {name}")
        if _sha256(path) != expected:
            raise ConceptIndexError(f"hash mismatch for {name}: the concept index was modified")
    if sys.byteorder != "little":  # pragma: no cover - the files are little-endian
        raise ConceptIndexError("the concept index needs a little-endian machine")
    return ConceptIndex(
        manifest=manifest,
        term_table=SortedTable.open(root / "terms.tbl", root / "terms.off"),
        doc_table=SortedTable.open(root / "docs.tbl", root / "docs.off"),
        doc_ids=_map_uint(root / "postings.doc", "I"),
        tfs=_map_uint(root / "postings.tf", "I"),
        lengths=_map_uint(root / "lengths.bin", "H"),
    )
