"""The Jev and Gemini tasks and their scoring (roadmap M11; §4 design approved 1 Oct 2026).

Two tasks over the sealed UK battery (2,112 rows):

- **End to end (Gemini, design point 1).** Gemini reads the query and returns the router's kind
  of answer: an outcome and legislation.gov.uk-style coordinates, as JSON held to a response
  schema. It is told the router's whole contract (``CONTRACT``) and works from memory, with no
  index. Its answers become ``eval.metrics.Outcome`` rows and are scored by the sealed run's
  own ``domain_metrics``.
- **Choice (Jev, point 2; Gemini, point 3).** One ``choice`` question per row and option count
  (3, 10, 30): which instrument does the text cite? The options are the right instrument(s),
  seeded distractors of the same series from nearby years, and "none of these". The right
  answer is always offered, so this is a best case (for Gemini, a perfect retriever).

The worked examples in ``CONTRACT`` were checked against the battery: none of their
instruments is a gold instrument, and none of their titles occurs in a battery query.
"""

from __future__ import annotations

import json
import random
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from batteries.schema import BatteryRow
from eval.metrics import Outcome
from legal_rag_router import RouteStatus
from legal_rag_router.coordinate import Coordinate
from legal_rag_router.index import InstrumentInfo, RouterIndex

SEED: Final = 20261001
OPTION_COUNTS: Final = (3, 10, 30)
NONE: Final = "none"
NONE_TEXT: Final = "None of these"
YEAR_WINDOW: Final = 2

# ---------------------------------------------------------------- end to end (point 1)

STATUS_FROM_GEMINI: Final = {
    "BOUND": RouteStatus.BOUNDED.value,
    "AMBIGUOUS": RouteStatus.AMBIGUOUS.value,
    "INSTRUMENT_NOT_FOUND": RouteStatus.INSTRUMENT_NOT_FOUND.value,
    "PROVISION_NOT_FOUND": RouteStatus.PROVISION_NOT_FOUND.value,
    "OUT_OF_COVERAGE": RouteStatus.OUT_OF_COVERAGE.value,
    "NO_CITATION": RouteStatus.UNRESOLVED.value,
}

CONTRACT: Final = """\
You route UK legal queries to the exact legislation they cite. Read the text and answer with
an outcome and the coordinates of every provision or instrument it cites. Work only from your
own knowledge of UK legislation as published on legislation.gov.uk; do not guess.

Coordinates follow legislation.gov.uk's identifiers, prefixed with "uk/":
  uk/{type}/{year}/{number} for an instrument, then the provision path.
  - Acts after 1962: uk/ukpga/1996/18 (Employment Rights Act 1996, chapter 18).
  - Older Acts use the regnal year as legislation.gov.uk does: Sale of Goods Act 1893 is
    uk/ukpga/Vict/56-57/71; Occupiers' Liability Act 1957 is uk/ukpga/Eliz2/5-6/31.
  - Statutory instruments: uk/uksi/2017/1012 (SI 2017/1012); Welsh SIs uk/wsi/...;
    Northern Ireland Orders in Council uk/nisi/....
  - Provisions: section s124, regulation reg3, article art4, rule rule2, schedule sch1 with
    paragraph sch1/para3; subsections and paragraphs follow as further segments, e.g.
    uk/ukpga/1996/18/s124/1ZA/a for section 124(1ZA)(a).
  - Cite the instrument alone (uk/ukpga/2004/37) when no provision is cited.

The index you route against is a snapshot of legislation.gov.uk taken on 2026-09-28. It covers
exactly four series: UK Public General Acts (ukpga, including regnal Acts), UK Statutory
Instruments (uksi), Wales Statutory Instruments (wsi) and Northern Ireland Orders in Council
(nisi). Everything else (Acts of the Scottish Parliament, Scottish SIs, Northern Ireland Acts and
Statutory Rules, local and private Acts, Church Measures, EU legislation and so on) is outside it.

Outcomes:
  BOUND                The text cites legislation in the covered series, and every cited
                       instrument and provision exists. Give every cited coordinate.
  AMBIGUOUS            A citation fits more than one instrument (a title without a year that
                       several Acts share, for example). Give every candidate's coordinate.
  INSTRUMENT_NOT_FOUND A cited instrument does not exist in the covered series. No coordinates.
  PROVISION_NOT_FOUND  The instrument exists but the cited provision does not. No coordinates.
  OUT_OF_COVERAGE      A cited instrument exists but is outside the four covered series.
                       No coordinates.
  NO_CITATION          The text cites no legislation. No coordinates.
When a text cites several things, the most cautious outcome decides: INSTRUMENT_NOT_FOUND, then
PROVISION_NOT_FOUND, then AMBIGUOUS, then OUT_OF_COVERAGE, then BOUND.

Examples:
  "reg. 3 of the Conservation of Habitats and Species Regulations 2017"
      -> BOUND ["uk/uksi/2017/1012/reg3"]
  "Sale of Goods Act 1893 s 14" -> BOUND ["uk/ukpga/Vict/56-57/71/s14"]
  "Occupiers' Liability Act 1957 s 2(2)" -> BOUND ["uk/ukpga/Eliz2/5-6/31/s2/2"]
  "Schedule 1 paragraph 3 to the Hunting Act 2004" -> BOUND ["uk/ukpga/2004/37/sch1/para3"]
  "section 1 of the Hunting Act 2004 and reg. 3 of the Conservation of Habitats and Species
   Regulations 2017" -> BOUND ["uk/ukpga/2004/37/s1", "uk/uksi/2017/1012/reg3"]
  "Hunting Act 2004 s 99" -> PROVISION_NOT_FOUND []
  "the Pennine Ferry Charges Order 2019" -> INSTRUMENT_NOT_FOUND []
  "Land Reform (Scotland) Act 2016 s 1" -> OUT_OF_COVERAGE []
  "What are my rights if my landlord keeps my deposit?" -> NO_CITATION []
"""

ROUTE_SCHEMA: Final = {
    "type": "OBJECT",
    "properties": {
        "outcome": {"type": "STRING", "enum": list(STATUS_FROM_GEMINI)},
        "coordinates": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["outcome", "coordinates"],
    "propertyOrdering": ["outcome", "coordinates"],
}


def route_prompt(row: BatteryRow) -> str:
    """The query, after any earlier turns the router would also be given as context."""
    if not row.context:
        return f"Text: {row.query}"
    earlier = "\n".join(f"- {turn}" for turn in row.context)
    return f"Earlier in the conversation:\n{earlier}\n\nText: {row.query}"


@dataclass(frozen=True, slots=True)
class Routed:
    status: str | None
    """The router status Gemini's outcome maps to; ``None`` if the answer was unusable."""
    coordinates: tuple[str, ...]
    malformed: tuple[str, ...]
    """Coordinates Gemini gave that do not parse; they never count as bound."""


def read_route(output: Any) -> Routed:
    if not isinstance(output, Mapping) or output.get("outcome") not in STATUS_FROM_GEMINI:
        return Routed(None, (), ())
    good: list[str] = []
    bad: list[str] = []
    for text in output.get("coordinates") or []:
        coordinate = Coordinate.try_parse(str(text).strip())
        (good if coordinate is not None else bad).append(
            str(coordinate) if coordinate is not None else str(text)
        )
    return Routed(STATUS_FROM_GEMINI[output["outcome"]], tuple(good), tuple(bad))


def outcome(battery: str, row: BatteryRow, routed: Routed) -> Outcome:
    """Gemini's answer as the sealed run's ``Outcome``; an unusable answer is unresolved."""
    status = routed.status or RouteStatus.UNRESOLVED.value
    bound = routed.coordinates if status == RouteStatus.BOUNDED.value else ()
    candidates = routed.coordinates if status == RouteStatus.AMBIGUOUS.value else ()
    return Outcome(
        battery=battery,
        row_id=row.id,
        source=row.source,
        expected_status=row.expected_status,
        expected=row.expected_coordinates,
        status=status,
        bound=bound,
        top_candidate=candidates[0] if candidates else None,
        corrected=False,
        split=row.split,
    )


INDEX_DEPENDENT: Final = frozenset({RouteStatus.OUT_OF_COVERAGE.value})
"""Expected outcomes that turn on our index's coverage rather than on the law; reported apart."""

# ---------------------------------------------------------------- choice (points 2 and 3)

CHOICE_INSTRUCTIONS: Final = (
    "Which UK legislation instrument does this text cite? Choose 'None of these' if it cites "
    "none of the listed instruments, or no legislation at all."
)
_YEAR = re.compile(r"\b(1[89]\d\d|20[0-2]\d)\b")
_SI_WORDS = re.compile(r"\b(regulations?|orders?|rules|s\.?\s?i\.?|statutory instrument)\b", re.I)


@dataclass(frozen=True, slots=True)
class Choice:
    """One choice question: option key -> instrument id, the right keys, the order shown."""

    row_id: str
    count: int
    options: dict[str, str]
    titles: dict[str, str]
    right: frozenset[str]


def gold_instruments(row: BatteryRow) -> tuple[str, ...] | None:
    """The instruments a correct choice may name; ``()`` when "none" is right; ``None`` when the
    row has no instrument-level answer (a provision missing from a real instrument, coverage, or
    an ambiguity the battery leaves without coordinates), so it is left out and counted."""
    if row.expected_coordinates:
        return tuple(
            dict.fromkeys(Coordinate.parse(c).instrument_id for c in row.expected_coordinates)
        )
    if row.expected_status in {
        RouteStatus.INSTRUMENT_NOT_FOUND.value,
        RouteStatus.UNRESOLVED.value,
    }:
        return ()
    return None


def identifier(series: str, year: int, number: int, coordinate: str) -> str:
    """The official citation shown beside a title, as a retriever's candidate list would."""
    if series == "ukpga":
        _, _, first, *rest = coordinate.split("/")  # uk/ukpga/{year | reign}/[session/]number
        regnal = not first.isdigit()
        return f"{first} {rest[0]} c. {number}" if regnal else f"{year} c. {number}"
    suffix = {"wsi": " (W.)", "nisi": " (N.I.)"}.get(series, "")
    return f"SI {year}/{number}{suffix}"


class Neighbours:
    """Every indexed instrument by (series, year), each labelled with its title and official
    citation: where distractors come from."""

    def __init__(self, items: Iterable[tuple[str, str, int, str]]) -> None:
        self.by_key: dict[tuple[str, int], list[str]] = {}
        self.titles: dict[str, str] = {}
        self.place: dict[str, tuple[str, int]] = {}
        for instrument_id, series, year, title in items:
            self.by_key.setdefault((series, year), []).append(instrument_id)
            self.titles[instrument_id] = title
            self.place[instrument_id] = (series, year)
        for ids in self.by_key.values():
            ids.sort()

    @classmethod
    def from_index(cls, index: RouterIndex) -> Neighbours:
        def rows() -> Iterable[tuple[str, str, int, str]]:
            for instrument_id, raw in index.tables["instruments"].items():
                info = InstrumentInfo.from_json(instrument_id, json.loads(raw))
                ident = identifier(info.series, info.year, info.number, info.coordinate)
                yield instrument_id, info.series, info.year, f"{info.title} ({ident})"

        return cls(rows())

    def near(
        self, series: str, year: int, exclude: set[str], want: int, rng: random.Random
    ) -> list[str]:
        """``want`` instruments of ``series``, from ``year`` outwards, nearest years first."""
        chosen: list[str] = []
        for spread in range(200):
            pool = [
                i
                for y in {year - spread, year + spread}
                for i in self.by_key.get((series, y), [])
                if i not in exclude and i not in chosen
            ]
            rng.shuffle(pool)
            chosen += pool[: want - len(chosen)]
            if len(chosen) >= want or (spread >= YEAR_WINDOW and not self.by_key):
                break
        return chosen


def build_choice(
    row: BatteryRow, count: int, neighbours: Neighbours, seed: int = SEED
) -> Choice | None:
    """The question for ``row`` with ``count`` instrument options plus "none of these"."""
    gold = gold_instruments(row)
    if gold is None:
        return None
    rng = random.Random(f"{seed}:{row.id}:{count}")
    right = [g for g in gold if g in neighbours.titles][:count]
    if gold and not right:
        return None  # the right instrument cannot be offered, so the row is left out
    if gold:
        series, year = neighbours.place[right[0]] if right else ("ukpga", 2000)
    else:
        years = [int(y) for y in _YEAR.findall(row.query)]
        series = "uksi" if _SI_WORDS.search(row.query) else "ukpga"
        year = years[0] if years else rng.randint(1970, 2025)
    distractors = neighbours.near(series, year, set(right), count - len(right), rng)
    instruments = right + distractors
    rng.shuffle(instruments)
    options = {f"option_{i}": inst for i, inst in enumerate(instruments)}
    titles = {key: neighbours.titles[inst] for key, inst in options.items()}
    titles[NONE] = NONE_TEXT
    options[NONE] = NONE
    keys = {key for key, inst in options.items() if inst in right} if right else {NONE}
    return Choice(row.id, count, options, titles, frozenset(keys))


def jev_question(choice: Choice) -> dict[str, Any]:
    return {
        "instrument": {
            "type": "choice",
            "instructions": CHOICE_INSTRUCTIONS,
            "criteria": dict(choice.titles),
        }
    }


def gemini_choice_prompt(row: BatteryRow, choice: Choice) -> str:
    listed = "\n".join(f"  {key}: {title}" for key, title in choice.titles.items())
    return f"{CHOICE_INSTRUCTIONS}\n\nOptions:\n{listed}\n\n{route_prompt(row)}"


def gemini_choice_schema(choice: Choice) -> dict[str, Any]:
    return {
        "type": "OBJECT",
        "properties": {"choice": {"type": "STRING", "enum": list(choice.titles)}},
        "required": ["choice"],
    }


def choice_from_jev(answers: Mapping[str, Mapping[str, Any]]) -> str | None:
    picked = (answers.get("instrument") or {}).get("choice")
    return str(picked) if picked is not None else None


def choice_from_gemini(output: Any) -> str | None:
    if isinstance(output, Mapping) and isinstance(output.get("choice"), str):
        return str(output["choice"])
    return None


def score_choices(answers: Iterable[tuple[Choice, str | None]]) -> dict[str, Any]:
    """Per option count: accuracy over all, over rows with a real instrument, and on rows where
    "none of these" is right (picking an instrument there is binding invented law)."""
    by_count: dict[int, dict[str, list[bool]]] = {}
    for choice, picked in answers:
        row = by_count.setdefault(choice.count, {"all": [], "real": [], "none": [], "unusable": []})
        correct = picked in choice.right
        row["all"].append(correct)
        row["none" if NONE in choice.right else "real"].append(correct)
        row["unusable"].append(picked is None or picked not in choice.options)
    out = {}
    for count, row in sorted(by_count.items()):
        none_rows = row["none"]
        out[str(count)] = {
            "questions": len(row["all"]),
            "correct": sum(row["all"]),
            "correct_real_instrument": f"{sum(row['real'])}/{len(row['real'])}",
            "correct_none": f"{sum(none_rows)}/{len(none_rows)}",
            "picked_an_instrument_when_none_was_right": sum(not c for c in none_rows),
            "unusable_answers": sum(row["unusable"]),
        }
    return out


def ensure_option_counts(counts: Sequence[int]) -> tuple[int, ...]:
    return tuple(sorted(set(counts)))
