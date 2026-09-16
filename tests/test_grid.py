#!/usr/bin/env python3
"""\
Walking a table's declared grid, row by row or whole, and reaching a cell by number.

`22d-merge-multi-row` is the merge document because its text names each position,
so a covered position is recognizable in the anchor's joined value, and its three
merges span rows as well as columns. `20-formula-shapes` carries the measurement
the ticket quotes, 26 stored cells in a declared grid of 96.

UPDATES
2026-09-14  Written for PYB-62.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/14"

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from conftest import findDocumentPath, readArchiveBodies
from pybers._persistence import readPackage
from pybers.addressing import ReferenceError
from pybers.table import Cell, Table


def openDocumentTable(name: str, table: str | int = 1) -> Table:
    """Return one table from the first sheet of a document."""
    return pybers.open(findDocumentPath(name)).sheet(1).table(table)


def openMergedTable() -> Table:
    """Return `22d`, five rows by seven columns with merges A2:A3, C2:D3 and F2:F4."""
    return openDocumentTable("22d-merge-multi-row")


def listWalkAddresses(cells: object) -> list[str]:
    """Return the written address of each cell in a walk, in the order walked."""
    return [str(cell.reference) for cell in cells]  # type: ignore[attr-defined]


# ── AC 1: the declared grid, each cell once ──────────────────────────────────


def testAWalkYieldsEveryPositionOfTheDeclaredGridInRowOrder() -> None:
    """`Table 2` stores one cell and declares ten rows by five columns."""
    table = openDocumentTable("20-formula-shapes", "Table 2")
    walked = listWalkAddresses(table.gridIterate())

    assert len(walked) == 50
    assert walked[:6] == ["A1", "B1", "C1", "D1", "E1", "A2"]
    assert walked[-1] == "E10"


def testAWalkYieldsEachCellOnce() -> None:
    walked = list(openMergedTable().gridIterate())

    assert len({id(cell) for cell in walked}) == len(walked)


def testAMergedBlockAppearsAtItsAnchorAndNowhereElse() -> None:
    walked = listWalkAddresses(openMergedTable().gridIterate())

    assert {"A2", "C2", "F2"} <= set(walked)
    assert not {"A3", "C3", "D2", "D3", "F3", "F4"} & set(walked)
    assert len(walked) == 35 - 6


# ── AC 2: row by row, with len, indexing and slicing ─────────────────────────


def testTheRowsOfATableAreItsDeclaredRows() -> None:
    rows = openMergedTable().rows

    assert len(rows) == 5
    assert rows[0].rowNumber == 1
    assert rows[-1].rowNumber == 5
    assert [row.rowNumber for row in rows[1:3]] == [2, 3]


def testARowHoldsOnlyTheCellsNoMergeSwallowed() -> None:
    rows = openMergedTable().rows

    assert listWalkAddresses(rows[1]) == ["A2", "B2", "C2", "E2", "F2", "G2"]
    assert listWalkAddresses(rows[2]) == ["B3", "E3", "G3"]
    assert len(rows[2]) == 3


def testIndexingARowCountsItsCellsRatherThanItsColumns() -> None:
    row = openMergedTable().rows[1]

    assert str(row[3].reference) == "E2"
    assert str(row[-1].reference) == "G2"
    assert listWalkAddresses(row[1:4]) == ["B2", "C2", "E2"]


def testIndexingPastTheEndRaisesIndexError() -> None:
    rows = openMergedTable().rows

    with pytest.raises(IndexError):
        rows[5]
    with pytest.raises(IndexError):
        rows[2][3]


def testWalkingRowByRowYieldsWhatTheWholeWalkYields() -> None:
    table = openMergedTable()

    assert [cell for row in table.rows for cell in row] == list(table.gridIterate())


def testARowTakenBeforeAMergeHoldsWhatTheMergeLeft() -> None:
    table = Table("Later", rowCount=2, colCount=3)
    row = table.rows[0]

    table.mergeAdd("A1:B2")

    assert listWalkAddresses(row) == ["A1", "C1"]
    assert len(row) == 2


def testRowsAndSlicesCompareByWhatTheyName() -> None:
    table = openMergedTable()

    assert table.rows[1] == table.rows[1]
    assert table.rows[1:3] == table.rows[1:3]
    assert table.rows[1] in table.rows
    assert table.rows[1] != openMergedTable().rows[1]


# ── AC 3: measuring or slicing creates no cell ───────────────────────────────


def testMeasuringAndSlicingAWalkCreatesNoCell() -> None:
    table = openDocumentTable("20-formula-shapes")
    stored = len(table.cells)

    rows = table.rows
    row = rows[3]
    measured = (len(rows), len(rows[2:9]), len(row), len(row[2:6]), len(row[-3:]))

    assert measured == (12, 7, 8, 4, 3)
    assert len(table.cells) == stored


def testAskingWhetherARowHoldsACellCreatesNoCell() -> None:
    table = openDocumentTable("20-formula-shapes")
    stored = len(table.cells)
    held = table.cell("A1")

    assert held in table.rows[0]
    assert held not in table.rows[1]
    assert len(table.cells) == stored


def testReachingACellCreatesOnlyThatCell() -> None:
    table = openDocumentTable("20-formula-shapes", "Table 2")

    table.rows[9][4]

    assert set(listWalkAddresses(table.cells.values())) == {"A1", "E10"}


def testAWholeWalkStoresEveryCellOfTheGrid() -> None:
    """The measurement the ticket records, 26 stored cells becoming 96."""
    table = openDocumentTable("20-formula-shapes")
    assert len(table.cells) == 26

    for _ in table.gridIterate():
        pass

    assert len(table.cells) == 96


def testAWalkChangesNothingInTheSavedFile(tmp_path: Path) -> None:
    source = findDocumentPath("20-formula-shapes")
    untouched, walked = tmp_path / "untouched.numbers", tmp_path / "walked.numbers"
    pybers.open(source).save(untouched)
    document = pybers.open(source)
    for sheet in document.sheets:
        for table in sheet.tables:
            for _ in table.gridIterate():
                pass

    document.save(walked)

    assert readArchiveBodies(readPackage(walked)) == readArchiveBodies(
        readPackage(untouched)
    )


# ── AC 4: no grid walks as nothing ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("rowCount", "colCount"), [(0, 0), (3, 0), (0, 3)], ids=["neither", "rows", "cols"]
)
def testATableThatDeclaresNoGridWalksAsNothing(rowCount: int, colCount: int) -> None:
    table = Table("Empty", rowCount=rowCount, colCount=colCount)

    assert list(table.gridIterate()) == []
    assert len(table.rows) == 0
    assert list(table.rows) == []


# ── AC 5: a cell by number, its axes named ───────────────────────────────────


def testRowAndColNameTheCellTheirAddressNames() -> None:
    table = openDocumentTable("20-formula-shapes")

    assert table.cell(row=3, col=5) is table.cell("E3")


def testANumberedCellHasItsAxesNamed() -> None:
    table = openDocumentTable("20-formula-shapes")

    with pytest.raises(TypeError):
        table.cell(3, 5)  # type: ignore[call-arg, misc]


@pytest.mark.parametrize(
    "named",
    [
        {"row": 3},
        {"col": 5},
        {},
        {"address": "E3", "row": 3, "col": 5},
        {"row": True, "col": 5},
        {"row": 3, "col": "E"},
        {"row": 0, "col": 5},
        {"row": 3, "col": -1},
        {"row": 13, "col": 1},
        {"row": 1, "col": 9},
    ],
    ids=[
        "rowAlone",
        "colAlone",
        "nothing",
        "addressAndNumbers",
        "boolRow",
        "letterCol",
        "rowZero",
        "colNegative",
        "rowPastGrid",
        "colPastGrid",
    ],
)
def testACellNamedWrongIsRefusedAndCreatesNothing(named: dict[str, object]) -> None:
    table = openDocumentTable("20-formula-shapes")
    stored = len(table.cells)

    with pytest.raises(ReferenceError):
        table.cell(**named)  # type: ignore[arg-type]
    assert len(table.cells) == stored


def testACoveredPositionIsRefusedByNumberAsByAddress() -> None:
    with pytest.raises(ReferenceError, match="anchor is A2"):
        openMergedTable().cell(row=3, col=1)


# ── AC 6: a walk and a lookup hand over the same cell ────────────────────────


def testEveryCellAWalkYieldsIsTheCellTheTableReturns() -> None:
    table = openMergedTable()

    assert all(cell is table.cell(cell.reference) for cell in table.gridIterate())


def testAWriteThroughAWalkReachesTheFile(tmp_path: Path) -> None:
    working = tmp_path / "walked.numbers"
    shutil.copy(findDocumentPath("20-formula-shapes"), working)
    document = pybers.open(working)

    last = list(document.sheet(1).table("Table 2").gridIterate())[-1]
    last.value = Decimal("7.25")
    document.save()

    reopened = pybers.open(working).sheet(1).table("Table 2")
    assert reopened.cells[last.reference].value == Decimal("7.25")


def testAWriteThroughARowReachesTheFile(tmp_path: Path) -> None:
    working = tmp_path / "rows.numbers"
    shutil.copy(findDocumentPath("20-formula-shapes"), working)
    document = pybers.open(working)

    document.sheet(1).table("Table 2").rows[4][2].value = "through a row"
    document.save()

    reopened = pybers.open(working).sheet(1).table("Table 2")
    assert reopened.cell(row=5, col=3).value == "through a row"


# ── AC 7: a cell says which merge it anchors ─────────────────────────────────


def testAnAnchorSaysWhichMergeItAnchors() -> None:
    anchor = openMergedTable().cell("C2").mergeAnchored

    assert anchor is not None
    assert str(anchor.extent) == "C2:D3"


def testACellAnchoringNoMergeSaysNothing() -> None:
    assert openMergedTable().cell("B2").mergeAnchored is None


def testAWalkFindsEveryMergeWithoutASecondLookup() -> None:
    found = [
        str(cell.mergeAnchored.extent)
        for cell in openMergedTable().gridIterate()
        if cell.mergeAnchored is not None
    ]

    assert found == ["A2:A3", "C2:D3", "F2:F4"]


def testAnUnmergedAnchorSaysNothing() -> None:
    table = openMergedTable()
    anchor = table.cell("A2")

    table.mergeRemove("A3")

    assert anchor.mergeAnchored is None


def testACellWithNoTableAnchorsNothing() -> None:
    assert Cell(pybers.CellReference(1, 1)).mergeAnchored is None


# ── A merge written with locking markers ─────────────────────────────────────


def testAMergeWrittenLockedKeepsItsAnchor() -> None:
    """Regression: `$A$1:B2` discarded A1's value and then refused A1 as covered."""
    table = Table("Locked", rowCount=3, colCount=3)
    table.cell("A1").value = "kept"

    table.mergeAdd("$A$1:B2")

    assert table.cell("A1").value == "kept"
    assert listWalkAddresses(table.rows[0]) == ["A1", "C1"]


def testAMergeIsTheSameBlockHoweverItIsLocked() -> None:
    locked = pybers.MergeRange(pybers.CellRange.parse("$A$1:B$2"))

    assert locked == pybers.MergeRange(pybers.CellRange.parse("A1:B2"))


# ── The two consumers ────────────────────────────────────────────────────────


def testAScriptFillsEveryEmptyCellInALoop(tmp_path: Path) -> None:
    """The `import pybers` consumer: a batch over a grid, no address built as text."""
    working = tmp_path / "filled.numbers"
    shutil.copy(findDocumentPath("20-formula-shapes"), working)
    document = pybers.open(working)

    table = document.sheet(1).table("Table 2")
    for cell in table.gridIterate():
        if cell.value is None and cell.formula is None:
            cell.value = Decimal("0")
    document.save()

    reopened = pybers.open(working).sheet(1).table("Table 2")
    assert len(reopened.cells) == 50
    assert reopened.cell(row=1, col=1).value == Decimal("42")


def testACliPrintsATableRowByRow() -> None:
    """The `pybers table show` consumer: one line per row, a merge shown once."""
    lines = [
        f"{row.rowNumber}: "
        + " | ".join(str(cell.value).split("\n")[0] for cell in row)
        for row in openMergedTable().rows
    ]

    assert lines[1] == (
        "2: two rows tall, anchor | b2 | two by two, anchor\td2 | e2 "
        "| three rows tall, anchor | g2"
    )
    assert lines[2] == "3: b3 | e3 | g3"


def testATuiDrawsOnlyTheVisibleWindowAndMovesItsCursorByNumber() -> None:
    """The grid view: a scrolled window of cells, creating only what it shows."""
    table = openDocumentTable("27-big-table")
    stored = len(table.cells)
    top, height, left, width = 1000, 3, 1, 2

    window = [
        [cell.value for cell in row[left : left + width]]
        for row in table.rows[top : top + height]
    ]
    cursor = table.cell(row=top + 1, col=left + 1)

    assert len(window) == height
    assert all(len(line) == width for line in window)
    assert window[0][0] is cursor.value
    assert len(table.cells) == stored


def testEveryNameThisTicketAddsIsReachableFromPybersAlone() -> None:
    """Neither consumer imports anything deeper than `pybers`."""
    assert pybers.TableRows is not None
    assert pybers.TableRow is not None
    assert hasattr(pybers.Table, "gridIterate")
    assert hasattr(pybers.Table, "rows")
    assert hasattr(pybers.Cell, "mergeAnchored")
