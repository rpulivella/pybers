#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
Reading a `.numbers` file into the object model, asserted against fixture contents.

Every expectation here is anchored in something the fixture states about itself: a
row of text labels beside the values it describes, a sheet name, a table name, or a
filename. That is what makes an assertion evidence rather than a restatement of
whatever the decoder happened to produce. A wrong offset in this format yields a
plausible wrong number rather than an exception, so a test that compares the reader
against itself proves nothing.

UPDATES
2026-08-31  Written for #1.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/31"

import datetime
from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from pybers.model import ReferenceError, columnLetter, columnNumber, parseReference

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"

allFixtures: list[Path] = sorted(fixtureDirectory.glob("*.numbers"))


def fixture(name: str):
    """Open one fixture by its stem."""
    return pybers.open(fixtureDirectory / f"{name}.numbers")


def onlyTable(name: str):
    """Return the single table of a single-table fixture."""
    document = fixture(name)
    return document.sheets[0].tables[0]


# ── AC 1: every fixture opens ────────────────────────────────────────────────

def test_thereIsACorpusToReadAtAll() -> None:
    """Guard the parametrization: an empty glob would make every case vacuous."""
    assert len(allFixtures) >= 40


@pytest.mark.parametrize("path", allFixtures, ids=lambda path: path.stem)
def test_everyFixtureOpensWithoutRaising(path: Path) -> None:
    document = pybers.open(path)
    assert document.sheets, f"{path.name} produced no sheets"


# ── AC 2: sheets in document order, carrying the name Numbers shows ──────────

def test_sheetsComeBackInOrderWithTheirTabNames() -> None:
    """`26-multi-sheets` names its three tabs, and two say what they are."""
    document = fixture("26-multi-sheets")
    names = [sheet.name for sheet in document.sheets]
    assert names == [
        "Sheet 1",
        "Duplicate of Sheet 1 and I have a tab color",
        "Duplicate of Sheet 1 and I have a background color",
    ]


# ── AC 3: tables in the sheet's own drawable order ───────────────────────────

def test_aSheetYieldsEveryTableItHolds() -> None:
    """`25-multi-tables` puts three tables on one sheet."""
    sheet = fixture("25-multi-tables").sheets[0]
    assert len(sheet.tables) == 3


def test_aSheetWithNoTableYieldsNone() -> None:
    """`34-shape` holds only drawables that are not tables, and must not invent one."""
    assert fixture("34-shape").sheets[0].tables == []


# ── AC 4: addressing, and an absent cell reading as empty ────────────────────

def test_anAbsentCellReadsAsEmptyRatherThanRaising() -> None:
    table = onlyTable("11-value-types-noformats")
    assert (400, 40) not in table.cells
    assert table.cellAt(400, 40).value is None


def test_readingAnAbsentCellDoesNotDisturbItsNeighbors() -> None:
    table = onlyTable("11-value-types-noformats")
    before = table.cellAt(1, 1).value
    table.cellAt(1, 40)
    assert table.cellAt(1, 1).value == before


def test_rowsAndColumnsCountFromOne() -> None:
    """A1 is the first cell, and the Python instinct of zero fails loudly."""
    table = onlyTable("11-value-types-noformats")
    assert table.cell("A1") is table.cellAt(1, 1)
    with pytest.raises(ReferenceError):
        table.cellAt(0, 0)


def test_columnLabelsAndNumbersAgreeAcrossTheBase26Boundary() -> None:
    assert columnLetter(1) == "A"
    assert columnLetter(26) == "Z"
    assert columnLetter(27) == "AA"
    assert columnNumber("AA") == 27
    for col in (1, 26, 27, 52, 53, 702, 703):
        assert columnNumber(columnLetter(col)) == col


def test_aReferenceIgnoresTheDollarSignsNumbersWrites() -> None:
    """Locking belongs to a formula, so `$A$1` and `A1` name the same cell."""
    assert parseReference("$A$1") == parseReference("A1") == (1, 1)


def test_aCellKnowsItsOwnReference() -> None:
    table = onlyTable("11-value-types-noformats")
    assert table.cellAt(1, 9).reference == "I1"


# ── AC 5: every value type the archive layer reads ───────────────────────────

def test_everyValueTypeDecodesAsTheFixtureLabelsIt() -> None:
    """Row 1 holds the values; row 2 labels each one in the fixture's own words."""
    table = onlyTable("11-value-types-noformats")
    labels = {
        column: table.cellAt(2, column).value for column in range(1, 10)
    }
    assert labels[1] == "plain number 1234.5"
    assert labels[3] == "date june 15 2027"

    assert table.cell("A1").value == Decimal("1234.5")
    assert table.cell("B1").value == Decimal("42")
    assert table.cell("C1").value == datetime.datetime(
        2027, 6, 15, tzinfo=datetime.timezone.utc
    )
    assert table.cell("D1").value == datetime.timedelta(minutes=20)
    assert table.cell("E1").value is True
    assert table.cell("I1").value == "Item 1"


def test_aCurrencyAmountReadsAsAnExactDecimal() -> None:
    table = onlyTable("12-number-currency")
    assert isinstance(table.cell("A1").value, Decimal)


# AC 5.a
def test_numbersAreDecimalAndNeverFloat() -> None:
    table = onlyTable("11-value-types-noformats")
    value = table.cell("A1").value
    assert isinstance(value, Decimal)
    assert not isinstance(value, float)


def test_aValueRoundTripsThroughStringWithNoDigitsGainedOrLost() -> None:
    """The reason `Decimal` is not a preference: `float` fails this."""
    table = onlyTable("11-value-types-noformats")
    value = table.cell("A1").value
    assert str(value) == "1234.5"
    assert Decimal(str(value)) == value


# AC 5.b
def test_aFormulaCellExposesItsCachedResult() -> None:
    """`18-formula-literals` labels each formula in the row beneath its result."""
    table = onlyTable("18-formula-literals")
    assert table.cellAt(2, 1).value == "1+1"
    assert table.cell("A1").value == Decimal("2")
    assert table.cellAt(2, 3).value == "SUM(1,2,3)"
    assert table.cell("C1").value == Decimal("6")
    assert table.cellAt(2, 7).value == '"a"&"b"'
    assert table.cell("G1").value == "ab"


# ── AC 6: merges read from the merge store ───────────────────────────────────

def test_mergesComeBackFromTheMergeStore() -> None:
    """`22-merge-2x2` carries five merged pairs across row 1, per findings-03."""
    table = onlyTable("22-merge-2x2")
    anchors = sorted(
        (merge.anchorRow, merge.anchorCol) for merge in table.mergeRanges
    )
    assert anchors == [(1, 1), (1, 3), (1, 5), (1, 7), (1, 9)]
    assert all(merge.rowSpan == 1 and merge.colSpan == 2 for merge in table.mergeRanges)


def test_theUnmergedTwinReportsNoMerges() -> None:
    """`22b` differs from `22` only in that the merges were undone."""
    assert onlyTable("22b-merge-2x2-unmerged").mergeRanges == []


def test_aCoveredCellIsDistinguishableFromAnEmptyOne() -> None:
    """A covered cell has NO record in the tile, so the grid alone cannot tell.

    B1 is covered by the merge anchored at A1, and H2 is genuinely empty. Both are
    absent from `cells` and nothing about the grid separates them, so a reader that
    consults only the tiles reports a merged table as a table full of holes.
    """
    table = onlyTable("22-merge-2x2")
    assert (1, 2) not in table.cells
    assert (2, 8) not in table.cells
    assert table.mergeCovering(1, 2) is not None
    assert table.mergeCovering(2, 8) is None


# ── AC 8: the whole corpus reads, and the traps stay caught ──────────────────

@pytest.mark.parametrize("path", allFixtures, ids=lambda path: path.stem)
def test_everyCellOfEveryTableReads(path: Path) -> None:
    document = pybers.open(path)
    for sheet in document.sheets:
        for table in sheet.tables:
            for (row, col), cell in table.cells.items():
                assert row >= 1 and col >= 1
                assert cell.row == row and cell.col == col


def test_aMultiTileTableKeepsItsRowsInOrder() -> None:
    """`27-big-table` is 2001 rows over 8 tiles, and every row labels itself.

    `tile_row_index` is local to its tile and the tile archives are not in row
    order, so a reader that ignores either produces a scrambled table and raises
    nothing. Row 2000 saying "row 2000" is what catches that.
    """
    table = onlyTable("27-big-table")
    rows = sorted({row for row, _ in table.cells})
    assert rows == list(range(1, 2002))
    assert table.cell("A1").value == "Label"
    assert table.cellAt(2002 - 1, 1).value == "row 2000"
    assert isinstance(table.cellAt(2001, 2).value, Decimal)


def test_astralCharactersSurviveTheRead() -> None:
    """`36-unicode-text` exists because run indices count UTF-16 code units."""
    table = onlyTable("36-unicode-text")
    texts = [
        cell.value for cell in table.cells.values() if isinstance(cell.value, str)
    ]
    assert any(max(text, default="", key=ord) > "￿" for text in texts)
