#!/usr/bin/env python3
"""\
One of a table's reference-counted lists, and the one place an entry is keyed,
claimed and released.

A format, a style, a pooled string, a formula, a control and a rich-text payload
each sit in a `TST.TableDataList` whose entries carry a refcount of the records
naming them. Numbers points every cell holding the same value at ONE entry, so a
shared entry is never overwritten: changing one cell that shares an entry with six
others must not rewrite all seven, the same aliasing hazard the frozen model closes
on the read side.

Private. Used by the table and formula features' archive halves.

UPDATES
2026-10-29  Written for PYB-278, from the string, formula, format and style pools.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/29"

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from .._generated import TSTArchives_pb2 as tst
from ..errors import WriteError
from .cells import CellRecord
from .rows import StoredTiles

type ListEntry = tst.TableDataList.ListEntry


@dataclass(slots=True)
class EntryPool[Value]:
    """A table's list of one kind of entry, each claimed by the records naming it.

    `stored` holds the value each live key names, for sharing, and `write` puts a
    value into an entry, None for a list pybers only counts. `spend` empties an
    entry released to 0 at once, where a list without one keeps the entry for
    `spentRemove` to decide at the end of the save, so a value written later in the
    same save can still share it.
    """

    dataList: tst.TableDataList
    noun: str
    write: Callable[[ListEntry, Value], None] | None = None
    stored: dict[int, Value] = field(default_factory=dict)
    spend: Callable[[ListEntry], None] | None = None
    touched: bool = False
    released: set[int] = field(default_factory=set)

    def entryFind(self, key: int) -> ListEntry | None:
        """Return one entry by key, or None when the list holds no such key."""
        for entry in self.dataList.entries:
            if entry.key == key:
                return entry
        return None

    def entryAdd(self, value: Value, refcount: int) -> int:
        """Add an entry holding a value under the next key, and return the key.

        Numbers never reuses a key, so `nextListID` only grows.
        """
        entry = self.dataList.entries.add()
        entry.key = self.dataList.nextListID
        entry.refcount = refcount
        assert self.write is not None, f"a {self.noun} list is only counted"
        self.write(entry, value)
        self.dataList.nextListID += 1
        self.stored[int(entry.key)] = value
        return int(entry.key)

    def keyFind(self, value: Value) -> int | None:
        """Return the key of a live entry holding exactly this value, if one does."""
        for key, stored in self.stored.items():
            if stored == value and self.entryFind(key) is not None:
                return key
        return None

    def keyFor(self, value: Value, previous: int | None = None) -> int:
        """Return the key a cell should name, sharing an entry when one matches.

        **Sharing is the only path, and that is what makes filling a column correct.**
        A relative formula resolves against whichever cell holds it, so one entry
        serves every cell into which it was dragged. `previous` is the key the cell
        names now, released when it stops naming it, and rewritten in place only when
        no other cell names it.
        """
        self.touched = True
        key = self.keyFind(value)
        if key is not None:
            if key != previous:
                self.claim(key)
                if previous is not None:
                    self.release(previous)
            return key
        existing = self.entryFind(previous) if previous is not None else None
        if existing is not None and existing.refcount <= 1:
            assert self.write is not None, f"a {self.noun} list is only counted"
            self.write(existing, value)
            self.stored[int(existing.key)] = value
            return int(existing.key)
        if previous is not None:
            self.release(previous)
        return self.entryAdd(value, 1)

    def claim(self, key: int, count: int = 1, where: str = "A copied record") -> None:
        """Add claims on a stored entry, refusing one the list does not hold."""
        entry = self.entryFind(key)
        if entry is None:
            raise WriteError(
                f"{where} would name {self.noun} {key}, which its table does not hold."
            )
        self.touched = True
        entry.refcount += count

    def release(self, key: int, count: int = 1) -> None:
        """Give up claims on a stored entry, never counting below 0."""
        entry = self.entryFind(key)
        if entry is None:
            return
        self.touched = True
        entry.refcount = max(0, entry.refcount - count)
        self.released.add(key)
        if entry.refcount == 0 and self.spend is not None:
            self.spend(entry)
            self.stored.pop(key, None)

    def spentRemove(
        self, tiles: StoredTiles, claims: Callable[[CellRecord], Iterable[int]]
    ) -> set[int]:
        """Remove each entry this save released to 0 that no record still names.

        Numbers removes such an entry on save, measured for a format in
        `54c-format-star-rating-cleared` and a string in `54b`. A count Numbers wrote
        can already undercount its cells, so the records are read rather than the
        count trusted: removing an entry a cell still names would orphan it.
        Returns the keys removed.
        """
        spent = {
            int(entry.key) for entry in self.dataList.entries
            if entry.key in self.released and entry.refcount == 0
        }
        if not spent:
            return spent
        for stored in tiles:
            for record in stored.records:
                spent.difference_update(claims(record))
        for position in reversed(range(len(self.dataList.entries))):
            if self.dataList.entries[position].key in spent:
                del self.dataList.entries[position]
        for key in spent:
            self.stored.pop(key, None)
        return spent


__all__ = ["EntryPool", "ListEntry"]
