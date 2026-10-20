#!/usr/bin/env python3
"""\
A cell reached by a reference, each owner taking its part and handing the rest down.

`20-formula-shapes` names two tables `Table 1`, one on each sheet, and one table
`Table 2`, so it holds a table name that is unique and one that is shared.

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

import pytest

import pybers
from conftest import findDocumentPath
from pybers import CellReference, SheetReference, TableReference


@pytest.fixture
def document() -> pybers.Document:
    """Return the document whose table names include a shared one."""
    return pybers.open(findDocumentPath("20-formula-shapes"))


@pytest.mark.parametrize(("text", "sheet", "table"), [
    ("B3", None, None),
    ("Q3::B$3", None, "Q3"),
    ("Budget::Q3::$B$3", "Budget", "Q3"),
])
def testAReferenceReadsTheOwnersItsTextNames(
    text: str, sheet: str | None, table: str | None
) -> None:
    reference = CellReference.parse(text)
    assert (None if reference.sheet is None else reference.sheet.name) == sheet
    assert (None if reference.table is None else reference.table.name) == table
    assert str(reference) == text


def testAReferenceRefusesAnEmptyTableName() -> None:
    with pytest.raises(pybers.ReferenceError, match="is no name"):
        CellReference.parse("::B3")


def testATypedReferenceWalksSheetThenTableThenCell(document: pybers.Document) -> None:
    reference = CellReference(
        1, 1, table=TableReference(sheet=SheetReference("Sheet 2"), name="Table 1")
    )
    assert document.cell(reference) is (
        document.sheet("Sheet 2").table("Table 1").cell("A1")
    )


def testAUniqueTableNameNeedsNoSheet(document: pybers.Document) -> None:
    assert document.cell("Table 2::B3") is (
        document.sheet("Sheet 1").table("Table 2").cell("B3")
    )


def testATableNameMatchesWhateverItsCase(document: pybers.Document) -> None:
    assert document.cell("table 2::B3") is document.cell("Table 2::B3")


def testASharedTableNameIsRefusedWithTheNamesThatMatch(
    document: pybers.Document,
) -> None:
    with pytest.raises(pybers.SelectionError) as raised:
        document.cell("Table 1::B3")
    assert "Sheet 1::Table 1, Sheet 2::Table 1" in str(raised.value)


def testAnUnknownTableIsRefusedWithTheTablesThatExist(
    document: pybers.Document,
) -> None:
    with pytest.raises(pybers.SelectionError) as raised:
        document.cell("Ledger::B3")
    assert "'Ledger'" in str(raised.value)
    assert "Sheet 1::Table 2" in str(raised.value)


def testADocumentRefusesAReferenceNamingNoTable(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError, match="names no table"):
        document.cell("B3")


def testASheetReachesItsOwnTable(document: pybers.Document) -> None:
    sheet = document.sheet("Sheet 1")
    assert sheet.cell("Table 1::C2") is sheet.table("Table 1").cell("C2")


def testASheetRefusesAReferenceNamingAnotherSheet(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError, match="names the sheet 'Sheet 2'"):
        document.sheet("Sheet 1").cell("Sheet 2::Table 1::A1")


def testASheetRefusesAReferenceNamingNoTable(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError, match="names no table"):
        document.sheet("Sheet 1").cell("B3")


def testATableTakesItsOwnQualifiedReference(document: pybers.Document) -> None:
    table = document.sheet("Sheet 1").table("Table 2")
    assert table.cell("Sheet 1::Table 2::B3") is table.cell("B3")


def testATableRefusesAReferenceNamingAnotherTable(document: pybers.Document) -> None:
    with pytest.raises(pybers.ReferenceError, match="names another table"):
        document.sheet("Sheet 1").table("Table 2").cell("Table 1::A1")


def testAReferenceOutsideItsTableNamesTheTablesSize(
    document: pybers.Document,
) -> None:
    with pytest.raises(pybers.ReferenceError, match="10 rows by 5 columns"):
        document.cell("Table 2::Z99")


def testACellsOwnReferenceLeadsBackToIt(document: pybers.Document) -> None:
    cell = document.sheet("Sheet 2").table("Table 1").cell("C4")
    assert document.cell(cell.reference) is cell
