#!/usr/bin/env python3
"""\
One table back into its archives: cell records, the tiles holding them, and merges.

**A record is patched, never rebuilt.** Only the sixteen value bytes move. The
header carries the storage version, the type and a flags bitmask, and the trailing
references point into the table's format and style lists, so a record rebuilt from
the model alone opens in Numbers showing the right number with the wrong formatting
and raises nothing on the way.

**A merge is stored as a formula**, shaped like `SUM($A$1:$B$1)` and evaluated by
nothing. It lives here rather than with the calculation engine because a merge
belongs to a table, and it was the one thing in the engine that knew a model type.

Private. The table feature offers `Table` and `Cell`, not the machinery that saves
one.

UPDATES
2026-09-18  Rows and records move to their new lines, and a removed one releases
            what it named as a merge-swallowed one does, for PYB-17.
2026-09-16  A record carries the chosen-format bit its cell holds, so literal
            text opens as Text, for PYB-83.
2026-09-16  A formula swapped for another is reported as added, so the engine
            hears what the cell reads now, for PYB-86.
2026-09-15  A merge releases the formulas, rich text, strings and styles of the
            records it removes, and a string nothing names is removed, for
            PYB-92.
2026-09-15  A format's refcount follows the cells naming it, for PYB-89. Each
            written record moves the counts its format slots changed, and a
            borrowed shape keeps only the format slot of its own kind. Byte 9
            `0x10` stores the kind a cell displays with rather than a key. A
            format nothing names is removed, and a merge releases the formats
            of the records it removes.
2026-09-14  Text is written and pooled, and a cell changes between text and
            a number, for #61. A format sits in the slot its kind uses, so a
            type change moves it, drops the control, and keeps the style.
2026-09-14  A row the file stores nothing for is created rather than the
            formula being dropped, for #78. The walk over `rowInfos` never
            saw it, and the save reported success.
2026-09-08  Split out of the writer for #58, taking the merge formula with it.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSTArchives_pb2 as tst
from .._persistence import IWAFile, chooseOffsetUnit, decodeRecord, decodeRow
from .._persistence.cells import (
    CellRecord,
    carriesChosenFormat,
    carriesFormula,
    chosenFormatBit,
    chosenFormatOffset,
    conditionalSlot,
    emptyOffset,
    findFormulaKeySlot,
    findSlotValue,
    listReferenceSlots,
    offsetWidth,
    referenceWidth,
    slotOrder,
    valueOffset,
)
from .._persistence.decimal128 import Decimal128, encodedLength
from .._persistence.index import (
    ArchiveIndex,
    originOffset,
    wordBits,
    wordMask,
)
from .._persistence.metadata import PackageRegistry, createSiblingArchive
from ..addressing import CellReference
from ..errors import WriteError
from ..formula._write import (
    FormulaPool,
    attachFormulaKey,
    buildFormulaRecord,
    classifyFormulaEdit,
    detachFormulaKey,
    patchFormulaKey,
    readFormulaPool,
)
from ._conditions import (
    ConditionalPlan,
    buildInheritedRecord,
    rewriteConditionalRecord,
    writeConditionalCounts,
)
from ._lines import GridMaps, LineMap, findDisplacedLine, listAddedLines
from ._read import (
    readMerges,
    readRichTextTable,
    readStringTable,
    resolveValue,
)
from .cells import Cell, MergeRange, Table

# `TST.Tile` and the type bytes a numeric record may carry. 2 is a plain number
# and 10 is currency, which is the same encoding under a different type.
tileTypeId: int = 6002
numericTypeBytes: tuple[int, ...] = (2, 10)

# A record's value is patched in place, leaving the twelve-byte header and the
# trailing references alone. Those references point at the table's format and
# style lists, so rewriting the whole record would strip a cell's number format
# while appearing to succeed.
valueEnd: int = valueOffset + encodedLength

# A pooled string cell holds a four-byte key where a number holds sixteen bytes of
# decimal128, so changing between them moves every trailing reference.
stringTypeByte: int = 3
stringKeyWidth: int = 4

# Byte 8's LOW nibble names what the value is, one value per type with no
# exception in 11,760 records: 1 is decimal128, 8 is a pooled string key. Its high
# bits are the attribute mask, and the reference count is
# `popcount(byte8 & 0xE0) + popcount(byte9) + popcount(byte10)`, which is what makes
# a format slot moving cost nothing: one bit leaves and one arrives. See
# findings-01-values.md.
valueKindMask: int = 0x0F
numberValueKind: int = 0x01
stringValueKind: int = 0x08
valueKindOffset: int = 8
typeByteOffset: int = 1


def refuseFormulaOverwrite(cell: Cell, record: CellRecord) -> None:
    """Refuse to write a value over a cell a formula backs, and say why.

    The one refusal that stays. Overwriting would discard the formula and leave the
    document's displayed number and its stored formula disagreeing until Numbers
    recalculated, which is a silent loss wearing the shape of a success.
    """
    if carriesFormula(record):
        raise WriteError(
            f"{cell.reference} is backed by a formula, so writing a value would "
            "discard it. Replace the formula instead, or clear it first."
        )


def buildWrittenRecord(
    cell: Cell,
    record: CellRecord,
    pool: StringPool | None,
    *,
    borrowed: bool = False,
    formatFor: Callable[[int], int | None] = lambda formatType: None,
) -> bytes:
    """Return this cell's record carrying its new value, changing type when it must.

    Four paths. Text over text and a number over a number patch the value in place,
    leaving the header and every trailing reference alone. Text over a number and a
    number over text go through `retypeRecord`, because the value widths differ by
    twelve bytes and everything behind them moves.

    **`borrowed` says the record belongs to another cell** and is here only for its
    shape. Without it, the template's pooled key is read as this cell's previous
    claim, and a pool entry nothing else names is then rewritten in place: writing
    into an empty `J1` changed `I1` from `Item 1` to the new text, with nothing
    raised. Found by the golden on 2026-09-14.
    """
    refuseFormulaOverwrite(cell, record)
    if borrowed:
        record = decodeRecord(record.column, borrowShape(record))
    value = cell.value

    if isinstance(value, str):
        if pool is None:
            raise WriteError(
                f"{cell.reference} was set to text and its table carries no string "
                "list to pool it in. A table that has never held text has none."
            )
        previous = (
            record.value
            if record.typeByte == stringTypeByte and not borrowed
            else None
        )
        key = pool.keyFor(value, previous if isinstance(previous, int) else None)
        encoded = key.to_bytes(stringKeyWidth, "little")
        if record.typeByte == stringTypeByte:
            return (
                record.raw[:valueOffset] + encoded
                + record.raw[valueOffset + stringKeyWidth:]
            )
        return retypeRecord(
            record, stringTypeByte, encoded,
            formatKey=formatFor(textFormatType),
        )

    if isinstance(value, Decimal):
        if record.typeByte == stringTypeByte:
            if pool is not None and not borrowed and isinstance(record.value, int):
                pool.release(record.value)
            return retypeRecord(
                record, numericTypeBytes[0], Decimal128(value).asBytes(),
                formatKey=formatFor(numberFormatType),
            )
        if record.typeByte not in numericTypeBytes:
            raise WriteError(
                f"{cell.reference} holds a value of type {record.typeByte} and a "
                "Decimal was written into it. Only a number, a currency amount and "
                "text can be written over so far."
            )
        return patchRecord(record, value)

    raise WriteError(
        f"{cell.reference} was set to {type(value).__name__}, and only a Decimal "
        "or a str can be written so far."
    )


def applyChosenFormat(raw: bytes, cell: Cell) -> bytes:
    """Return a record carrying the chosen-format bit its cell holds."""
    header = bytearray(raw[:valueOffset])
    if cell.formatChosen:
        header[chosenFormatOffset] |= chosenFormatBit
    else:
        header[chosenFormatOffset] &= ~chosenFormatBit
    return bytes(header) + raw[valueOffset:]


def patchRecord(record: CellRecord, value: Decimal) -> bytes:
    """Return one cell record with its number replaced and everything else kept.

    Only the sixteen value bytes move. The header carries the storage version, the
    type and a flags bitmask, and the trailing references point into the table's
    format and style lists, so a record rebuilt from scratch would open in Numbers
    showing the right number with the wrong formatting and raise nothing on the way.
    """
    if len(record.raw) < valueEnd:
        raise WriteError(
            f"The record for column {record.column + originOffset} is "
            f"{len(record.raw)} bytes, too short to hold a decimal128 value."
        )
    return (
        record.raw[:valueOffset] + Decimal128(value).asBytes() + record.raw[valueEnd:]
    )


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

# The control a cell presents as, a `control_cell_spec_table` key. Measured against
# 11-value-types-noformats, whose five control cells carry keys 1 to 5 in the order
# the table lists them and whose plain cells carry no such slot. A control describes
# the value it was built for, so it does not survive that value being replaced: a
# star rating left on a cell that became text makes Numbers present text as stars.
controlSlot: tuple[int, int] = (9, 0x04)

# Which per-kind slot a cell displays with, as a kind rather than a key: 1 number
# through 6 checkbox. In all 11,581 records the documents carry, it names a kind slot
# the record holds, and no refcount counts it. Read as a format key until
# `54-format-star-rating` stored 5 where no list holds a key 5.
displayedKindSlot: tuple[int, int] = (9, 0x10)


def findSlotKind(slot: tuple[int, int]) -> int:
    """Return the kind `displayedKindSlot` stores for one per-kind format slot."""
    return countedFormatSlots.index(slot) + 1

# A format entry states its own kind. `260` carries nothing else, so a text format
# can be created for a table that has never held any.
numberFormatType: int = 256
textFormatType: int = 260

# Numbers' automatic number format, identical in `11-value-types-noformats` and
# `20-formula-shapes`: a `256` entry is never written bare, as a `260` one is.
automaticDecimalPlaces: int = 253
automaticNegativeStyle: int = 0

# The plain number `42` in `20-formula-shapes`, Numbers' own record for an unstyled
# number: a twelve-byte header, the decimal128 value, then the kind it displays with
# and its number format key, which a created record replaces with its table's own.
plainNumberRecord: bytes = bytes.fromhex(
    "0502000000000000013000002a0000000000000000000000000040300100000001000000"
)

# A first row written into an empty tile carries 255 narrow offset slots, measured in
# `01-text-plain`, `11-value-types-noformats` and `18-formula-literals` alike.
narrowRowSlots: int = 255

def findFormatKey(dataList: tst.TableDataList, formatType: int) -> int:
    """Return a key naming a format of this kind, creating one when there is none.

    A `260` entry carries nothing but its kind, so creating one states no more than
    the documents do. Counts nothing: `moveFormatReferences` counts the record that
    names the key, so looking a format up once for many cells counts every cell.

    **Takes the resolved list rather than resolving one.** `ArchiveIndex.resolve`
    parses the archive afresh on every call, so a function that resolved its own
    copy would add an entry to a throwaway: the key came back real, the entry never
    reached the file, and cells named a format the table did not hold. Found
    reviewing #61, in a golden Numbers had already accepted.
    """
    for entry in dataList.entries:
        if entry.HasField("format") and entry.format.format_type == formatType:
            return int(entry.key)
    fresh = dataList.entries.add()
    fresh.key = dataList.nextListID
    fresh.refcount = 0
    fresh.format.format_type = formatType
    if formatType == numberFormatType:
        fresh.format.decimal_places = automaticDecimalPlaces
        fresh.format.negative_style = automaticNegativeStyle
        fresh.format.show_thousands_separator = False
    dataList.nextListID += 1
    return int(fresh.key)


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


# A style's refcount is how often its key sits in these two slots, which reproduces
# every style list in the documents, measured 2026-09-15 for PYB-92.
countedStyleSlots: tuple[tuple[int, int], ...] = ((8, 0x20), (8, 0x40))


def listStyleClaims(record: CellRecord) -> Iterable[int]:
    """Return the style keys a record names, once per counted slot."""
    return [
        key
        for slot, key in zip(
            listReferenceSlots(record.raw), record.references, strict=True
        )
        if slot in countedStyleSlots
    ]


# A rich-text cell names its payload by key, and an entry's refcount is how many such
# records name it, which reproduces all 16 rich-text lists in the documents.
richTextTypeByte: int = 9


def listRichTextClaims(record: CellRecord) -> Iterable[int]:
    """Return the rich-text key a rich-text record names, if it is one."""
    if record.typeByte == richTextTypeByte and isinstance(record.value, int):
        return (record.value,)
    return ()


def releaseEntries(dataList: tst.TableDataList, keys: Iterable[int]) -> bool:
    """Release one reference per key given, and say whether any count moved."""
    named = Counter(keys)
    moved = False
    for entry in dataList.entries:
        if entry.key in named:
            entry.refcount = max(0, entry.refcount - named[entry.key])
            moved = True
    return moved


def findTemplateRecord(
    index: ArchiveIndex, store: tst.DataStore, typeByte: int
) -> CellRecord | None:
    """Return a record to shape a new one from, preferring the type being written.

    A record created for a cell that had none has to choose every header byte and
    every trailing reference. Those references are keys into this table's own lists,
    so they are copied from a sibling rather than derived. The same reasoning shaped
    a new tile row for PYB-78.

    **A record of the other type will do**, which is what lets the first text reach a
    table holding only numbers. Retyping places the references for the kind being
    written, so what is borrowed is the style and the shape rather than anything the
    old value chose. The preference is the type being written, then the other one it
    can be converted from.
    """
    found: dict[int, CellRecord] = {}
    for entry in store.tiles.tiles:
        tile = index.resolve(entry.tile, tst.Tile)
        for rowInfo in tile.rowInfos:
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                if carriesFormula(record):
                    continue
                found.setdefault(record.typeByte, record)
                if typeByte in found:
                    return found[typeByte]
    for candidate in (typeByte, stringTypeByte, *numericTypeBytes):
        if candidate in found:
            return found[candidate]
    return None


def buildFreshRecord(
    column: int, typeByte: int, formatFor: Callable[[int], int | None]
) -> CellRecord:
    """Return Numbers' plain-number record for a table holding no record to copy.

    A number keeps the record's format key, so it is replaced with this table's own.
    Text is retyped from it, which replaces the key itself, so asking for a number
    format there would leave an entry nothing names.
    """
    key = 0
    if typeByte in numericTypeBytes:
        found = formatFor(numberFormatType)
        if found is None:
            raise WriteError(
                "This table carries no format list, so a number written into it "
                "would name a format nothing holds."
            )
        key = found
    references = (
        findSlotKind(numberFormatSlot).to_bytes(referenceWidth, "little")
        + key.to_bytes(referenceWidth, "little")
    )
    return decodeRecord(column, plainNumberRecord[:-2 * referenceWidth] + references)


def measureValueWidth(record: CellRecord) -> int:
    """Return how many bytes this record's value occupies, for a type being changed."""
    if record.typeByte == stringTypeByte:
        return stringKeyWidth
    if record.typeByte in numericTypeBytes:
        return encodedLength
    raise WriteError(
        f"A record of type {record.typeByte} holds a value this library cannot "
        "measure, so the references behind it cannot be placed."
    )


def borrowShape(record: CellRecord) -> bytes:
    """Return a sibling's record reduced to what a new cell may take from it.

    A control describes the cell it was built for: writing into an empty cell gave
    it the pop-up menu of the cell whose shape it took. Found by the golden on
    2026-09-14. Byte 6's `0x80` goes too, marking a format a person chose, 108
    records against 4515 that leave it clear.

    So does every format slot but the one the record's own kind uses. A remembered
    date or duration format is the sibling's, and naming it would claim a count in
    a slot this library does not maintain. A borrowed shape is not a borrowed
    decision.
    """
    raw = record.raw
    raw = bytes(raw[:6]) + bytes([raw[6] & ~chosenFormatBit]) + bytes(raw[7:])
    own = textFormatSlot if record.typeByte == stringTypeByte else numberFormatSlot
    dropped = {controlSlot, *countedFormatSlots} - {own}
    slots = listReferenceSlots(raw)
    start = len(raw) - len(slots) * referenceWidth
    kept = [
        raw[start + index * referenceWidth:start + (index + 1) * referenceWidth]
        for index, slot in enumerate(slots) if slot not in dropped
    ]
    header = bytearray(raw[:start])
    for at, bit in dropped:
        header[at] &= ~bit
    return bytes(header) + b"".join(kept)


def retypeRecord(
    record: CellRecord,
    typeByte: int,
    value: bytes,
    *,
    formatKey: int | None,
) -> bytes:
    """Return one record holding a different kind of value, its format slot moved.

    A format reference sits in the slot its KIND uses, so a cell becoming text moves
    its format from byte 9's `0x20` to byte 10's `0x02` and names a text format
    rather than keeping the number format it displayed with. One bit leaves and one
    arrives, so the count the reference rule derives is unchanged.

    Every other reference keeps its slot and its value, which is what carries a
    cell's style across. `formatKey` is None when the table has no format list, and
    the old slot is then dropped without a replacement.
    """
    width = measureValueWidth(record)
    if len(record.raw) < valueOffset + width:
        raise WriteError(
            f"The record for column {record.column + originOffset} is "
            f"{len(record.raw)} bytes, too short to hold the value it declares."
        )
    toText = typeByte == stringTypeByte
    leaving = numberFormatSlot if toText else textFormatSlot
    arriving = textFormatSlot if toText else numberFormatSlot

    slots = listReferenceSlots(record.raw)
    carried = {
        slot: reference
        for slot, reference in zip(slots, record.references, strict=True)
        if slot not in (leaving, controlSlot)
    }
    if formatKey is not None:
        carried[arriving] = formatKey
        # The cell now displays as its new kind, so the kind it displays with follows.
        if displayedKindSlot in carried:
            carried[displayedKindSlot] = findSlotKind(arriving)

    header = bytearray(record.raw[:valueOffset])
    header[typeByteOffset] = typeByte
    kind = stringValueKind if toText else numberValueKind
    header[valueKindOffset] = (header[valueKindOffset] & ~valueKindMask) | kind
    for at, bit in (leaving, arriving, controlSlot):
        header[at] &= ~bit
    for at, bit in carried:
        header[at] |= bit

    tail = b"".join(
        carried[slot].to_bytes(referenceWidth, "little")
        for slot in slotOrder if slot in carried
    )
    return bytes(header) + value + tail


def findRowsNeedingStorage(
    table: Table, firstRow: int, tileSize: int, present: frozenset[int]
) -> list[int]:
    """Return the rows of this tile holding a formula the file stores no row for.

    Numbers writes a `TileRowInfo` only for a row that holds something, so a table
    declaring ten rows can carry one. A formula written into any of the other nine
    was dropped by the walk over `rowInfos`, and the save reported success.
    """
    wanted = set()
    for reference, cell in table.cells.items():
        row = reference.row - originOffset
        if (cell.formula is None and cell.value is None) or row in present:
            continue
        if firstRow <= row < firstRow + tileSize:
            wanted.add(row)
    return sorted(wanted)


def createRowStorage(tile: tst.Tile, tileRowIndex: int) -> tst.TileRowInfo:
    """Add an empty row to a tile, shaped like the rows already in it.

    The offset array's length is copied from a sibling rather than computed: a
    narrow row carries a fixed 255 slots whatever the column count, and the one
    wide row measured carries one slot per column, so a rule fitted to that single
    sample would be a guess. A tile holding no row takes the narrow shape Numbers
    writes for a first row, which the caller allows only where 255 slots suffice.

    `numrows` is corrected because Numbers keeps it accurate, and `numCells`,
    `maxRow` and `maxColumn` are left alone because Numbers writes zero in all
    three on tiles full of data.
    """
    sibling = tile.rowInfos[0] if tile.rowInfos else None
    slots = (
        len(sibling.cell_offsets) // offsetWidth if sibling is not None
        else narrowRowSlots
    )
    empty = emptyOffset.to_bytes(offsetWidth, "little") * slots
    created = tst.TileRowInfo()
    created.tile_row_index = tileRowIndex
    created.cell_count = 0
    created.cell_storage_buffer_pre_bnc = b""
    created.cell_offsets_pre_bnc = empty
    created.storage_version = (
        sibling.storage_version if sibling is not None else tile.storage_version
    )
    created.cell_storage_buffer = b""
    created.cell_offsets = empty
    if sibling is not None and sibling.has_wide_offsets:
        created.has_wide_offsets = True

    at = len(tile.rowInfos)
    for position, existing in enumerate(tile.rowInfos):
        if existing.tile_row_index > tileRowIndex:
            at = position
            break
    tile.rowInfos.insert(at, created)
    tile.numrows = len(tile.rowInfos)
    return created


def rewriteRow(
    offsets: bytes,
    buffer: bytes,
    offsetUnit: int,
    replacements: dict[int, bytes],
    removals: frozenset[int] = frozenset(),
) -> tuple[bytes, bytes]:
    """Rebuild one row's offset array and storage buffer, replacing and dropping.

    The whole row is rebuilt rather than patched in place because a record's offset
    is where the previous ones ended, so a record that changes length moves every
    record after it. Untouched records are re-emitted from the bytes they were read
    from, so a row with one edit differs in exactly one record.

    A dropped column takes the same empty offset a column that never held anything
    takes, which is what a cell swallowed by a merge looks like in the file: no
    record at all rather than an empty one.
    """
    slots = len(offsets) // offsetWidth
    existing = {
        record.column: record for record in decodeRow(offsets, buffer, offsetUnit)
    }

    rebuiltOffsets = bytearray()
    rebuiltBuffer = bytearray()
    for column in range(slots):
        record = existing.get(column)
        body = replacements.get(column)
        if body is None and record is not None:
            body = record.raw
        # A replacement for a column with no record CREATES one, which is how a
        # formula reaches a cell that was empty. The offset array already carries a
        # slot for every column, so nothing grows.
        if body is None or column in removals:
            rebuiltOffsets += emptyOffset.to_bytes(offsetWidth, "little")
            continue
        # A row counting offsets in words can only name a position the unit
        # divides, so a record of any other length would silently move every
        # record after it. Refuse rather than write a row that reads back wrong.
        if len(rebuiltBuffer) % offsetUnit:
            raise WriteError(
                f"Column {column} would start at byte {len(rebuiltBuffer)} of the "
                f"row buffer, which is not a multiple of the {offsetUnit}-byte "
                "unit this row counts its offsets in."
            )
        rebuiltOffsets += (len(rebuiltBuffer) // offsetUnit).to_bytes(
            offsetWidth, "little"
        )
        rebuiltBuffer += body
    return bytes(rebuiltOffsets), bytes(rebuiltBuffer)


def moveGridRecords(
    store: tst.DataStore,
    tileRange: TileRange,
    maps: GridMaps,
    table: Table,
    release: Callable[[CellRecord, CellReference], bool],
    plan: ConditionalPlan | None = None,
) -> set[int]:
    """Move every stored row and record to its new line, releasing the removed ones.

    A row keeps its bytes and only its index changes, so a record moved rather than
    edited is the record Numbers wrote. Rows are dealt back to tiles by their new
    row number, which is what carries a row over a tile boundary. Returns the tile
    ids left holding nothing, tile 0 aside, which a table always keeps.
    """
    tileSize = store.tiles.tile_size
    tiles = dict(tileRange.tiles)
    moved: list[tuple[int, tst.TileRowInfo, tst.Tile]] = []
    storedRecords: dict[int, list[CellRecord]] = {}
    for tileid, tile in tiles.items():
        for rowInfo in tile.rowInfos:
            stored = tileid * tileSize + rowInfo.tile_row_index
            row = maps.rows.lineMap(stored)
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            records = decodeRow(rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit)
            storedRecords[stored] = records
            for record in records:
                column = maps.columns.lineMap(record.column)
                if row is None or column is None:
                    reference = CellReference(
                        stored + originOffset, record.column + originOffset
                    )
                    release(record, reference)
            if row is None:
                continue
            # Rules first, while each record still sits where it was stored, since a
            # relative rule is worked out from the cell it colors.
            if plan is not None:
                rewriteConditionalRow(rowInfo, unit, stored, plan)
            if maps.columns.changed:
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRowColumns(
                    rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit,
                    maps.columns, table.colCount,
                )
            rowInfo.cell_count = len(
                decodeRow(rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit)
            )
            moved.append((row, rowInfo, tile))

    copies: dict[int, list[tst.TileRowInfo]] = {tileid: [] for tileid in tiles}
    for row, rowInfo, _ in moved:
        # A row carries its own offset width, so it may sit in any tile.
        tileRange.tileFor(row // tileSize)
        copies.setdefault(row // tileSize, [])
        copy = tst.TileRowInfo()
        copy.CopyFrom(rowInfo)
        copy.tile_row_index = row % tileSize
        copies[row // tileSize].append(copy)
    for tileid, tile in tileRange.tiles.items():
        del tile.rowInfos[:]
        tile.rowInfos.extend(
            sorted(copies.get(tileid, []), key=lambda rowInfo: rowInfo.tile_row_index)
        )
        tile.numrows = len(tile.rowInfos)
    if plan is not None:
        addInheritedRecords(tileRange, tileSize, maps, storedRecords, plan)
    return {
        tileid for tileid, tile in tileRange.tiles.items()
        if tileid and not tile.rowInfos
    }


def rewriteConditionalRow(
    rowInfo: tst.TileRowInfo, unit: int, row: int, plan: ConditionalPlan
) -> None:
    """Point every record of one stored row at the rule its old rule became."""
    replacements = {}
    for record in decodeRow(rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit):
        rewritten = rewriteConditionalRecord(record, row, plan)
        if rewritten is not None:
            replacements[record.column] = rewritten
    if replacements:
        rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRow(
            rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit, replacements
        )


def addInheritedRecords(
    tileRange: TileRange,
    tileSize: int,
    maps: GridMaps,
    storedRecords: dict[int, list[CellRecord]],
    plan: ConditionalPlan,
) -> None:
    """Give each added line the highlighting of the line it displaced.

    The added cells take empty records naming the displaced cells' rules, which is
    what `57-conditions-row-inserted` and `-column-inserted` hold. A cell whose
    displaced neighbor names no rule receives nothing.
    """
    inherited: dict[tuple[int, int], bytes] = {}
    for row in listAddedLines(maps.rows):
        displaced = findDisplacedLine(maps.rows, row)
        if displaced is None:
            continue
        for record in storedRecords.get(displaced, []):
            key = findSlotValue(record, conditionalSlot)
            column = maps.columns.lineMap(record.column)
            if key is not None and column is not None:
                inherited[(row, column)] = buildInheritedRecord(
                    plan.keyFor(key, displaced, record.column)[0]
                )
    for column in listAddedLines(maps.columns):
        displaced = findDisplacedLine(maps.columns, column)
        if displaced is None:
            continue
        for stored, records in storedRecords.items():
            movedRow = maps.rows.lineMap(stored)
            if movedRow is None:
                continue
            for record in records:
                key = findSlotValue(record, conditionalSlot)
                if record.column == displaced and key is not None:
                    inherited[(movedRow, column)] = buildInheritedRecord(
                        plan.keyFor(key, stored, displaced)[0]
                    )
    byRow: dict[int, dict[int, bytes]] = {}
    for (row, column), raw in inherited.items():
        byRow.setdefault(row, {})[column] = raw
    for row, placed in sorted(byRow.items()):
        tile = tileRange.tileFor(row // tileSize)
        if not any(held.tile_row_index == row % tileSize for held in tile.rowInfos):
            createRowStorage(tile, row % tileSize)
        # Found again rather than taken from the creation, because a repeated field
        # stores a copy of what is inserted into it.
        rowInfo = next(
            held for held in tile.rowInfos if held.tile_row_index == row % tileSize
        )
        unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
        rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRow(
            rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit, placed
        )
        rowInfo.cell_count = len(
            decodeRow(rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit)
        )


@dataclass
class TileRange:
    """A table's tiles, creating one only when a row lands where none exists.

    **Tiles are sparse**, measured 2026-09-21 in a table grown to 100,000 rows with
    values scattered through it: only the tiles holding rows exist, ids 0 to 7 then
    15, 16, 24 and on. A created tile takes its shape from an existing one, since a
    tile's own fields say nothing about which rows it holds.
    """

    index: ArchiveIndex
    registry: PackageRegistry
    owners: dict[int, IWAFile]
    store: tst.DataStore
    tiles: dict[int, tst.Tile] = field(default_factory=dict)

    def tileFor(self, tileid: int) -> tst.Tile:
        """Return the tile holding a block of rows, creating it if the file lacks it."""
        if tileid in self.tiles:
            return self.tiles[tileid]
        last = max(self.tiles)
        sibling = self.index.archive(
            next(entry.tile.identifier for entry in self.store.tiles.tiles
                 if entry.tileid == last)
        )
        created = tst.Tile()
        created.maxColumn = 0
        created.maxRow = 0
        created.numCells = 0
        created.numrows = 0
        created.storage_version = self.tiles[last].storage_version
        created.last_saved_in_BNC = self.tiles[last].last_saved_in_BNC
        created.should_use_wide_rows = self.tiles[last].should_use_wide_rows
        entry = self.store.tiles.tiles.add()
        entry.tileid = tileid
        entry.tile.identifier = createSiblingArchive(
            self.registry, self.index, self.owners, sibling.identifier,
            created.SerializeToString(),
        )
        self.tiles[tileid] = created
        return created


def buildTileRange(
    index: ArchiveIndex,
    registry: PackageRegistry,
    owners: dict[int, IWAFile],
    store: tst.DataStore,
) -> TileRange:
    """Return a table's tiles as stored, ready to create any a moved row needs."""
    return TileRange(
        index, registry, owners, store,
        {
            entry.tileid: index.resolve(entry.tile, tst.Tile)
            for entry in store.tiles.tiles
        },
    )


def writeTileRange(
    registry: PackageRegistry,
    store: tst.DataStore,
    tiles: dict[int, tst.Tile],
    spent: set[int],
) -> None:
    """Rewrite the tile list and the row tree, dropping a tile holding nothing.

    `rowTileTree` maps each tile's first row to its id, and `nextRowStripID` is the
    highest tile id plus one: 391 for a sparse table of 18 tiles whose last is 390.
    """
    tileSize = store.tiles.tile_size
    identifiers = {entry.tileid: entry.tile.identifier for entry in store.tiles.tiles}
    kept = sorted(tileid for tileid in tiles if tileid not in spent)
    del store.tiles.tiles[:]
    for tileid in kept:
        entry = store.tiles.tiles.add()
        entry.tileid = tileid
        entry.tile.identifier = identifiers[tileid]
    del store.rowTileTree.nodes[:]
    for tileid in kept:
        node = store.rowTileTree.nodes.add()
        node.key = tileid * tileSize
        node.value = tileid
    store.nextRowStripID = max(kept) + 1
    for tileid in spent:
        registry.archiveRemove(identifiers[tileid])


def rewriteRowColumns(
    offsets: bytes, buffer: bytes, unit: int, columns: LineMap, colCount: int
) -> tuple[bytes, bytes]:
    """Rebuild one row with each record in its new column and removed ones dropped.

    A row carrying one offset slot per column grows or shrinks with the table; the
    narrow shape keeps its fixed 255 slots, so a record past them is refused.
    """
    slots = len(offsets) // offsetWidth
    if slots == len(columns.lines) and slots != narrowRowSlots:
        slots = colCount
    placed: dict[int, bytes] = {}
    for record in decodeRow(offsets, buffer, unit):
        column = columns.lineMap(record.column)
        if column is None:
            continue
        if column >= slots:
            raise WriteError(
                f"A record would move to column {column + originOffset}, past the "
                f"{slots} offset slots its row carries."
            )
        placed[column] = record.raw
    empty = emptyOffset.to_bytes(offsetWidth, "little") * slots
    return rewriteRow(empty, b"", unit, placed)


@dataclass(frozen=True, slots=True)
class TableEdits:
    """What one table's write changed, in the terms the engine has to be told.

    `written` drives the dirty set and says a cell moved. `formulaAdded` and
    `formulaRemoved` are a different fact: the calculation engine keeps its own
    register of which cells hold formulas, and a cell that merely changed value
    does not belong in either list.

    **A formula swapped for another is `formulaAdded`**, since the register also
    carries what each formula reads, and the cell now reads something else.
    """

    written: list[tuple[int, int]]
    formulaAdded: list[tuple[int, int]]
    formulaRemoved: list[tuple[int, int]]


def applyFormulaEdit(
    edit: str, raw: bytes, record: CellRecord, cell: Cell, pool: FormulaPool
) -> bytes:
    """Carry out one cell's formula change against the record and the pool together.

    The two always move as a pair: a key written into a record that the pool does
    not carry names nothing, and an entry the pool holds that no record names is
    dead weight that `refcount` then lies about.
    """
    if edit == "attach":
        assert cell.formula is not None
        return attachFormulaKey(raw, record, pool.keyFor(cell.formula))
    if edit == "detach":
        pool.release(record.references[findFormulaKeySlot(record)])
        return detachFormulaKey(raw, record)
    assert cell.formula is not None
    return patchFormulaKey(
        raw,
        record,
        pool.keyFor(cell.formula, record.references[findFormulaKeySlot(record)]),
    )


def applyTableEdits(
    index: ArchiveIndex,
    owners: dict[int, IWAFile],
    table: Table,
    model: tst.TableModelArchive,
    swallowed: frozenset[tuple[int, int]] = frozenset(),
    maps: GridMaps | None = None,
    registry: PackageRegistry | None = None,
    plan: ConditionalPlan | None = None,
) -> TableEdits:
    """Write every changed cell of one table back into the tiles it came from.

    Returns the stored coordinates it wrote, counted from zero, because the
    calculation engine has to be told which cells moved and this is the only place
    that knows. Returning them rather than a count is what lets `refs_to_dirty` name
    exactly the cells that changed.

    Walks the tile list rather than the archives, matching the read path exactly.
    Tile archive identifiers are not in row order, so iterating archives as found
    would write a cell into the wrong row and raise nothing.
    """
    store = model.base_data_store
    tileSize = store.tiles.tile_size

    # Resolved through the same tables the reader used, because a record holds a
    # pooled key rather than its text. Comparing the model's string against that
    # key would make every text cell look edited on every save.
    strings = readStringTable(index, store)
    richText = readRichTextTable(index, store)
    pool = readFormulaPool(index, store)
    textPool = readStringPool(index, store)
    # Resolved ONCE, because resolving parses afresh and a second copy would take
    # the edits with it. Rewritten only when a written record moved a count.
    formatList = (
        index.resolve(store.format_table, tst.TableDataList)
        if store.format_table.identifier else None
    )
    formatKeys: dict[int, int] = {}
    formatsMoved: set[int] = set()
    tiles: list[tst.Tile] = []
    styleList = (
        index.resolve(store.styleTable, tst.TableDataList)
        if store.styleTable.identifier else None
    )
    stylesMoved = False
    richTextList = (
        index.resolve(store.rich_text_table, tst.TableDataList)
        if store.HasField("rich_text_table") else None
    )
    richTextMoved = False

    def formatFor(formatType: int) -> int | None:
        """Return the key naming a format of this kind, caching the lookup."""
        if formatList is None:
            return None
        if formatType not in formatKeys:
            formatKeys[formatType] = findFormatKey(formatList, formatType)
        return formatKeys[formatType]

    def formatsCount(
        before: bytes | None, after: bytes | None, where: CellReference
    ) -> None:
        """Move the format refcounts one written or removed record changed."""
        if formatList is not None:
            formatsMoved.update(
                moveFormatReferences(formatList, before, after, str(where))
            )

    def releaseRecord(record: CellRecord, reference: CellReference) -> bool:
        """Release every list entry a removed record names, reporting a formula."""
        nonlocal stylesMoved, richTextMoved
        formatsCount(record.raw, None, reference)
        if textPool is not None:
            for key in listStringClaims(record):
                textPool.release(key)
        if styleList is not None:
            stylesMoved |= releaseEntries(styleList, listStyleClaims(record))
        if richTextList is not None:
            richTextMoved |= releaseEntries(richTextList, listRichTextClaims(record))
        if pool is not None and carriesFormula(record):
            pool.release(record.references[findFormulaKeySlot(record)])
            return True
        return False

    # Resolved once, because resolving parses afresh and the structural move below
    # has to be what the walk after it sees.
    restructured = maps is not None and maps.changed
    if maps is not None and restructured:
        if registry is None:
            raise WriteError(
                f"{table.name!r} has rows or columns added or removed, and writing "
                "that needs the package registry the document writer holds."
            )
        covered = buildTileRange(index, registry, owners, store)
        spent = moveGridRecords(store, covered, maps, table, releaseRecord, plan)
        writeTileRange(registry, store, covered.tiles, spent)
    # Resolved once, because resolving parses afresh and the structural move above
    # has to be what the walk below sees.
    tileArchives = [
        (
            entry,
            index.archive(entry.tile.identifier),
            covered.tiles[entry.tileid] if restructured
            else index.resolve(entry.tile, tst.Tile),
        )
        for entry in store.tiles.tiles
    ]

    written: list[tuple[int, int]] = []
    formulaAdded: list[tuple[int, int]] = []
    formulaRemoved: list[tuple[int, int]] = []

    # A row belongs to the tile covering its index, and a tile that holds nothing
    # may be absent. No table in the 46 documents has such a gap, so this refuses
    # rather than guessing what an absent tile should be built from, and refusing
    # is what keeps the formula from being dropped in silence.
    if pool is not None:
        # Compared by tile rather than by row: a table at Numbers' million-row
        # limit spans 3907 tiles, so naming every row covered would build a
        # million-element set on every save to answer a question this answers in
        # one division.
        coveredTiles = frozenset(entry.tileid for entry in store.tiles.tiles)
        uncovered = [
            reference
            for reference, held in table.cells.items()
            if held.formula is not None
            and (reference.row - originOffset) // tileSize not in coveredTiles
        ]
        if uncovered:
            first = min(uncovered, key=lambda reference: (reference.row, reference.col))
            raise WriteError(
                f"Row {first.row} of {table.name!r} holds a formula and no tile "
                f"covers it. The table declares {model.number_of_rows} rows and "
                f"stores {len(store.tiles.tiles)} tile(s) of {tileSize}."
            )

    for entry, archive, tile in tileArchives:
        tiles.append(tile)
        firstRow = entry.tileid * tileSize
        touched = restructured

        # Rows the file stores nothing for, materialized before the walk below,
        # which only ever sees a row that already has storage. Doing it here rather
        # than inside the walk keeps `rowInfos` from being mutated while iterated.
        createdRows: set[int] = set()
        if pool is not None:
            stored = frozenset(
                firstRow + rowInfo.tile_row_index for rowInfo in tile.rowInfos
            )
            for missing in findRowsNeedingStorage(table, firstRow, tileSize, stored):
                if not tile.rowInfos and table.colCount > narrowRowSlots:
                    raise WriteError(
                        f"Row {missing + originOffset} of {table.name!r} is the first "
                        f"row of an empty tile in a table of {table.colCount} columns. "
                        "Numbers' first row for more than 255 columns has not been "
                        "measured, so it is not written."
                    )
                createRowStorage(tile, missing - firstRow)
                createdRows.add(missing)
                touched = True

        for rowInfo in tile.rowInfos:
            offsetUnit = chooseOffsetUnit(
                rowInfo.has_wide_offsets, tile.should_use_wide_rows
            )
            row = firstRow + rowInfo.tile_row_index
            replacements: dict[int, bytes] = {}
            removals = frozenset(
                column for (swallowedRow, column) in swallowed if swallowedRow == row
            )
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, offsetUnit
            ):
                reference = CellReference(
                    row + originOffset, record.column + originOffset
                )
                if (row, record.column) in swallowed:
                    if releaseRecord(record, reference):
                        formulaRemoved.append((row, record.column))
                    continue
                cell = table.cells.get(reference)
                if cell is None:
                    continue
                valueChanged = cell.value != resolveValue(record, strings, richText)
                edit = classifyFormulaEdit(cell.formula, record, pool)
                chosenChanged = cell.formatChosen != carriesChosenFormat(record)
                if not valueChanged and edit == "none" and not chosenChanged:
                    continue
                patched = record.raw
                # The value first, so that writing a value OVER a formula still
                # refuses here rather than being masked by the formula edit below.
                # Attaching a formula is a different act and is allowed.
                if valueChanged:
                    patched = buildWrittenRecord(
                        cell, record, textPool, formatFor=formatFor
                    )
                    formatsCount(record.raw, patched, reference)
                if pool is not None and edit != "none":
                    patched = applyFormulaEdit(edit, patched, record, cell, pool)
                    if edit in ("attach", "replace"):
                        formulaAdded.append((row, record.column))
                    elif edit == "detach":
                        formulaRemoved.append((row, record.column))
                replacements[record.column] = applyChosenFormat(patched, cell)
            present = frozenset(
                record.column
                for record in decodeRow(
                    rowInfo.cell_offsets, rowInfo.cell_storage_buffer, offsetUnit
                )
            )
            # A cell the model gave a formula to but the file has no record for.
            # The loop above cannot see these: it walks records, and these have
            # none. Skipped when a merge swallowed the position, which is an
            # absence Numbers means rather than one to fill.
            if pool is not None:
                for column in range(table.colCount):
                    if column in present or (row, column) in swallowed:
                        continue
                    reference = CellReference(row + originOffset, column + originOffset)
                    cell = table.cells.get(reference)
                    if cell is None:
                        continue
                    if cell.formula is not None:
                        replacements[column] = applyChosenFormat(
                            buildFormulaRecord(pool.keyFor(cell.formula)), cell
                        )
                        formulaAdded.append((row, column))
                        continue
                    if cell.value is None:
                        continue
                    # A value needs a record shaped like one this table already
                    # holds, since its trailing references are keys into the
                    # table's own lists rather than anything derivable.
                    wanted = (
                        stringTypeByte if isinstance(cell.value, str)
                        else numericTypeBytes[0]
                    )
                    shape = findTemplateRecord(index, store, wanted)
                    if shape is None:
                        shape = buildFreshRecord(column, wanted, formatFor)
                    replacements[column] = applyChosenFormat(
                        buildWrittenRecord(
                            cell, shape, textPool, borrowed=True, formatFor=formatFor
                        ),
                        cell,
                    )
                    formatsCount(None, replacements[column], reference)
            dropped = removals & present
            if not replacements and not dropped:
                continue
            rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRow(
                rowInfo.cell_offsets,
                rowInfo.cell_storage_buffer,
                offsetUnit,
                replacements,
                dropped,
            )
            # Corrected only on a row this save created. An edited row carries the
            # count Numbers wrote and this library has never maintained it, so
            # fixing those here would rewrite every golden to no measured benefit.
            if row in createdRows:
                rowInfo.cell_count = sum(
                    1 for column in range(len(rowInfo.cell_offsets) // offsetWidth)
                    if int.from_bytes(
                        rowInfo.cell_offsets[column * offsetWidth:][:offsetWidth],
                        "little",
                    ) != emptyOffset
                )
            written.extend((row, column) for column in replacements)
            touched = True

        if touched:
            owners[archive.identifier].messageReplace(
                archive.identifier, 0, tile.SerializeToString()
            )

    if plan is not None and restructured:
        writeConditionalCounts(plan, tiles)

    if formatList is not None and formatsMoved:
        removeSpentEntries(
            formatList, formatsMoved, tiles,
            lambda record: countFormatClaims(record.raw).keys(),
        )
        formatId = store.format_table.identifier
        owners[formatId].messageReplace(
            formatId, 0, formatList.SerializeToString()
        )

    if styleList is not None and stylesMoved:
        styleId = store.styleTable.identifier
        owners[styleId].messageReplace(
            styleId, 0, styleList.SerializeToString()
        )

    if richTextList is not None and richTextMoved:
        richTextId = store.rich_text_table.identifier
        owners[richTextId].messageReplace(
            richTextId, 0, richTextList.SerializeToString()
        )

    if textPool is not None and textPool.touched:
        for key in removeSpentEntries(
            textPool.dataList, textPool.released, tiles, listStringClaims
        ):
            textPool.stored.pop(key, None)
        textId = store.stringTable.identifier
        owners[textId].messageReplace(
            textId, 0, textPool.dataList.SerializeToString()
        )

    if pool is not None and pool.touched:
        poolId = store.formula_table.identifier
        owners[poolId].messageReplace(
            poolId, 0, pool.dataList.SerializeToString()
        )
    return TableEdits(written, formulaAdded, formulaRemoved)


# A merge is written as `SUM($A$1:$B$1)`, so it carries SUM's index in Apple's
# own function table. The number is theirs and is not derivable from the schemas.
sumFunctionIndex: int = 168


def writeMergeFormula(
    store: tst.FormulaStoreArchive, merge: MergeRange, ownerUid: tsp.UUID
) -> None:
    """Add one merged region to a table's merge store, as the formula Numbers writes.

    **A merge is stored as a formula, not as a flag on a cell.** Each region is a
    complete formula shaped like `SUM($A$1:$B$1)`: a colon-tract node carrying the
    rectangle with all four sticky bits set, then the function node for SUM. Nothing
    evaluates it; the shape is how a merge is expressed.

    The tract's table identifier is the table's own `formula_owner_uid`, split from
    two 64-bit halves into four 32-bit words, which is a different spelling of the
    same value in a different archive. Measured 2026-09-02 against `22-merge-2x2`.
    """
    pair = store.formulas.add()
    pair.formula_index = len(store.formulas) - 1

    node = pair.formula.AST_node_array.AST_node.add()
    node.AST_node_type = tsce.ASTNodeArrayArchive.COLON_TRACT_NODE
    identifier = node.AST_cross_table_reference_extra_info.table_id
    identifier.uuid_w0 = ownerUid.lower & wordMask
    identifier.uuid_w1 = ownerUid.lower >> wordBits
    identifier.uuid_w2 = ownerUid.upper & wordMask
    identifier.uuid_w3 = ownerUid.upper >> wordBits
    node.AST_sticky_bits.begin_row_is_absolute = True
    node.AST_sticky_bits.begin_column_is_absolute = True
    node.AST_sticky_bits.end_row_is_absolute = True
    node.AST_sticky_bits.end_column_is_absolute = True

    startRow, startCol, endRow, endCol = merge.bounds
    tract = node.AST_colon_tract
    columns = tract.absolute_column.add()
    columns.range_begin = startCol - originOffset
    rows = tract.absolute_row.add()
    rows.range_begin = startRow - originOffset
    # `range_end` is omitted for a span of one rather than repeating the beginning,
    # which is how Numbers writes its own and how the reader expects to find them.
    if endCol != startCol:
        columns.range_end = endCol - originOffset
    if endRow != startRow:
        rows.range_end = endRow - originOffset
    tract.preserve_rectangular = True

    function = pair.formula.AST_node_array.AST_node.add()
    function.AST_node_type = tsce.ASTNodeArrayArchive.FUNCTION_NODE
    function.AST_function_node_index = sumFunctionIndex
    function.AST_function_node_numArgs = 1


def findAddedMerges(table: Table, model: tst.TableModelArchive) -> list[MergeRange]:
    """Return the merges the model holds that the stored archive does not.

    Compared against what is stored rather than tracked as merges are added, for
    the same reason `applyMerges` does it: a caller reaches `mergeRanges`
    directly, so a flag set at `mergeAdd` would go stale.

    **Call this BEFORE `applyMerges`**, which rewrites the very store it reads.
    Measured 2026-09-07 on `22c-merge-overpaints`: the same call returns one
    merge before and none after, so the wrong order leaves every covered position
    unswallowed and raises nothing.
    """
    stored = {str(merge.extent) for merge in readMerges(model)}
    return [merge for merge in table.mergeRanges if str(merge.extent) not in stored]


def applyMerges(
    table: Table, model: tst.TableModelArchive, ownerUid: tsp.UUID
) -> frozenset[tuple[int, int]]:
    """Rewrite a table's merge store when its merges differ, and say which cells moved.

    **A merge changes what a reference means, so it changes results**, which is why
    every position whose merge state changed is returned for dirty-marking. **The
    store is emptied rather than removed** when the last merge goes; `merge_owner` is
    present in both twins. Both measured 2026-09-02 across `22-merge-2x2` and its
    unmerged twin, recorded in findings-03-structure.md.

    Compared against what is stored rather than tracked as merges are added, since a
    caller reaches `mergeRanges` directly and a dirty flag would go stale.
    """
    stored = readMerges(model)
    wanted = sorted(str(merge.extent) for merge in table.mergeRanges)
    if wanted == sorted(str(merge.extent) for merge in stored):
        return frozenset()

    store = model.merge_owner.formula_store
    del store.formulas[:]
    for merge in table.mergeRanges:
        writeMergeFormula(store, merge, ownerUid)
    store.next_formula_index = len(store.formulas)

    # Both directions matter: a merge that appeared invalidates references INTO it,
    # and one that went away makes references valid again.
    before = {str(merge.extent): merge for merge in stored}
    after = {str(merge.extent): merge for merge in table.mergeRanges}
    changed = (set(before) ^ set(after))
    return frozenset(
        (reference.row - originOffset, reference.col - originOffset)
        for extent in changed
        for reference in (before.get(extent) or after[extent]).extent
    )
