#!/usr/bin/env python3
"""\
A cell's position, how it is pointed at, and the owners a reference names.

`20-formula-shapes` names two tables `Table 1`, one on each sheet, so a reference
built from a cell has to carry the sheet to say which.

UPDATES
2026-10-20  Written for PYB-217, the offset between two addresses included.
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
from pybers import (
    CellAddress,
    CellOffset,
    CellReference,
    SheetReference,
    TableReference,
)


@pytest.fixture
def document() -> pybers.Document:
    """Return the document whose two sheets each hold a `Table 1`."""
    return pybers.open(findDocumentPath("20-formula-shapes"))


@pytest.mark.parametrize(("row", "col"), [(0, 1), (1, 0), (1_000_001, 1), (1, 1001)])
def testAnAddressOutsideEveryTableIsRefused(row: int, col: int) -> None:
    with pytest.raises(pybers.ReferenceError):
        CellAddress(row, col)


def testAnAddressRefusesABooleanCoordinate() -> None:
    with pytest.raises(pybers.ReferenceError, match="not a whole number"):
        CellAddress(True, 1)


def testAnAddressReadsAndWritesItsText() -> None:
    address = CellAddress.parse("AB12")
    assert (address.row, address.col) == (12, 28)
    assert str(address) == "AB12"


def testAnAddressRefusesALockAndNamesTheAddressMeant() -> None:
    with pytest.raises(pybers.ReferenceError, match=r"carries a lock.*B3"):
        CellAddress.parse("$B$3")


def testAddressesSortByRowThenColumn() -> None:
    addresses = [CellAddress(2, 1), CellAddress(1, 3), CellAddress(1, 2)]
    assert sorted(addresses) == [
        CellAddress(1, 2), CellAddress(1, 3), CellAddress(2, 1)
    ]


def testEveryLockedSpellingStandsOnOneAddress() -> None:
    spellings = ["B3", "$B3", "B$3", "$B$3"]
    assert {CellReference.parse(text).address for text in spellings} == {
        CellAddress(3, 2)
    }


def testAQualifiedReferenceWritesItsOwners() -> None:
    reference = CellReference(
        3, 2, rowAbsolute=True,
        table=TableReference(sheet=SheetReference("Budget"), name="Q3"),
    )
    assert str(reference) == "Budget::Q3::B$3"
    assert reference.sheet == SheetReference("Budget")


def testAReferenceWithNoTableNamesNoSheet() -> None:
    assert CellReference(3, 2).sheet is None


@pytest.mark.parametrize("make", [
    lambda: SheetReference(""),
    lambda: TableReference(name=""),
])
def testAnOwnerRefusesAnEmptyName(make: object) -> None:
    with pytest.raises(pybers.ReferenceError, match="is no name"):
        make()  # type: ignore[operator]


def testATableKeysItsCellsByAddressWhateverTheSpelling() -> None:
    table = pybers.Table(name="Table 1", rowCount=3, colCount=3)
    assert table.cell("$A$1") is table.cell("A1")
    assert list(table.cells) == [CellAddress(1, 1)]


def testACellsReferenceNamesItsSheetAndTable(document: pybers.Document) -> None:
    cell = document.sheet("Sheet 2").table("Table 1").cell("B3")
    assert cell.address == CellAddress(3, 2)
    assert str(cell.reference) == "Sheet 2::Table 1::B3"
    assert cell.reference.address == cell.address


def testACellsReferenceFollowsARename(document: pybers.Document) -> None:
    table = document.sheet("Sheet 2").table("Table 1")
    cell = table.cell("B3")
    table.name = "Ledger"
    assert str(cell.reference) == "Sheet 2::Ledger::B3"


def testATableFindsTheSheetHoldingIt(document: pybers.Document) -> None:
    sheet = document.sheet("Sheet 2")
    assert sheet.table("Table 1").sheet is sheet


def testATableOutsideADocumentHasNoSheet() -> None:
    table = pybers.Table(name="Loose", rowCount=2, colCount=2)
    assert table.sheet is None
    assert str(table.cell("A1").reference) == "Loose::A1"


def testAnAddressStandsWhereAReferenceIsTaken() -> None:
    table = pybers.Table(name="Table 1", rowCount=3, colCount=3)
    assert table.cell(CellAddress(2, 2)) is table.cell("B2")


def testAnAddressPlusAnOffsetIsAnAddress() -> None:
    assert CellAddress(3, 2) + CellOffset(1, -1) == CellAddress(4, 1)


def testAnAddressMinusAnAddressIsTheOffsetBetweenThem() -> None:
    assert CellAddress(5, 5) - CellAddress(3, 2) == CellOffset(2, 3)


def testAnAddressMinusAnOffsetStepsBack() -> None:
    assert CellAddress(3, 2) - CellOffset(1, 1) == CellAddress(2, 1)


def testOffsetsAddSubtractAndNegate() -> None:
    assert CellOffset(1, 2) + CellOffset(3, -4) == CellOffset(4, -2)
    assert CellOffset(1, 2) - CellOffset(3, 4) == CellOffset(-2, -2)
    assert -CellOffset(1, -2) == CellOffset(-1, 2)


def testAnOffsetMayBeZeroOrNegative() -> None:
    assert CellAddress(2, 2) + CellOffset(0, 0) == CellAddress(2, 2)
    assert CellAddress(2, 2) - CellAddress(3, 3) == CellOffset(-1, -1)


def testAnOffsetPastTheEdgeOfEveryTableIsRefused() -> None:
    with pytest.raises(pybers.ReferenceError, match="before row 1"):
        CellAddress(1, 1) + CellOffset(-1, 0)


def testTwoAddressesDoNotAdd() -> None:
    with pytest.raises(TypeError):
        CellAddress(1, 1) + CellAddress(1, 1)  # type: ignore[operator]


def testAnOffsetRefusesABooleanAxis() -> None:
    with pytest.raises(pybers.ReferenceError, match="not a whole number"):
        CellOffset(True, 0)

