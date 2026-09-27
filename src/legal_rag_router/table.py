"""Memory-mapped sorted key/value tables (roadmap decision Q-M6-1).

A table is two files:

``{name}.tbl``  UTF-8 lines ``key\\tvalue\\n`` (or ``key\\n`` when there is no value),
                sorted by the UTF-8 bytes of ``key``, keys unique
``{name}.off``  the byte offset of each line start, little-endian uint32

Opening a table maps both files; nothing is parsed up front, so load time does not grow
with the index, and memory is only the pages actually touched. A lookup is a binary search
over the offsets (about 21 comparisons for 2M keys, a few microseconds). Values are opaque
strings; callers store JSON where they need structure.

Tables are immutable once opened and safe to read from several threads.
"""

from __future__ import annotations

import mmap
import sys
from array import array
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Final

__all__ = ["SortedTable", "encode_table"]

_OFFSET_TYPECODE: Final = "I"
_MAX_TABLE_BYTES: Final = (1 << 32) - 1


def encode_table(items: Iterable[tuple[str, str]]) -> tuple[bytes, bytes]:
    """Serialise ``(key, value)`` pairs into ``(.tbl bytes, .off bytes)``.

    Raises:
        ValueError: on a duplicate key, a key or value containing a tab or newline, an
            empty key, or a table too large for 32-bit offsets.
    """
    encoded: list[tuple[bytes, bytes]] = []
    for key, value in items:
        if not key or any(ch in key for ch in "\t\n") or "\n" in value:
            raise ValueError(f"invalid table key or value: {key!r}")
        encoded.append((key.encode("utf-8"), value.encode("utf-8")))
    encoded.sort(key=lambda kv: kv[0])
    lines: list[bytes] = []
    offsets = array(_OFFSET_TYPECODE)
    position = 0
    previous: bytes | None = None
    for raw_key, raw_value in encoded:
        if raw_key == previous:
            raise ValueError(f"duplicate table key: {raw_key.decode()!r}")
        previous = raw_key
        line = raw_key + (b"\t" + raw_value if raw_value else b"") + b"\n"
        offsets.append(position)
        position += len(line)
        if position > _MAX_TABLE_BYTES:
            raise ValueError("table exceeds 4 GiB")
        lines.append(line)
    if sys.byteorder != "little":  # pragma: no cover - big-endian hosts only
        offsets.byteswap()
    return b"".join(lines), offsets.tobytes()


class SortedTable:
    """Read-only view of a sorted table, memory-mapped from disk."""

    __slots__ = ("_data", "_maps", "_name", "_offsets")

    def __init__(
        self, data: bytes | mmap.mmap, offsets: memoryview | array[int], name: str
    ) -> None:
        self._data = data
        self._offsets = offsets
        self._name = name
        self._maps: tuple[mmap.mmap, ...] = ()

    @classmethod
    def open(cls, tbl: Path, off: Path) -> SortedTable:
        """Map ``tbl``/``off`` into memory. Empty tables need no mapping."""
        name = tbl.stem
        if tbl.stat().st_size == 0:
            return cls(b"", array(_OFFSET_TYPECODE), name)
        with tbl.open("rb") as fh:
            data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        with off.open("rb") as fh:
            off_map = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        offsets: memoryview | array[int]
        if sys.byteorder == "little":
            offsets = memoryview(off_map).cast(_OFFSET_TYPECODE)
        else:  # pragma: no cover - big-endian hosts only
            offsets = array(_OFFSET_TYPECODE, off_map[:])
            offsets.byteswap()
        table = cls(data, offsets, name)
        table._maps = (data, off_map)
        return table

    @classmethod
    def from_items(cls, items: Iterable[tuple[str, str]], name: str = "table") -> SortedTable:
        """Build an in-memory table (tests and tools)."""
        data, raw_offsets = encode_table(items)
        offsets = array(_OFFSET_TYPECODE)
        offsets.frombytes(raw_offsets)
        if sys.byteorder != "little":  # pragma: no cover
            offsets.byteswap()
        return cls(data, offsets, name)

    def __len__(self) -> int:
        return len(self._offsets)

    def __repr__(self) -> str:
        return f"SortedTable({self._name!r}, {len(self)} keys)"

    # ------------------------------------------------------------------ internals

    def _line(self, index: int) -> tuple[int, int, int]:
        """(start, key_end, line_end) of line ``index``; line_end excludes the newline."""
        start = self._offsets[index]
        end = (
            self._offsets[index + 1] - 1 if index + 1 < len(self._offsets) else len(self._data) - 1
        )
        tab = self._data.find(b"\t", start, end)
        return start, (tab if tab != -1 else end), end

    def _key_at(self, index: int) -> bytes:
        start, key_end, _ = self._line(index)
        return self._data[start:key_end]

    def _lower_bound(self, key: bytes) -> int:
        lo, hi = 0, len(self._offsets)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._key_at(mid) < key:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def _entry(self, index: int) -> tuple[str, str]:
        start, key_end, end = self._line(index)
        key = self._data[start:key_end].decode("utf-8")
        value = self._data[key_end + 1 : end].decode("utf-8") if key_end < end else ""
        return key, value

    # ------------------------------------------------------------------ public

    def get(self, key: str) -> str | None:
        """The value stored for ``key`` (``""`` if the key has none), or ``None``."""
        raw = key.encode("utf-8")
        index = self._lower_bound(raw)
        if index < len(self._offsets) and self._key_at(index) == raw:
            return self._entry(index)[1]
        return None

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self.get(key) is not None

    def prefix(self, prefix: str) -> Iterator[tuple[str, str]]:
        """Every ``(key, value)`` whose key starts with ``prefix``, in key order."""
        raw = prefix.encode("utf-8")
        index = self._lower_bound(raw)
        while index < len(self._offsets) and self._key_at(index).startswith(raw):
            yield self._entry(index)
            index += 1

    def items(self) -> Iterator[tuple[str, str]]:
        """Every ``(key, value)`` in key order."""
        for index in range(len(self._offsets)):
            yield self._entry(index)
