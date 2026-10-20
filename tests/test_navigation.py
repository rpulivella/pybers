#!/usr/bin/env python3
"""\
Reaching a sheet or a table by name or position, and iterating a document's cells.

Anchored in documents the same way `test_document.py` is: a table named `Lower` is
named that because it sits below the first one, and `20-formula-shapes` carries a
`Table 1` on each of two sheets. An assertion that quotes the file is evidence,
whereas one that quotes the reader is a restatement.

Two cases cannot come from a document at all, because Numbers will not create them:
two tables on one sheet sharing a name, and two sheets sharing one. Those are built
by hand, which is the honest way to test a defense against something the documents have
no example of.

UPDATES
2026-09-02  Written for #14.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/02"

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from conftest import allDocuments, findDocumentPath
from pybers.document import Document, SelectionError, Sheet
from pybers.table import Cell, Table


def openDocument(name: str) -> Document:
    """Open one document by its stem."""
    return pybers.open(findDocumentPath(name))


# ── AC 1: a sheet and a table by name or by position ─────────────────────────

def test_aSheetComesBackByNameAndByPosition() -> None:
    """`26-multi-sheets` names its three tabs, and the first is `Sheet 1`."""
    document = openDocument("26-multi-sheets")
    assert document.sheet("Sheet 1").name == "Sheet 1"
    assert document.sheet(2).name == "Duplicate of Sheet 1 and I have a tab color"


def test_aTableComesBackByNameAndByPosition() -> None:
    """`25-multi-tables` puts `Table 1`, `Lower` and `Right` on one sheet."""
    sheet = openDocument("25-multi-tables").sheet(1)
    assert sheet.table("Lower").name == "Lower"
    assert sheet.table(3).name == "Right"


def test_positionCountsFromOne() -> None:
    """AC 1.i. Position 1 is the first sheet, and position 0 is nothing at all."""
    document = openDocument("26-multi-sheets")
    assert document.sheet(1) is document.sheets[0]
    with pytest.raises(SelectionError):
        document.sheet(0)


def test_theListsRemainSoAnOrdinaryLoopStillWorks() -> None:
    """AC 1.ii. Selection is added beside `sheets` and `tables`, not in place of
    them."""
    document = openDocument("25-multi-tables")
    assert [sheet.name for sheet in document.sheets] == ["Sheet 1"]
    assert [table.name for table in document.sheets[0].tables] == [
        "Table 1",
        "Lower",
        "Right",
    ]


def test_neitherANameNorAPositionIsRefusedRatherThanCoerced() -> None:
    """A bool is an int in Python, and `True` is not position 1 in anyone's intent."""
    sheet = openDocument("25-multi-tables").sheet(1)
    with pytest.raises(SelectionError):
        sheet.table(True)
    with pytest.raises(SelectionError):
        sheet.table(1.0)  # type: ignore[arg-type]


# ── AC 2: position is the document's own order ───────────────────────────────

def test_positionIsThePlaceInTheFilesOwnList() -> None:
    """Selection by position agrees with the list the reader built, cell for cell.

    That list is `TN.DocumentArchive.sheets` and `TN.SheetArchive.drawable_infos`,
    neither of which is sorted, so agreeing with it is the whole claim. A table's
    position says nothing about where it sits on the page: `Lower` is below the
    first table and `Right` is beside it, and the drawable list orders them
    `Table 1`, `Lower`, `Right` regardless.
    """
    document = openDocument("26-multi-sheets")
    for position, sheet in enumerate(document.sheets, start=1):
        assert document.sheet(position) is sheet
        for tablePosition, table in enumerate(sheet.tables, start=1):
            assert sheet.table(tablePosition) is table


# ── AC 3: an absent name says what was asked for and what is present ─────────

def test_anAbsentSheetNameIsReportedWithWhatIsPresent() -> None:
    document = openDocument("26-multi-sheets")
    with pytest.raises(SelectionError) as raised:
        document.sheet("Sheet 9")
    message = str(raised.value)
    assert "'Sheet 9'" in message
    for name in (sheet.name for sheet in document.sheets):
        assert repr(name) in message


def test_anAbsentTableNameIsReportedWithWhatIsPresent() -> None:
    sheet = openDocument("25-multi-tables").sheet(1)
    with pytest.raises(SelectionError) as raised:
        sheet.table("Upper")
    message = str(raised.value)
    assert "'Upper'" in message
    assert "'Table 1'" in message and "'Lower'" in message and "'Right'" in message


def test_aPositionBeyondTheEndSaysHowManyThereAre() -> None:
    sheet = openDocument("25-multi-tables").sheet(1)
    with pytest.raises(SelectionError) as raised:
        sheet.table(4)
    assert "3 tables" in str(raised.value)


def test_askingAnEmptyContainerSaysNothingIsPresent() -> None:
    """An empty list still has to produce a sentence, not a dangling colon."""
    with pytest.raises(SelectionError) as raised:
        Sheet(name="Empty").table("Anything")
    assert "Present: nothing." in str(raised.value)
    with pytest.raises(SelectionError) as raised:
        Document().sheet("Anything")
    assert "Present: nothing." in str(raised.value)


def test_aTableNameMatchesRegardlessOfCase() -> None:
    """AC 3.i. Numbers treats two table names differing only in case as one name and
    will not create both, stated by the cells of `42-table-titles-captions`, so
    matching caselessly cannot merge two tables a document distinguishes."""
    sheet = openDocument("25-multi-tables").sheet(1)
    assert sheet.table("lower") is sheet.table("LOWER") is sheet.table("Lower")


def test_aSheetNameMatchesExactly() -> None:
    """The counterpart, and it is not an oversight.

    Nothing shows Numbers enforcing anything about sheet names, so folding their
    case would be this library inventing a collision the file does not have.
    """
    document = openDocument("26-multi-sheets")
    with pytest.raises(SelectionError):
        document.sheet("sheet 1")


# ── AC 4: a repeated name raises rather than picking the first ───────────────

def test_twoSheetsSharingANameSelectNeither() -> None:
    """Built by hand: no document holds two sheets sharing a name, and nothing shows
    Numbers preventing it either, so the case is covered rather than assumed away."""
    document = Document(sheets=[Sheet(name="Summary"), Sheet(name="Summary")])
    with pytest.raises(SelectionError) as raised:
        document.sheet("Summary")
    assert "1, 2" in str(raised.value)
    assert document.sheet(2) is document.sheets[1]


def test_twoTablesSharingANameSelectNeither() -> None:
    """Numbers appends `-1` to prevent this, so it only arises through this library."""
    sheet = Sheet(name="Sheet 1", tables=[Table(name="Costs"), Table(name="COSTS")])
    with pytest.raises(SelectionError) as raised:
        sheet.table("costs")
    assert "'costs'" in str(raised.value)


# ── AC 5: the iteration, in a stated order ───────────────────────────────────

def test_theIterationTakesSheetsThenTablesThenRowsThenColumns() -> None:
    """`20-formula-shapes` is two sheets, three tables, and a table whose cells run
    down column A and then across rows 11 and 12."""
    document = openDocument("20-formula-shapes")
    found = list(document.cellsIterate())
    assert [sheet.name for sheet, _, _ in found[:1]] == ["Sheet 1"]
    assert [sheet.name for sheet, _, _ in found[-1:]] == ["Sheet 2"]

    firstTable = document.sheet(1).table("Table 1")
    references = [
        str(cell.address) for _, table, cell in found if table is firstTable
    ]
    assert references == (
        [f"A{row}" for row in range(1, 11)]
        + [f"{column}11" for column in "ABCDEFGH"]
        + [f"{column}12" for column in "ABCDEFGH"]
    )


def test_theIterationTakesTablesInSheetOrder() -> None:
    document = openDocument("20-formula-shapes")
    seen: list[tuple[str, str]] = []
    for sheet, table, _ in document.cellsIterate():
        if not seen or seen[-1] != (sheet.name, table.name):
            seen.append((sheet.name, table.name))
    assert seen == [
        ("Sheet 1", "Table 1"),
        ("Sheet 1", "Table 2"),
        ("Sheet 2", "Table 1"),
    ]


def test_aCellArrivesWithTheTableAndSheetHoldingIt() -> None:
    """AC 5.i. `20-formula-shapes` holds three cells at A1, in three tables, two of
    which are named `Table 1` on different sheets. The reference alone tells them
    apart in none of the three cases."""
    document = openDocument("20-formula-shapes")
    atA1 = [
        (sheet.name, table.name, cell.value)
        for sheet, table, cell in document.cellsIterate()
        if str(cell.address) == "A1"
    ]
    assert atA1 == [
        ("Sheet 1", "Table 1", Decimal(1)),
        ("Sheet 1", "Table 2", Decimal(42)),
        ("Sheet 2", "Table 1", Decimal(53)),
    ]


def test_theYieldedCellIsTheTablesOwnCellAndNotACopy() -> None:
    document = openDocument("20-formula-shapes")
    sheet, table, cell = next(iter(document.cellsIterate()))
    assert cell is table.cells[cell.address]
    assert table is sheet.tables[0]
    assert isinstance(cell, Cell)


def test_theIterationCoversStoredCellsAndNotAnEmptyRectangle() -> None:
    """AC 5.ii. `22-merge-2x2` declares a 2 by 13 grid, 26 positions, and stores 18
    cells: the rest are empty or swallowed by one of its five merges, and neither
    kind has a record in a tile at all."""
    document = openDocument("22-merge-2x2")
    table = document.sheet(1).table(1)
    yielded = [str(cell.address) for _, _, cell in document.cellsIterate()]
    assert len(yielded) == len(table.cells) == 18
    assert table.rowCount * table.colCount == 26
    # A1:B1 is merged, so A1 is yielded once and B1 not at all.
    assert "A1" in yielded and "B1" not in yielded


def test_aDocumentWithNoTablesYieldsNothing() -> None:
    """`34-shape` holds only drawables that are not tables."""
    assert list(openDocument("34-shape").cellsIterate()) == []


@pytest.mark.parametrize(
    "path", allDocuments, ids=lambda path: path.stem
)
def test_everyDocumentYieldsEveryCellItStores(path: Path) -> None:
    """Totality: across the documents every stored cell is yielded exactly once."""
    document = pybers.open(path)
    stored = sum(
        len(table.cells) for sheet in document.sheets for table in sheet.tables
    )
    found = list(document.cellsIterate())
    assert len(found) == stored
    assert len({id(cell) for _, _, cell in found}) == stored


# ── AC 6: the iteration drives an edit that survives a save ─────────────────

def test_theIterationDrivesAnEditThatSurvivesAReopen(tmp_path: Path) -> None:
    """Read each cell's value and type as it arrives, change it, count as it goes,
    then save and reopen and find the same order and the new values.

    Only the typed numbers are edited. Rows 11 and 12 of `Table 1` are the formula
    row and its commentary, and the writer refuses a formula-backed cell rather than
    discarding the formula, which is a stated limit of the write path rather than
    anything about the iteration.
    """
    target = tmp_path / "20-formula-shapes.numbers"
    shutil.copy(findDocumentPath("20-formula-shapes"), target)
    document = pybers.open(target)

    countBySheet: dict[str, int] = {}
    edited: dict[tuple[str, str, str], Decimal] = {}
    for sheet, table, cell in document.cellsIterate():
        countBySheet[sheet.name] = countBySheet.get(sheet.name, 0) + 1
        if not isinstance(cell.value, Decimal) or cell.address.row > 10:
            continue
        replacement = cell.value + Decimal(1000)
        cell.value = replacement
        edited[(sheet.name, table.name, str(cell.address))] = replacement

    assert countBySheet == {"Sheet 1": 27, "Sheet 2": 1}
    assert len(edited) == 12
    order = [
        (sheet.name, table.name, str(cell.address))
        for sheet, table, cell in document.cellsIterate()
    ]

    document.save()
    reopened = pybers.open(target)

    assert [
        (sheet.name, table.name, str(cell.address))
        for sheet, table, cell in reopened.cellsIterate()
    ] == order
    for sheet, table, cell in reopened.cellsIterate():
        key = (sheet.name, table.name, str(cell.address))
        if key in edited:
            assert cell.value == edited[key]
