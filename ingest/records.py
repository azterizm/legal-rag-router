"""Normalised corpus records (vault 01 §4) and their on-disk JSONL form.

One JSONL file per instrument, at ``data/{jurisdiction}/{series}/{year}/{instrument_id}.jsonl``:

* line 1 is an :class:`InstrumentRecord`;
* each following line is a :class:`ProvisionRecord`, in document order.

A provision's ``text`` holds **its own text only**, excluding the text of its child
provisions (roadmap decision 11): ``text`` is the lead-in before the first child and
``text_after`` the closing words after the children. The full text of a provision is
``text`` + its children's full texts (in ``order``) + ``text_after``. Every record
carries a ``checksum_sha256`` over its canonical JSON form without that field, so any
later edit is detectable.

Pydantic is used here, at ingest, and never in the router's hot path.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable, Iterator
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from legal_rag_router.coordinate import Coordinate, CoordinateError

__all__ = [
    "RECORD_SCHEMA_VERSION",
    "AlternativeNumber",
    "HarvestedCitation",
    "InstrumentRecord",
    "ProvisionRecord",
    "canonical_json",
    "read_instrument_file",
    "write_instrument_file",
]

RECORD_SCHEMA_VERSION = 1

AuthorityType = Literal["PRIMARY_ACT", "SECONDARY_INSTRUMENT"]
TextVersion = Literal["current", "as_enacted"]
Structure = Literal["full", "metadata_only"]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def canonical_json(data: Any) -> str:
    """Deterministic JSON: sorted keys, no insignificant whitespace, UTF-8 characters kept."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _checksum(payload: dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k != "checksum_sha256"}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


class _Record(BaseModel):
    """Shared behaviour: frozen, strict field set, self-verifying checksum."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = RECORD_SCHEMA_VERSION
    coordinate: str
    instrument_id: str
    checksum_sha256: Sha256 | None = None

    @field_validator("coordinate")
    @classmethod
    def _valid_coordinate(cls, value: str) -> str:
        try:
            Coordinate.parse(value)
        except CoordinateError as exc:
            raise ValueError(str(exc)) from exc
        return value

    @model_validator(mode="after")
    def _consistent_ids(self) -> _Record:
        if Coordinate.parse(self.coordinate).instrument_id != self.instrument_id:
            raise ValueError("instrument_id does not match coordinate")
        return self

    def sealed(self) -> Self:
        """Return a copy with ``checksum_sha256`` computed over the other fields."""
        payload = self.model_dump(mode="json")
        return self.model_copy(update={"checksum_sha256": _checksum(payload)})

    def verify(self) -> bool:
        """True when the stored checksum matches the record's content."""
        return self.checksum_sha256 == _checksum(self.model_dump(mode="json"))


class AlternativeNumber(BaseModel):
    """Another official number the instrument carries (regnal, W., C., L., S., NI …)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: str = Field(min_length=1)
    value: str = Field(min_length=1)


class InstrumentRecord(_Record):
    """First line of an instrument file: identity, titles, status and structure."""

    record_type: Literal["instrument"] = "instrument"
    domain: str
    jurisdiction: str
    authority_type: AuthorityType
    document_type: str
    title: str = Field(min_length=1)
    title_as_published: str = Field(min_length=1)
    year: int = Field(ge=1000, le=2999)
    number: int = Field(ge=1)
    alternative_numbers: tuple[AlternativeNumber, ...] = ()
    enactment_date: date | None = None
    made_date: date | None = None
    repealed: bool
    structure: Structure
    provision_count: int = Field(ge=0)
    alternative_versions: int = Field(default=0, ge=0)
    duplicated_provisions: tuple[str, ...] = ()
    """Coordinates the source publishes more than once (e.g. schedule parts that restart
    paragraph numbering under one id). Only the first occurrence has a record."""
    groups: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    text_version: TextVersion
    version_date: date | None = None
    normative_tier: int = Field(ge=1, le=4)
    licence: str
    source_url: str
    source_sha256: Sha256

    @model_validator(mode="after")
    def _instrument_level(self) -> InstrumentRecord:
        if not Coordinate.parse(self.coordinate).is_instrument:
            raise ValueError("an instrument record needs an instrument-level coordinate")
        if (self.structure == "metadata_only") != (self.provision_count == 0):
            raise ValueError("structure must be metadata_only exactly when there are no provisions")
        return self


class ProvisionRecord(_Record):
    """One citable provision: a section, subsection, schedule paragraph, part …"""

    record_type: Literal["provision"] = "provision"
    parent: str
    order: int = Field(ge=0)
    number_label: str | None = None
    title: str | None = None
    repealed: bool = False
    prospective: bool = False
    text: str = ""
    text_after: str = ""
    amendment_history: tuple[dict[str, Any], ...] = ()  # filled by Phase 2 (temporal)
    source_url: str

    @model_validator(mode="after")
    def _below_parent(self) -> ProvisionRecord:
        coordinate = Coordinate.parse(self.coordinate)
        parent = Coordinate.try_parse(self.parent)
        if coordinate.is_instrument:
            raise ValueError("a provision record needs a provision-level coordinate")
        if parent is None or not parent.is_ancestor_of(coordinate):
            raise ValueError("parent must be an ancestor of the coordinate")
        return self


class HarvestedCitation(BaseModel):
    """A cross-reference as written in the source, with the target the source links it to.

    These are the ground truth for the coverage sweep and the misroute battery (plan,
    "Missed patterns" §2). ``context`` is the enclosing text block as published and
    ``span`` locates ``text`` inside it, so a harvested pair can be replayed as a query.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_coordinate: str
    kind: Literal["citation", "subref"]
    text: str
    context: str
    span: tuple[int, int]
    target_uri: str
    target_coordinate: str | None
    target_class: str | None = None
    citation_id: str | None = None
    citation_ref: str | None = None
    in_commentary: bool = False
    in_amendment: bool = False

    @model_validator(mode="after")
    def _span_inside_context(self) -> HarvestedCitation:
        start, end = self.span
        if not 0 <= start <= end <= len(self.context):
            raise ValueError("span lies outside context")
        return self


def write_instrument_file(
    path: Path, instrument: InstrumentRecord, provisions: Iterable[ProvisionRecord]
) -> None:
    """Write one instrument file atomically (temp file + rename), sealing every record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            for record in (instrument, *provisions):
                fh.write(canonical_json(record.sealed().model_dump(mode="json")))
                fh.write("\n")
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_instrument_file(path: Path) -> tuple[InstrumentRecord, Iterator[ProvisionRecord]]:
    """Read an instrument file, validating and checksum-verifying every record.

    Raises:
        ValueError: if the file is empty, malformed, or a checksum does not match.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"{path}: empty instrument file")
    instrument = InstrumentRecord.model_validate_json(lines[0])
    if not instrument.verify():
        raise ValueError(f"{path}: checksum mismatch on the instrument record")

    def provisions() -> Iterator[ProvisionRecord]:
        for lineno, line in enumerate(lines[1:], start=2):
            record = ProvisionRecord.model_validate_json(line)
            if not record.verify():
                raise ValueError(f"{path}:{lineno}: checksum mismatch")
            if record.instrument_id != instrument.instrument_id:
                raise ValueError(f"{path}:{lineno}: record belongs to another instrument")
            yield record

    return instrument, provisions()
