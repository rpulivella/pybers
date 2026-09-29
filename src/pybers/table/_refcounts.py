#!/usr/bin/env python3
"""\
The refcounts a table's lists keep: which records claim which entry, and how many.

A format, a style, a pooled string and a rich-text payload each carry a refcount of
the records naming them. A record written moves the counts its slots changed, a
record removed releases what it named, and an entry released to 0 that no record
still names is removed at the end of the save, as Numbers removes it.

Private. Part of the table feature's archive half.

UPDATES
2026-09-29  A copied record claims its string and style entries, for PYB-118.
2026-09-22  Split out of the table writer for PYB-113.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/22"

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from .._generated import TSTArchives_pb2 as tst
from .._persistence import chooseOffsetUnit, decodeRecord, decodeRow
from .._persistence.cells import CellRecord, listReferenceSlots
from .._persistence.index import ArchiveIndex
from ..errors import WriteError
from ._read import readStringTable

# A pooled string cell holds a four-byte key where a number holds sixteen bytes of
# decimal128, so changing between them moves every trailing reference.
stringTypeByte: int = 3


# A rich-text cell names its payload by key, and an entry's refcount is how many such
# records name it, which reproduces all 16 rich-text lists in the documents.
richTextTypeByte: int = 9


# Which bit carries which format reference, measured across the documents: a slot is
# per format KIND rather than per cell, which is why a number and a string in one
# table put their format in different places. See findings-01-values.md.
numberFormatSlot: tuple[int, int] = (9, 0x20)
currencyFormatSlot: tuple[int, int] = (9, 0x40)
dateFormatSlot: tuple[int, int] = (9, 0x80)
durationFormatSlot: tuple[int, int] = (10, 0x01)
textFormatSlot: tuple[int, int] = (10, 0x02)
checkboxFormatSlot: tuple[int, int] = (10, 0x04)


# A format's refcount is how often its key sits in these slots, which reproduces
# every format list in the documents. The order is Numbers' own: a kind is its
# position here counted from 1, which is what `displayedKindSlot` stores.
countedFormatSlots: tuple[tuple[int, int], ...] = (
    numberFormatSlot, currencyFormatSlot, dateFormatSlot,
    durationFormatSlot, textFormatSlot, checkboxFormatSlot,
)


# A style's refcount is how often its key sits in these two slots, which reproduces
# every style list in the documents, measured 2026-09-15 for PYB-92.
countedStyleSlots: tuple[tuple[int, int], ...] = ((8, 0x20), (8, 0x40))


@dataclass
class StringPool:
    """A table's pooled strings, and the one place a written one is added.

    The counterpart of `FormulaPool` and shaped like it on purpose. Numbers points
    every cell holding the same text at ONE entry and keeps a refcount, so writing
    an entry per cell diverges from what Numbers itself writes the moment the same
    label appears twice.

    A shared entry is never overwritten. Changing the text of one cell that shares
    an entry with six others must not rewrite all seven, which is the same aliasing
    hazard the frozen model closes on the read side.
    """

    dataList: tst.TableDataList
    stored: dict[int, str]
    touched: bool = False
    released: set[int] = field(default_factory=set)

    def entryFor(self, key: int) -> tst.TableDataList.ListEntry | None:
        """Return one pooled entry by key, or None when the table has no such key."""
        for entry in self.dataList.entries:
            if entry.key == key:
                return entry
        return None

    def keyFor(self, text: str, previous: int | None = None) -> int:
        """Return the key a cell should name, sharing an entry when one matches.

        `previous` is the key the cell names now, released when it stops naming it.
        """
        self.touched = True
        for key, stored in self.stored.items():
            entry = self.entryFor(key)
            if stored != text or entry is None:
                continue
            if key == previous:
                return key
            entry.refcount += 1
            if previous is not None:
                self.release(previous)
            return key

        existing = self.entryFor(previous) if previous is not None else None
        if existing is not None and existing.refcount <= 1:
            existing.string = text
            self.stored[existing.key] = text
            return existing.key
        if previous is not None:
            self.release(previous)
        fresh = self.dataList.entries.add()
        fresh.key = self.dataList.nextListID
        fresh.refcount = 1
        fresh.string = text
        self.dataList.nextListID += 1
        self.stored[fresh.key] = text
        return fresh.key

    def claim(self, key: int) -> None:
        """Add one cell's claim on a stored string, as a copied record makes."""
        entry = self.entryFor(key)
        if entry is None:
            raise WriteError(
                f"A copied record names string {key}, which is not stored."
            )
        self.touched = True
        entry.refcount += 1

    def release(self, key: int) -> None:
        """Give up one cell's claim on a stored string.

        An entry released to 0 stays until the save ends, so text written later in
        the same save can still share it. `removeSpentEntries` decides then.
        """
        entry = self.entryFor(key)
        if entry is None:
            return
        self.touched = True
        entry.refcount = max(0, entry.refcount - 1)
        self.released.add(key)


def readStringPool(index: ArchiveIndex, store: tst.DataStore) -> StringPool | None:
    """Return the table's string pool, or None when it carries no string list.

    A table that has never held text carries no list to write into, which is a
    different state from one whose list is empty.
    """
    if not store.stringTable.identifier:
        return None
    return StringPool(
        dataList=index.resolve(store.stringTable, tst.TableDataList),
        stored=readStringTable(index, store),
    )


def countFormatClaims(raw: bytes) -> Counter[int]:
    """Return how often one record names each format, counted as refcounts count."""
    references = decodeRecord(0, raw).references
    return Counter(
        key
        for slot, key in zip(listReferenceSlots(raw), references, strict=True)
        if slot in countedFormatSlots
    )


def moveFormatReferences(
    dataList: tst.TableDataList, before: bytes | None, after: bytes | None, where: str
) -> set[int]:
    """Move refcounts from the formats a record named to those it names now.

    `before` is None for a record no cell owned, and `after` for one being removed.
    Only a slot that changed moves a count, so an entry no written record touches
    keeps the count Numbers wrote even where that count disagrees with its cells.
    Returns the keys whose counts moved.
    """
    change = countFormatClaims(after) if after is not None else Counter()
    change.subtract(countFormatClaims(before) if before is not None else Counter())
    entries = {int(entry.key): entry for entry in dataList.entries}
    moved: set[int] = set()
    for key, delta in change.items():
        if not delta:
            continue
        entry = entries.get(key)
        if entry is None:
            if delta < 0:
                continue
            raise WriteError(
                f"{where} would name format {key}, which its table's format list "
                "does not hold."
            )
        entry.refcount = max(0, entry.refcount + delta)
        moved.add(key)
    return moved


def removeSpentEntries(
    dataList: tst.TableDataList,
    released: set[int],
    tiles: list[tst.Tile],
    claims: Callable[[CellRecord], Iterable[int]],
) -> set[int]:
    """Remove each entry this save released to 0 that no record still names.

    Numbers removes such an entry on save and never reuses its key, measured for a
    format in `54c-format-star-rating-cleared` and a string in `54b`. A count
    Numbers wrote can already undercount its cells, so the records are read rather
    than the count trusted: removing an entry a cell still names would orphan it.
    Returns the keys removed.
    """
    spent = {
        int(entry.key) for entry in dataList.entries
        if entry.key in released and entry.refcount == 0
    }
    if not spent:
        return spent
    for tile in tiles:
        for rowInfo in tile.rowInfos:
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                spent.difference_update(claims(record))
    for position in reversed(range(len(dataList.entries))):
        if dataList.entries[position].key in spent:
            del dataList.entries[position]
    return spent


def listStringClaims(record: CellRecord) -> Iterable[int]:
    """Return the pooled string key a text record names, if it is one."""
    if record.typeByte == stringTypeByte and isinstance(record.value, int):
        return (record.value,)
    return ()


def listStyleClaims(record: CellRecord) -> Iterable[int]:
    """Return the style keys a record names, once per counted slot."""
    return [
        key
        for slot, key in zip(
            listReferenceSlots(record.raw), record.references, strict=True
        )
        if slot in countedStyleSlots
    ]


def listRichTextClaims(record: CellRecord) -> Iterable[int]:
    """Return the rich-text key a rich-text record names, if it is one."""
    if record.typeByte == richTextTypeByte and isinstance(record.value, int):
        return (record.value,)
    return ()


def claimEntries(dataList: tst.TableDataList, keys: Iterable[int]) -> bool:
    """Add one reference per key given, and say whether any count moved."""
    named = Counter(keys)
    moved = False
    for entry in dataList.entries:
        if entry.key in named:
            entry.refcount += named[entry.key]
            moved = True
    return moved


def releaseEntries(dataList: tst.TableDataList, keys: Iterable[int]) -> bool:
    """Release one reference per key given, and say whether any count moved."""
    named = Counter(keys)
    moved = False
    for entry in dataList.entries:
        if entry.key in named:
            entry.refcount = max(0, entry.refcount - named[entry.key])
            moved = True
    return moved


__all__ = [
    "StringPool",
    "checkboxFormatSlot",
    "claimEntries",
    "countFormatClaims",
    "countedFormatSlots",
    "countedStyleSlots",
    "currencyFormatSlot",
    "dateFormatSlot",
    "durationFormatSlot",
    "listRichTextClaims",
    "listStringClaims",
    "listStyleClaims",
    "moveFormatReferences",
    "numberFormatSlot",
    "readStringPool",
    "releaseEntries",
    "removeSpentEntries",
    "richTextTypeByte",
    "stringTypeByte",
    "textFormatSlot",
]
