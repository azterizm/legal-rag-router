"""Coverage sweep over harvested citations (plan "Missed patterns" 2; roadmap D3, M7k).

The statute book marks every cross-reference with its target, which gives real citations
written by people together with the right answer. This module:

1. **Splits** the harvest, before the grammar sees any of it, into ``sweep`` and
   ``heldout`` by a salted SHA-256 of each citation's identity. The rule is deterministic,
   stable as the harvest grows, and recorded in ``reports/harvest-split.json``. Held-out
   citations are never swept: they are the source of the misroute battery (M8).
2. **Sweeps** the ``sweep`` side: each citation is replayed as it appears in the source
   text, and the router's answer is classified against the source's own target.

Usage::

    uv run python -m eval.sweep split-manifest --out reports/harvest-split.json
    uv run python -m eval.sweep run --harvest data/harvest/uk_citations.jsonl \\
        --index data/index --sample 20000 --out reports/coverage-sweep-uk.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from legal_rag_router import Coordinate, Router, RouteStatus

__all__ = ["HELDOUT_PERCENT", "SPLIT_SALT", "Outcome", "bucket", "classify", "main", "replay_query"]

SPLIT_SALT: Final = "lrr-harvest-split-v1"
HELDOUT_PERCENT: Final = 20
WINDOW_BEFORE: Final = 160
WINDOW_AFTER: Final = 120

Outcome = Literal[
    "correct", "misroute", "dropped", "wrong_provision", "miss", "ambiguous",
    "false_abstention", "out_of_coverage",
]  # fmt: skip


def bucket(citation: dict[str, object]) -> Literal["sweep", "heldout"]:
    """The split a harvested citation belongs to (deterministic, salt-versioned)."""
    identity = "|".join(
        str(citation.get(k) or "")
        for k in ("source_coordinate", "citation_id", "text", "target_uri")
    )
    digest = hashlib.sha256(f"{SPLIT_SALT}|{identity}".encode()).hexdigest()
    return "heldout" if int(digest[:8], 16) % 100 < HELDOUT_PERCENT else "sweep"


def split_manifest() -> dict[str, object]:
    return {
        "salt": SPLIT_SALT,
        "heldout_percent": HELDOUT_PERCENT,
        "identity_fields": ["source_coordinate", "citation_id", "text", "target_uri"],
        "rule": "heldout iff int(sha256(salt|identity)[:8], 16) % 100 < heldout_percent",
        "created": datetime.now(UTC).date().isoformat(),
        "note": "Fixed before the grammar saw any harvested citation (roadmap D3).",
    }


_CLAUSE_START_RE: Final = re.compile(r"(?:;\s+|\.\s+(?=[A-Z(])|\bby(?: virtue of)?\s+)")
_CLAUSE_END_RE: Final = re.compile(r";|\.\s+(?=[A-Z])")


def replay_query(citation: dict[str, object]) -> str:
    """The citation as its author wrote it: the clause of the source text that holds it."""
    return replay(citation)[0]


def replay(citation: dict[str, object]) -> tuple[str, int, int]:
    """:func:`replay_query`, with the cited text's span inside the returned query.

    Starts after the last clause break before the citation (``;``, a sentence end, or the
    agentive "by" of an amendment note, "Words in s. 109(1) inserted by <citation>", whose
    leading provision belongs to the host instrument, not to the citation), and ends at
    the next clause break after it. Both ends are bounded by fixed windows.
    """
    context = str(citation.get("context") or citation.get("text") or "")
    span = citation.get("span") or (0, len(context))
    start, end = int(span[0]), int(span[1])  # type: ignore[index]
    lo = max(0, start - WINDOW_BEFORE)
    breaks = [m.end() for m in _CLAUSE_START_RE.finditer(context, lo, start)]
    if breaks:
        lo = breaks[-1]
    elif lo > 0:
        cut = context.find(" ", lo)
        lo = cut + 1 if 0 <= cut < start else lo
    hi = min(len(context), end + WINDOW_AFTER)
    closing = _CLAUSE_END_RE.search(context, end, hi)
    if closing is not None:
        hi = closing.start()
    elif hi < len(context):
        cut = context.rfind(" ", end, hi)
        hi = cut if cut > end else hi
    clause = context[lo:hi]
    lead = len(clause) - len(clause.lstrip())
    return clause.strip(), start - lo - lead, end - lo - lead


def _related(a: Coordinate, b: Coordinate) -> bool:
    return a == b or a.is_ancestor_of(b) or b.is_ancestor_of(a)


def classify(router: Router, citation: dict[str, object]) -> tuple[Outcome, str]:
    """Route a harvested citation and compare with the source's own target.

    A bound result without the target is a ``misroute`` when one of the router's citations
    covers the cited text (it read that citation and bound something else), and ``dropped``
    when none does (it bound other citations in the clause and never saw this one).
    """
    query, cited_start, cited_end = replay(citation)
    target = Coordinate.parse(str(citation["target_coordinate"]))
    result = router.route(query)
    status = result.status
    if status is RouteStatus.BOUNDED:
        instruments = {c.instrument_id for c in result.coordinates}
        if target.instrument_id not in instruments:
            seen = any(c.span[0] < cited_end and cited_start < c.span[1] for c in result.citations)
            return ("misroute" if seen else "dropped"), query
        if target.is_instrument or any(
            _related(c, target)
            for c in result.coordinates
            if c.instrument_id == target.instrument_id
        ):
            return "correct", query
        return "wrong_provision", query
    outcome: Outcome = {
        RouteStatus.UNRESOLVED: "miss",
        RouteStatus.AMBIGUOUS: "ambiguous",
        RouteStatus.OUT_OF_COVERAGE: "out_of_coverage",
    }.get(status, "false_abstention")  # type: ignore[assignment]
    return outcome, query


def _shape(text: str) -> str:
    return re.sub(r"\d+", "N", re.sub(r"\s+", " ", text.strip().casefold()))[:60]


@dataclass
class SweepReport:
    counts: Counter[str]
    examples: dict[str, list[tuple[str, str, str]]]
    miss_shapes: Counter[str]
    considered: int
    skipped: Counter[str]


def eligible(router: Router, rows: Iterable[dict[str, object]]) -> Iterator[dict[str, object]]:
    for row in rows:
        target = row.get("target_coordinate")
        if row.get("kind") != "citation" or not target or bucket(row) != "sweep":
            continue
        try:
            coordinate = Coordinate.parse(str(target))
        except ValueError:
            continue
        if router.index.instrument(coordinate.instrument_id) is None:
            continue  # target not indexed (other series, or not downloaded yet)
        if str(coordinate) not in router.index.coordinates:
            continue
        yield row


def run(router: Router, harvest: Path, *, sample: int | None, seed: int = 20260927) -> SweepReport:
    with harvest.open(encoding="utf-8") as fh:
        rows = list(eligible(router, (json.loads(line) for line in fh if line.strip())))
    if sample is not None and len(rows) > sample:
        rows = random.Random(seed).sample(rows, sample)  # noqa: S311 - reproducible sample
    counts: Counter[str] = Counter()
    miss_shapes: Counter[str] = Counter()
    examples: dict[str, list[tuple[str, str, str]]] = {}
    for row in rows:
        outcome, query = classify(router, row)
        counts[outcome] += 1
        if outcome == "miss":
            miss_shapes[_shape(str(row["text"]))] += 1
        bucket_examples = examples.setdefault(outcome, [])
        if len(bucket_examples) < 25:  # noqa: PLR2004
            bucket_examples.append((str(row["text"]), query, str(row["target_coordinate"])))
    return SweepReport(counts, examples, miss_shapes, len(rows), Counter())


def render(report: SweepReport, *, index_label: str) -> str:
    total = max(report.considered, 1)
    intro = (
        f"Index: `{index_label}`. Citations swept: {report.considered} (the `sweep` side of "
        f"the harvest split; {HELDOUT_PERCENT} % is held out for the misroute battery and "
        "never swept). Quoted source text: legislation.gov.uk, Crown copyright, Open "
        "Government Licence v3.0."
    )
    lines = [
        "# Coverage sweep (UK)",
        "",
        intro,
        "",
        "| Outcome | Count | Share |",
        "|---|---|---|",
    ]
    for outcome, count in report.counts.most_common():
        lines.append(f"| {outcome} | {count} | {100 * count / total:.2f} % |")
    lines += [
        "",
        (
            "`misroute`: the router read the cited text and bound another instrument. "
            "`dropped`: it bound other citations in the same clause and never recognised "
            "this one."
        ),
    ]
    lines += ["", "## Most frequent missed citation shapes", "", "| Shape | Count |", "|---|---|"]
    lines += [f"| `{shape}` | {count} |" for shape, count in report.miss_shapes.most_common(40)]
    for outcome in (
        "misroute", "dropped", "wrong_provision", "false_abstention", "miss", "ambiguous",
    ):  # fmt: skip
        rows = report.examples.get(outcome, [])
        if not rows:
            continue
        lines += [
            "",
            f"## Examples: {outcome}",
            "",
            "| Citation | Query (source text) | Target |",
            "|---|---|---|",
        ]
        for text, query, target in rows[:15]:
            safe = query.replace("|", "\\\\|")[:220]
            lines.append(f"| `{text[:40]}` | {safe} | `{target}` |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    manifest = sub.add_parser("split-manifest")
    manifest.add_argument("--out", type=Path, required=True)
    runner = sub.add_parser("run")
    runner.add_argument("--harvest", type=Path, required=True)
    runner.add_argument("--index", type=Path, required=True)
    runner.add_argument("--sample", type=int, default=None)
    runner.add_argument("--out", type=Path, required=True)
    runner.add_argument("--index-label", help="how the report names the index (default: its path)")
    args = parser.parse_args(argv)

    if args.command == "split-manifest":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(split_manifest(), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
        return 0
    router = Router.from_path(args.index)
    report = run(router, args.harvest, sample=args.sample)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        render(report, index_label=args.index_label or str(args.index)), encoding="utf-8"
    )
    print(json.dumps(dict(report.counts)), f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
