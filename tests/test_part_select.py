#!/usr/bin/env python3
"""\
`Document.partSelect`, the sheet, table, range or cell a selector names.

`20-formula-shapes` holds `Table 1` on each of its two sheets and `Table 2` on the
first alone, ten rows by five columns, so it holds a table name that is unique and
one that is shared.

UPDATES
2026-10-27  Written for PYB-260.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/27"

import pytest

import pybers
from conftest import findDocumentPath


@pytest.fixture
def document() -> pybers.Document:
    """Return the document whose table names are unique on one sheet and shared."""
    return pybers.open(findDocumentPath("20-formula-shapes"))


def testAScriptReadsTheCellsOfARange(document: pybers.Document) -> None:
    part = document.partSelect("Sheet 1::Table 1::A1:B3")
    assert isinstance(part, pybers.CellRange)
    cells = document.sheet("Sheet 1").table("Table 1").range(part)
    assert [str(cell.address) for cell in cells] == [
        "A1", "B1", "A2", "B2", "A3", "B3",
    ]


def testANameAloneSelectsASheet(document: pybers.Document) -> None:
    assert document.partSelect("Sheet 2") is document.sheet("Sheet 2")


def testANameNoSheetCarriesSelectsTheTableOfThatName(
    document: pybers.Document,
) -> None:
    assert document.partSelect("table 2") is document.sheet("Sheet 1").table("Table 2")


def testASheetAndATableSelectTheTable(document: pybers.Document) -> None:
    assert document.partSelect("Sheet 2::Table 1") is (
        document.sheet("Sheet 2").table("Table 1")
    )


@pytest.mark.parametrize("selector", ["Table 2::B3", "Sheet 1::Table 2::B3"])
def testACellIsTheCellAReferenceReaches(
    document: pybers.Document, selector: str
) -> None:
    assert document.partSelect(selector) is document.cell("Table 2::B3")


@pytest.mark.parametrize(("selector", "extent"), [
    ("Table 2::B2:C4", "B2:C4"),
    ("Table 2::B", "B"),
    ("Table 2::3:3", "3"),
])
def testARangeNamesItsSheetAndTable(
    document: pybers.Document, selector: str, extent: str
) -> None:
    part = document.partSelect(selector)
    assert isinstance(part, pybers.CellRange)
    assert str(part) == f"Sheet 1::Table 2::{extent}"


def testARangeReachingOutsideItsTableIsRefusedAsWritten(
    document: pybers.Document,
) -> None:
    with pytest.raises(pybers.ReferenceError) as raised:
        document.partSelect("Table 2::B:F")
    assert str(raised.value) == (
        "B:F reaches outside 'Table 2', which is 10 rows by 5 columns."
    )


def testASheetIsReadBeforeATableOfTheSameName(document: pybers.Document) -> None:
    document.sheet("Sheet 2").name = "Table 2"
    assert document.partSelect("Table 2") is document.sheet("Table 2")
    assert document.partSelect("Sheet 1::Table 2") is (
        document.sheet("Sheet 1").table("Table 2")
    )


def testATableIsReadBeforeACellOfTheSameName(document: pybers.Document) -> None:
    document.sheet("Sheet 2").name = "Table 2"
    document.sheet("Table 2").table("Table 1").name = "B3"
    assert document.partSelect("Table 2::B3") is document.sheet("Table 2").table("B3")
    assert document.partSelect("Sheet 1::Table 2::B3") is document.cell(
        "Sheet 1::Table 2::B3"
    )


def testANameNothingCarriesIsRefusedListingTheSheetsAndTables(
    document: pybers.Document,
) -> None:
    with pytest.raises(pybers.SelectionError) as raised:
        document.partSelect("Ledger")
    assert str(raised.value) == (
        "No sheet or table in this document is named 'Ledger'. The sheets are "
        "'Sheet 1', 'Sheet 2'. The tables are 'Sheet 1::Table 1', "
        "'Sheet 1::Table 2', 'Sheet 2::Table 1'."
    )


def testACellNamingNoTableIsRefusedShowingHowOneReads(
    document: pybers.Document,
) -> None:
    with pytest.raises(pybers.SelectionError, match="B3 names no table"):
        document.partSelect("B3")


def testASharedTableNameIsRefusedListingBoth(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError) as raised:
        document.partSelect("Table 1::B3")
    assert "'Sheet 1::Table 1', 'Sheet 2::Table 1'" in str(raised.value)


def testCellsOfASheetAreRefusedListingItsTables(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError) as raised:
        document.partSelect("Sheet 1::B2:C3")
    assert str(raised.value) == (
        "Sheet 1::B2:C3 names a sheet and its cells, and a sheet holds only tables. "
        "The tables are 'Table 1', 'Table 2'."
    )


def testAnAbsentTableOnANamedSheetIsRefusedListingItsTables(
    document: pybers.Document,
) -> None:
    with pytest.raises(pybers.SelectionError) as raised:
        document.partSelect("Sheet 2::Ledger::A1")
    assert str(raised.value) == (
        "No table in 'Sheet 2' is named 'Ledger'. The tables are 'Table 1'."
    )


def testACellOutsideItsTableIsRefusedWithTheTablesSize(
    document: pybers.Document,
) -> None:
    with pytest.raises(pybers.ReferenceError) as raised:
        document.partSelect("Table 2::F1")
    assert str(raised.value) == (
        "F1 is outside 'Table 2', which is 10 rows by 5 columns."
    )


def testMoreThanThreeNamesAreRefused(document: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError, match="more than a sheet, a table"):
        document.partSelect("Sheet 1::Table 2::B3::C4")
