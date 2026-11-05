#!/usr/bin/env python3
"""\
A sheet, a table and a cell reached by the typed lookups through the one resolver.

`20-formula-shapes` names two tables `Table 1`, one on each sheet, and one table
`Table 2`, so it holds a table name that is unique and one that is shared.

UPDATES
2026-11-03  The typed lookups, `document.cell` and `sheet.cell` removed, for
            PYB-223.
2026-10-27  Each listed table name quoted, for PYB-260.
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


def testATableReferenceNamingItsSheetReachesThatTable(
    document: pybers.Document,
) -> None:
    reference = TableReference(sheet=SheetReference("Sheet 2"), name="Table 1")
    assert document.table(reference) is document.sheet("Sheet 2").table("Table 1")


def testAUniqueTableNameNeedsNoSheet(document: pybers.Document) -> None:
    assert document.table("Table 2") is document.sheet("Sheet 1").table("Table 2")


def testATableNameMatchesWhateverItsCase(document: pybers.Document) -> None:
    assert document.table("table 2") is document.table("Table 2")


def testASheetNameMatchesOnlyItsOwnCase(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError, match="'sheet 1'"):
        document.sheet("sheet 1")


def testANameIsTakenLiterallyNeverAsAPattern(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError, match="'Table \\*'"):
        document.table("Table *")


def testASharedTableNameIsRefusedWithTheNamesThatMatch(
    document: pybers.Document,
) -> None:
    with pytest.raises(pybers.SelectionError) as raised:
        document.table("Table 1")
    assert "'Sheet 1::Table 1', 'Sheet 2::Table 1'" in str(raised.value)


def testAnUnknownTableIsRefusedWithTheTablesThatExist(
    document: pybers.Document,
) -> None:
    with pytest.raises(pybers.SelectionError) as raised:
        document.table("Ledger")
    assert str(raised.value).startswith("No table in this document is named 'Ledger'.")
    assert "'Sheet 1::Table 2'" in str(raised.value)


def testNoSheetNamedIsRefusedWhenThereAreSeveral(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError) as raised:
        document.sheet()
    assert str(raised.value) == (
        "No sheet was named, and this document holds 2. Name one. The sheets are "
        "'Sheet 1', 'Sheet 2'."
    )


def testNoTableNamedIsRefusedListingEveryTable(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError, match="'Sheet 2::Table 1'"):
        document.table()


def testNoNameReachesTheOnlySheetAndTheOnlyTable() -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Ledger", 3, 3)
    assert document.sheet() is document.sheets[0]
    assert document.table() is table
    assert document.sheet().table() is table


def testASheetWithNoTableRefusesNoNameSayingSo() -> None:
    with pytest.raises(pybers.SelectionError, match="holds none"):
        pybers.create("en_US").sheet().table()


def testASheetReachesItsOwnTable(document: pybers.Document) -> None:
    sheet = document.sheet("Sheet 2")
    assert sheet.table("table 1") is sheet.tables[0]


def testASheetRefusesATableItDoesNotHold(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError) as raised:
        document.sheet("Sheet 2").table("Table 2")
    assert str(raised.value) == (
        "No table in 'Sheet 2' is named 'Table 2'. The tables are 'Table 1'."
    )


def testABoolIsNeitherANameNorAPosition(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError, match="neither"):
        document.sheet(True)


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
        document.table("Table 2").cell("Z99")


def testACellsOwnReferenceSelectsIt(document: pybers.Document) -> None:
    cell = document.sheet("Sheet 2").table("Table 1").cell("C4")
    assert document.select(str(cell.reference)) == (cell.reference,)
