"""The sealed run (plan step 9, roadmap M10): every plan battery through ``Router.route``.

    uv run python -m eval.run --seal seals/battery-2026-09-29.json

It refuses to start unless the battery seal verifies (batteries, index files, aliases,
harvest split, typo thresholds, package version) and every tracked file is committed, so the
commit it records is the code that ran. It writes:

- ``results/{jurisdiction}-run-{date}.json``: run metadata, the metrics per domain, and every
  row's outcome;
- ``results/{jurisdiction}-run-{date}.md``: the per-domain table;
- ``seals/results-{date}.json``: the SHA-256 of both, citing the battery seal.

Metrics and scoring: :mod:`eval.metrics`. Only ``route`` runs here; discovery has its own
sealed run (``eval.discovery``, roadmap D5).
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from batteries.schema import BATTERIES, BatteryRow, read_battery
from eval.metrics import Outcome, domain_metrics
from eval.seal import REPO, SealError, _git, seal_results, verify_battery_seal
from legal_rag_router import Router, __version__


def route_row(router: Router, battery: str, row: BatteryRow) -> Outcome:
    result = router.route(row.query, context=list(row.context) if row.context else None)
    return Outcome(
        battery=battery,
        row_id=row.id,
        source=row.source,
        expected_status=row.expected_status,
        expected=row.expected_coordinates,
        status=result.status.value,
        bound=tuple(str(c) for c in result.coordinates),
        top_candidate=str(result.candidates[0].coordinate) if result.candidates else None,
        corrected=bool(result.corrections),
        split=row.split,
    )


def run(router: Router, battery_dir: Path) -> list[Outcome]:
    return [
        route_row(router, battery, row)
        for battery in BATTERIES
        for row in read_battery(battery_dir / f"{battery}.jsonl")
    ]


_TABLE = (
    ("collision", "Collision (bound to another instrument)"),
    ("misroute", "Misroute (bound, expected not met)"),
    ("misroute_wrong_instrument", "  of which: wrong instrument"),
    ("miss_heldout", "Miss (held-out real citations, unresolved)"),
    ("false_abstention", "False abstention (real law refused)"),
    ("covered_reported_out_of_coverage", "Covered law reported out of coverage"),
    ("uncovered_refused", "Out-of-coverage law refused"),
    ("bound_on_invented", "Bound on invented law"),
    ("strict_abstention", "Strict abstention on invented law"),
    ("typo_auto_correct_precision", "Typo: auto-correct precision"),
    ("typo_auto_correct_recall", "Typo: auto-correct recall"),
    ("typo_clarify_recall", "Typo: clarify recall"),
    ("typo_bound_when_it_should_not", "Typo: bound when it should not"),
)


def markdown(meta: dict[str, Any], metrics: dict[str, dict[str, Any]]) -> str:
    lines = [
        f"# Sealed run: {meta['jurisdiction'].upper()} batteries ({meta['date']})",
        "",
        (
            f"Battery seal `{meta['battery_seal']}` (`{meta['battery_seal_sha256'][:16]}…`), "
            f"commit `{meta['git_commit'][:12]}`, index snapshot {meta['index_snapshot']}, "
            f"{meta['python']} on {meta['platform']}. Rates are counts over rows; the last "
            "column is the one-sided 95 % Clopper-Pearson upper bound."
        ),
        "",
    ]
    for domain, values in metrics.items():
        lines += [f"## {domain}", "", "| Metric | Count | Rows | Rate | 95 % upper |",
                  "|---|---|---|---|---|"]  # fmt: skip
        for key, label in _TABLE:
            v = values[key]
            lines.append(f"| {label} | {v['count']} | {v['total']} | {100 * v['rate']:.2f} % "
                         f"| {100 * v['upper_95']:.2f} % |")  # fmt: skip
        lines += [
            "",
            "| Battery | Rows | Status as expected | Met (bound rows) |",
            "|---|---|---|---|",
        ]
        for name, b in values["batteries"].items():
            met = f"{b['met']['count']}/{b['met']['total']}" if "met" in b else "—"
            s = b["status_as_expected"]
            lines.append(f"| {name} | {b['rows']} | {s['count']}/{s['total']} | {met} |")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--seal", type=Path, required=True, help="the tagged battery seal")
    parser.add_argument("--index", type=Path, default=REPO / "data" / "index")
    parser.add_argument("--jurisdiction", default="uk")
    parser.add_argument("--repo", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    repo: Path = args.repo
    try:
        seal = verify_battery_seal(args.seal, repo, args.index)
    except SealError as exc:
        print(f"REFUSED: {exc}")
        return 1
    if seal["kind"] != "battery":
        print(f"REFUSED: {args.seal} is a {seal['kind']} seal, not the battery seal")
        return 1
    if _git(repo, "status", "--porcelain", "--untracked-files=no"):
        print("REFUSED: commit every tracked change first, so the recorded commit is what ran")
        return 1
    started = datetime.now(UTC)
    router = Router.from_path(args.index)
    battery_dir = repo / "batteries" / args.jurisdiction
    outcomes = run(router, battery_dir)
    date = started.date().isoformat()
    meta = {
        "jurisdiction": args.jurisdiction,
        "date": date,
        "started": started.isoformat(timespec="seconds"),
        "finished": datetime.now(UTC).isoformat(timespec="seconds"),
        "battery_seal": args.seal.name,
        "battery_seal_sha256": seal["seal_sha256"],
        "git_commit": _git(repo, "rev-parse", "HEAD"),
        "package_version": __version__,
        "index_snapshot": router.index.snapshot,
        "python": f"Python {sys.version.split()[0]}",
        "platform": platform.platform(),
    }
    domains: dict[str, list[Outcome]] = {}
    rows = {r.id: r for b in BATTERIES for r in read_battery(battery_dir / f"{b}.jsonl")}
    for outcome in outcomes:
        domains.setdefault(rows[outcome.row_id].domain, []).append(outcome)
    metrics = {domain: domain_metrics(rows_) for domain, rows_ in sorted(domains.items())}
    results = repo / "results"
    results.mkdir(exist_ok=True)
    json_path = results / f"{args.jurisdiction}-run-{date}.json"
    md_path = results / f"{args.jurisdiction}-run-{date}.md"
    payload = {"run": meta, "metrics": metrics, "rows": [_row(o) for o in outcomes]}
    json_path.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown(meta, metrics) + "\n", encoding="utf-8")
    sealed = seal_results(repo, [json_path, md_path], args.seal)
    seal_path = repo / "seals" / f"results-{date}.json"
    seal_path.write_text(json.dumps(sealed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(md_path.read_text(encoding="utf-8"))
    print(f"results sealed: {sealed['seal_sha256']} -> {seal_path}")
    return 0


def _row(outcome: Outcome) -> dict[str, Any]:
    return {
        "battery": outcome.battery,
        "id": outcome.row_id,
        "source": outcome.source,
        "split": outcome.split,
        "expected_status": outcome.expected_status,
        "expected": list(outcome.expected),
        "status": outcome.status,
        "bound": list(outcome.bound),
        "top_candidate": outcome.top_candidate,
        "corrected": outcome.corrected,
        "met": outcome.met,
        "wrong_instrument": outcome.wrong_instrument,
    }


if __name__ == "__main__":
    raise SystemExit(main())
