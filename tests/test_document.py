#!/usr/bin/env python3
"""\
Reading a `.numbers` file into the object model, asserted against document contents.

Every expectation here is anchored in something the document states about itself: a
row of text labels beside the values it describes, a sheet name, a table name, or a
filename. That is what makes an assertion evidence rather than a restatement of
whatever the decoder happened to produce. A wrong offset in this format yields a
plausible wrong number rather than an exception, so a test that compares the reader
against itself proves nothing.

UPDATES
2026-09-16  A document found in neither directory, or in both, fails for
            PYB-90 rather than skipping.
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

import conftest
import pybers
from conftest import allDocuments, findDocumentPath
from pybers.addressing import (
    CellReference,
    ReferenceError,
    toColumnLetter,
    toColumnNumber,
)


def openDocument(name: str):
    """Open one document by its stem."""
    return pybers.open(findDocumentPath(name))


def openOnlyTable(name: str):
    """Return the single table of a single-table document."""
    document = openDocument(name)
    return document.sheets[0].tables[0]


# ── AC 1: every document opens ────────────────────────────────────────────────

def test_thereAreDocumentsToReadAtAll() -> None:
    """Guard the parametrization: an empty glob would make every case vacuous."""
    assert len(allDocuments) >= 62


def test_aDocumentInNeitherDirectoryFailsRatherThanSkipping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(conftest, "documentDirectories", (tmp_path,))
    with pytest.raises(AssertionError, match="in 0 document directories"):
        findDocumentPath("00-baseline")


def test_aDocumentInBothDirectoriesFails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origins, measurements = tmp_path / "fixtures", tmp_path / "measurements"
    for directory in (origins, measurements):
        directory.mkdir()
        (directory / "00-baseline.numbers").write_bytes(b"")
    monkeypatch.setattr(conftest, "documentDirectories", (origins, measurements))
    with pytest.raises(AssertionError, match="in 2 document directories"):
        findDocumentPath("00-baseline")


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def test_everyDocumentOpensWithoutRaising(path: Path) -> None:
    document = pybers.open(path)
    assert document.sheets, f"{path.name} produced no sheets"


# ── AC 2: sheets in document order, carrying the name Numbers shows ──────────

def test_sheetsComeBackInOrderWithTheirTabNames() -> None:
    """`26-multi-sheets` names its three tabs, and two say what they are."""
    document = openDocument("26-multi-sheets")
    names = [sheet.name for sheet in document.sheets]
    assert names == [
        "Sheet 1",
        "Duplicate of Sheet 1 and I have a tab color",
        "Duplicate of Sheet 1 and I have a background color",
    ]


# ── AC 3: tables in the sheet's own drawable order ───────────────────────────

def test_aSheetYieldsEveryTableItHolds() -> None:
    """`25-multi-tables` puts three tables on one sheet."""
    sheet = openDocument("25-multi-tables").sheets[0]
    assert len(sheet.tables) == 3


def test_aSheetWithNoTableYieldsNone() -> None:
    """`34-shape` holds only drawables that are not tables, and must not invent one."""
    assert openDocument("34-shape").sheets[0].tables == []


# ── AC 4: addressing, and an absent cell reading as empty ────────────────────

def test_anAbsentCellReadsAsEmptyRatherThanRaising() -> None:
    """J1 is the one cell inside this table's declared 2 by 10 grid that holds
    nothing, so it is absent from the archive without being outside the table."""
    table = openOnlyTable("11-value-types-noformats")
    assert CellReference.parse("J1") not in table.cells
    assert table.cell("J1").value is None


def test_aCellOutsideTheDeclaredGridIsRefused() -> None:
    """A Numbers table is a fixed number of rows and columns, unlike a sheet in
    Excel, so an address beyond it names nothing rather than naming an empty cell."""
    table = openOnlyTable("11-value-types-noformats")
    assert table.extent is not None
    with pytest.raises(ReferenceError):
        table.cell("AN400")


def test_readingAnAbsentCellDoesNotDisturbItsNeighbors() -> None:
    table = openOnlyTable("11-value-types-noformats")
    before = table.cell("A1").value
    table.cell("J1")
    assert table.cell("A1").value == before


def test_rowsAndColumnsCountFromOne() -> None:
    """A1 is the first cell, and the Python instinct of zero fails loudly."""
    table = openOnlyTable("11-value-types-noformats")
    assert table.cell("A1") is table.cell(CellReference(1, 1))
    with pytest.raises(ReferenceError):
        CellReference(0, 0)


def test_columnLabelsAndNumbersAgreeAcrossTheBase26Boundary() -> None:
    assert toColumnLetter(1) == "A"
    assert toColumnLetter(26) == "Z"
    assert toColumnLetter(27) == "AA"
    assert toColumnNumber("AA") == 27
    for col in (1, 26, 27, 52, 53, 702, 703):
        assert toColumnNumber(toColumnLetter(col)) == col


def test_aLockedReferenceAddressesTheSameCellAndIsNotTheSameReference() -> None:
    """`$A$1` and `A1` name one cell, and a table stores it once either way.

    They still compare unequal, because locking is part of what was written. AC 2
    covers that side; this covers the side a table cares about.
    """
    table = openOnlyTable("11-value-types-noformats")
    assert CellReference.parse("$A$1").asRowColumn() == (1, 1)
    assert table.cell("$A$1") is table.cell("A1")


def test_aCellKnowsItsOwnReference() -> None:
    table = openOnlyTable("11-value-types-noformats")
    assert table.cell("I1").reference == CellReference(1, 9)


# ── AC 5: every value type the persistence layer reads ───────────────────────

def test_everyValueTypeDecodesAsTheMeasurementLabelsIt() -> None:
    """Row 1 holds the values; row 2 labels each one in the measurement's own words."""
    table = openOnlyTable("11-value-types-noformats")
    labels = {
        column: table.cell(CellReference(2, column)).value
        for column in range(1, 10)
    }
    assert labels[1] == "plain number 1234.5"
    assert labels[3] == "date june 15 2027"

    assert table.cell("A1").value == Decimal("1234.5")
    assert table.cell("B1").value == Decimal("42")
    assert table.cell("C1").value == datetime.datetime(
        2027, 6, 15, tzinfo=datetime.UTC
    )
    assert table.cell("D1").value == datetime.timedelta(minutes=20)
    assert table.cell("E1").value is True
    assert table.cell("I1").value == "Item 1"


def test_aCurrencyAmountReadsAsAnExactDecimal() -> None:
    table = openOnlyTable("12-number-currency")
    assert isinstance(table.cell("A1").value, Decimal)


# AC 5.a
def test_numbersAreDecimalAndNeverFloat() -> None:
    table = openOnlyTable("11-value-types-noformats")
    value = table.cell("A1").value
    assert isinstance(value, Decimal)
    assert not isinstance(value, float)


def test_aValueRoundTripsThroughStringWithNoDigitsGainedOrLost() -> None:
    """The reason `Decimal` is not a preference: `float` fails this."""
    table = openOnlyTable("11-value-types-noformats")
    value = table.cell("A1").value
    assert str(value) == "1234.5"
    assert Decimal(str(value)) == value


# AC 5.b
def test_aFormulaCellExposesItsCachedResult() -> None:
    """`18-formula-literals` labels each formula in the row beneath its result."""
    table = openOnlyTable("18-formula-literals")
    assert table.cell("A2").value == "1+1"
    assert table.cell("A1").value == Decimal("2")
    assert table.cell("C2").value == "SUM(1,2,3)"
    assert table.cell("C1").value == Decimal("6")
    assert table.cell("G2").value == '"a"&"b"'
    assert table.cell("G1").value == "ab"


# ── AC 6: merges read from the merge store ───────────────────────────────────

def test_mergesComeBackFromTheMergeStore() -> None:
    """`22-merge-2x2` carries five merged pairs across row 1, per findings-03."""
    table = openOnlyTable("22-merge-2x2")
    anchors = sorted(merge.anchor.asRowColumn() for merge in table.mergeRanges)
    assert anchors == [(1, 1), (1, 3), (1, 5), (1, 7), (1, 9)]
    assert all(
        merge.extent.rowSpan == 1 and merge.extent.colSpan == 2
        for merge in table.mergeRanges
    )


def test_theUnmergedTwinReportsNoMerges() -> None:
    """`22b` differs from `22` only in that the merges were undone."""
    assert openOnlyTable("22b-merge-2x2-unmerged").mergeRanges == []


def test_aCoveredCellIsDistinguishableFromAnEmptyOne() -> None:
    """A covered cell has NO record in the tile, so the grid alone cannot tell.

    B1 is covered by the merge anchored at A1, and H2 is genuinely empty. Both are
    absent from `cells` and nothing about the grid separates them, so a reader that
    consults only the tiles reports a merged table as a table full of holes.
    """
    table = openOnlyTable("22-merge-2x2")
    assert CellReference.parse("B1") not in table.cells
    assert CellReference.parse("H2") not in table.cells
    assert table.mergeCovering("B1") is not None
    assert table.mergeCovering("H2") is None


def test_aCoveredCellIsNotAddressableAndLeavesNoRecord() -> None:
    """`22-merge-2x2` merges A1:B1, so B1 is swallowed and only A1 addresses it."""
    table = openOnlyTable("22-merge-2x2")
    stored = len(table.cells)
    with pytest.raises(ReferenceError):
        table.cell("B1")
    assert len(table.cells) == stored
    assert table.cell("A1").value == "Hello"


# ── AC 8: every document reads, and the traps stay caught ──────────────────

@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def test_everyCellOfEveryTableReads(path: Path) -> None:
    document = pybers.open(path)
    for sheet in document.sheets:
        for table in sheet.tables:
            for reference, cell in table.cells.items():
                assert reference.row >= 1 and reference.col >= 1
                assert cell.reference == reference


def test_aMultiTileTableKeepsItsRowsInOrder() -> None:
    """`27-big-table` is 2001 rows over 8 tiles, and every row labels itself.

    `tile_row_index` is local to its tile and the tile archives are not in row
    order, so a reader that ignores either produces a scrambled table and raises
    nothing. Row 2000 saying "row 2000" is what catches that.
    """
    table = openOnlyTable("27-big-table")
    rows = sorted({reference.row for reference in table.cells})
    assert rows == list(range(1, 2002))
    assert table.cell("A1").value == "Label"
    assert table.cell("A2001").value == "row 2000"
    assert isinstance(table.cell("B2001").value, Decimal)


def test_astralCharactersSurviveTheRead() -> None:
    """`36-unicode-text` exists because run indices count UTF-16 code units."""
    table = openOnlyTable("36-unicode-text")
    texts = [
        cell.value for cell in table.cells.values() if isinstance(cell.value, str)
    ]
    assert any(max(text, default="", key=ord) > "￿" for text in texts)
