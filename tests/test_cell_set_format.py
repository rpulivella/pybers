#!/usr/bin/env python3
"""\
A format set with a value, or alone, through `cellSet` and `pybers set --cell-format`.

Each test edits a copy of `13-number-percent`, whose `A1` is a number Automatic
formats and whose `B1` is the same number in a percent format a person chose.

UPDATES
2026-11-10  Written for PYB-145.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/10"

from decimal import Decimal
from pathlib import Path

import pytest
from test_cli_set import runSetCommand
from test_writer import listArchiveDifferences

import pybers
from conftest import copyDocument
from pybers import CellFormatAutomatic, CellFormatNumber, CellFormatPercent, CellKind
from pybers._persistence import readPackage


@pytest.fixture
def working(tmp_path: Path) -> Path:
    """Return a copy of the document, so a save never touches the fixture."""
    return copyDocument("13-number-percent", tmp_path)


def readFormat(path: Path, address: str) -> object:
    """Return the format one cell of the saved document shows its value with."""
    return pybers.open(path).sheets[0].tables[0].cell(address).presentation.format


def testAFormatAloneIsSavedAndTheValueKept(working: Path) -> None:
    document = pybers.open(working)
    document.cellSet("::Table 1::A1", format=CellFormatNumber())
    document.save()
    cell = pybers.open(working).sheets[0].tables[0].cell("A1")
    assert cell.value == Decimal("0.25")
    assert cell.presentation.format == CellFormatNumber()


def testAutomaticReplacesAChosenFormatWithTheOneNumbersPicks(working: Path) -> None:
    document = pybers.open(working)
    document.cellSet("::Table 1::B1", format=CellFormatAutomatic())
    document.save()
    assert readFormat(working, "B1") == CellFormatAutomatic(CellFormatNumber())


def testAValueAndAFormatAreSetInOneCall(working: Path) -> None:
    document = pybers.open(working)
    (change,) = document.cellSet(
        "::Table 1::A2", Decimal(7), format=CellFormatNumber()
    ).changes
    assert (change.kindBefore, change.kindAfter) == (CellKind.TEXT, CellKind.NUMBER)
    assert change.formatAfter == CellFormatNumber()
    document.save()
    assert readFormat(working, "A2") == CellFormatNumber()


def testTheChangeSaysWhichFormatTheCellShowedAndShows(working: Path) -> None:
    (change,) = pybers.open(working).cellSet(
        "::Table 1::A1", format=CellFormatNumber()
    ).changes
    assert change.formatBefore == CellFormatAutomatic(CellFormatNumber())
    assert change.formatAfter == CellFormatNumber()
    assert change.changed


def testAFormatTheCellShowsAlreadyChangesNothing(working: Path) -> None:
    before = readPackage(working)
    document = pybers.open(working)
    changes = document.cellSet("::Table 1::B1", format=CellFormatPercent())
    assert not changes.changed
    document.save()
    assert listArchiveDifferences(before, readPackage(working)) == []


def testAFormatPybersCannotYetWriteIsRefusedAndNothingChanges(working: Path) -> None:
    document = pybers.open(working)
    with pytest.raises(pybers.WriteError, match="cannot yet write a percent format"):
        document.cellSet("::Table 1::A1:B1", format=CellFormatPercent())
    assert document.sheets[0].tables[0].cell("A1").presentation.format == (
        CellFormatAutomatic(CellFormatNumber())
    )


def testAnEmptyCellIsRefusedAFormat(working: Path) -> None:
    with pytest.raises(pybers.WriteError, match="holds no value"):
        pybers.open(working).cellSet("::Table 1::H1", format=CellFormatNumber())


def testACallGivenNeitherPartIsRefused(working: Path) -> None:
    with pytest.raises(pybers.WriteError, match="neither a value nor a format"):
        pybers.open(working).cellSet("::Table 1::A1")


def testACommandSetsAFormatAloneByItsTextForm(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 1::B1", "--cell-format", "automatic")
    assert result.exit_code == 0, result.output
    assert readFormat(working, "B1") == CellFormatAutomatic(CellFormatNumber())


def testACommandSetsAValueAndAFormatTogether(working: Path) -> None:
    result = runSetCommand(
        str(working), "::Table 1::A2", "7", "--cell-format", "number"
    )
    assert result.exit_code == 0, result.output
    assert readFormat(working, "A2") == CellFormatNumber()


def testACommandRefusesAFormatNamingNoFamily(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 1::A1", "--cell-format", "percentage")
    assert result.exit_code == 1
    assert "'percentage' is no format family" in result.output


def testACommandGivenNeitherPartIsRefused(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 1::A1")
    assert result.exit_code == 2
    assert "Give a VALUE, a --cell-format, or both." in result.output
