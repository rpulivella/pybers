#!/usr/bin/env python3
"""\
A format through a range, a save, a fill, a copy and a move, and one pybers cannot read.

`13-number-percent` holds a number Automatic formats in `A1` and a percent a person
chose in `B1`, and `86-custom-text-and-currency` custom formats pybers reads as unknown.

UPDATES
2026-11-10  Written for PYB-145 AC 1, AC 4 and AC 5.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/10"

from collections.abc import Callable
from pathlib import Path

import pytest
from test_writer import readRecordAt

import pybers
from conftest import copyDocument
from pybers import (
    CellFormatAutomatic,
    CellFormatNumber,
    CellFormatPercent,
    CellFormatUnknown,
    CellValueFill,
    FormulaReferenceRelocation,
)

relative = FormulaReferenceRelocation.PRESERVE_RELATIVE_POSITION


@pytest.fixture
def working(tmp_path: Path) -> Path:
    """Return a copy of the percent document, so a save never touches the fixture."""
    return copyDocument("13-number-percent", tmp_path)


def readFormat(path: Path, address: str) -> object:
    """Return the format one cell of the saved document shows its value with."""
    return pybers.open(path).sheets[0].tables[0].cell(address).presentation.format


def editAndSave(path: Path, edit: Callable[[pybers.Table], object]) -> None:
    """Make one edit to the first table and save the document."""
    document = pybers.open(path)
    edit(document.sheets[0].tables[0])
    document.save()


def readRowOne(path: Path) -> list[pybers.Cell]:
    """Return the measured cells `A1` to `G1` of the saved document."""
    table = pybers.open(path).sheets[0].tables[0]
    return [table.cell(f"{column}1") for column in "ABCDEFG"]


def testARangeTakesAFormatAndEveryValueStays(working: Path) -> None:
    before = [cell.value for cell in readRowOne(working)]
    document = pybers.open(working)
    document.cellSet("::Table 1::A1:G1", format=CellFormatAutomatic())
    document.save()
    assert [cell.value for cell in readRowOne(working)] == before
    assert {cell.presentation.format for cell in readRowOne(working)} == {
        CellFormatAutomatic(CellFormatNumber())
    }


@pytest.mark.parametrize(("edit", "address"), [
    (lambda table: table.cellsFill(
        "B1", "B1:B2", references=relative, values=CellValueFill.REPEAT_SOURCE_VALUE
    ), "B2"),
    (lambda table: table.cellsCopy("B1", "H1", references=relative), "H1"),
    (lambda table: table.cellsMove("B1", "H1", references=relative), "H1"),
    (lambda table: table.rowAdd(1), "B2"),
])
def testAChosenFormatTravelsWithItsCell(
    edit: Callable[[pybers.Table], object], address: str, working: Path
) -> None:
    editAndSave(working, edit)
    assert readFormat(working, address) == CellFormatPercent()


@pytest.mark.parametrize("edit", [
    lambda table: table.cellsCopy("A1", "H1", references=relative),
    lambda table: table.cellsMove("A1", "H1", references=relative),
])
def testAFormatSetBeforeACopyOrMoveIsSavedWhereTheCellLands(
    edit: Callable[[pybers.Table], object], working: Path
) -> None:
    document = pybers.open(working)
    document.cellSet("::Table 1::A1", format=CellFormatNumber())
    edit(document.sheets[0].tables[0])
    document.save()
    assert readFormat(working, "H1") == CellFormatNumber()


def testAFormatPybersCannotReadIsCarriedThroughAnEdit(tmp_path: Path) -> None:
    working = copyDocument("86-custom-text-and-currency", tmp_path)
    before = readRecordAt(working, "A1").raw
    assert isinstance(readFormat(working, "A1"), CellFormatUnknown)
    document = pybers.open(working)
    document.cellSet("::Table 1::A2", "edited")
    document.save()
    assert readRecordAt(working, "A1").raw == before
    assert isinstance(readFormat(working, "A1"), CellFormatUnknown)
