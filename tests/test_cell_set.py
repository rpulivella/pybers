#!/usr/bin/env python3
"""\
One cell set by its reference, the change reported, and a preview changing nothing.

Each test edits a copy of `20-formula-shapes`, whose `Table 2` is ten rows by five
columns and named on one sheet only, so `Table 2::B2` needs no sheet.

UPDATES
2026-10-20  Written for PYB-217.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/20"

from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from conftest import copyDocument
from pybers import CellAddress, CellKind


@pytest.fixture
def working(tmp_path: Path) -> Path:
    """Return a copy of the document, so a save never touches the fixture."""
    return copyDocument("20-formula-shapes", tmp_path)


def testAScriptSetsACellAndTheSaveKeepsIt(working: Path) -> None:
    document = pybers.open(working)
    document.cellSet("Table 2::B2", Decimal("1250.00"))
    document.save()
    cell = pybers.open(working).cell("Table 2::B2")
    assert (cell.value, cell.kind) == (Decimal("1250.00"), CellKind.NUMBER)


def testTheChangeSaysWhatTheCellHeldAndHolds(working: Path) -> None:
    change = pybers.open(working).cellSet("Table 2::B2", "hello")
    assert str(change.reference) == "Sheet 1::Table 2::B2"
    assert (change.valueBefore, change.valueAfter) == (None, "hello")
    assert (change.kindBefore, change.kindAfter) == (CellKind.EMPTY, CellKind.TEXT)
    assert change.changed


def testAnIntIsWrittenAsThatExactNumber(working: Path) -> None:
    change = pybers.open(working).cellSet("Table 2::B2", 42)
    assert change.valueAfter == Decimal(42)
    assert isinstance(change.valueAfter, Decimal)


def testAFloatIsRefusedNamingTheDecimalMeant(working: Path) -> None:
    with pytest.raises(pybers.WriteError, match=r"Decimal\('0.1'\)"):
        pybers.open(working).cellSet("Table 2::B2", 0.1)


def testAValueNoCellHoldsIsRefused(working: Path) -> None:
    with pytest.raises(pybers.WriteError, match="was given a list"):
        pybers.open(working).cellSet("Table 2::B2", [1])


def testSettingTheValueAlreadyThereChangesNothing(working: Path) -> None:
    document = pybers.open(working)
    document.cellSet("Table 2::B2", Decimal("7"))
    assert not document.cellSet("Table 2::B2", Decimal("7")).changed


def testOneNumberWrittenWithMoreDigitsIsAChange(working: Path) -> None:
    document = pybers.open(working)
    document.cellSet("Table 2::B2", Decimal("7"))
    assert document.cellSet("Table 2::B2", Decimal("7.0")).changed


def testAPreviewReportsTheChangeAndCreatesNothing(working: Path) -> None:
    document = pybers.open(working)
    table = document.cell("Table 2::A1").table
    assert table is not None
    change = document.cellSet("Table 2::B2", 42, preview=True)
    assert (change.kindBefore, change.kindAfter) == (CellKind.EMPTY, CellKind.NUMBER)
    assert CellAddress(2, 2) not in table.cells


def testAnAddressOutsideTheTableIsRefusedWithoutExtend(working: Path) -> None:
    with pytest.raises(pybers.ReferenceError, match="10 rows by 5 columns"):
        pybers.open(working).cellSet("Table 2::G12", 1)


def testExtendGrowsTheTableToHoldTheAddress(working: Path) -> None:
    document = pybers.open(working)
    change = document.cellSet("Table 2::G12", 1, extend=True)
    table = document.cell("Table 2::G12").table
    assert table is not None
    assert (change.rowsAdded, change.colsAdded) == (2, 2)
    assert (table.rowCount, table.colCount) == (12, 7)


def testAPreviewOfExtendLeavesTheTableItsSize(working: Path) -> None:
    document = pybers.open(working)
    change = document.cellSet("Table 2::G12", 1, extend=True, preview=True)
    table = document.cell("Table 2::A1").table
    assert table is not None
    assert (change.rowsAdded, change.colsAdded) == (2, 2)
    assert (table.rowCount, table.colCount) == (10, 5)


def testARefusedValueLeavesTheTableUngrown(working: Path) -> None:
    document = pybers.open(working)
    with pytest.raises(pybers.WriteError):
        document.cellSet("Table 2::G12", 0.5, extend=True)
    table = document.cell("Table 2::A1").table
    assert table is not None
    assert (table.rowCount, table.colCount) == (10, 5)


def testAValueOverAFormulaIsRefused(working: Path) -> None:
    document = pybers.open(working)
    formulaCell = next(
        cell for _, _, cell in document.cellsIterate() if cell.formula is not None
    )
    with pytest.raises(pybers.WriteError, match="backed by a formula"):
        document.cellSet(formulaCell.reference, 1)


def testAssigningAnIntToACellWritesThatExactNumber() -> None:
    cell = pybers.Table(name="Table 1", rowCount=2, colCount=2).cell("A1")
    cell.value = 42
    assert cell.value == Decimal(42)
    assert isinstance(cell.value, Decimal)


def testAssigningAFloatToACellIsRefusedAtOnce() -> None:
    cell = pybers.Table(name="Table 1", rowCount=2, colCount=2).cell("A1")
    with pytest.raises(pybers.WriteError, match=r"Decimal\('0.1'\)"):
        cell.value = 0.1  # type: ignore[assignment]
    assert cell.value is None


def testAssigningOverAFormulaIsRefusedAtOnce(working: Path) -> None:
    document = pybers.open(working)
    formulaCell = next(
        cell for _, _, cell in document.cellsIterate() if cell.formula is not None
    )
    cached = formulaCell.value
    with pytest.raises(pybers.WriteError, match="backed by a formula"):
        formulaCell.value = 1
    assert formulaCell.value == cached

