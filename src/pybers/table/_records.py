#!/usr/bin/env python3
"""\
One cell record written: its value patched, its type changed, or a new one shaped.

**A record is patched, never rebuilt.** Only the sixteen value bytes move. The
header carries the storage version, the type and a flags bitmask, and the trailing
references point into the table's format and style lists, so a record rebuilt from
the model alone opens in Numbers showing the right number with the wrong formatting
and raises nothing on the way.

Private. Part of the table feature's archive half.

UPDATES
2026-10-01  The format slots moved to `_persistence.cells`, for PYB-141.
2026-09-30  A date is written over a date and a duration over a duration, for
            PYB-137.
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

import datetime
import struct
from collections.abc import Callable
from decimal import Decimal

from .._generated import TSTArchives_pb2 as tst
from .._persistence import chooseOffsetUnit, decodeRecord, decodeRow
from .._persistence.cells import (
    CellRecord,
    appleEpoch,
    carriesFormula,
    chosenFormatBit,
    chosenFormatOffset,
    countedFormatSlots,
    displayedKindSlot,
    listReferenceSlots,
    numberFormatSlot,
    referenceWidth,
    slotOrder,
    textFormatSlot,
    valueOffset,
)
from .._persistence.decimal128 import Decimal128, encodedLength
from .._persistence.index import ArchiveIndex
from ..addressing.reference import originOffset
from ..errors import WriteError
from ._refcounts import StringPool, stringTypeByte
from .cells import Cell

# The type bytes a numeric record may carry. 2 is a plain number and 10 is
# currency, which is the same encoding under a different type.
numericTypeBytes: tuple[int, ...] = (2, 10)

# A date is a float64 count of seconds since 2001-01-01 UTC, at the same offset as a
# number, so a date over a date patches eight bytes in place.
dateTypeByte: int = 5
dateWidth: int = 8
# A duration is a float64 count of seconds, laid out as a date is.
durationTypeByte: int = 7


# A record's value is patched in place, leaving the twelve-byte header and the
# trailing references alone. Those references point at the table's format and
# style lists, so rewriting the whole record would strip a cell's number format
# while appearing to succeed.
valueEnd: int = valueOffset + encodedLength


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


# The control a cell presents as, a `control_cell_spec_table` key. Measured against
# 11-value-types-noformats, whose five control cells carry keys 1 to 5 in the order
# the table lists them and whose plain cells carry no such slot. A control describes
# the value it was built for, so it does not survive that value being replaced: a
# star rating left on a cell that became text makes Numbers present text as stars.
controlSlot: tuple[int, int] = (9, 0x04)


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


def patchRichTextKey(raw: bytes, key: int) -> bytes:
    """Return a rich-text record naming a different rich-text entry."""
    encoded = key.to_bytes(stringKeyWidth, "little")
    return raw[:valueOffset] + encoded + raw[valueOffset + stringKeyWidth:]


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

    if isinstance(value, datetime.datetime):
        if record.typeByte != dateTypeByte:
            raise WriteError(
                f"{cell.reference} holds a value of type {record.typeByte} and a "
                "date was written into it. A date can only be written over a date "
                "so far."
            )
        return patchDateRecord(record, value)

    if isinstance(value, datetime.timedelta):
        if record.typeByte != durationTypeByte:
            raise WriteError(
                f"{cell.reference} holds a value of type {record.typeByte} and a "
                "duration was written into it. A duration can only be written over "
                "a duration so far."
            )
        return patchSecondsRecord(record, value.total_seconds())

    raise WriteError(
        f"{cell.reference} was set to {type(value).__name__}, and only a Decimal, "
        "a str, a date or a duration can be written so far."
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


def patchDateRecord(record: CellRecord, value: datetime.datetime) -> bytes:
    """Return one date record with its moment replaced and everything else kept."""
    if value.tzinfo is None:
        raise WriteError(
            f"The date {value} has no time zone, so its seconds since 2001-01-01 UTC "
            "cannot be worked out."
        )
    return patchSecondsRecord(record, (value - appleEpoch).total_seconds())


def patchSecondsRecord(record: CellRecord, seconds: float) -> bytes:
    """Return one date or duration record with its seconds replaced, all else kept."""
    if len(record.raw) < valueOffset + dateWidth:
        raise WriteError(
            f"The record for column {record.column + originOffset} is "
            f"{len(record.raw)} bytes, too short to hold a date or duration."
        )
    return (
        record.raw[:valueOffset] + struct.pack("<d", seconds)
        + record.raw[valueOffset + dateWidth:]
    )


def findFormatKey(dataList: tst.TableDataList, formatType: int) -> int:
    """Return a key naming a format of this kind, creating one when there is none.

    A `260` entry carries nothing but its kind, so creating one states no more than
    the documents do. Counts nothing: `moveFormatReferences` counts the record that
    names the key, so looking a format up once for many cells counts every cell.
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


__all__ = [
    "applyChosenFormat",
    "borrowShape",
    "buildFreshRecord",
    "buildWrittenRecord",
    "patchRichTextKey",
    "findFormatKey",
    "findTemplateRecord",
    "numericTypeBytes",
]
