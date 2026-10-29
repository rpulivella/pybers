#!/usr/bin/env python3
"""\
One cell record written: its value patched, its kind changed, or a new one shaped.

**A record is patched, never rebuilt.** A value of the kind the record already
holds replaces only the value bytes, so its format, style and control stay. The
trailing references point into the table's format and style lists, so a record
rebuilt from the model alone opens in Numbers showing the right number with the
wrong formatting and raises nothing on the way.

**A value of another kind retypes the record** to that kind's Automatic format, as
a value typed into a fresh cell takes it, and drops the control the old value had.

Private. Part of the table feature's archive half.

UPDATES
2026-10-29  A format keyed through the format pool, and a template found
            through `StoredTiles`, for PYB-278.
2026-10-22  The chosen bit set or cleared is the one for the slot a record shows,
            and a retyped record keeps none, for PYB-255.
2026-10-22  A `CurrencyAmount` writes as currency, and a new code keeps the other
            settings of its format, for PYB-220.
2026-10-20  Any value is written over any value, each kind's record shape held in
            one table, for PYB-144. A new cell's shape is a sibling's style alone.
2026-10-11  Fixed tables are frozendict, for PYB-189.
2026-10-09  A refused write names what the cell holds in words, for PYB-168.
2026-10-01  The format slots moved to `_persistence.cells`, and a cell's chosen
            format is read from its description, for PYB-141.
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
from dataclasses import dataclass
from decimal import Decimal

from .._generated import TSKArchives_pb2 as tsk
from .._generated import TSTArchives_pb2 as tst
from .._persistence import decodeRecord
from .._persistence.cells import (
    CellRecord,
    appleEpoch,
    carriesFormula,
    checkboxFormatSlot,
    chosenFormatBit,
    chosenFormatOffset,
    countedFormatSlots,
    currencyFormatSlot,
    dateFormatSlot,
    displayedKindSlot,
    durationFormatSlot,
    findChosenBit,
    findSlotValue,
    listReferenceSlots,
    numberFormatSlot,
    patchSlotValue,
    referenceWidth,
    slotOrder,
    textFormatSlot,
    valueOffset,
)
from .._persistence.decimal128 import Decimal128, encodedLength
from .._persistence.index import ArchiveIndex
from .._persistence.pool import EntryPool
from .._persistence.rows import readStoredTiles
from ..addressing.reference import originOffset
from ..currency import CurrencyAmount
from ..errors import WriteError
from ._read import controlSlot, currencyFormatType, currencyTypeByte, storedKinds
from ._refcounts import stringTypeByte
from .cell import Cell, CellValue, refuseValueOverFormula
from .kinds import CellKind

# How a refusal names what a cell holds, in the words a person would use.
kindPhrases: frozendict[CellKind, str] = frozendict({
    CellKind.NUMBER: "a number",
    CellKind.CURRENCY: "a currency amount",
    CellKind.TEXT: "text",
    CellKind.RICH_TEXT: "rich text",
    CellKind.DATE_TIME: "a date",
    CellKind.DURATION: "a duration",
    CellKind.BOOLEAN: "a boolean",
    CellKind.ERROR: "a formula that failed",
})


@dataclass(frozen=True, slots=True)
class RecordShape:
    """How a record type holds its value: the bits naming it, its width, its format.

    `valueBits` is byte 8's low five bits, one value per type across 73,445 records.
    See findings-01-values.md.
    """

    valueBits: int
    width: int
    formatSlot: tuple[int, int] | None


numberTypeByte: int = 2
dateTypeByte: int = 5
booleanTypeByte: int = 6
durationTypeByte: int = 7
emptyTypeByte: int = 0
richTextTypeByte: int = 9

# Every record type whose value a write can replace. Empty and rich text are never
# written, only written over, so they name no format of their own to keep.
recordShapes: frozendict[int, RecordShape] = frozendict({
    emptyTypeByte: RecordShape(0x00, 0, None),
    numberTypeByte: RecordShape(0x01, encodedLength, numberFormatSlot),
    stringTypeByte: RecordShape(0x08, 4, textFormatSlot),
    dateTypeByte: RecordShape(0x04, 8, dateFormatSlot),
    booleanTypeByte: RecordShape(0x02, 8, checkboxFormatSlot),
    durationTypeByte: RecordShape(0x02, 8, durationFormatSlot),
    richTextTypeByte: RecordShape(0x10, 4, None),
    currencyTypeByte: RecordShape(0x01, encodedLength, currencyFormatSlot),
})
valueBitsMask: int = 0x1F
valueKindOffset: int = 8
typeByteOffset: int = 1
# Bytes 6 and 7 hold flags the formats set. A value typed into a fresh cell stores
# none, measured in `72-date-time-zones`, `11-value-types-noformats` `D1` and `42`
# in `20-formula-shapes`, so a retyped record, which takes Automatic, clears them.
formatFlagsOffset: int = 6
formatFlagsWidth: int = 2



def findSlotKind(slot: tuple[int, int]) -> int:
    """Return the kind `displayedKindSlot` stores for one per-kind format slot."""
    return countedFormatSlots.index(slot) + 1


# Numbers' Automatic format for each kind it gives one, as the documents store it:
# the number in `11-value-types-noformats` and `20-formula-shapes`, the duration in
# `11` `D1`, and the boolean a formula in `69-functions-added-in-15-4` returned.
automaticNumberFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=256, decimal_places=253, negative_style=0,
    show_thousands_separator=False,
)
automaticTextFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=260
)
automaticDurationFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=268, duration_style=1, duration_unit_largest=8,
    duration_unit_smallest=8, use_automatic_duration_units=True,
)
automaticBooleanFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=1
)
# A date has no Automatic, since Numbers names a pattern for every date it stores, so
# pybers writes ISO 8601 order, the same in every region. Numbers stores `yyyy-MM-dd`
# in `66-series-horizontal-base`; PYB-145 sets any other.
dateOnlyFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=261, date_time_format="yyyy-MM-dd"
)
dateAndTimeFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=261, date_time_format="yyyy-MM-dd HH:mm"
)


# As Numbers' menu writes it, in `88-formula-currency-results` and `12-number-currency`.
def buildCurrencyFormat(code: str) -> tsk.FormatStructArchive:
    """Return the Currency format Numbers gives an amount in one currency."""
    return tsk.FormatStructArchive(
        format_type=currencyFormatType, decimal_places=2, currency_code=code,
        negative_style=0,
        show_thousands_separator=False, use_accounting_style=False,
    )


# A currency amount a person formatted sets both, measured on all 296 such records.
currencyChosenBit: int = 0x02
currencyCellOffset: int = 7
currencyCellBit: int = 0x08


def findAutomaticFormat(value: CellValue) -> tsk.FormatStructArchive:
    """Return the format a value takes in a cell whose kind it changed."""
    if isinstance(value, CurrencyAmount):
        return buildCurrencyFormat(value.currency)
    if isinstance(value, str):
        return automaticTextFormat
    if isinstance(value, bool):
        return automaticBooleanFormat
    if isinstance(value, datetime.datetime):
        return dateOnlyFormat if value.time() == datetime.time() else dateAndTimeFormat
    if isinstance(value, datetime.timedelta):
        return automaticDurationFormat
    return automaticNumberFormat


def patchRichTextKey(raw: bytes, key: int) -> bytes:
    """Return a rich-text record naming a different rich-text entry."""
    encoded = key.to_bytes(recordShapes[richTextTypeByte].width, "little")
    return raw[:valueOffset] + encoded + raw[valueOffset + len(encoded):]


def refuseFormulaOverwrite(cell: Cell, record: CellRecord) -> None:
    """Refuse to write a value over a cell a formula backs, and say why.

    The one refusal that stays. Overwriting would discard the formula and leave the
    document's displayed number and its stored formula disagreeing until Numbers
    recalculated, which is a silent loss wearing the shape of a success.
    """
    if carriesFormula(record):
        refuseValueOverFormula(cell.address)


def formatStoredValue(record: CellRecord) -> str:
    """Return what a record holds as a person would say it: `is empty`, `holds text`."""
    kind = storedKinds.get(record.typeByte)
    if kind is None:
        return f"holds a value of a type pybers does not recognize, {record.typeByte}"
    if kind is CellKind.EMPTY:
        return "is empty"
    return f"holds {kindPhrases.get(kind, kind.value)}"


def findWrittenTypeByte(value: CellValue) -> int:
    """Return the record type a value is stored as, a number as a plain number."""
    if isinstance(value, CurrencyAmount):
        return currencyTypeByte
    if isinstance(value, str):
        return stringTypeByte
    if isinstance(value, bool):
        return booleanTypeByte
    if isinstance(value, datetime.datetime):
        return dateTypeByte
    if isinstance(value, datetime.timedelta):
        return durationTypeByte
    return numberTypeByte


def encodeSeconds(seconds: float) -> bytes:
    """Return seconds as the float64 a date, duration or boolean record stores."""
    return struct.pack("<d", seconds)


def encodeCellValue(
    cell: Cell, record: CellRecord, pool: EntryPool[str] | None, borrowed: bool
) -> tuple[int, bytes]:
    """Return the record type a cell's value is stored as, and its value bytes."""
    value = cell.value
    if isinstance(value, str):
        if pool is None:
            raise WriteError(
                f"{cell.address} was set to text and its table carries no string "
                "list to pool it in. A table that has never held text has none."
            )
        own = record.typeByte == stringTypeByte and not borrowed
        key = pool.keyFor(
            value, record.value if own and isinstance(record.value, int) else None
        )
        width = recordShapes[stringTypeByte].width
        return stringTypeByte, key.to_bytes(width, "little")
    if isinstance(value, bool):
        return booleanTypeByte, encodeSeconds(1.0 if value else 0.0)
    if isinstance(value, CurrencyAmount):
        return currencyTypeByte, Decimal128(value.amount).asBytes()
    if isinstance(value, Decimal):
        # A number over currency keeps its currency, which the format holds.
        kept = record.typeByte == currencyTypeByte and not borrowed
        return (
            currencyTypeByte if kept else numberTypeByte,
            Decimal128(value).asBytes(),
        )
    if isinstance(value, datetime.datetime):
        return dateTypeByte, encodeSeconds((value - appleEpoch).total_seconds())
    if isinstance(value, datetime.timedelta):
        return durationTypeByte, encodeSeconds(value.total_seconds())
    raise WriteError(
        f"{cell.address} was given a {type(value).__name__}, and pybers writes a "
        "Decimal, a CurrencyAmount, a str, a bool, a datetime or a timedelta."
    )


def buildWrittenRecord(
    cell: Cell,
    record: CellRecord,
    pool: EntryPool[str] | None,
    *,
    borrowed: bool = False,
    formatFor: Callable[[tsk.FormatStructArchive], int | None] = lambda wanted: None,
    formatOf: Callable[[int], tsk.FormatStructArchive | None] = lambda key: None,
) -> bytes:
    """Return this cell's record carrying its new value, retyped when its kind changed.

    **`borrowed` says the record belongs to another cell** and is here only for its
    style. Without it, the template's pooled key is read as this cell's previous
    claim, and a pool entry nothing else names is then rewritten in place: writing
    into an empty `J1` changed `I1` from `Item 1` to the new text, with nothing
    raised. Found by the golden on 2026-09-14.
    """
    refuseFormulaOverwrite(cell, record)
    if borrowed:
        record = decodeRecord(record.column, borrowShape(record))
    typeByte, encoded = encodeCellValue(cell, record, pool, borrowed)
    if typeByte == record.typeByte and not borrowed:
        patched = patchValue(record, encoded)
        if isinstance(cell.value, CurrencyAmount):
            patched = patchCurrencyCode(patched, record, cell, formatFor, formatOf)
        return patched
    own = record.typeByte == stringTypeByte and not borrowed
    if own and pool is not None and isinstance(record.value, int):
        pool.release(record.value)
    retyped = retypeRecord(
        record, typeByte, encoded,
        formatKey=formatFor(findAutomaticFormat(cell.value)),
    )
    if typeByte != currencyTypeByte:
        return retyped
    header = bytearray(retyped[:valueOffset])
    header[chosenFormatOffset] |= currencyChosenBit
    header[currencyCellOffset] |= currencyCellBit
    return bytes(header) + retyped[valueOffset:]


def patchCurrencyCode(
    raw: bytes,
    record: CellRecord,
    cell: Cell,
    formatFor: Callable[[tsk.FormatStructArchive], int | None],
    formatOf: Callable[[int], tsk.FormatStructArchive | None],
) -> bytes:
    """Return a currency record naming its new currency, every other setting kept.

    A custom format holds its currency in the document's list, which PYB-245 edits.
    """
    assert isinstance(cell.value, CurrencyAmount)
    key = findSlotValue(record, currencyFormatSlot)
    current = None if key is None else formatOf(key)
    if current is not None and current.currency_code == cell.value.currency:
        return raw
    if current is not None and current.format_type != currencyFormatType:
        raise WriteError(
            f"{cell.address} shows its currency through a custom format, and pybers "
            f"cannot change it to {cell.value.currency} yet."
        )
    wanted = buildCurrencyFormat(cell.value.currency)
    if current is not None:
        wanted.CopyFrom(current)
        wanted.currency_code = cell.value.currency
    fresh = formatFor(wanted)
    if fresh is None or key is None:
        raise WriteError(
            f"{cell.address} names no currency format to change to "
            f"{cell.value.currency}."
        )
    return patchSlotValue(raw, currencyFormatSlot, fresh)


def applyChosenFormat(raw: bytes, cell: Cell) -> bytes:
    """Return a record carrying the chosen bit its cell holds, for the slot it shows."""
    header = bytearray(raw[:valueOffset])
    chosenBit = findChosenBit(raw)
    if cell.presentation.formatChosen:
        header[chosenFormatOffset] |= chosenBit
    else:
        header[chosenFormatOffset] &= ~chosenBit
    return bytes(header) + raw[valueOffset:]


def findRecordShape(record: CellRecord) -> RecordShape:
    """Return how a record holds its value, refusing a type pybers cannot replace."""
    shape = recordShapes.get(record.typeByte)
    if shape is None:
        raise WriteError(
            f"The cell in column {record.column + originOffset} "
            f"{formatStoredValue(record)}, so pybers cannot tell where its value ends."
        )
    if len(record.raw) < valueOffset + shape.width:
        raise WriteError(
            f"The record for column {record.column + originOffset} is "
            f"{len(record.raw)} bytes, too short to hold the value it declares."
        )
    return shape


def patchValue(record: CellRecord, encoded: bytes) -> bytes:
    """Return one record with its value replaced and every other byte kept."""
    width = findRecordShape(record).width
    return record.raw[:valueOffset] + encoded + record.raw[valueOffset + width:]


def findFormatKey(
    pool: EntryPool[tsk.FormatStructArchive], wanted: tsk.FormatStructArchive
) -> int:
    """Return a key naming exactly this format, creating an entry when none does.

    Counts nothing: `moveFormatReferences` counts the record that names the key, so
    looking a format up once for many cells counts every cell.
    """
    key = pool.keyFind(wanted)
    return pool.entryAdd(wanted, 0) if key is None else key


def findTemplateRecord(
    index: ArchiveIndex, store: tst.DataStore, typeByte: int
) -> CellRecord | None:
    """Return a record to shape a new one from, preferring the type being written.

    A record created for a cell that had none has to choose every header byte and
    every trailing reference. Those references are keys into this table's own lists,
    so they are copied from a sibling rather than derived. The same reasoning shaped
    a new tile row for PYB-78. Any type pybers can replace will do, since what is
    borrowed is the style, never the value or the format.
    """
    fallback: CellRecord | None = None
    for stored in readStoredTiles(index, store):
        for record in stored.records:
            if carriesFormula(record) or record.typeByte not in recordShapes:
                continue
            if record.typeByte == typeByte:
                return record
            fallback = fallback or record
    return fallback


# The plain number `42` in `20-formula-shapes`, Numbers' own record for an unstyled
# number, used when a table holds no record to borrow a shape from.
plainNumberRecord: bytes = bytes.fromhex(
    "0502000000000000013000002a0000000000000000000000000040300100000001000000"
)


def borrowShape(record: CellRecord) -> bytes:
    """Return a sibling's record reduced to what a new cell may take from it: its style.

    A control describes the cell it was built for: writing into an empty cell gave
    it the pop-up menu of the cell whose shape it took. Found by the golden on
    2026-09-14. Every format slot and the displayed kind go too, since a new cell
    takes the Automatic format of its own kind, and so does byte 6's `0x80`, a
    format a person chose. A borrowed shape is not a borrowed decision.
    """
    raw = record.raw
    raw = bytes(raw[:6]) + bytes([raw[6] & ~chosenFormatBit]) + bytes(raw[7:])
    return removeSlots(raw, {controlSlot, displayedKindSlot, *countedFormatSlots})


def removeSlots(raw: bytes, dropped: set[tuple[int, int]]) -> bytes:
    """Return a record without the references some slots hold, their bits cleared."""
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


def applyAutomaticFormat(
    raw: bytes,
    value: CellValue,
    formatFor: Callable[[tsk.FormatStructArchive], int | None],
) -> bytes:
    """Return a record in its kind's Automatic format, its control gone, its value kept.

    A star rating is a format as well as a control, so dropping the control alone
    leaves Numbers drawing stars it can no longer edit, as a golden showed.
    """
    record = decodeRecord(0, raw)
    width = findRecordShape(record).width
    return retypeRecord(
        record, record.typeByte, raw[valueOffset:valueOffset + width],
        formatKey=formatFor(findAutomaticFormat(value)),
    )


def retypeRecord(
    record: CellRecord,
    typeByte: int,
    value: bytes,
    *,
    formatKey: int | None,
) -> bytes:
    """Return a record holding a value of another kind, in its Automatic format.

    The old kind's format slot and any control go, and the new kind's slot names
    `formatKey`. One bit leaves and one arrives, so the count the reference rule
    derives is unchanged. Every other reference keeps its slot and its value, which
    is what carries a cell's style across.
    """
    if formatKey is None:
        raise WriteError(
            f"The cell in column {record.column + originOffset} would change kind, "
            "and its table carries no format list to name the new kind's format in."
        )
    leaving = findRecordShape(record)
    arriving = recordShapes[typeByte]
    assert arriving.formatSlot is not None

    slots = listReferenceSlots(record.raw)
    carried = {
        slot: reference
        for slot, reference in zip(slots, record.references, strict=True)
        if slot not in (leaving.formatSlot, controlSlot)
    }
    carried[arriving.formatSlot] = formatKey
    carried[displayedKindSlot] = findSlotKind(arriving.formatSlot)

    header = bytearray(record.raw[:valueOffset])
    header[typeByteOffset] = typeByte
    header[formatFlagsOffset:formatFlagsOffset + formatFlagsWidth] = bytes(
        formatFlagsWidth
    )
    header[valueKindOffset] = (
        header[valueKindOffset] & ~valueBitsMask | arriving.valueBits
    )
    for at, bit in slots:
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
    "buildWrittenRecord",
    "findFormatKey",
    "findTemplateRecord",
    "findWrittenTypeByte",
    "numberTypeByte",
    "patchRichTextKey",
    "plainNumberRecord",
    "recordShapes",
    "applyAutomaticFormat",
]
