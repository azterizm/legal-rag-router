"""The limits table (bench/pit) is exactly what the Orders as made say, and the chain is whole."""

import dataclasses
import hashlib
import json
from collections import defaultdict

import pytest

from bench.pit.fetch_orders import ORDERS, order_path
from bench.pit.limits import LIMITS_JSON, TARGETS, LimitsError, build, load_orders, render


@pytest.fixture(scope="module")
def table() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = json.loads(LIMITS_JSON.read_text(encoding="utf-8"))
    return rows


def test_committed_table_is_rebuilt_from_the_orders() -> None:
    assert LIMITS_JSON.read_text(encoding="utf-8") == render(build(load_orders()))


def test_every_order_listed_is_on_disk_under_its_own_identity() -> None:
    assert sorted(o.si for o in load_orders()) == sorted(f"uk/{o}" for o in ORDERS)


def test_each_row_traces_to_its_source_bytes(table: list[dict[str, object]]) -> None:
    for row in table:
        raw = order_path(str(row["si"])[3:]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["xml_sha256"]
        assert str(row["amount"]) in raw.decode("utf-8")


def test_intervals_are_contiguous_per_provision(table: list[dict[str, object]]) -> None:
    by_coordinate: dict[object, list[dict[str, object]]] = defaultdict(list)
    for row in table:
        by_coordinate[row["coordinate"]].append(row)
    assert set(by_coordinate) == set(TARGETS.values())
    for rows in by_coordinate.values():
        assert [r["valid_to"] for r in rows[:-1]] == [r["valid_from"] for r in rows[1:]]
        assert rows[-1]["valid_to"] is None
        assert [r["previous_amount"] for r in rows[1:]] == [r["amount"] for r in rows[:-1]]


def test_a_missing_order_breaks_the_chain() -> None:
    orders = load_orders()
    del orders[3]
    with pytest.raises(LimitsError, match=r"missing from the chain|not revoked"):
        build(orders)


def test_a_changed_figure_breaks_the_chain() -> None:
    orders = load_orders()
    rows = tuple(
        dataclasses.replace(r, new="£99,999") if "124" in r.provision else r for r in orders[5].rows
    )
    orders[5] = dataclasses.replace(orders[5], rows=rows)
    with pytest.raises(LimitsError, match="missing from the chain"):
        build(orders)


def test_the_cs2_probe_row(table: list[dict[str, object]]) -> None:
    rows = [
        r
        for r in table
        if r["coordinate"] == "uk/ukpga/1996/18/s124"
        and str(r["valid_from"]) <= "2012-01-01" < str(r["valid_to"])
    ]
    assert [(r["amount"], r["si"]) for r in rows] == [("£68,400", "uk/uksi/2010/2926")]
