from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from legal_rag_router.table import SortedTable, encode_table


def _open(tmp_path: Path, items: list[tuple[str, str]]) -> SortedTable:
    data, offsets = encode_table(items)
    (tmp_path / "t.tbl").write_bytes(data)
    (tmp_path / "t.off").write_bytes(offsets)
    return SortedTable.open(tmp_path / "t.tbl", tmp_path / "t.off")


def test_get_prefix_items(tmp_path: Path) -> None:
    table = _open(tmp_path, [("b", "2"), ("a", "1"), ("ab", ""), ("c/x", "3"), ("c/y", "4")])
    assert len(table) == 5
    assert table.get("a") == "1"
    assert table.get("ab") == ""  # present without a value
    assert table.get("zz") is None
    assert "b" in table
    assert "zz" not in table
    assert 3 not in table
    assert list(table.prefix("c/")) == [("c/x", "3"), ("c/y", "4")]
    assert list(table.prefix("d")) == []
    assert [k for k, _ in table.items()] == ["a", "ab", "b", "c/x", "c/y"]
    assert "5 keys" in repr(table)


def test_empty_table(tmp_path: Path) -> None:
    table = _open(tmp_path, [])
    assert len(table) == 0
    assert table.get("a") is None
    assert list(table.items()) == []


def test_unicode_keys_sort_by_bytes(tmp_path: Path) -> None:
    table = _open(tmp_path, [("código", "1"), ("codigo", "2"), ("zeta", "3")])
    assert table.get("código") == "1"
    assert table.get("codigo") == "2"


@pytest.mark.parametrize(
    "items",
    [
        [("a", "1"), ("a", "2")],
        [("", "1")],
        [("a\tb", "1")],
        [("a\nb", "1")],
        [("a", "x\ny")],
    ],
)
def test_invalid_tables_are_rejected(items: list[tuple[str, str]]) -> None:
    with pytest.raises(ValueError, match=r"invalid|duplicate"):
        encode_table(items)


_KEY = st.text(
    alphabet=st.characters(codec="utf-8", exclude_characters="\t\n"),
    min_size=1,
    max_size=12,
)


@given(st.dictionaries(_KEY, st.text(alphabet="abc,|", max_size=5), max_size=40), _KEY)
def test_lookup_matches_dict(mapping: dict[str, str], probe: str) -> None:
    table = SortedTable.from_items(mapping.items())
    for key, value in mapping.items():
        assert table.get(key) == value
    assert table.get(probe) == mapping.get(probe)
    expected = sorted((k, v) for k, v in mapping.items() if k.startswith(probe[:1]))
    assert sorted(table.prefix(probe[:1])) == expected


def test_tables_over_the_size_cap_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from legal_rag_router import table  # noqa: PLC0415

    monkeypatch.setattr(table, "_MAX_TABLE_BYTES", 10)
    with pytest.raises(ValueError, match="exceeds"):
        encode_table([("key-one", "value"), ("key-two", "value")])
