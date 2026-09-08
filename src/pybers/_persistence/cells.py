#!/usr/bin/env python3
"""\
Cell values: the one part of the format the protobuf schemas do not describe.

A table's rows live in `TST.Tile`, but the cells inside a row do not. They sit in an
opaque `cell_storage_buffer` indexed by a `cell_offsets` array, in a layout Apple
never published. Everything here was reverse-engineered against the fixtures under
tests/fixtures/, each of which carries a row of text labels describing its own
contents, which is what makes a decode verifiable rather than merely plausible.

The failure mode to keep in mind while reading this module: a wrong offset in this
format yields **wrong numbers, not an exception**. Every field is a fixed-width
integer or float, so misreading one still parses. That is why the layout constants
below are stated once and why the tests assert decoded values against fixtures whose
contents are known independently.

Values are returned as `Decimal`, never `float`. Numbers stores them as IEEE-754
decimal128, so `1234.5` is exact; routing it through a binary float would introduce
rounding error into a document that never had any. See `pybers.model.table`.

UPDATES
2026-08-18  Written. Decodes numbers, currency, text, dates, booleans and durations,
            verified against fixtures 11 through 14.
2026-09-03  The formula flag moved here from the writer for #41, so the one
            module documenting the record layout owns all of it.
2026-09-01  Moved the decimal128 codec out to pybers._persistence.decimal128, which
            owns the format's limits and its 16-byte form as a real type. This
            module keeps only Apple's own undocumented cell layout.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/18"

import datetime
import struct
from dataclasses import dataclass

from ..errors import PybersError
from .decimal128 import Decimal128

# Apple counts dates from 2001-01-01 UTC rather than the Unix epoch.
appleEpoch: datetime.datetime = datetime.datetime(
    2001, 1, 1, tzinfo=datetime.UTC
)

# Every offset is a uint16 in both layouts, and this value marks a column with no
# cell at all. An empty cell is an ABSENCE of a record, not a record holding
# nothing, so it never reaches the decoder below.
offsetWidth: int = 2
emptyOffset: int = 0xFFFF

# What an offset COUNTS varies with the row's width. A table of 255 columns or
# fewer counts bytes; a wider one counts four-byte words, which keeps the offset a
# uint16 while a row grows to Numbers' 1000-column limit. Lossless because every
# record is already four-byte aligned: measured 2026-09-06, all 9,497 offsets in
# the 46 fixtures that predate 45-columns-over-255 are multiples of four.
offsetUnitByte: int = 1
offsetUnitWord: int = 4

# The value begins here in every record seen. Bytes 0-11 carry the storage version,
# the type, a flags bitmask at 6-7, and four bytes whose purpose is not established.
valueOffset: int = 12

# Byte 9 of the header is a second bitmask, and this bit marks a cell backed by a
# formula. Established across the corpus on 2026-09-01: in all 74 tables, a table
# declaring formulas has marked records and a table declaring none has none. The
# marked count can exceed the declared count, because the formula list is pooled,
# so a dragged formula and a merge both reuse one entry across several cells.
formulaFlagOffset: int = 9
formulaFlagBit: int = 0x02


class CellDecodeError(PybersError, RuntimeError):
    """A cell record that could not be decoded."""


@dataclass(frozen=True)
class CellRecord:
    """One decoded cell: its value, the raw type byte, and the references after it.

    `typeByte` is kept raw rather than mapped to an enum. It agrees with
    `TST.CellType` for the common types and then does not: currency is 10, which
    neither `CellType` nor `CellValueType` defines. Preserving the byte means an
    unrecognized type is carried through rather than rejected, which matters for a
    library whose first duty is not to damage documents it does not fully understand.

    `references` are the trailing uint32 values, whose presence is gated by the flags
    bitmask. They point into the table's data lists, the last one varies with the
    display format. Their individual meanings are not established, so they are kept
    as read.
    """

    column: int
    typeByte: int
    flags: int
    value: object
    references: tuple[int, ...]
    raw: bytes


def decodeCellValue(typeByte: int, body: bytes) -> tuple[object, int]:
    """Return one cell's value and the number of bytes it occupied.

    The width is returned because the trailing references start immediately after the
    value, so it is not a fixed offset. Reading them at a constant position was a real
    bug: it silently skipped two fields on every date, boolean and duration cell while
    still parsing, because what followed was also integers.

    An unrecognized type yields `None` and consumes nothing, so the record survives
    intact even when its value cannot be interpreted.
    """
    if typeByte in (2, 10):
        # 2 is a plain number, 10 is currency. Currency is a distinct type but not a
        # distinct encoding: the amount sits here identically, and which currency it
        # is belongs to the format, not the value.
        return Decimal128.fromBytes(body[:16]).value, 16
    if typeByte == 3:
        # A key into the table's STRING data list. Strings are pooled and shared
        # across cells; only the key lives in the record.
        return int.from_bytes(body[:4], "little"), 4
    if typeByte == 9:
        # Rich text: a key into the table's RICH_TEXT_PAYLOAD list rather than the
        # string list. Same four-byte shape as a plain string, and that similarity is
        # exactly what made it dangerous. Before this branch existed the width defaulted
        # to zero, so the payload key was mistaken for the first trailing reference and
        # every reference on a rich-text cell was read one slot early. It produced
        # plausible style keys pointing at the wrong styles, with nothing raising.
        return int.from_bytes(body[:4], "little"), 4
    if typeByte == 5:
        seconds = struct.unpack("<d", body[:8])[0]
        return appleEpoch + datetime.timedelta(seconds=seconds), 8
    if typeByte == 6:
        return struct.unpack("<d", body[:8])[0] != 0, 8
    if typeByte == 7:
        return datetime.timedelta(seconds=struct.unpack("<d", body[:8])[0]), 8
    return None, 0


def decodeRecord(column: int, record: bytes) -> CellRecord:
    """Decode one cell record from a row's storage buffer."""
    if len(record) < valueOffset:
        raise CellDecodeError(
            f"Cell record for column {column} is {len(record)} bytes, shorter than "
            f"the {valueOffset}-byte header."
        )
    typeByte = record[1]
    flags = int.from_bytes(record[6:8], "little")
    value, width = decodeCellValue(typeByte, record[valueOffset:])

    referenceStart = valueOffset + width
    references = tuple(
        int.from_bytes(record[at:at + 4], "little")
        for at in range(referenceStart, len(record) - 3, 4)
    )
    return CellRecord(
        column=column,
        typeByte=typeByte,
        flags=flags,
        value=value,
        references=references,
        raw=record,
    )


# Byte 8 bit 0x40 puts exactly one reference ahead of the formula key. Measured
# 2026-09-04 by refcount reproduction: across every fixture and all 74 formula
# cells, of every assignment of a slot to each flag shape, exactly one
# reproduces each pooled formula's own refcount, and it turns on this bit alone.
# What the preceding reference is has not been established, only that it is
# there. 46-formula-rare-functions is the only fixture that sets the bit, which
# is why a constant slot read the whole corpus correctly and read that one wrong.
precedingReferenceOffset: int = 8
precedingReferenceBit: int = 0x40


def formulaKeySlot(record: CellRecord) -> int:
    """Return which trailing reference of a record holds its formula key."""
    carries = (
        len(record.raw) > precedingReferenceOffset
        and bool(record.raw[precedingReferenceOffset] & precedingReferenceBit)
    )
    return 1 if carries else 0


def carriesFormula(record: CellRecord) -> bool:
    """Report whether a cell record is backed by a formula."""
    return (
        len(record.raw) > formulaFlagOffset
        and bool(record.raw[formulaFlagOffset] & formulaFlagBit)
    )


def offsetUnitFor(hasWideOffsets: bool, tileUsesWideRows: bool) -> int:
    """Return what one row's offsets count, from the archive's own two flags.

    The parameters carry Apple's spelling because they are Apple's fields:
    `TileRowInfo.has_wide_offsets` and `Tile.should_use_wide_rows`. Both are set
    together in every document measured, and either alone is honored.
    """
    return offsetUnitWord if hasWideOffsets or tileUsesWideRows else offsetUnitByte


def decodeRow(
    cellOffsets: bytes, storageBuffer: bytes, offsetUnit: int
) -> list[CellRecord]:
    """Decode every populated cell in one row.

    The offsets array holds one slot per addressable column, most of them marked
    empty. A record runs from its own offset to the next populated one, so the
    offsets must be walked in column order for the boundaries to be right. The
    slot count is taken from the array itself rather than from a rule, since the
    two layouts size it differently and both sizes are already written down here.
    """
    count = len(cellOffsets) // offsetWidth
    unpacked = struct.unpack(
        f"<{count}H", cellOffsets[:count * offsetWidth]
    )
    populated = [
        (column, at * offsetUnit)
        for column, at in enumerate(unpacked)
        if at != emptyOffset
    ]

    beyond = [column for column, at in populated if at >= len(storageBuffer)]
    if beyond:
        raise CellDecodeError(
            f"{len(beyond)} of {len(populated)} cell offsets fall outside the "
            f"{len(storageBuffer)}-byte storage buffer, the first at column "
            f"{beyond[0]}. Offsets counted in units of {offsetUnit} byte(s)."
        )

    records: list[CellRecord] = []
    for index, (column, at) in enumerate(populated):
        end = (
            populated[index + 1][1]
            if index + 1 < len(populated)
            else len(storageBuffer)
        )
        records.append(decodeRecord(column, storageBuffer[at:end]))
    return records
