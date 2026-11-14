#!/usr/bin/env python3
"""\
A format set with a value, or alone, through `cellSet` and `pybers set --cell-format`.

Each test edits a copy of `13-number-percent`, whose `A1` is a number Automatic
formats and whose `B1` is the same number in a percent format a person chose.

UPDATES
2026-11-10  A format that cannot show the value is refused unless Automatic is asked
            for, for PYB-145 AC 10.
2026-11-10  Setting one part leaves the others as they were, for PYB-145 AC 19.
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

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from test_cell_value_kinds import readFormatEntry
from test_cli_set import runSetCommand
from test_writer import listArchiveDifferences, readRecordAt

import pybers
from conftest import copyDocument, readPlainText
from pybers import (
    UNCHANGED,
    CellFormatAutomatic,
    CellFormatConflict,
    CellFormatNumber,
    CellFormatPercent,
    CellFormatText,
    CellKind,
)
from pybers._persistence import readPackage
from pybers._persistence.cells import (
    controlSlot,
    countedFormatSlots,
    displayedKindSlot,
    durationFormatSlot,
    findSlotValue,
    listReferenceSlots,
)


@pytest.fixture
def working(tmp_path: Path) -> Path:
    """Return a copy of the document, so a save never touches the fixture."""
    return copyDocument("13-number-percent", tmp_path)


def readOtherParts(path: Path, address: str) -> dict[tuple[int, int], int | None]:
    """Return every reference a saved record holds beside its format and control."""
    record = readRecordAt(path, address)
    shown = {*countedFormatSlots, displayedKindSlot, controlSlot}
    return {slot: findSlotValue(record, slot)
            for slot in listReferenceSlots(record.raw) if slot not in shown}


def setAndSave(path: Path, address: str, value: object, **parts: object) -> None:
    """Set one cell of the first table and save the document."""
    document = pybers.open(path)
    table = document.sheets[0].tables[0]
    document.cellSet(f"::{table.name}::{address}", value, **parts)
    document.save()


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


def testARangeFormatsEveryCellItsEmptyAndFormulaCellsIncluded(
    tmp_path: Path,
) -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Range", rows=1, cols=3)
    table.cell("A1").value = Decimal(5)
    table.cell("C1").formulaText = "=A1*2"
    working = tmp_path / "range.numbers"
    document.save(working)
    reopened = pybers.open(working)
    assert not reopened.cellSet("::Range::A1:C1", format=CellFormatNumber()).skipped
    reopened.save()
    saved = pybers.open(working).table("Range")
    assert [saved.cell(each).presentation.format for each in ("A1", "B1", "C1")] == [
        CellFormatNumber(), CellFormatNumber(), CellFormatNumber()
    ]


@pytest.mark.parametrize("chosen", [
    CellFormatNumber(), pybers.CellFormatDateTime(), pybers.CellFormatDuration(),
    CellFormatText(),
])
def testAnEmptyCellHoldsAChosenFormat(
    chosen: pybers.CellFormat, tmp_path: Path
) -> None:
    document = pybers.create("en_US")
    document.sheet().tableAdd("Blank", rows=1, cols=1)
    working = tmp_path / "blank.numbers"
    document.save(working)
    reopened = pybers.open(working)
    reopened.cellSet("::Blank::A1", format=chosen)
    reopened.save()
    cell = pybers.open(working).table("Blank").cell("A1")
    assert (cell.value, cell.presentation.format) == (None, chosen)


def testAnEmptyCellRefusesAFormatPybersCannotWriteYet(tmp_path: Path) -> None:
    document = pybers.create("en_US")
    document.sheet().tableAdd("Blank", rows=1, cols=1)
    working = tmp_path / "blank.numbers"
    document.save(working)
    with pytest.raises(pybers.WriteError, match="cannot yet write a percent format"):
        pybers.open(working).cellSet("::Blank::A1", format=CellFormatPercent())


def testAFormulaWithNoResultHoldsItsFormatUntilNumbersCalculates(
    tmp_path: Path,
) -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Calc", rows=1, cols=2)
    table.cell("A1").formulaText = "=DATE(2026,11,10)"
    working = tmp_path / "calc.numbers"
    document.save(working)
    reopened = pybers.open(working)
    reopened.cellSet("::Calc::A1", format=pybers.CellFormatDateTime())
    reopened.save()
    cell = pybers.open(working).table("Calc").cell("A1")
    assert (cell.formulaText, cell.value) == ("=DATE(2026,11,10)", None)
    assert cell.presentation.format == pybers.CellFormatDateTime()


def testAFormulaWithNoResultRefusesAFormatPybersCannotWriteForIt(
    tmp_path: Path,
) -> None:
    document = pybers.create("en_US")
    document.sheet().tableAdd("Calc", rows=1, cols=1).cell("A1").formulaText = "=1"
    working = tmp_path / "calc.numbers"
    document.save(working)
    with pytest.raises(pybers.WriteError, match="cannot yet write a currency format"):
        pybers.open(working).cellSet("::Calc::A1", format=pybers.CellFormatCurrency())


def testACallGivenNeitherPartIsRefused(working: Path) -> None:
    with pytest.raises(
        pybers.WriteError, match="no value, format, control or cell style"
    ):
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
    assert "'percentage' is no format family" in readPlainText(result.output)


def testACommandGivenNeitherPartIsRefused(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 1::A1")
    assert result.exit_code == 2
    shown = readPlainText(result.output)
    assert "Give a VALUE, a --cell-format, a --cell-control or a --cell-style." in (
        shown
    )


@pytest.mark.parametrize(("stem", "address"), [
    ("28-style-fills", "B1"), ("04-text-monospace", "A1"),
])
def testAFormatAloneLeavesTheCellsStyle(
    stem: str, address: str, tmp_path: Path
) -> None:
    working = copyDocument(stem, tmp_path)
    before = readOtherParts(working, address)
    setAndSave(working, address, UNCHANGED, format=CellFormatText())
    assert readOtherParts(working, address) == before
    assert readFormat(working, address) == CellFormatText()


@pytest.mark.parametrize(("stem", "address", "value"), [
    ("28-style-fills", "B1", "changed"), ("04-text-monospace", "A1", Decimal(3)),
])
def testAValueAloneLeavesTheCellsStyle(
    stem: str, address: str, value: object, tmp_path: Path
) -> None:
    working = copyDocument(stem, tmp_path)
    before = readOtherParts(working, address)
    setAndSave(working, address, value)
    assert readOtherParts(working, address) == before


def testAValueOfTheSameKindKeepsTheFormatAPersonChose(working: Path) -> None:
    before = findSlotValue(readRecordAt(working, "B1"), countedFormatSlots[0])
    setAndSave(working, "B1", Decimal("0.5"))
    assert readFormat(working, "B1") == CellFormatPercent()
    assert findSlotValue(readRecordAt(working, "B1"), countedFormatSlots[0]) == before


def testAValueOfAnotherKindTakesTheAutomaticFormatOfItsKind(working: Path) -> None:
    setAndSave(working, "B1", "a quarter")
    assert readFormat(working, "B1") == CellFormatAutomatic(CellFormatText())


def testAFormatThatCannotShowTheValueIsRefusedNamingBoth(working: Path) -> None:
    document = pybers.open(working)
    refusal = "A2 holds a text value, which a number format cannot show"
    with pytest.raises(pybers.WriteError, match=refusal):
        document.cellSet("::Table 1::A2", format=CellFormatNumber())
    assert document.sheets[0].tables[0].cell("A2").presentation.format == (
        CellFormatText()
    )


def testAValueTheFormatFitsIsJudgedByTheValueBeingWritten(working: Path) -> None:
    with pytest.raises(pybers.WriteError, match="would hold a text value"):
        pybers.open(working).cellSet(
            "::Table 1::A1", "a quarter", format=CellFormatNumber()
        )


def testAConflictFallingBackGivesAutomaticAndSaysWhy(working: Path) -> None:
    document = pybers.open(working)
    changes = document.cellSet(
        "::Table 1::A1:A2", format=CellFormatNumber(),
        conflict=CellFormatConflict.AUTOMATIC,
    )
    (skip,) = changes.skipped
    assert skip.reason.endswith("number format cannot show. It takes Automatic.")
    document.save()
    assert readFormat(working, "A1") == CellFormatNumber()
    assert readFormat(working, "A2") == CellFormatAutomatic(CellFormatText())


def testACommandFallsBackToAutomaticWhenAsked(working: Path) -> None:
    result = runSetCommand(
        str(working), "::Table 1::A2", "--cell-format", "number",
        "--conflict", "automatic",
    )
    assert result.exit_code == 0, result.output
    assert "It takes Automatic." in readPlainText(result.output)
    assert readFormat(working, "A2") == CellFormatAutomatic(CellFormatText())


def testACommandRefusesAFormatThatCannotShowTheValue(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 1::A2", "--cell-format", "number")
    assert result.exit_code == 1
    assert "which a number format cannot show" in readPlainText(result.output)


def testABooleanFormatNoMenuOffersIsRefused(tmp_path: Path) -> None:
    working = copyDocument("90-values-for-booleans", tmp_path)
    with pytest.raises(pybers.WriteError, match="offers no boolean format to choose"):
        pybers.open(working).cellSet(
            "::Table 1::A1", True, format=pybers.CellFormatBoolean()
        )


@pytest.mark.parametrize(("value", "largest", "smallest"), [
    (datetime.timedelta(minutes=20), 8, 8),
    (datetime.timedelta(hours=1, minutes=30), 4, 8),
    (datetime.timedelta(days=71, hours=11, milliseconds=10), 1, 32),
])
def testAnAutomaticDurationStoresTheUnitsItsValueHolds(
    value: datetime.timedelta, largest: int, smallest: int, working: Path
) -> None:
    setAndSave(working, "A1", value)
    entry = readFormatEntry(working, "A1").format
    assert (entry.duration_unit_largest, entry.duration_unit_smallest) == (
        largest, smallest
    )


def testACalculatedFormulaTakesAFormatAndKeepsItsFormula(tmp_path: Path) -> None:
    working = copyDocument("20-formula-shapes", tmp_path)
    document = pybers.open(working)
    document.cellSet("Sheet 1::Table 1::A11", format=CellFormatNumber())
    document.save()
    cell = pybers.open(working).sheet("Sheet 1").table("Table 1").cell("A11")
    assert (cell.formulaText, cell.value) == ("=SUM(A1:A10)", Decimal(55))
    assert cell.presentation.format == CellFormatNumber()


def testAFormatAFormulasResultDoesNotFitWaitsInItsSlot(tmp_path: Path) -> None:
    working = copyDocument("20-formula-shapes", tmp_path)
    document = pybers.open(working)
    document.cellSet("Sheet 1::Table 1::A11", format=pybers.CellFormatDuration())
    document.save()
    cell = pybers.open(working).sheet("Sheet 1").table("Table 1").cell("A11")
    assert cell.presentation.format == CellFormatAutomatic(CellFormatNumber())
    record = readRecordAt(working, "A11", "Table 1")
    assert findSlotValue(record, durationFormatSlot) is not None
    assert record.raw[6] & 0x04


def testAChosenTextFormatOnAFormulaIsRefused(tmp_path: Path) -> None:
    working = copyDocument("20-formula-shapes", tmp_path)
    with pytest.raises(pybers.WriteError, match="keeps no chosen text format"):
        pybers.open(working).cellSet(
            "Sheet 1::Table 1::D11", format=CellFormatText()
        )
