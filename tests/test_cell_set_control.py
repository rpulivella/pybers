#!/usr/bin/env python3
"""\
A control set as its own part of a cell, removed with None, and its text form.

Each test edits a copy of `11-value-types-noformats`, which holds a checkbox in `E1`, a
star rating in `F1`, a slider in `G1`, a stepper in `H1` and a pop-up menu in `I1`, and
text in `A2`.

UPDATES
2026-11-10  Written for PYB-145 AC 20.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/10"

import re
from decimal import Decimal
from pathlib import Path

import pytest
from test_cli_set import runSetCommand
from test_writer import listArchiveDifferences

import pybers
from conftest import copyDocument, readPlainText
from pybers import (
    UNCHANGED,
    CellControlPopUpMenu,
    CellControlSlider,
    CellFormatAutomatic,
    CellFormatBoolean,
    CellFormatNumber,
)
from pybers._persistence import readPackage

slider = CellControlSlider(Decimal(0), Decimal(9), Decimal(1))


@pytest.fixture
def working(tmp_path: Path) -> Path:
    """Return a copy of the document, so a save never touches the fixture."""
    return copyDocument("11-value-types-noformats", tmp_path)


def readPresentation(path: Path, address: str) -> pybers.CellPresentation:
    """Return how one cell of the saved document shows its value."""
    return pybers.open(path).sheets[0].tables[0].cell(address).presentation


def setAndSave(path: Path, address: str, **parts: object) -> pybers.CellChanges:
    """Set parts of one cell of the first table, save, and return the changes."""
    document = pybers.open(path)
    changes = document.cellSet(f"::Table 1::{address}", UNCHANGED, **parts)
    document.save()
    return changes


def testRemovingASliderKeepsTheFormatItShowedThrough(working: Path) -> None:
    (change,) = setAndSave(working, "G1", control=None).changes
    assert isinstance(change.controlBefore, CellControlSlider)
    assert change.controlAfter is None
    shown = readPresentation(working, "G1")
    assert (shown.control, shown.format) == (None, CellFormatNumber())


def testRemovingACheckboxLeavesItsValueAutomatic(working: Path) -> None:
    setAndSave(working, "E1", control=None)
    shown = readPresentation(working, "E1")
    assert (shown.control, shown.format) == (
        None, CellFormatAutomatic(CellFormatBoolean())
    )


def testRemovingNoControlChangesNothing(working: Path) -> None:
    before = readPackage(working)
    changes = setAndSave(working, "A1", control=None)
    assert not changes.changed
    assert listArchiveDifferences(before, readPackage(working)) == []


def testAControlBesideAFormatItCannotUseIsRefusedNamingBoth(working: Path) -> None:
    refusal = (
        "A2 shows its value through a text format, which a slider control cannot use. "
        "It uses currency, fraction, number, numeral-system, percent, scientific."
    )
    with pytest.raises(pybers.WriteError, match=re.escape(refusal)):
        pybers.open(working).cellSet("::Table 1::A2", control=slider)


def testAControlPybersCannotYetWriteIsRefused(working: Path) -> None:
    with pytest.raises(pybers.WriteError, match="cannot yet write a slider control"):
        pybers.open(working).cellSet("::Table 1::A1", control=slider)


def testAFormatBeneathAControlIsRefusedUnlessTheControlGoes(working: Path) -> None:
    with pytest.raises(pybers.WriteError, match="shows its value through a control"):
        pybers.open(working).cellSet("::Table 1::G1", format=CellFormatAutomatic())
    setAndSave(working, "G1", control=None, format=CellFormatAutomatic())
    shown = readPresentation(working, "G1")
    assert (shown.control, shown.format) == (
        None, CellFormatAutomatic(CellFormatNumber())
    )


@pytest.mark.parametrize("control", [
    pybers.CellControlCheckbox(), pybers.CellControlStarRating(), slider,
    CellControlPopUpMenu(("Item 1", 'say "yes"; or not', "a, b"), False),
])
def testAControlReadsBackFromItsTextForm(control: pybers.CellControl) -> None:
    assert pybers.parseCellControl(pybers.formatCellControl(control)) == control


def testNoneNamesNoControl() -> None:
    assert pybers.parseCellControl("none") is None


@pytest.mark.parametrize(("text", "refusal"), [
    ("knob", "'knob' is no control. Use one of: none, checkbox"),
    ("slider; minimum: 0", "slider needs maximum, increment."),
    ("slider; minimum: x; maximum: 1; increment: 1",
     "slider minimum is 'x', not a number"),
    ("checkbox; size: 2", "checkbox has no setting 'size'; it takes no settings."),
    ("pop-up-menu; items: a; starts-with-first-item: no", "not a list of quoted items"),
])
def testATextFormNamingNoControlOrSettingIsRefusedSayingWhich(
    text: str, refusal: str
) -> None:
    with pytest.raises(pybers.CellControlError, match=re.escape(refusal)):
        pybers.parseCellControl(text)


def testACommandRemovesAControl(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 1::G1", "--cell-control", "none")
    assert result.exit_code == 0, result.output
    assert readPresentation(working, "G1").control is None


def testACommandRefusesAControlNamingNone(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 1::G1", "--cell-control", "knob")
    assert result.exit_code == 1
    assert "'knob' is no control" in readPlainText(result.output)
