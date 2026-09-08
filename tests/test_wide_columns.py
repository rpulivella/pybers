#!/usr/bin/env python3
"""\
A table wider than 255 columns, which stores its row offsets differently.

Numbers gives a row of 255 columns or fewer a fixed 255 slots holding byte
offsets. Past that it gives one slot per column holding offsets counted in
four-byte words, which keeps every offset a uint16 while a row grows to the
1000-column limit. The two layouts are indistinguishable to a decoder that
ignores the unit, because a wrong offset in this format yields a wrong value
rather than an exception.

`45-columns-over-255` is 300 columns by 7 rows, every cell naming its own
address, with four cells cleared from the last row so an empty slot in the wide
form is covered too.

UPDATES
2026-09-06  Written for #48.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/06"

from pathlib import Path

import pytest

import pybers
from conftest import archiveBodies
from pybers._generated import TSTArchives_pb2 as tst
from pybers.numbersfile import readPackage, writePackage
from pybers.numbersfile.cells import offsetUnitByte, offsetUnitFor, offsetUnitWord
from pybers.reader import ReadError
from pybers.writer import WriteError, rewriteRow, tileTypeId

fixtures: Path = Path(__file__).parent / "fixtures"
wideFixture: Path = fixtures / "45-columns-over-255.numbers"
narrowFixture: Path = fixtures / "11-value-types-noformats.numbers"

# The four cells cleared from the last row of the wide fixture.
clearedCells: tuple[str, ...] = ("B7", "E7", "DV7", "KM7")

# One synthetic record, the twelve-byte header and nothing after it. Its length
# is a multiple of four, as every record Numbers writes is.
alignedRecord: bytes = bytes(12)


def firstTable(document: pybers.Document) -> pybers.Table:
    """Return the document's first table."""
    return document.sheets[0].tables[0]


def testOffsetsCountWordsOnlyWhenTheArchiveSaysTheRowIsWide() -> None:
    """Either of Apple's two flags selects the word unit, and neither means byte."""
    assert offsetUnitFor(False, False) == offsetUnitByte
    assert offsetUnitFor(True, False) == offsetUnitWord
    assert offsetUnitFor(False, True) == offsetUnitWord
    assert offsetUnitFor(True, True) == offsetUnitWord


def testATableWiderThanTwoHundredFiftyFiveColumnsOpens() -> None:
    """The whole point: this raised before, on the first row of the first tile."""
    table = firstTable(pybers.open(wideFixture))
    assert (table.rowCount, table.colCount) == (7, 300)


def testEveryPopulatedCellReportsTheAddressItNames() -> None:
    """Each cell holds its own coordinate as text, so a wrong offset is visible.

    Column 300 matters most, being furthest from the start of the row: an offset
    off by a factor of four lands somewhere else entirely.
    """
    table = firstTable(pybers.open(wideFixture))
    assert table.cell("A1").value == "col1"
    assert table.cell("KN1").value == "col300"
    assert table.cell("B2").value == "r1c2"
    assert table.cell("KN7").value == "r6c300"


def testAClearedCellInAWideRowStaysEmpty() -> None:
    """An empty slot is `0xFFFF` in both layouts rather than a position.

    Reading the marker as an offset would give these cells a neighbor's text and
    shift every record after them, without raising.
    """
    table = firstTable(pybers.open(wideFixture))
    assert [table.cell(reference).value for reference in clearedCells] == [None] * 4
    assert table.cell("A7").value == "r6c1"
    assert table.cell("C7").value == "r6c3"


def testTheWideFixtureWritesBackUnchanged(tmp_path: Path) -> None:
    """The base contract, on the one fixture that reaches the other layout."""
    target = tmp_path / "written.numbers"
    pybers.open(wideFixture).save(target)
    assert archiveBodies(readPackage(target)) == archiveBodies(
        readPackage(wideFixture)
    )


def testANarrowTableStillReadsAsItDid() -> None:
    """A 255-slot row decodes exactly as before, so the fix added a case."""
    assert firstTable(pybers.open(narrowFixture)).cell("A2").value is not None


def testARowWhoseOffsetsFallOutsideItsBufferNamesWhereItIs(tmp_path: Path) -> None:
    """A byte count alone gives no way to find the row that carries it.

    Built by telling a narrow tile its rows are wide, which multiplies every
    offset by four and is the exact shape of the defect this ticket fixes.
    """
    package = readPackage(narrowFixture)
    for iwaFile in package.iwaFiles:
        for archive in list(iwaFile.archives):
            if archive.messages[0].typeId != tileTypeId:
                continue
            tile = tst.Tile()
            tile.ParseFromString(archive.messages[0].data)
            tile.should_use_wide_rows = True
            iwaFile.messageReplace(archive.identifier, 0, tile.SerializeToString())

    target = tmp_path / "mislabeled.numbers"
    writePackage(package, target)
    with pytest.raises(ReadError) as raised:
        pybers.open(target)

    message = str(raised.value)
    assert target.name in message
    assert "table" in message
    assert "row 1" in message


def testRewritingAWideRowScalesTheOffsetsItWrites() -> None:
    """A rebuilt wide row names positions in words, as the row it replaced did."""
    offsets = b"\x00\x00\x03\x00"
    buffer = alignedRecord * 2
    rebuiltOffsets, rebuiltBuffer = rewriteRow(offsets, buffer, offsetUnitWord, {})
    assert rebuiltOffsets == offsets
    assert rebuiltBuffer == buffer


def testRewritingANarrowRowStillNamesPositionsInBytes() -> None:
    """The same rebuild on a byte-counting row, which must not be rescaled."""
    offsets = b"\x00\x00\x0c\x00"
    buffer = alignedRecord * 2
    rebuiltOffsets, rebuiltBuffer = rewriteRow(offsets, buffer, offsetUnitByte, {})
    assert rebuiltOffsets == offsets
    assert rebuiltBuffer == buffer


def testARecordTheOffsetUnitCannotNameIsRefused() -> None:
    """A record of a length the unit does not divide would move every record
    after it, so the write refuses rather than producing a row that reads back
    as different values."""
    with pytest.raises(WriteError, match="not a multiple of the 4-byte"):
        rewriteRow(
            b"\x00\x00\x03\x00",
            alignedRecord * 2,
            offsetUnitWord,
            {0: alignedRecord + b"\x00\x00"},
        )
