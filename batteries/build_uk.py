"""Build the UK battery files (plan step 8) from the hand rows and fixed-seed samples.

Build machine only: needs the full index (``data/index``), the harvest and the catalogue.

    uv run python -m batteries.build_uk

Nothing here runs the router. Hand labels come from grammar.md; this script only checks
their facts against the index (coordinates exist, ``absent:`` ones do not, invented titles
are unknown to index and catalogue). Sampled rows take their answer from the source's own
citation link (``misroute``) or from the index itself (``false_abstention``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Final
from urllib.parse import urlencode

from batteries import hand_uk
from batteries.hand_uk import Hand
from batteries.schema import BATTERY_DIR, AbsenceCheck, BatteryRow, read_battery, write_battery
from eval.sweep import eligible, replay_query
from ingest.build_index import title_variants
from legal_rag_router import Router
from legal_rag_router.coordinate import Coordinate
from legal_rag_router.index import InstrumentInfo, RouterIndex
from legal_rag_router.normalise import split_title_year

SEED: Final = 20260928
MISROUTE_SAMPLE: Final = 1000
FALSE_ABSTENTION_SAMPLE: Final = 700
TYPO_SPLIT_SALT: Final = "lrr-typo-split-v1"
TYPO_DEV_PERCENT: Final = 30
"""Roadmap D2: this share of typo rows is ``dev`` (published, for tuning); the rest is sealed."""

HAND: Final = {
    "collision": hand_uk.COLLISION,
    "misroute": hand_uk.MISROUTE,
    "false_abstention": hand_uk.FALSE_ABSTENTION,
    "invented": hand_uk.INVENTED,
    "ambiguous": hand_uk.AMBIGUOUS,
    "typo": hand_uk.TYPO,
    "identifier": hand_uk.IDENTIFIER,
    "informal": hand_uk.INFORMAL,
    "catalogue": hand_uk.CATALOGUE,
}


class LabelError(ValueError):
    """A hand label's facts disagree with the index."""


# ---------------------------------------------------------------- hand rows


_ABSENT_RE: Final = re.compile(r"absent: (uk/\S+?)(?:;|$)")
_TITLE_RE: Final = re.compile(
    r"(?:^|\b(?:of|to|by)\s+)(?:the\s+)?"
    r"(?P<title>[^,;]*?\b(?:act|order|regulations|rules)\s+(?P<year>\d{4}))\b",
    re.IGNORECASE,
)


def invented_title(query: str) -> tuple[str, int]:
    """The instrument title a hand-written invented row cites, and its year."""
    matches = list(_TITLE_RE.finditer(query))
    if not matches:
        raise LabelError(f"no title in {query!r}")
    match = matches[-1]
    return match.group("title").strip(), int(match.group("year"))


def _check_hand(
    index: RouterIndex, battery: str, row: Hand, catalogue_note: str
) -> AbsenceCheck | None:
    for coordinate in row.coordinates:
        canonical = index.coordinates.canonical(coordinate)
        if canonical != coordinate:
            raise LabelError(f"{battery}: {row.query!r}: {coordinate} is not in the index")
        parsed = Coordinate.parse(coordinate)
        info = index.info(parsed.instrument_id)
        if row.status == hand_uk.B and "/".join(parsed.provision) in info.duplicated:
            raise LabelError(f"{battery}: {row.query!r}: {coordinate} is published twice")
    for absent in _ABSENT_RE.findall(row.notes):
        if absent in index.coordinates:
            raise LabelError(f"{battery}: {row.query!r}: {absent} exists")
        parsed = Coordinate.parse(absent)
        if parsed.provision and index.instrument(parsed.instrument_id) is None:
            raise LabelError(f"{battery}: {row.query!r}: the instrument of {absent} is missing")
    if not row.absent_title:
        return _absent_number(index, row, catalogue_note)
    title, year = invented_title(row.query)
    keys = title_variants(f"{title}")
    strict = battery == "invented" and "wrong year" not in row.notes
    for key in keys[:2] if strict else keys[:1]:
        for table in ("titles", "coverage_titles"):
            if index.ids(table, key):
                raise LabelError(f"{battery}: {row.query!r}: {key!r} is a real title ({table})")
    words = split_title_year(title)[0]
    query = urlencode({"title": words, "year": year})
    return AbsenceCheck(
        catalogue=catalogue_note,
        search_url=f"https://www.legislation.gov.uk/all?{query}",
    )


def _absent_number(index: RouterIndex, row: Hand, catalogue_note: str) -> AbsenceCheck | None:
    """An instrument invented by number (``SI 2011/9999``): absent from index and catalogue."""
    absent = [Coordinate.parse(c) for c in _ABSENT_RE.findall(row.notes)]
    instruments = [c for c in absent if not c.provision]
    if row.status != hand_uk.I or not instruments:
        return None
    for coordinate in instruments:
        if index.coverage(str(coordinate)) is not None:
            raise LabelError(f"{row.query!r}: {coordinate} is in the catalogue")
    path = "/".join(instruments[0].instrument[:])
    return AbsenceCheck(
        catalogue=catalogue_note, search_url=f"https://www.legislation.gov.uk/{path}"
    )


def part_sections(index: RouterIndex, coordinates: tuple[str, ...]) -> tuple[str, ...]:
    """A Part or Chapter label as the sections it binds to (grammar.md UK-P-13, UK-P-14).

    The first sealed run found two rows labelled ``…/pt2/ch1`` where the grammar binds the
    chapter's sections; ingest's part → sections map gives the label.
    """
    expanded: list[str] = []
    for coordinate in coordinates:
        parsed = Coordinate.parse(coordinate)
        groups = index.info(parsed.instrument_id).groups if parsed.provision else {}
        tail = "/".join(parsed.provision)
        if tail in groups:
            expanded += [f"{parsed.instrument_coordinate}/{s}" for s in groups[tail]]
        else:
            expanded.append(coordinate)
    return tuple(expanded)


def hand_rows(index: RouterIndex, battery: str, catalogue_note: str) -> Iterator[BatteryRow]:
    for row in HAND[battery]:
        check = _check_hand(index, battery, row, catalogue_note)
        coordinates = row.coordinates
        if row.status == hand_uk.B:
            coordinates = part_sections(index, coordinates)
        yield BatteryRow(
            id="uk-x-0000",  # renumbered by _numbered
            query=row.query,
            context=row.context,
            lang="en",
            domain="uk_legislation",
            expected_status=row.status,  # type: ignore[arg-type]
            expected_coordinates=coordinates,
            source="hand",
            notes=row.notes,
            surface_form_ids=row.forms,
            absence_verified_via=check if battery == "invented" else None,
        )


# ---------------------------------------------------------------- misroute (sampled)


def misroute_rows(router: Router, harvest: Path) -> list[BatteryRow]:
    """Held-out harvested citations (roadmap D3), drawn with a fixed seed.

    Each row is the clause of the source text that holds the citation; the expected answer
    is the source's own link target. The grammar never saw these rows.
    """
    with harvest.open(encoding="utf-8") as fh:
        pool = list(eligible(router, (json.loads(line) for line in fh if line.strip()), "heldout"))
    sample = random.Random(SEED).sample(pool, MISROUTE_SAMPLE)
    return [
        BatteryRow(
            id="uk-x-0000",
            query=replay_query(citation),
            lang="en",
            domain="uk_legislation",
            expected_status="ROUTE_BOUNDED",
            expected_coordinates=(str(citation["target_coordinate"]),),
            source="real_document",
            notes=(
                f"harvest {citation['source_coordinate']} #{citation['citation_id']}: "
                f"cited {str(citation['text'])!r}"
            ),
        )
        for citation in sample
    ]


# ---------------------------------------------------------------- false abstention (sampled)

_UNITS: Final = {
    "s": ("section", "s."),
    "reg": ("regulation", "reg."),
    "art": ("article", "art."),
    "rule": ("rule", "r."),
}
_PROVISION_RE: Final = re.compile(
    r"^(?P<unit>s|reg|art|rule)(?P<n>[0-9]{1,4}[A-Z]{0,3})(?P<subs>(?:/[0-9A-Za-z]{1,4}){0,2})$"
)
_SCHEDULE_RE: Final = re.compile(
    r"^sch(?P<sch>[0-9]{1,3}[A-Z]?)/para(?P<n>[0-9]{1,3}[A-Z]?)(?P<subs>(?:/[0-9A-Za-z]{1,4}){0,1})$"
)


def provision_label(provision: str) -> tuple[str, str] | None:
    """Long and short written forms of a provision path, or ``None`` if not phrased here."""
    if m := _PROVISION_RE.match(provision):
        long, short = _UNITS[m.group("unit")]
        subs = "".join(f"({s})" for s in m.group("subs").split("/") if s)
        return f"{long} {m.group('n')}{subs}", f"{short} {m.group('n')}{subs}"
    if m := _SCHEDULE_RE.match(provision):
        subs = "".join(f"({s})" for s in m.group("subs").split("/") if s)
        sch, n = m.group("sch"), m.group("n")
        return f"paragraph {n}{subs} of Schedule {sch}", f"Sch. {sch} para. {n}{subs}"
    return None


_ACT_TEMPLATES: Final = (
    "{long} of the {title}",
    "{title}, {short}",
    "{short} {title}",
    "What does {long} of the {title} provide?",
    "Under {long} of the {title}, what applies?",
)
_ACT_NUMBER_TEMPLATES: Final = (
    "{title} ({year} c. {number}), {short}",
    "{year} c. {number}, {short}",
)
_SI_TEMPLATES: Final = (
    "{long} of the {title}",
    "{title}, {short}",
    "What does {long} of the {title} say?",
)
_SI_NUMBER_TEMPLATES: Final = (
    "{title} (S.I. {year}/{number}), {short}",
    "{short} of S.I. {year}/{number}",
)


def _sampleable(index: RouterIndex, info: InstrumentInfo) -> bool:
    if info.structure != "full" or len(info.title.split()) > 20:  # noqa: PLR2004 - UK-W-04
        return False
    keys = title_variants(info.title)
    return bool(keys) and index.ids("titles", keys[0]) == (info.instrument_id,)


def false_abstention_rows(index: RouterIndex) -> list[BatteryRow]:
    """Provisions drawn from the index, half from Acts and half from SIs (SIs are 85 % of
    the instruments with structure, so an unstratified draw would barely test Act forms).

    Instrument first, then a provision in it, each phrased with a template chosen by the
    same seeded generator.
    """
    rng = random.Random(SEED)
    strata: dict[bool, list[str]] = {True: [], False: []}
    for key, _ in index.tables["instruments"].prefix("uk_"):
        strata[key.startswith("uk_ukpga_")].append(key)
    rows: list[BatteryRow] = []
    tried: set[str] = set()
    per_stratum = FALSE_ABSTENTION_SAMPLE // 2
    for pool in (strata[True], strata[False]):
        drawn = 0
        while drawn < per_stratum:
            iid = rng.choice(pool)
            if iid in tried:
                continue
            tried.add(iid)
            info = index.info(iid)
            if not _sampleable(index, info):
                continue
            labelled = [
                (coordinate, label)
                for coordinate in index.coordinates.descendants(info.coordinate)
                if (provision := coordinate.removeprefix(info.coordinate + "/"))
                not in info.duplicated
                and (label := provision_label(provision)) is not None
            ]
            if not labelled:
                continue
            coordinate, (long, short) = rng.choice(labelled)
            rows.append(_phrased(rng, info, coordinate, long, short))
            drawn += 1
    return rows


def _phrased(
    rng: random.Random, info: InstrumentInfo, coordinate: str, long: str, short: str
) -> BatteryRow:
    calendar = info.coordinate.count("/") == 3  # noqa: PLR2004 - uk/series/year/n
    si = info.series in {"uksi", "wsi", "nisi"}
    templates: Sequence[str] = _SI_TEMPLATES if si else _ACT_TEMPLATES
    if calendar and (si or info.series == "ukpga"):
        templates = (*templates, *(_SI_NUMBER_TEMPLATES if si else _ACT_NUMBER_TEMPLATES))
    template = rng.choice(templates)
    title = info.title.removeprefix("The ") if si else info.title
    query = template.format(long=long, short=short, title=title, year=info.year, number=info.number)
    return BatteryRow(
        id="uk-x-0000",
        query=query[0].upper() + query[1:],
        lang="en",
        domain="uk_legislation",
        expected_status="ROUTE_BOUNDED",
        expected_coordinates=(coordinate,),
        source="sampled",
        notes=f"template {template!r}",
    )


# ---------------------------------------------------------------- assembly


def typo_split(row_id: str) -> str:
    digest = hashlib.sha256(f"{TYPO_SPLIT_SALT}|{row_id}".encode()).hexdigest()
    return "dev" if int(digest[:8], 16) % 100 < TYPO_DEV_PERCENT else "test"


def _numbered(battery: str, rows: list[BatteryRow]) -> list[BatteryRow]:
    out = []
    for i, row in enumerate(rows, start=1):
        row_id = f"uk-{battery}-{i:04d}"
        update: dict[str, object] = {"id": row_id}
        if battery == "typo":
            update["split"] = typo_split(row_id)
        out.append(BatteryRow.model_validate({**row.model_dump(), **update}))
    return out


def keep_searched(rows: list[BatteryRow], path: Path) -> list[BatteryRow]:
    """Carry each ``searched`` date over from ``path`` where the row and its check are unchanged.

    A rebuild cannot re-run ``verify_absence``; the date stays only while the search it
    records is still the one the row asks for.
    """
    if not path.exists():
        return rows
    before = {r.id: r for r in read_battery(path)}
    kept = []
    for row in rows:
        old = before.get(row.id)
        check, old_check = row.absence_verified_via, old and old.absence_verified_via
        if (
            old is not None
            and check is not None
            and old_check is not None
            and old.query == row.query
            and old_check.model_copy(update={"searched": None}) == check
        ):
            kept.append(row.model_copy(update={"absence_verified_via": old_check}))
        else:
            kept.append(row)
    return kept


def build(index_dir: Path, harvest: Path, catalogue: Path, out: Path) -> dict[str, Counter[str]]:
    router = Router.from_path(index_dir)
    index = router.index
    digest = hashlib.sha256(catalogue.read_bytes()).hexdigest()[:12]
    entries = sum(1 for _ in catalogue.open(encoding="utf-8"))
    catalogue_note = (
        f"absent from the index (snapshot {index.snapshot}) and from the catalogue "
        f"of the source's feeds ({entries:,} entries, sha256 {digest}…)"
    )
    summary: dict[str, Counter[str]] = {}
    for battery in HAND:
        rows = list(hand_rows(index, battery, catalogue_note))
        if battery == "misroute":
            rows += misroute_rows(router, harvest)
        elif battery == "false_abstention":
            rows += false_abstention_rows(index)
        path = out / f"{battery}.jsonl"
        write_battery(path, keep_searched(_numbered(battery, rows), path))
        written = read_battery(path)
        summary[battery] = Counter(r.expected_status for r in written)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--index", type=Path, default=Path("data/index"))
    parser.add_argument("--harvest", type=Path, default=Path("data/harvest/uk_citations.jsonl"))
    parser.add_argument("--catalogue", type=Path, default=Path("data/catalogue/uk_catalogue.jsonl"))
    parser.add_argument("--out", type=Path, default=BATTERY_DIR / "uk")
    args = parser.parse_args(argv)
    summary = build(args.index, args.harvest, args.catalogue, args.out)
    for battery, counts in summary.items():
        print(f"{battery:18s} {sum(counts.values()):5d}  {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
