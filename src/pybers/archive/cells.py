#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
2026-09-01  Fixed decodeDecimal128 obeying the caller's decimal context, which
            rounded a value on read and made a file's contents depend on what
            the calling program had set.
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
from decimal import Decimal

# Apple counts dates from 2001-01-01 UTC rather than the Unix epoch.
appleEpoch: datetime.datetime = datetime.datetime(
    2001, 1, 1, tzinfo=datetime.timezone.utc
)

# Offsets are uint16 unless the row says otherwise, and this value marks a column
# with no cell at all. An empty cell is an ABSENCE of a record, not a record holding
# nothing, so it never reaches the decoder below.
emptyOffsetNarrow: int = 0xFFFF
emptyOffsetWide: int = 0xFFFFFFFF

# The value begins here in every record seen. Bytes 0-11 carry the storage version,
# the type, a flags bitmask at 6-7, and four bytes whose purpose is not established.
valueOffset: int = 12


class CellDecodeError(RuntimeError):
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


# Both IEEE-754 decimal128 forms are implemented. The largest coefficient the format
# may hold is 10^34 - 1; anything above it is non-canonical and reads as zero.
maximumCoefficient: int = 10**34 - 1

# The exponent is stored biased so it can be unsigned.
exponentBias: int = 6176


def decodeDecimal128(raw: bytes) -> Decimal:
    """Decode 16 bytes of little-endian IEEE-754 decimal128 into a Decimal.

    Apple stores numbers in the binary-integer (BID) interchange form, which has two
    layouts selected by the two bits below the sign.

    The common one puts a 14-bit biased exponent at bits 126-113 and a 113-bit
    coefficient below it. Every value in every file examined uses this.

    When both selector bits are set the fields move: the exponent sits at bits
    124-111 and the coefficient gains an implied leading `100`. That form can only
    express coefficients of 2^113 or more, which is already past the 10^34 - 1 this
    format may hold, so a canonical encoder never emits it, which is why it has
    never been seen here. It is decoded anyway rather than refused, because a reader
    that rejects a file over a corner the specification already defines is worse than
    one that follows the specification. Per IEEE 754 a coefficient beyond the maximum
    is non-canonical and its value is zero.
    """
    if len(raw) < 16:
        raise CellDecodeError(f"decimal128 needs 16 bytes, got {len(raw)}.")
    low = int.from_bytes(raw[:8], "little")
    high = int.from_bytes(raw[8:16], "little")

    sign = -1 if (high >> 63) & 1 else 1

    if (high >> 61) & 0x03 == 0x03:
        exponent = ((high >> 47) & 0x3FFF) - exponentBias
        # 47 bits of the high word, then the whole low word, under an implied 0b100.
        mantissa = (0b100 << 111) | ((high & 0x00007FFFFFFFFFFF) << 64) | low
    else:
        exponent = ((high >> 49) & 0x3FFF) - exponentBias
        # 49 bits of the high word, then the whole low word.
        mantissa = ((high & 0x0001FFFFFFFFFFFF) << 64) | low

    if mantissa > maximumCoefficient:
        mantissa = 0

    # Built from its digit tuple rather than with `scaleb`, which is an arithmetic
    # operation and therefore obeys the caller's thread-local decimal context. Under
    # the default precision of 28 that silently rounded the 34 digits decimal128 can
    # hold, and under a caller who had set `prec=6` for their own arithmetic it
    # turned 1234567.891 on disk into 1.23457E+6 with nothing raising. What a file
    # says cannot depend on what the calling program happens to be doing.
    return Decimal((0 if sign > 0 else 1, tuple(int(d) for d in str(mantissa)), exponent))


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
        return decodeDecimal128(body[:16]), 16
    if typeByte == 3:
        # A key into the table's STRING data list. Strings are pooled and shared
        # across cells; only the key lives in the record.
        return int.from_bytes(body[:4], "little"), 4
    if typeByte == 9:
        # Rich text: a key into the table's RICH_TEXT_PAYLOAD list rather than the
        # string list. Same four-byte shape as a plain string, and that similarity is
        # exactly what made it dangerous. Before this branch existed the width defaulted to zero,
        # so the payload key was mistaken for the first trailing reference and every
        # reference on a rich-text cell was read one slot early. It produced plausible
        # style keys pointing at the wrong styles, with nothing raising.
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


def decodeRow(cellOffsets: bytes, storageBuffer: bytes, wideOffsets: bool) -> list[CellRecord]:
    """Decode every populated cell in one row.

    The offsets array has a fixed slot per possible column, most of them marked
    empty. A record runs from its own offset to the next populated one, so the
    offsets must be walked in column order for the boundaries to be right.
    """
    width = 4 if wideOffsets else 2
    empty = emptyOffsetWide if wideOffsets else emptyOffsetNarrow
    count = len(cellOffsets) // width
    unpacked = struct.unpack(f"<{count}{'I' if wideOffsets else 'H'}", cellOffsets[:count * width])

    populated = [(column, at) for column, at in enumerate(unpacked) if at != empty]
    records: list[CellRecord] = []
    for index, (column, at) in enumerate(populated):
        end = populated[index + 1][1] if index + 1 < len(populated) else len(storageBuffer)
        records.append(decodeRecord(column, storageBuffer[at:end]))
    return records
