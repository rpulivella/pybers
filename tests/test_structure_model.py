#!/usr/bin/env python3
"""\
Rows and columns added and removed in the model, against Numbers' own edits.

Sizes, merges, every formula node and every plain value, and the acceptance
criteria stated as the few lines a script or a command line writes.

UPDATES
2026-09-21  Split out of `test_structure` for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/21"

from collections.abc import Callable
from pathlib import Path

import pytest
from structurefacts import (
    baseFixture,
    measuredEdits,
    openBase,
    reduceModel,
)

import pybers
from conftest import findDocumentPath
from pybers.addressing.reference import ReferenceError as CellReferenceError


@pytest.mark.parametrize("name", sorted(measuredEdits))
def testAnEditReachesTheModelNumbersReached(name: str) -> None:
    """PYB-17 AC 1 to 4: sizes, merges, every formula node and every plain value."""
    document = openBase()
    measuredEdits[name](document.sheets[0].table("Table 1"))
    assert reduceModel(document) == reduceModel(pybers.open(findDocumentPath(name)))


def testARangeGrowingPastTheInsertionMovesOnlyItsFarEnd() -> None:
    """PYB-17 AC 2.i, the ticket's own example on a table built by hand."""
    table = pybers.Table("Ledger", rowCount=30, colCount=4)
    table.cell("D1").formulaText = "=SUM(C3:C25)"
    table.rowAdd(10)
    assert table.cell("D1").formulaText == "=SUM(C3:C26)"


def testAReferenceWhollyBeforeTheInsertionIsNotRewritten() -> None:
    """PYB-17 AC 2.ii: `B4` reads `A1`, and an insertion at row 5 leaves it alone."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    before = table.cell("B4").formula
    table.rowAdd(5)
    assert table.cell("B4").formula is before


def testAMovedFormulaStillReadsTheCellBeforeTheInsertion() -> None:
    """`B4` moves to `B5` and its offset grows, so it still names `A1`."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    table.rowAdd(3)
    assert table.cell("B5").formulaText == "=A1"


def testALockedReferenceFollowsTheLineItNames() -> None:
    """Locking survives a drag, not the grid changing under it, as `56b` measured."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    table.rowAdd(2, 2)
    assert table.cell("B4").formulaText == "=SUM($A$1:$A$12)"
    assert table.cell("B7").formulaText == "=$A$10"


def testMergesGrowMoveOrStayWithAnInsertion() -> None:
    """PYB-17 AC 3, one of each, as `56f` holds them."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    table.rowAdd(3)
    extents = {str(merge.extent) for merge in table.mergeRanges}
    assert {"C1:D1", "C2:D4", "C9:D9"} <= extents


def testRemovingAReferencedRowReportsTheCellItBroke() -> None:
    """PYB-17 AC 4: `B10` read rows 2 and 3, and says so rather than repointing."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    lost = table._rowIdentities[1:3]
    broken = table.rowRemove(2, 2)
    assert [str(cell.address) for cell in broken] == ["B8"]
    formula = table.cell("B8").formula
    assert formula is not None
    reference = formula.references[0]
    assert reference.broken
    assert reference.loss is not None and reference.loss.rows == tuple(lost)
    assert table.cell("B8").formulaText == "=SUM(#REF!)"


def testRemovingAReferencedColumnBreaksAFormulaInAnotherTable() -> None:
    """A formula elsewhere names this table by identity, and follows it too."""
    document = openBase()
    broken = document.sheets[0].table("Table 1").columnRemove("C", 5)
    found = {
        (cell.table.name, str(cell.address)) for cell in broken if cell.table
    }
    assert found == {("Table 1", "B12"), ("Table 2", "A3")}


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda table: table.rowAdd(0), "from 1 to 13"),
        (lambda table: table.rowAdd(14), "from 1 to 13"),
        (lambda table: table.rowAdd(3, 0), "one or more rows"),
        (lambda table: table.rowAdd(True), "named by a number"),
        (lambda table: table.rowRemove(12, 2), "cannot be removed"),
        (lambda table: table.rowRemove(1, 12), "would leave none"),
        (lambda table: table.columnAdd("LEDGER"), "past column"),
        (lambda table: table.rowAdd(1, 1000000), "past the 1000000"),
    ],
)
def testARefusedEditLeavesTheDocumentAsItWas(
    edit: Callable[[pybers.Table], object], message: str
) -> None:
    """Every refusal is checked before anything moves."""
    document = openBase()
    before = reduceModel(document)
    with pytest.raises(CellReferenceError, match=message):
        edit(document.sheets[0].table("Table 1"))
    assert reduceModel(document) == before


# The two edits AppleScript cannot make, because Numbers widens a selected row or
# column over the merges it touches. Each was made from one selected cell.
def testATableAddedAndEditedBeforeItsFirstSaveWritesItsIdentities(
    tmp_path: Path,
) -> None:
    """A created table writes the model's identities, so the edit needs no replay."""
    document = openBase()
    table = document.sheets[0].tableAdd("Fresh", rows=3, cols=2)
    table.rowAdd(2)
    target = tmp_path / "created.numbers"
    document.save(target)
    reopened = pybers.open(target).sheets[0].table("Fresh")
    assert reopened.rowCount == 4
    assert reopened._rowIdentities == table._rowIdentities


def testAScriptAuthorInsertsARowAndSaves(tmp_path: Path) -> None:
    """The few lines a script writes: open, insert, save, and read it back."""
    document = pybers.open(baseFixture)
    document.sheet(1).table("Table 1").rowAdd(3)
    document.save(tmp_path / "scripted.numbers")
    table = pybers.open(tmp_path / "scripted.numbers").sheet(1).table("Table 1")
    assert table.cell("B1").formulaText == "=SUM(A1:A11)"


def testACommandLineRemovesAColumnByLetterAndReportsWhatBroke() -> None:
    """A CLI passes the column as typed and prints the cells now reading #REF!."""
    arguments = ["Table 1", "E"]
    document = pybers.open(baseFixture)
    broken = document.sheet(1).table(arguments[0]).columnRemove(arguments[1])
    assert [f"{cell.address}" for cell in broken] == ["B12"]
