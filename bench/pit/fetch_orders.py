"""Fetch the Employment Rights (Increase of Limits) Orders as made, for the limits table.

    uv run python -m bench.pit.fetch_orders --contact https://github.com/you/your-fork

The scraped data cannot supply past limits: revoked Orders are blanked to dots and the Act
holds only its current sums (``legal-rag-temporal`` PLAN §2). Each Order's ``/made`` text is
fetched once through :class:`ingest.cache.Fetcher` (1 request per 5 s, identified client,
cached) and written to ``bench/pit/orders/`` so the table can be rebuilt and checked offline.
The list is the GB Orders in the catalogue from SI 2010/2926; :mod:`bench.pit.limits` checks it is
complete by following each Order's revocation of the one before.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

from ingest.cache import Fetcher

REPO: Final = Path(__file__).resolve().parents[2]
ORDERS_DIR: Final = Path(__file__).resolve().parent / "orders"
ORDERS: Final = (
    "uksi/2010/2926",
    "uksi/2011/3006",
    "uksi/2012/3007",
    "uksi/2014/382",
    "uksi/2015/226",
    "uksi/2016/288",
    "uksi/2017/175",
    "uksi/2018/194",
    "uksi/2019/324",
    "uksi/2020/205",
    "uksi/2021/208",
    "uksi/2022/182",
    "uksi/2023/318",
    "uksi/2024/213",
    "uksi/2025/348",
    "uksi/2026/310",
)
"""Employment Rights (Increase of Limits) Orders, GB, from the catalogue, from SI 2010/2926.

The table starts there: see :mod:`bench.pit.limits` for why SI 2008/3055 and SI 2009/3274 are
not enough to go back further.
"""


def made_url(order: str) -> str:
    return f"https://www.legislation.gov.uk/{order}/made/data.xml"


def order_path(order: str) -> Path:
    return ORDERS_DIR / (order.replace("/", "-") + ".xml")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--contact", required=True, help="e-mail or URL for the User-Agent")
    parser.add_argument("--cache", type=Path, default=REPO / ".cache" / "http")
    args = parser.parse_args(argv)
    ORDERS_DIR.mkdir(exist_ok=True)
    with Fetcher(args.cache, f"legal-rag-router-bench/0.1 (+{args.contact})") as fetcher:
        for order in ORDERS:
            result = fetcher.get(made_url(order))
            if result.status != 200:  # noqa: PLR2004
                print(f"{order}: HTTP {result.status}", file=sys.stderr)
                return 1
            order_path(order).write_bytes(result.read())
            print(f"{order}: {'cache' if result.from_cache else 'fetched'}")
        print(f"requests made: {fetcher.requests_made}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
