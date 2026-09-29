"""Battery row schema (plan step 8, roadmap M8). Validated in CI by ``tests/test_batteries.py``.

A battery file is JSON Lines, one :class:`BatteryRow` per line, at
``batteries/{jurisdiction}/{battery}.jsonl``. The battery name is the file stem.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from legal_rag_router import RouteStatus
from legal_rag_router.coordinate import Coordinate

__all__ = [
    "BATTERIES",
    "BATTERY_DIR",
    "CONCEPT_DIR",
    "AbsenceCheck",
    "BatteryRow",
    "ConceptRow",
    "read_battery",
    "read_concepts",
    "write_battery",
    "write_concepts",
]

BATTERY_DIR: Final = Path(__file__).resolve().parent
BATTERIES: Final = (
    "collision",
    "misroute",
    "false_abstention",
    "invented",
    "ambiguous",
    "typo",
    "identifier",
    "informal",
    "catalogue",
)
"""Every battery the plan names; a file per jurisdiction where one applies."""

Status = Literal[
    "ROUTE_BOUNDED",
    "ROUTE_AMBIGUOUS",
    "EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND",
    "EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND",
    "ROUTE_OUT_OF_COVERAGE",
    "ROUTE_UNRESOLVED",
]
if set(Status.__args__) != {s.value for s in RouteStatus}:  # type: ignore[attr-defined]
    raise ImportError("battery statuses differ from RouteStatus")


class AbsenceCheck(BaseModel):
    """How an invented instrument's absence was confirmed (plan step 8, ``invented``).

    ``catalogue`` is the offline check: the title is in neither the index nor the catalogue
    harvested from the source's own feeds. ``search_url`` is the source's own search for the
    title; ``searched`` is the date someone ran it and saw no result (``None`` until then).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    catalogue: str = Field(min_length=1)
    search_url: str = Field(pattern=r"^https://")
    searched: date | None = None


class BatteryRow(BaseModel):
    """One labelled query. Field order is the plan's (step 8)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z]{2}-[a-z_]+-[0-9]{4}$")
    query: str = Field(min_length=1, max_length=8192)
    context: tuple[str, ...] | None = None
    lang: Literal["en", "es"]
    domain: Literal["uk_legislation", "es_legislation"]
    expected_status: Status
    expected_coordinates: tuple[str, ...] = ()
    """For ``ROUTE_BOUNDED``: coordinates that must be bound (others may be too, when the
    query cites several). For ``ROUTE_AMBIGUOUS`` typo rows: the right top candidate."""
    source: Literal["hand", "real_document", "sampled"]
    notes: str = ""
    surface_form_ids: tuple[str, ...] = ()
    """grammar.md rows the query exercises (``UK-I-16`` …)."""
    absence_verified_via: AbsenceCheck | None = None
    split: Literal["dev", "test"] | None = None
    """Typo rows only (roadmap D2): thresholds are tuned on ``dev``, never on ``test``."""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for coordinate in (*self.expected_coordinates, *(self.context or ())):
            Coordinate.parse(coordinate)  # raises ValueError on a malformed coordinate
        if self.expected_status == "ROUTE_BOUNDED" and not self.expected_coordinates:
            raise ValueError("a ROUTE_BOUNDED row names the coordinates it expects")
        if (
            self.expected_status
            in {
                "EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND",
                "EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND",
                "ROUTE_OUT_OF_COVERAGE",
                "ROUTE_UNRESOLVED",
            }
            and self.expected_coordinates
        ):
            raise ValueError(f"a {self.expected_status} row binds nothing")
        for form in self.surface_form_ids:
            if not form.startswith(f"{self.id[:2].upper()}-"):
                raise ValueError(f"surface form {form} is not a {self.id[:2]} grammar row")
        return self


def read_battery(path: Path) -> list[BatteryRow]:
    """Every row of a battery file, validated, with the battery's own rules applied."""
    battery = path.stem
    rows = [
        BatteryRow.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    prefix = f"{path.parent.name}-{battery}-"
    for row in rows:
        if not row.id.startswith(prefix):
            raise ValueError(f"{path.name}: row {row.id} does not start with {prefix}")
        if (battery == "typo") != (row.split is not None):
            raise ValueError(f"{path.name}: row {row.id}: `split` is for typo rows only")
        if battery != "invented" and row.absence_verified_via is not None:
            raise ValueError(f"{path.name}: row {row.id}: absence checks are for invented rows")
        if (
            battery == "invented"
            and row.expected_status == "EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND"
            and row.absence_verified_via is None
        ):
            raise ValueError(f"{path.name}: row {row.id}: an invented instrument needs its check")
    ids = [row.id for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path.name}: duplicate row ids")
    return rows


def write_battery(path: Path, rows: list[BatteryRow]) -> None:
    """Canonical form: one compact JSON object per line, fields in schema order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(row.model_dump(mode="json", exclude_defaults=True), ensure_ascii=False)
        for row in rows
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- concept battery (stage D)

CONCEPT_DIR: Final = BATTERY_DIR / "concept"
"""``batteries/concept/{jurisdiction}.jsonl``: outside the nine plan batteries and their seal."""


class ConceptRow(BaseModel):
    """A citation-less research query and the provisions that answer it (docs/discovery.md).

    ``gold`` holds the acceptable answers: a discovered candidate is a hit when it is one
    of them or lies beneath one. An empty ``gold`` is a query no indexed statute answers
    (out of jurisdiction, or no statutory answer): the good outcome is no confident candidate.
    ``route_status`` is what ``route()`` must return for the same query (grammar.md labels).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z]{2}-concept-[0-9]{4}$")
    query: str = Field(min_length=1, max_length=4096)
    lang: Literal["en", "es"]
    domain: Literal["uk_legislation", "es_legislation"]
    area: str = Field(pattern=r"^[a-z_]+$")
    route_status: Status
    gold: tuple[str, ...] = ()
    source: Literal["hand", "user_probe", "appendix_b"]
    split: Literal["dev", "test"]
    notes: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for coordinate in self.gold:
            Coordinate.parse(coordinate)
        if self.source != "hand" and self.split != "test":
            raise ValueError("rows from your sources are test only")
        return self


def read_concepts(path: Path) -> list[ConceptRow]:
    rows = [
        ConceptRow.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [row.id for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path.name}: duplicate row ids")
    return rows


def write_concepts(path: Path, rows: list[ConceptRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(row.model_dump(mode="json", exclude_defaults=True), ensure_ascii=False)
        for row in rows
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
