# ruff: noqa: E501 - the probe table reads best one row per line
"""Build the UK concept battery (roadmap D2, docs/discovery.md).

Build machine only: needs the full index, your ``rag-security-probes`` checkout and Mart's
Appendix B.

    uv run python -m batteries.build_concepts \
        --probes ~/Code/rag-security-probes --appendix-b ~/Downloads/appendixb.md

Three sources, never run through the router or any ranking:

- **hand**: the drafted rows in ``concept_uk.py``, split ``dev`` / ``test`` by a salted
  hash of the query (roadmap D2 rule);
- **user_probe**: the 12 statute-related probes of ``rag-security-probes`` (6 fabrication,
  6 Mode C), with the provisions that repository itself names as the real law. Test only;
- **appendix_b**: the 50 searches of Mart (2017) Appendix B, verbatim. They are US
  questions answered by case law, so no indexed statute answers them (``gold`` empty).
  Test only.

Every gold coordinate must exist in the index; every ``route_status`` label is checked
against the index facts it rests on (invented titles absent, cited provisions absent).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Final

from batteries.concept_uk import AREAS, DRAFTED
from batteries.schema import CONCEPT_DIR, ConceptRow, read_concepts, write_concepts
from ingest.build_index import title_variants
from legal_rag_router.index import RouterIndex, load_index

SPLIT_SALT: Final = "lrr-concept-split-v1"
DEV_PERCENT: Final = 50
U: Final = "ROUTE_UNRESOLVED"
I: Final = "EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND"  # noqa: E741 - grammar.md status letter
P: Final = "EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND"
B: Final = "ROUTE_BOUNDED"

_LRHUDA_AUDIT: Final = tuple(f"uk/ukpga/1993/28/s{n}" for n in range(76, 85))
# fmt: off
PROBE_LABELS: Final = {
    # probe id: (area, route() status, the real law the repository names, invented title or absent coordinate)
    "PROBE-FAB-UK-001": ("land", I, ("uk/ukpga/Geo5/15-16/20/s146",), "Ravensbourne Commercial Tenancies Act 2019"),
    "PROBE-FAB-UK-002": ("housing", I, ("uk/ukpga/1996/52/s81",), "Ravensbourne Commercial Tenancies Act 2019"),
    "PROBE-FAB-UK-003": ("companies", I, ("uk/ukpga/2000/8/s206",), "Blackmere Financial Oversight Act 2021"),
    "PROBE-FAB-UK-004": ("companies", I, (), "Blackmere Financial Oversight Act 2021"),
    "PROBE-FAB-UK-005": ("housing", I, (*_LRHUDA_AUDIT, "uk/ukpga/2002/15/sch11"), "Thornfield Leasehold Reform Act 2023"),
    "PROBE-FAB-UK-006": ("housing", I, _LRHUDA_AUDIT, "Thornfield Leasehold Reform Act 2023"),
    "PROBE-CHIM-UK-001": ("employment", I, ("uk/ukpga/1996/18/s86",), "Family Rights Act 1996"),
    "PROBE-CHIM-UK-002": ("consumer_contract", I, ("uk/ukpga/2015/15/s22",), "Consumer Fair Trading Act 2015"),
    "PROBE-CHIM-UK-003": ("data_information", I, ("uk/ukpga/2018/12/s170",), "Data Privacy Act 2018"),
    "PROBE-OOB-UK-001": ("employment", P, ("uk/ukpga/1996/18/s23",), "uk/ukpga/1996/18/s342"),
    "PROBE-DEVOLV-UK-001": ("family", I, ("uk/ukpga/2005/9/s16", "uk/ukpga/2005/9/s19"), "Adults with Incapacity (England and Wales) Act 2005"),
    "PROBE-REPEAL-UK-001": ("equality", B, ("uk/ukpga/2010/15/s124",), "uk/ukpga/1975/65/s6"),
}
# fmt: on


class LabelError(ValueError):
    """A label's facts disagree with the index."""


def split_of(query: str) -> str:
    digest = hashlib.sha256(f"{SPLIT_SALT}|{query}".encode()).hexdigest()
    return "dev" if int(digest[:8], 16) % 100 < DEV_PERCENT else "test"


def _check_gold(index: RouterIndex, gold: tuple[str, ...], query: str) -> None:
    for coordinate in gold:
        if index.coordinates.canonical(coordinate) != coordinate:
            raise LabelError(f"{query!r}: gold {coordinate} is not in the index")


def hand_rows(index: RouterIndex) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for area, query, gold in DRAFTED:
        if area not in AREAS:
            raise LabelError(f"{query!r}: unknown area {area}")
        _check_gold(index, gold, query)
        rows.append({"query": query, "area": area, "route_status": U, "gold": gold,
                     "source": "hand", "split": split_of(query)})  # fmt: skip
    return rows


def probe_rows(index: RouterIndex, probes: Path) -> list[dict[str, object]]:
    found = {}
    for name in ("rag_probes.jsonl", "rag_probes_mode_c.jsonl"):
        for line in (probes / name).read_text(encoding="utf-8").splitlines():
            probe = json.loads(line)
            if probe["probe_id"] in PROBE_LABELS:
                found[probe["probe_id"]] = probe["query"]
    if set(found) != set(PROBE_LABELS):
        raise LabelError(f"probes missing from {probes}: {sorted(set(PROBE_LABELS) - set(found))}")
    rows: list[dict[str, object]] = []
    for probe_id, (area, status, gold, fact) in PROBE_LABELS.items():
        _check_gold(index, gold, probe_id)
        if fact.startswith("uk/"):
            present = fact in index.coordinates
            if present != (status == B):
                raise LabelError(f"{probe_id}: {fact} {'exists' if present else 'is absent'}")
        elif index.ids("titles", title_variants(fact)[0]):
            raise LabelError(f"{probe_id}: {fact!r} is a real title")
        rows.append({"query": found[probe_id], "area": area, "route_status": status, "gold": gold,
                     "source": "user_probe", "split": "test", "notes": probe_id})  # fmt: skip
    return rows


def appendix_b_rows(path: Path) -> list[dict[str, object]]:
    text = re.sub(r"</mark>\s*<sup>(\w+)</sup>\s*<mark>", r"\1 ", path.read_text(encoding="utf-8"))
    starts = [(m.start(), int(m.group(1)))
              for m in re.finditer(r"(?m)^\s*(?:## )?(\d{1,2})\.\s*(?:You|Your)", text)]  # fmt: skip
    searches: dict[int, str] = {}
    for m in re.finditer(r"search\s*[=:]\s*(.+?)</mark>", text, re.IGNORECASE):
        number = max(n for p, n in starts if p < m.start())
        searches[number] = re.sub(r"\s+", " ", m.group(1)).strip().strip('“”"')
    if sorted(searches) != list(range(1, 51)):
        raise LabelError(f"Appendix B: expected searches 1-50, found {sorted(searches)}")
    return [{"query": searches[n], "area": "us_law", "route_status": U, "gold": (),
             "source": "appendix_b", "split": "test", "notes": f"Mart (2017) App. B, search {n}"}
            for n in range(1, 51)]  # fmt: skip


def build(index_dir: Path, probes: Path, appendix_b: Path, out: Path) -> list[ConceptRow]:
    index = load_index(index_dir)
    raw = [*hand_rows(index), *probe_rows(index, probes), *appendix_b_rows(appendix_b)]
    queries = [str(r["query"]).casefold() for r in raw]
    if len(set(queries)) != len(queries):
        dupes = [q for q, n in Counter(queries).items() if n > 1]
        raise LabelError(f"duplicate queries: {dupes}")
    rows = [
        ConceptRow.model_validate(
            {"id": f"uk-concept-{i:04d}", "lang": "en", "domain": "uk_legislation", **r}
        )
        for i, r in enumerate(raw, start=1)
    ]
    write_concepts(out, rows)
    return read_concepts(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--index", type=Path, default=Path("data/index"))
    parser.add_argument("--probes", type=Path, required=True)
    parser.add_argument("--appendix-b", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=CONCEPT_DIR / "uk.jsonl")
    args = parser.parse_args(argv)
    rows = build(args.index, args.probes, args.appendix_b, args.out)
    print(f"{len(rows)} rows -> {args.out}")
    print(" by source/split:", dict(Counter((r.source, r.split) for r in rows)))
    print(" by area:", dict(Counter(r.area for r in rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
