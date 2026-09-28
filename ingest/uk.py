"""UK ingest: legislation.gov.uk CLML XML → normalised records and harvested citations.

Reads the raw cache in ``uk_scrap_data/raw_xml/{series}/{year}/{n}.xml.gz`` (git-ignored,
never published) and writes one JSONL file per instrument under ``data/uk/`` (see
``ingest/records.py``) plus ``data/harvest/uk_citations.jsonl``.

Identity always comes from the document's own ``IdURI``, never from the file path: the
scraper keyed pre-1963 Acts on calendar year and chapter, which is not unique (roadmap U2),
and some files under ``uksi/`` are canonically ``wsi``/``nisi`` (U6).

Usage::

    uv run python -m ingest.uk --source uk_scrap_data --data data
    uv run python -m ingest.uk --source uk_scrap_data --data /tmp/fixture \\
        --only uk_ukpga_1996_18 uk_ukpga_2006_46
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import os
import re
import sys
import time
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Final
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeET

from ingest.records import (
    AlternativeNumber,
    HarvestedCitation,
    InstrumentRecord,
    ProvisionRecord,
    canonical_json,
    write_instrument_file,
)
from legal_rag_router.coordinate import Coordinate, CoordinateError
from legal_rag_router.grammars.uk import (
    SCHEME,
    legislation_path,
    provision_from_legislation_tokens,
)
from legal_rag_router.normalise import title_words

__all__ = [
    "IngestError",
    "ParsedInstrument",
    "clean_title",
    "coordinate_from_uri",
    "main",
    "other_titles",
    "parse_clml",
]

log = logging.getLogger("ingest.uk")

LEG: Final = "{http://www.legislation.gov.uk/namespaces/legislation}"
UKM: Final = "{http://www.legislation.gov.uk/namespaces/metadata}"
DC: Final = "{http://purl.org/dc/elements/1.1/}"
DCT: Final = "{http://purl.org/dc/terms/}"

SITE: Final = "https://www.legislation.gov.uk/"
_ID_URI: Final = re.compile(r"^https?://www\.legislation\.gov\.uk/(?:id/)?(?P<path>[^?#]+?)/?$")
_REPEAL_SUFFIX: Final = re.compile(r"\s*\((?:repealed|revoked)\b[^()]*\)\s*$", re.IGNORECASE)
_WS: Final = re.compile(r"\s+")
_HEAD_ID_URI: Final = re.compile(rb'IdURI="https?://www\.legislation\.gov\.uk/id/([^"]+)"')

LICENCE: Final = "OGL-3.0"
DOMAIN: Final = "uk_legislation"

# Subtrees that never contain provisions of this instrument.
_SKIP: Final = frozenset({f"{UKM}Metadata", f"{LEG}Contents", f"{LEG}Resources"})
# Editorial apparatus: not part of a provision's text.
_EDITORIAL: Final = frozenset(
    {
        f"{LEG}{t}"
        for t in (
            "Commentaries",
            "Commentary",
            "CommentaryRef",
            "Footnotes",
            "Footnote",
            "FootnoteRef",
            "MarginNotes",
            "MarginNoteRef",
            "Resources",
        )
    }
)
# Headings and numbers are stored in their own fields, not in ``text``.
_LABELS: Final = frozenset({f"{LEG}Pnumber", f"{LEG}Number", f"{LEG}Title", f"{LEG}TitleBlock"})
_BLOCK_AMENDMENT: Final = f"{LEG}BlockAmendment"
_VERSIONS: Final = f"{LEG}Versions"
_VERSION: Final = f"{LEG}Version"
_COMMENTARIES: Final = f"{LEG}Commentaries"
_CITATION: Final = f"{LEG}Citation"
_SUBREF: Final = f"{LEG}CitationSubRef"
_CONTEXT_TAGS: Final = frozenset({f"{LEG}Text", f"{LEG}Title", f"{LEG}Para", f"{LEG}Entry"})
_GROUP_PREFIXES: Final = ("pt", "ch", "grp", "app")
# Only structural elements can be provisions. Others carry an IdURI too — notably
# ``InternalLink``, whose IdURI is the *target* of an in-text cross-reference.
_STRUCTURAL: Final = frozenset(
    f"{LEG}{t}"
    for t in (
        "P1",
        "P2",
        "P3",
        "P4",
        "P5",
        "P6",
        "P7",
        "P",
        "Pblock",
        "PsubBlock",
        "Part",
        "Chapter",
        "Schedule",
        "Group",
        "Appendix",
    )
)


class IngestError(ValueError):
    """Raised when a document cannot be ingested at all."""


@dataclass(slots=True)
class ParsedInstrument:
    instrument: InstrumentRecord
    provisions: list[ProvisionRecord]
    citations: list[HarvestedCitation]
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------- helpers


def _clean(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _uri_path(uri: str | None) -> str | None:
    if not uri:
        return None
    match = _ID_URI.match(uri.strip())
    return match.group("path") if match else None


_VIEW_SUFFIXES: Final = frozenset(
    {"contents", "enacted", "made", "created", "adopted", "data.xml"}
    | {"england", "wales", "scotland", "ni", "england+wales"}
)
_DATE_SEGMENT: Final = re.compile(r"\d{4}-\d{2}-\d{2}")


def _split_instrument(parts: tuple[str, ...]) -> tuple[Coordinate, list[str]] | None:
    arity = SCHEME.instrument_arity(parts)
    if arity is None or arity > len(parts):
        return None
    try:
        return Coordinate.of("uk", parts[:arity]), list(parts[arity:])
    except CoordinateError:
        return None


def coordinate_from_uri(uri: str | None) -> Coordinate | None:
    """Map a legislation.gov.uk URI (``/id/`` or document form) to a coordinate, if it is one.

    View suffixes (``/contents``, ``/enacted``, ``/made``, point-in-time dates, extents,
    ``data.xml``) are dropped. An unmapped provision path yields ``None``.
    """
    path = _uri_path(uri)
    split = _split_instrument(tuple(p for p in path.split("/") if p)) if path else None
    if split is None:
        return None
    instrument, rest = split
    while rest and (rest[-1] in _VIEW_SUFFIXES or _DATE_SEGMENT.fullmatch(rest[-1])):
        rest.pop()
    if not rest:
        return instrument
    provision = provision_from_legislation_tokens(rest)
    try:
        return instrument.child(*provision) if provision is not None else None
    except CoordinateError:
        return None


def clean_title(published: str) -> tuple[str, bool]:
    """Strip legislation.gov.uk's "(repealed …)" / "(revoked …)" suffix.

    Returns ``(title, repealed)``; the suffix is how the source marks a whole instrument
    as no longer in force.
    """
    title = _REPEAL_SUFFIX.sub("", published).strip()
    return (title or published.strip()), _REPEAL_SUFFIX.search(published) is not None


def other_titles(metadata: Element, instrument: Coordinate, title: str) -> tuple[str, ...]:
    """Titles the effects list gives this instrument besides its own (decision 17).

    Each ``ukm:UnappliedEffect`` / ``ukm:Effect`` names the affected instrument by every
    title it has had ("Senior Courts Act 1981", "Supreme Court Act 1981"). Only effects on
    this instrument count; the result is sorted and excludes the current title.
    """
    own = title_words(title)
    found: set[str] = set()
    for tag in ("UnappliedEffect", "Effect"):
        for effect in metadata.iter(f"{UKM}{tag}"):
            if coordinate_from_uri(effect.get("AffectedURI")) != instrument:
                continue
            for node in effect.findall(f"{UKM}AffectedTitle"):
                text = _text_of(node)
                if text and title_words(clean_title(text)[0]) != own:
                    found.add(clean_title(text)[0])
    return tuple(sorted(found))


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _text_of(element: Element | None) -> str | None:
    if element is None:
        return None
    text = _clean("".join(element.itertext()))
    return text or None


# ---------------------------------------------------------------------------- parser


@dataclass(slots=True)
class _TextSink:
    before: list[str] = field(default_factory=list)
    after: list[str] = field(default_factory=list)
    split: bool = False

    def add(self, text: str) -> None:
        (self.after if self.split else self.before).append(text)


class _Parser:
    """One pass over a CLML document. Not reusable across documents."""

    def __init__(self, root: Element, instrument: Coordinate) -> None:
        self.root = root
        self.instrument = instrument
        self.instrument_prefix = "/".join(instrument.instrument) + "/"
        self.provisions: list[ProvisionRecord] = []
        self.citations: list[HarvestedCitation] = []
        self.warnings: list[str] = []
        self.seen: set[str] = set()
        self.seen_keys: dict[str, str] = {}
        self.groups: dict[str, list[str]] = {}
        self.group_members: dict[str, set[str]] = {}
        self.alternative_versions = 0
        self.duplicated: dict[str, None] = {}  # ordered set
        self._provision_cache: dict[int, Coordinate | None] = {}

    # --- provision identity

    def provision_of(self, element: Element) -> Coordinate | None:
        key = id(element)
        if key in self._provision_cache:
            return self._provision_cache[key]
        coordinate = self._compute_provision(element)
        self._provision_cache[id(element)] = coordinate
        return coordinate

    def _compute_provision(self, element: Element) -> Coordinate | None:
        if element.tag not in _STRUCTURAL:
            return None
        tokens: list[str] | None = None
        path = _uri_path(element.get("IdURI"))
        if path is not None:
            if not path.startswith(self.instrument_prefix):
                return None
            tokens = path[len(self.instrument_prefix) :].split("/")
        elif element.get("id"):
            tokens = element.get("id", "").split("-")
        if not tokens or "crossheading" in tokens:
            return None
        provision = provision_from_legislation_tokens(tokens)
        if provision is None:
            return None
        try:
            return self.instrument.child(*provision)
        except CoordinateError:
            return None

    # --- text

    def own_text(self, element: Element) -> tuple[str, str]:
        """``element``'s own text, split at its child provisions.

        Returns ``(before, after)``: the words before the first child provision (the
        lead-in) and after it (closing words such as "…shall not exceed the amount").
        The full text is ``before`` + the children's full texts + ``after``.
        """
        sink = _TextSink()
        self._collect(element, sink, strip_labels=True)
        return _clean("".join(sink.before)), _clean("".join(sink.after))

    def _collect(self, element: Element, sink: _TextSink, *, strip_labels: bool) -> None:
        """Add ``element``'s text to ``sink``, skipping child provisions (they have their
        own records; the first one moves ``sink`` to its closing half), editorial
        apparatus, and — outside quoted amendments — headings and numbers (kept in
        ``title`` / ``number_label``)."""
        if element.text:
            sink.add(element.text)
        for child in element:
            quoted = child.tag == _BLOCK_AMENDMENT
            is_provision = strip_labels and not quoted and self.provision_of(child) is not None
            if is_provision:
                sink.split = True
            elif child.tag not in _EDITORIAL and not (strip_labels and child.tag in _LABELS):
                self._collect(child, sink, strip_labels=strip_labels and not quoted)
            if child.tail:
                sink.add(child.tail)

    # --- walk

    def walk(self) -> None:
        self._walk(self.root, self.instrument, status=None, groups=(), heading=None, context=None)
        commentaries = self.root.find(f".//{_COMMENTARIES}")
        if commentaries is not None:
            self._harvest_all(commentaries, self.instrument, None, in_commentary=True)

    def _harvest_all(
        self,
        element: Element,
        source: Coordinate,
        context: Element | None,
        *,
        in_commentary: bool = False,
        in_amendment: bool = False,
    ) -> None:
        """Harvest every citation under ``element`` (no provisions are emitted here)."""
        if element.tag in _CONTEXT_TAGS:
            context = element
        if element.tag in (_CITATION, _SUBREF):
            self._harvest(
                element, source, context, in_commentary=in_commentary, in_amendment=in_amendment
            )
        for child in element:
            self._harvest_all(
                child, source, context, in_commentary=in_commentary, in_amendment=in_amendment
            )

    def _walk(
        self,
        element: Element,
        enclosing: Coordinate,
        *,
        status: str | None,
        groups: tuple[str, ...],
        heading: str | None,
        context: Element | None,
    ) -> None:
        if element.tag in _SKIP or element.tag == _COMMENTARIES:
            return
        if element.tag == _VERSIONS:  # alternative extent texts; the main text is indexed
            self.alternative_versions += sum(1 for _ in element.iter(_VERSION))
            return
        if element.tag in _CONTEXT_TAGS:
            context = element
        if element.tag == _BLOCK_AMENDMENT:
            self._harvest_all(element, enclosing, context, in_amendment=True)
            return
        status = element.get("Status", status)
        if element.tag == f"{LEG}P1group":
            heading = _text_of(element.find(f"{LEG}Title"))
        coordinate = self.provision_of(element)
        if coordinate is not None and self._emit(element, coordinate, status, groups, heading):
            enclosing = coordinate
            if coordinate.provision[-1].startswith(_GROUP_PREFIXES):
                groups = (*groups, "/".join(coordinate.provision))
        if element.tag in (_CITATION, _SUBREF):
            self._harvest(element, enclosing, context, in_commentary=False, in_amendment=False)
        for child in element:
            self._walk(
                child,
                enclosing,
                status=status,
                groups=groups,
                heading=heading if element.tag == f"{LEG}P1group" else None,
                context=context,
            )

    def _emit(
        self,
        element: Element,
        coordinate: Coordinate,
        status: str | None,
        groups: tuple[str, ...],
        heading: str | None,
    ) -> bool:
        text = str(coordinate)
        if text in self.seen:
            self.warnings.append(f"duplicate provision {text}; first occurrence kept")
            self.duplicated.setdefault(text, None)
            return False
        key = coordinate.key
        if key in self.seen_keys:
            self.warnings.append(f"case variant {text} of {self.seen_keys[key]}")
        self.seen_keys.setdefault(key, text)
        self.seen.add(text)

        parent = coordinate.parent
        while parent is not None and not parent.is_instrument and str(parent) not in self.seen:
            parent = parent.parent
        tail = "/".join(coordinate.provision)
        for group in groups:
            if group == tail or tail.startswith(group + "/"):
                continue
            members = self.group_members.setdefault(group, set())
            parent_tail = "/".join(coordinate.provision[:-1])
            if parent_tail not in members:
                self.groups.setdefault(group, []).append(tail)
            members.add(tail)

        title = heading if element.tag == f"{LEG}P1" else None
        if title is None:
            title = _text_of(element.find(f"{LEG}Title")) or _text_of(
                element.find(f"{LEG}TitleBlock/{LEG}Title")
            )
        label = _text_of(element.find(f"{LEG}Pnumber")) or _text_of(element.find(f"{LEG}Number"))
        text_before, text_after = self.own_text(element)
        self.provisions.append(
            ProvisionRecord(
                coordinate=text,
                instrument_id=coordinate.instrument_id,
                parent=str(parent if parent is not None else self.instrument),
                order=len(self.provisions),
                number_label=label,
                title=title,
                repealed=status == "Repealed",
                prospective=status == "Prospective",
                text=text_before,
                text_after=text_after,
                source_url=SITE
                + "/".join((*coordinate.instrument, legislation_path(coordinate.provision))),
            )
        )
        return True

    # --- citations

    def _harvest(
        self,
        element: Element,
        source: Coordinate,
        container: Element | None,
        *,
        in_commentary: bool,
        in_amendment: bool,
    ) -> None:
        uri = element.get("URI")
        text = _clean("".join(element.itertext()))
        if not uri or not text:
            return
        context, span = self._context(container, element, text)
        target = coordinate_from_uri(uri)
        self.citations.append(
            HarvestedCitation(
                source_coordinate=str(source),
                kind="citation" if element.tag == _CITATION else "subref",
                text=text,
                context=context,
                span=span,
                target_uri=uri,
                target_coordinate=str(target) if target is not None else None,
                target_class=element.get("Class"),
                citation_id=element.get("id"),
                citation_ref=element.get("CitationRef"),
                in_commentary=in_commentary,
                in_amendment=in_amendment,
            )
        )

    @staticmethod
    def _context(
        container: Element | None, element: Element, text: str
    ) -> tuple[str, tuple[int, int]]:
        """The enclosing text block, whitespace-normalised, and the citation's span in it."""
        if container is None:
            return text, (0, len(text))
        before: list[str] = []
        _Parser._text_before(container, element, before)
        start = len(_WS.sub(" ", "".join(before)).lstrip())
        context = _clean("".join(container.itertext()))
        if context[start : start + len(text)] != text:
            start = context.find(text)
            if start < 0:
                return text, (0, len(text))
        return context, (start, start + len(text))

    @staticmethod
    def _text_before(node: Element, target: Element, out: list[str]) -> bool:
        if node is target:
            return True
        if node.text:
            out.append(node.text)
        for child in node:
            if _Parser._text_before(child, target, out):
                return True
            if child.tail:
                out.append(child.tail)
        return False


def parse_clml(data: bytes, *, source_sha256: str | None = None) -> ParsedInstrument:
    """Parse one CLML document into an instrument record, provisions and citations.

    Raises:
        IngestError: if the document is not UK legislation this ingest understands.
    """
    try:
        root = SafeET.fromstring(data)
    except SafeET.ParseError as exc:
        raise IngestError(f"XML parse error: {exc}") from exc
    path = _uri_path(root.get("IdURI"))
    if path is None:
        raise IngestError("document has no IdURI")
    try:
        instrument = Coordinate.parse(f"uk/{path}")
    except CoordinateError as exc:
        raise IngestError(f"IdURI {path!r} is not a UK instrument coordinate") from exc
    if not instrument.is_instrument:
        raise IngestError(f"IdURI {path!r} names a provision, not an instrument")

    metadata = root.find(f"{UKM}Metadata")
    if metadata is None:
        raise IngestError("document has no metadata")
    kind = metadata.find(f"{UKM}PrimaryMetadata")
    if kind is None:
        kind = metadata.find(f"{UKM}SecondaryMetadata")
    if kind is None:
        raise IngestError("document has neither primary nor secondary metadata")
    classification = kind.find(f"{UKM}DocumentClassification")

    def cls_value(name: str) -> str | None:
        found = classification.find(f"{UKM}{name}") if classification is not None else None
        return found.get("Value") if found is not None else None

    def meta_value(name: str) -> str | None:
        found = kind.find(f"{UKM}{name}")
        return found.get("Value") if found is not None else None

    def meta_date(name: str) -> date | None:
        found = kind.find(f"{UKM}{name}")
        return _date(found.get("Date")) if found is not None else None

    published_title = _text_of(metadata.find(f"{DC}title"))
    if not published_title:
        raise IngestError("document has no title")
    title, repealed = clean_title(published_title)
    year_value, number_value = meta_value("Year"), meta_value("Number")
    if not (year_value and year_value.isdigit() and number_value and number_value.isdigit()):
        raise IngestError("document has no numeric Year/Number")

    parser = _Parser(root, instrument)
    parser.walk()
    warnings = parser.warnings
    if instrument.instrument[1].isdigit() and instrument.instrument[1] != year_value:
        warnings.append(f"metadata year {year_value} differs from IdURI year")

    primary = cls_value("DocumentCategory") == "primary"
    sha = source_sha256 or hashlib.sha256(data).hexdigest()
    record = InstrumentRecord(
        coordinate=str(instrument),
        instrument_id=instrument.instrument_id,
        domain=DOMAIN,
        jurisdiction="UK",
        authority_type="PRIMARY_ACT" if primary else "SECONDARY_INSTRUMENT",
        document_type=cls_value("DocumentMainType") or "unknown",
        title=title,
        title_as_published=published_title,
        year=int(year_value),
        number=int(number_value),
        alternative_numbers=tuple(
            AlternativeNumber(category=a.get("Category", "unknown"), value=a.get("Value", ""))
            for a in kind.findall(f"{UKM}AlternativeNumber")
            if a.get("Value")
        ),
        enactment_date=meta_date("EnactmentDate"),
        made_date=meta_date("Made"),
        repealed=repealed,
        structure="full" if parser.provisions else "metadata_only",
        provision_count=len(parser.provisions),
        alternative_versions=parser.alternative_versions,
        duplicated_provisions=tuple(parser.duplicated),
        groups={k: tuple(v) for k, v in sorted(parser.groups.items())},
        other_titles=other_titles(metadata, instrument, title),
        text_version="current" if cls_value("DocumentStatus") == "revised" else "as_enacted",
        version_date=_date(_text_of(metadata.find(f"{DCT}valid"))),
        normative_tier=1 if primary else 2,
        licence=LICENCE,
        source_url=SITE + path,
        source_sha256=sha,
    )
    return ParsedInstrument(record, parser.provisions, parser.citations, warnings)


# ---------------------------------------------------------------------------- orchestration


def instrument_file(data_dir: Path, instrument: InstrumentRecord) -> Path:
    series = Coordinate.parse(instrument.coordinate).series
    return data_dir / "uk" / series / str(instrument.year) / f"{instrument.instrument_id}.jsonl"


def harvest_part(data_dir: Path, instrument_id: str) -> Path:
    """Per-instrument harvest file; parts are concatenated into ``uk_citations.jsonl``."""
    return data_dir / "harvest" / "uk" / f"{instrument_id}.jsonl"


def discover_sources(raw_xml: Path) -> list[Path]:
    return sorted(raw_xml.glob("*/*/*.xml.gz"))


def peek_instrument_id(path: Path) -> str | None:
    """Read just enough of a file to learn its instrument_id (for ``--only``)."""
    with gzip.open(path) as fh:
        head = fh.read(4096)
    match = _HEAD_ID_URI.search(head)
    if not match:
        return None
    coordinate = Coordinate.try_parse("uk/" + match.group(1).decode("ascii", "replace"))
    return coordinate.instrument_id if coordinate else None


def _existing_source_sha(path: Path) -> str | None:
    try:
        with path.open(encoding="utf-8") as fh:
            first = fh.readline()
        value = json.loads(first).get("source_sha256")
        return value if isinstance(value, str) else None
    except (OSError, ValueError):
        return None


@dataclass(slots=True)
class _Outcome:
    source: str
    instrument_id: str | None = None
    output: str | None = None
    status: str = "ok"  # ok | skipped | failed
    structure: str | None = None
    provisions: int = 0
    citations: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def _ingest_one(source: Path, data_dir: Path, *, force: bool) -> _Outcome:
    outcome = _Outcome(source=str(source))
    try:
        raw = gzip.decompress(source.read_bytes())
        sha = hashlib.sha256(raw).hexdigest()
        parsed = parse_clml(raw, source_sha256=sha)
        out = instrument_file(data_dir, parsed.instrument)
        outcome.instrument_id = parsed.instrument.instrument_id
        outcome.output = str(out)
        outcome.structure = parsed.instrument.structure
        outcome.provisions = len(parsed.provisions)
        outcome.warnings = parsed.warnings
        outcome.citations = len(parsed.citations)
        part = harvest_part(data_dir, parsed.instrument.instrument_id)
        if not force and _existing_source_sha(out) == sha and part.exists():
            outcome.status = "skipped"
            return outcome
        write_instrument_file(out, parsed.instrument, parsed.provisions)
        _write_lines(part, (canonical_json(c.model_dump(mode="json")) for c in parsed.citations))
    except (IngestError, OSError, EOFError, ValueError) as exc:
        outcome.status = "failed"
        outcome.error = f"{type(exc).__name__}: {exc}"
    return outcome


def run(
    sources: Sequence[Path], data_dir: Path, *, workers: int, force: bool
) -> Iterator[_Outcome]:
    if workers <= 1:
        for source in sources:
            yield _ingest_one(source, data_dir, force=force)
        return
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_ingest_one, s, data_dir, force=force) for s in sources]
        for future in futures:
            yield future.result()


def _write_lines(path: Path, lines: Iterable[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for line in lines:
            fh.write(line)
            fh.write("\n")
            count += 1
    tmp.replace(path)
    return count


def _concatenate(paths: Iterable[Path]) -> Iterator[str]:
    for path in paths:
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                yield from (line.rstrip("\n") for line in fh if line.strip())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest legislation.gov.uk CLML into records.")
    parser.add_argument("--source", type=Path, required=True, help="dir containing raw_xml/")
    parser.add_argument("--data", type=Path, required=True, help="output data root")
    parser.add_argument("--only", nargs="*", default=None, help="instrument_ids to ingest")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--force", action="store_true", help="rewrite unchanged instruments")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    sources = discover_sources(args.source / "raw_xml")
    if args.only is not None:
        wanted = set(args.only)
        sources = [s for s in sources if peek_instrument_id(s) in wanted]
        missing = wanted - {peek_instrument_id(s) for s in sources}
        if missing:
            log.warning("not found in raw cache: %s", ", ".join(sorted(missing)))
    log.info("ingesting %d source files with %d workers", len(sources), args.workers)

    started = time.monotonic()
    status: Counter[str] = Counter()
    structures: Counter[str] = Counter()
    by_instrument: dict[str, str] = {}
    failures: list[dict[str, str]] = []
    collisions: list[dict[str, str]] = []
    warnings: Counter[str] = Counter()
    provisions = 0
    for i, outcome in enumerate(run(sources, args.data, workers=args.workers, force=args.force)):
        status[outcome.status] += 1
        if outcome.status == "failed":
            failures.append({"source": outcome.source, "error": outcome.error or ""})
            continue
        assert outcome.instrument_id is not None  # noqa: S101 - set on every non-failure
        previous = by_instrument.setdefault(outcome.instrument_id, outcome.source)
        if previous != outcome.source:
            collisions.append(
                {
                    "instrument_id": outcome.instrument_id,
                    "sources": f"{previous} | {outcome.source}",
                }
            )
        structures[outcome.structure or "unknown"] += 1
        provisions += outcome.provisions
        for warning in outcome.warnings:
            warnings[" ".join(warning.split(" ", 2)[:2])] += 1
        if (i + 1) % 1000 == 0:
            log.info("%d / %d files", i + 1, len(sources))

    harvest_count = _write_lines(
        args.data / "harvest" / "uk_citations.jsonl",
        _concatenate(harvest_part(args.data, i) for i in sorted(by_instrument)),
    )
    report = {
        "generated_at_unix": int(time.time()),
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "source_files": len(sources),
        "status": dict(status),
        "structure": dict(structures),
        "instruments": len(by_instrument),
        "provisions": provisions,
        "harvested_citations": harvest_count,
        "warnings": dict(warnings.most_common()),
        "identity_collisions": collisions,
        "failures": failures,
    }
    report_path = args.data / "uk" / "INGEST_REPORT.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log.info(
        "done: %s", json.dumps({k: report[k] for k in ("status", "instruments", "provisions")})
    )
    return 1 if failures or collisions else 0


if __name__ == "__main__":
    sys.exit(main())
