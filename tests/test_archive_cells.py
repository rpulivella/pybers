#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
Cell decoding, asserted against fixtures whose contents are known independently.

Every expectation here comes from a fixture that labels its own cells in an adjacent
row of text. That is the only reason these assertions mean anything: a wrong offset in
this format produces plausible wrong numbers rather than an exception, so a decoder can
only be checked against content established outside itself.

UPDATES
2026-08-18  Written with pybers.archive.cells.
2026-09-01  Added the caller-context regression, for #2.
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
import decimal
from decimal import Decimal
from pathlib import Path

import pytest

from pybers.archive import readPackage
from pybers.archive.cells import (
    CellDecodeError,
    decodeDecimal128,
    decodeRow,
    exponentBias,
)

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"

# TST.Tile and TST.TableModelArchive. Named here rather than imported because these
# identifiers are ours, read from the archive, and do not come from a generated constant.
tileTypeId: int = 6002
tableModelTypeId: int = 6001


def fixturePath(name: str) -> Path:
    """Return a fixture path, skipping when it has not been made yet."""
    path = fixtureDirectory / f"{name}.numbers"
    if not path.is_file():
        pytest.skip(f"Fixture {path.name} is not present.")
    return path


def valueRow(name: str) -> dict[int, object]:
    """Decode document row 0 of a fixture, returning column to value.

    Row 0 holds the values in every fixture built for this purpose; the labels sit in a
    later row and are read by eye, not by the tests.

    **Resolved through the tile list, not by scanning tile archives.** `27-big-table`
    established two things that make the obvious approach wrong: `tile_row_index` is
    local to its tile and restarts at zero in each one, so a 2001-row table has eight
    different rows numbered zero; and tile archive identifiers are not in row order, so
    iterating archives as they appear scrambles the table. `TileStorage.tiles` carries
    the authoritative order and the `tileid` that maps a tile to its row range.
    """
    from pybers._generated import TSTArchives_pb2 as tst

    package = readPackage(fixturePath(name))
    tiles = {
        archive.identifier: message.data
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
        for message in archive.messages
        if message.typeId == tileTypeId
    }

    for iwaFile in package.iwaFiles:
        for archive in iwaFile.archives:
            for message in archive.messages:
                if message.typeId != tableModelTypeId:
                    continue
                model = tst.TableModelArchive()
                model.ParseFromString(message.data)
                storage = model.base_data_store.tiles
                for entry in storage.tiles:
                    # Only the tile holding document row 0 is wanted here.
                    if entry.tileid * (storage.tile_size or 256) != 0:
                        continue
                    raw = tiles.get(entry.tile.identifier)
                    if raw is None:
                        continue
                    tile = tst.Tile()
                    tile.ParseFromString(raw)
                    for info in tile.rowInfos:
                        if info.tile_row_index != 0:
                            continue
                        records = decodeRow(
                            info.cell_offsets,
                            info.cell_storage_buffer,
                            info.has_wide_offsets,
                        )
                        if records:
                            return {r.column: r.value for r in records}
    raise AssertionError(f"No populated row 0 found in {name}.")


def testDecimal128DecodesExactly() -> None:
    """1234.5 is exact, which is the whole reason values are not floats.

    Built by hand rather than read from a file, so this tests the decoder and not the
    fixture: mantissa 12345 with exponent -1.
    """
    raw = (12345).to_bytes(8, "little") + ((6176 - 1) << 49).to_bytes(8, "little")
    assert decodeDecimal128(raw) == Decimal("1234.5")
    assert decodeDecimal128(raw) != Decimal("1234.4999999999999")


def testDecimal128CarriesSign() -> None:
    """The sign is the top bit, not a separate field."""
    negative = (12345).to_bytes(8, "little") + (
        (1 << 63) | ((6176 - 1) << 49)
    ).to_bytes(8, "little")
    assert decodeDecimal128(negative) == Decimal("-1234.5")


def testDecimal128ReadsTheLargeCoefficientFormAsZero() -> None:
    """The second BID layout decodes, and a non-canonical coefficient is zero.

    Setting both selector bits selects the form whose coefficient carries an implied
    leading `100`, which puts it past the 10^34 - 1 this format may hold. IEEE 754
    calls that non-canonical and gives it the value zero, so this must return a
    number rather than raising, and the number must be zero.
    """
    selector = (0x03 << 61) | (exponentBias << 47)
    raw = (0).to_bytes(8, "little") + selector.to_bytes(8, "little")
    assert decodeDecimal128(raw) == Decimal(0)


def testDecimal128RejectsAShortBuffer() -> None:
    """Too few bytes raises rather than decoding whatever happens to be there."""
    with pytest.raises(CellDecodeError, match="16 bytes"):
        decodeDecimal128(b"\x00" * 8)


def testValueTypesFixture() -> None:
    """Every value type in 11, matching the labels that fixture carries in its own text."""
    values = valueRow("11-value-types-noformats")

    assert values[0] == Decimal("1234.5")
    assert values[1] == Decimal("42")
    assert values[2] == datetime.datetime(2027, 6, 15, tzinfo=datetime.timezone.utc)
    assert values[3] == datetime.timedelta(minutes=20)
    assert values[4] is True
    # A star rating, a slider and a stepper: interactive controls store ordinary
    # numbers and reference their presentation separately, so they need no value type
    # of their own.
    assert values[5] == Decimal("3")
    assert values[6] == Decimal("50")
    assert values[7] == Decimal("1")

    # The cell labeled "empty" has no record at all, so it never appears.
    assert 9 not in values


def testCurrencyIsANumberWithADifferentTypeByte() -> None:
    """Currency decodes to the same value a plain number would.

    Currency is type 10 where a plain number is type 2, but the amount is encoded
    identically. Which currency it is belongs to the format, not the value, so the two
    must decode alike.
    """
    values = valueRow("12-number-currency")
    assert values[0] == Decimal("1234.5")
    for column in (1, 2, 3, 4):
        assert values[column] == Decimal("1234.5")
    for column in (5, 6, 8):
        assert values[column] == Decimal("-1234.5")


def testPercentStoresTheFractionNotTheDisplayedNumber() -> None:
    """A cell displaying 1,000% holds 10.0, and one displaying -0.25% holds -0.0025."""
    values = valueRow("13-number-percent")
    assert values[0] == Decimal("0.25")
    assert values[2] == Decimal("10.0")
    for column in (4, 5, 6):
        assert values[column] == Decimal("-0.0025")


def testDateTimeLivesInsideTheValue() -> None:
    """A date-time is one number: the time is not a separate field."""
    values = valueRow("14-number-date")
    midnight = datetime.datetime(2027, 6, 15, tzinfo=datetime.timezone.utc)
    withTime = datetime.datetime(2027, 6, 15, 11, tzinfo=datetime.timezone.utc)

    assert values[0] == midnight
    assert values[1] == withTime
    assert values[5] == withTime
    assert values[6] == withTime


def testFormulaCellCachesItsTypedResult() -> None:
    """A formula cell is typed by its RESULT, and the result is already stored.

    From 18, whose formulas compute from literals only: `=1+1` is an ordinary number
    cell holding 2 and `="a"&"b"` is a text cell. Reading a value therefore never
    requires evaluating a formula.
    """
    values = valueRow("18-formula-literals")
    assert values[0] == Decimal("2")       # =1+1
    assert values[1] == Decimal("6")       # =2*3
    assert values[2] == Decimal("6")       # =SUM(1,2,3)
    assert values[4] == Decimal("3")       # =ROUND(2.5,0)
    assert values[5] == Decimal("1")       # =IF(1>0,1,2)


def testUnknownTypeIsPreservedRatherThanRejected() -> None:
    """An unrecognized type byte yields no value but keeps the record intact.

    Currency is type 10, which neither published enum names, so this is not
    hypothetical. A library whose first duty is not to damage documents has to carry
    through what it does not understand.
    """
    from pybers.archive.cells import decodeRecord

    record = bytes([5, 99, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]) + b"\x01\x00\x00\x00"
    decoded = decodeRecord(0, record)
    assert decoded.typeByte == 99
    assert decoded.value is None
    assert decoded.raw == record


def testRichTextCellConsumesItsPayloadKey() -> None:
    """A rich-text cell's payload key is its VALUE, not its first style reference.

    Type 9 carries a four-byte key into the table's RICH_TEXT_PAYLOAD list, the same
    shape as a plain string's key into the STRING list. Before that was known the width
    defaulted to zero, so the payload key was mistaken for the first trailing reference
    and every reference on a rich-text cell was read one slot early, yielding plausible
    style keys that pointed at the wrong styles, with nothing raising.

    Built by hand so it tests the decoder rather than a fixture.
    """
    from pybers.archive.cells import decodeRecord

    record = (
        bytes([5, 9, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        + (7).to_bytes(4, "little")      # the rich-text payload key
        + (4).to_bytes(4, "little")      # the style reference that follows it
        + (1).to_bytes(4, "little")
    )
    decoded = decodeRecord(0, record)
    assert decoded.typeByte == 9
    assert decoded.value == 7, "the payload key is the value"
    assert decoded.references == (4, 1), "references start AFTER the payload key"


# ── The decode must not depend on the caller's decimal context ───────────────

@pytest.mark.parametrize("precision", [3, 6, 10, 28, 50])
def testDecimal128DecodesTheSameUnderAnyCallerContext(precision: int) -> None:
    """A regression. `scaleb` is arithmetic, so it obeyed the thread-local context.

    Under the default precision of 28 that rounded away the 34 digits decimal128
    can hold, and a caller who had set `prec=6` for their own arithmetic read
    1234567.891 out of a file as 1.23457E+6, with nothing raising. No fixture
    caught it because the most precise value in the whole corpus has 15 digits.
    """
    # A byte literal rather than a call to the encoder, so this regression stands
    # on its own if the encoder ever changes or breaks.
    raw = b"\xd3\x02\x96\x49" + bytes(10) + b"\x3a\x30"
    previous = decimal.getcontext().prec
    decimal.getcontext().prec = precision
    try:
        assert decodeDecimal128(raw) == Decimal("1234567.891")
    finally:
        decimal.getcontext().prec = previous


def testDecimal128KeepsAllThirtyFourDigits() -> None:
    """The format holds 34 significant digits and the decoder must return them all."""
    # 3.141592653589793238462643383279502, encoded by hand so the assertion does
    # not lean on the encoder.
    value = Decimal("3.141592653589793238462643383279502")
    assert len(value.as_tuple().digits) == 34
    raw = ((0 << 127) | ((-33 + exponentBias) << 113) | int("3141592653589793238462643383279502")).to_bytes(16, "little")
    assert decodeDecimal128(raw) == value
