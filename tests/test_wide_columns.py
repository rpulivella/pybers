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
2026-10-22  The golden's comparison moved to the golden builders, for PYB-255.
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

import shutil
from pathlib import Path

import pytest

import pybers
from conftest import (
    findDocumentPath,
    readRecordedColumns,
    readRecordedRows,
)
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import readPackage, writePackage
from pybers._persistence.cells import chooseOffsetUnit, offsetUnitByte, offsetUnitWord
from pybers._persistence.difference import listPackageDifferences
from pybers._persistence.types import findArchiveTypeId
from pybers.addressing.reference import CellReference, originOffset
from pybers.errors import ReadError, WriteError
from pybers.table._tiles import rewriteRow

wideFixture: Path = findDocumentPath("45-columns-over-255")
narrowMeasurement: Path = findDocumentPath("11-value-types-noformats")

tileTypeId: int = findArchiveTypeId(tst.Tile)

# The four cells cleared from the last row of the wide fixture.
clearedCells: tuple[str, ...] = ("B7", "E7", "DV7", "KM7")

# The edit exercised end to end. It sits past the 255-column boundary and in the
# one row carrying gaps, so a rebuild that fills an empty slot shows up here.
# The row and column are stored coordinates, counted from zero, which is why
# they read one lower than the `KI7` the same cells answer to.
wideMerge: str = "KI7:KJ7"
editedRow: int = 6
wideMergeCovered: int = 295

# One synthetic record, the twelve-byte header and nothing after it. Its length
# is a multiple of four, as every record Numbers writes is.
alignedRecord: bytes = bytes(12)


def findFirstTable(document: pybers.Document) -> pybers.Table:
    """Return the document's first table."""
    return document.sheets[0].tables[0]


def testOffsetsCountWordsOnlyWhenTheRowSaysItIsWide() -> None:
    """The row's own flag decides, and the tile's says nothing about its rows."""
    assert chooseOffsetUnit(False, False) == offsetUnitByte
    assert chooseOffsetUnit(True, False) == offsetUnitWord
    assert chooseOffsetUnit(False, True) == offsetUnitByte
    assert chooseOffsetUnit(True, True) == offsetUnitWord


def testATileMarkedWideWhoseRowsAreNarrowOpens() -> None:
    """`58-buckets-at-limit` sets the tile's flag over rows that keep byte offsets.

    Reading those by the tile's flag put every record past the end of its buffer.
    """
    table = findFirstTable(pybers.open(findDocumentPath("58-buckets-at-limit")))
    assert table.rowCount == 65536
    assert table.cell(row=1, col=1).value is not None


def testATableWiderThanTwoHundredFiftyFiveColumnsOpens() -> None:
    """The whole point: this raised before, on the first row of the first tile."""
    table = findFirstTable(pybers.open(wideFixture))
    assert (table.rowCount, table.colCount) == (7, 300)


def testEveryPopulatedCellReportsTheAddressItNames() -> None:
    """Each cell holds its own coordinate as text, so a wrong offset is visible.

    Column 300 matters most, being furthest from the start of the row: an offset
    off by a factor of four lands somewhere else entirely.
    """
    table = findFirstTable(pybers.open(wideFixture))
    assert table.cell("A1").value == "col1"
    assert table.cell("KN1").value == "col300"
    assert table.cell("B2").value == "r1c2"
    assert table.cell("KN7").value == "r6c300"


def testAClearedCellInAWideRowStaysEmpty() -> None:
    """An empty slot is `0xFFFF` in both layouts rather than a position.

    Reading the marker as an offset would give these cells a neighbor's text and
    shift every record after them, without raising.
    """
    table = findFirstTable(pybers.open(wideFixture))
    assert [table.cell(reference).value for reference in clearedCells] == [None] * 4
    assert table.cell("A7").value == "r6c1"
    assert table.cell("C7").value == "r6c3"


def testTheWideFixtureWritesBackUnchanged(tmp_path: Path) -> None:
    """The base contract, on the one fixture that reaches the other layout."""
    target = tmp_path / "written.numbers"
    pybers.open(wideFixture).save(target)
    assert listPackageDifferences(readPackage(wideFixture), readPackage(target)) == []


def testANarrowTableStillReadsAsItDid() -> None:
    """A 255-slot row decodes exactly as before, so the fix added a case."""
    assert findFirstTable(pybers.open(narrowMeasurement)).cell("A2").value is not None


def testARowWhoseOffsetsFallOutsideItsBufferNamesWhereItIs(tmp_path: Path) -> None:
    """A byte count alone gives no way to find the row that carries it.

    Built by telling each narrow row it is wide, which multiplies every offset by
    four and is the exact shape of the defect the wide-row ticket fixed.
    """
    package = readPackage(narrowMeasurement)
    for iwaFile in package.iwaFiles:
        for archive in list(iwaFile.archives):
            if archive.messages[0].typeId != tileTypeId:
                continue
            tile = tst.Tile()
            tile.ParseFromString(archive.messages[0].data)
            for rowInfo in tile.rowInfos:
                rowInfo.has_wide_offsets = True
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


@pytest.fixture
def widelyMerged(tmp_path: Path) -> Path:
    """The wide fixture with one merge past column 255, written and closed.

    A merge is the only edit that reaches `rewriteRow` on this document: every
    cell is text, so a value write refuses, and a formula attach refuses because
    no dependency tile covers these columns. Measured 2026-09-08 for #53.
    """
    target = Path(shutil.copy(wideFixture, tmp_path / "45-merged.numbers"))
    document = pybers.open(target)
    findFirstTable(document).mergeAdd(wideMerge)
    document.save()
    return target


def testAMergePastColumnTwoFiftyFiveDropsOnlyTheCoveredRecord(
    widelyMerged: Path,
) -> None:
    """One record leaves the row, and no slot gains one."""
    before = readRecordedColumns(wideFixture, editedRow)
    after = readRecordedColumns(widelyMerged, editedRow)
    assert before - after == {wideMergeCovered}
    assert after - before == set()


def testEveryOtherCellInTheEditedRowStillNamesItself(widelyMerged: Path) -> None:
    """A wrong offset yields a wrong value, not an exception, so read all of them."""
    table = findFirstTable(pybers.open(widelyMerged))
    surviving = {
        column: table.cell(CellReference(editedRow + originOffset, column)).value
        for column in range(originOffset, table.colCount + originOffset)
        if column != wideMergeCovered + originOffset
    }
    original = findFirstTable(pybers.open(wideFixture))
    assert surviving == {
        column: original.cell(CellReference(editedRow + originOffset, column)).value
        for column in surviving
    }


@pytest.mark.parametrize("reference", clearedCells)
def testAGapInTheEditedRowIsStillAGap(widelyMerged: Path, reference: str) -> None:
    """An empty slot is an absent record, and a rebuild must not fill one in."""
    assert findFirstTable(pybers.open(widelyMerged)).cell(reference).value is None


def testTheRowsTheEditDidNotTouchAreUnchanged(widelyMerged: Path) -> None:
    """An edit to one row rewrites that row and leaves the rest of the tile alone."""
    before = readRecordedRows(wideFixture)
    after = readRecordedRows(widelyMerged)
    assert {row: columns for row, columns in before.items() if row != editedRow} == {
        row: columns for row, columns in after.items() if row != editedRow
    }


def testAFormulaStillCannotReachAColumnPastTwoFiftyFive(tmp_path: Path) -> None:
    """Refuse rather than leave this document half-edited.

    Registering a formula in one of the engine's two registers and not the other
    would leave a stale result Numbers never recalculates, so the write refuses
    instead. Borrowed from `19` because this fixture holds no formula to copy.
    """
    borrowed = findFirstTable(pybers.open(findDocumentPath("19-formula-dragged")))
    target = Path(shutil.copy(wideFixture, tmp_path / "45-formula.numbers"))
    document = pybers.open(target)
    findFirstTable(document).cell("KJ7").formula = borrowed.cell("E2").formula
    with pytest.raises(WriteError, match="No dependency tile covers"):
        document.save()
