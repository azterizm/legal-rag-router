"""Battery seal (plan step 9): canonical-JSON SHA-256 over everything a run depends on.

    uv run python -m eval.seal battery            # writes seals/battery-YYYY-MM-DD.json
    uv run python -m eval.seal verify seals/battery-YYYY-MM-DD.json

The seal records the SHA-256 of every battery file, every index file (the index is not in
git, so its bytes are pinned here), the alias TOMLs, the frozen typo thresholds, the package
version, the harvest split manifest (which citations are held out, roadmap D3) and the git
commit the batteries were sealed at. It is committed and tagged before
the run; ``verify`` recomputes it and names every file that differs, and the M10 runner
refuses to start on any difference. Same approach as the benchmark audit seal
(``jev-vs-sovereign-benchmark/src/engine/audit_seal.py``), without its ML imports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from legal_rag_router import __version__
from legal_rag_router.typo import DEFAULT_POLICY

REPO: Final = Path(__file__).resolve().parents[1]
SEAL_FORMAT: Final = 1


class SealError(RuntimeError):
    """The seal cannot be made (dirty tree) or does not match (named differences)."""


def canonical(payload: object) -> bytes:
    """The one byte form a payload is hashed in: sorted keys, no spaces, UTF-8."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_hashes(paths: Iterable[Path], root: Path) -> dict[str, str]:
    out = {}
    for path in sorted(paths):
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        out[path.relative_to(root).as_posix()] = digest.hexdigest()
    return out


def battery_contents(repo: Path, index_dir: Path) -> dict[str, Any]:
    """Everything a sealed run depends on, by content hash."""
    manifest = json.loads((index_dir / "index-manifest.json").read_text(encoding="utf-8"))
    return {
        "batteries": _file_hashes((repo / "batteries").glob("*/*.jsonl"), repo),
        "index": {
            "snapshot": manifest["snapshot"],
            "format_version": manifest["format_version"],
            "files": _file_hashes((p for p in index_dir.iterdir() if p.is_file()), index_dir),
        },
        "aliases": _file_hashes((repo / "aliases").glob("*.toml"), repo),
        "harvest_split": _file_hashes([repo / "reports" / "harvest-split.json"], repo),
        "typo_policy": asdict(DEFAULT_POLICY),
        "package_version": __version__,
    }


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 - fixed git arguments, no shell
        ["git", *args],  # noqa: S607 - git from PATH, as every developer tool here
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def seal_battery(repo: Path, index_dir: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """The battery seal for the current commit. Tracked files must be committed first."""
    if _git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise SealError("commit every tracked change before sealing")
    contents = battery_contents(repo, index_dir)
    return {
        "seal_format": SEAL_FORMAT,
        "kind": "battery",
        "sealed_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "git_commit": _git(repo, "rev-parse", "HEAD"),
        "battery_sha256": sha256_of(canonical(contents["batteries"])),
        "seal_sha256": sha256_of(canonical(contents)),
        "contents": contents,
    }


def _differences(sealed: Mapping[str, Any], now: Mapping[str, Any], path: str = "") -> list[str]:
    out = []
    for key in sorted(set(sealed) | set(now)):
        where = f"{path}{key}"
        a, b = sealed.get(key), now.get(key)
        if isinstance(a, Mapping) and isinstance(b, Mapping):
            out += _differences(a, b, f"{where}/")
        elif a != b:
            out.append(f"{where}: sealed {a!r}, now {b!r}")
    return out


def verify_battery_seal(seal_path: Path, repo: Path, index_dir: Path) -> dict[str, Any]:
    """The seal, if everything it pins is unchanged. Raises :class:`SealError` otherwise."""
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if seal.get("kind") != "battery" or seal.get("seal_format") != SEAL_FORMAT:
        raise SealError(f"{seal_path} is not a format-{SEAL_FORMAT} battery seal")
    if sha256_of(canonical(seal["contents"])) != seal["seal_sha256"]:
        raise SealError(f"{seal_path} has been edited: its contents no longer match its hash")
    differences = _differences(seal["contents"], battery_contents(repo, index_dir))
    if differences:
        raise SealError("the sealed inputs changed:\n  " + "\n  ".join(differences))
    return dict(seal)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--repo", type=Path, default=REPO, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("battery", help="seal the batteries at the current commit")
    make.add_argument("--index", type=Path, default=REPO / "data" / "index")
    make.add_argument("--out", type=Path, default=None)
    check = sub.add_parser("verify", help="check a battery seal against the working tree")
    check.add_argument("seal", type=Path)
    check.add_argument("--index", type=Path, default=REPO / "data" / "index")
    args = parser.parse_args(argv)
    try:
        if args.command == "battery":
            seal = seal_battery(args.repo, args.index)
            out = args.out or args.repo / "seals" / f"battery-{seal['sealed_at'][:10]}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"sealed {len(seal['contents']['batteries'])} battery files at "
                  f"{seal['git_commit'][:12]}: {seal['seal_sha256']} -> {out}")  # fmt: skip
        else:
            seal = verify_battery_seal(args.seal, args.repo, args.index)
            print(f"OK: {args.seal} matches ({seal['seal_sha256']})")
    except SealError as exc:
        print(f"SEAL ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
