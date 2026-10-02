"""Package the router index and concept index as release assets (roadmap M12).

Usage: python scripts/package_index.py OUT_DIR [--index DIR] [--concepts DIR]

Each directory is loaded and verified first (every file against its manifest hash), then
written to ``OUT_DIR`` as ``{kind}-{jurisdiction}-{snapshot}.tar.gz`` with its files at the
archive root, so the README's commands unpack it straight into ``data/index`` or
``data/concepts``. The archive holds exactly the directory's files, so the unpacked index still
verifies against the battery seal. Archives are reproducible: names sorted, owners and
modes normalised, timestamps fixed. ``NOTICE`` and ``SHA256SUMS`` (over every asset) are
written beside the archives. Refuses to overwrite an existing asset.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import shutil
import sys
import tarfile
from pathlib import Path

from legal_rag_router import load_index
from legal_rag_router.concepts import load_concepts

REPO = Path(__file__).resolve().parent.parent
NOTICE = REPO / "NOTICE"
JURISDICTION = "uk"
# 2026-09-28T00:00:00Z: a fixed timestamp keeps the archives byte-identical between builds.
MTIME = 1790553600


def _info(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mtime = MTIME
    info.mode = 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def archive(source: Path, target: Path) -> None:
    """Write ``source``'s files to ``target`` (a reproducible ``.tar.gz``)."""
    files = sorted(p for p in source.iterdir() if p.is_file())
    with (
        target.open("xb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar,
    ):
        for path in files:
            with path.open("rb") as fh:
                tar.addfile(_info(path.name, path.stat().st_size), fh)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package(out: Path, index: Path, concepts: Path | None) -> list[Path]:
    """Verify, archive and checksum. Returns the asset paths, ``SHA256SUMS`` last."""
    out.mkdir(parents=True, exist_ok=True)
    snapshot = load_index(index).snapshot
    sources = [("index", index)]
    if concepts is not None:
        found = str(load_concepts(concepts).manifest.get("snapshot"))
        if found != snapshot:
            raise SystemExit(f"concept index snapshot {found} differs from the index's {snapshot}")
        sources.append(("concepts", concepts))
    assets: list[Path] = []
    for kind, source in sources:
        target = out / f"{kind}-{JURISDICTION}-{snapshot}.tar.gz"
        archive(source, target)
        assets.append(target)
    notice = out / "NOTICE"
    if notice.exists():
        raise FileExistsError(notice)
    shutil.copyfile(NOTICE, notice)
    assets.append(notice)
    sums = out / "SHA256SUMS"
    with sums.open("x", encoding="utf-8") as fh:
        fh.writelines(f"{sha256(p)}  {p.name}\n" for p in assets)
    return [*assets, sums]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--index", type=Path, default=REPO / "data" / "index")
    parser.add_argument("--concepts", type=Path, default=REPO / "data" / "concepts")
    parser.add_argument("--no-concepts", action="store_true")
    args = parser.parse_args(argv)
    concepts = None if args.no_concepts else args.concepts
    for path in package(args.out, args.index, concepts):
        print(f"{path.stat().st_size / 1e6:9.1f} MB  {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
