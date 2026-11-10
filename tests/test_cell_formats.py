#!/usr/bin/env python3
"""\
The format a cell shows its value with, a closed family whose Automatic holds its pick.

`13-number-percent` labels a plain number, which Numbers formats Automatically, beside
percentages a person chose.

UPDATES
2026-11-09  Written for PYB-145.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/09"

from dataclasses import dataclass
from typing import assert_never

import pytest
from test_cli_show import runShowCommand

import pybers
from conftest import findDocumentPath, listShownFields
from pybers import (
    CellFormat,
    CellFormatAutomatic,
    CellFormatBoolean,
    CellFormatCheckbox,
    CellFormatCurrency,
    CellFormatDateTime,
    CellFormatDuration,
    CellFormatFamily,
    CellFormatFraction,
    CellFormatNumber,
    CellFormatNumberCustom,
    CellFormatNumeralSystem,
    CellFormatPercent,
    CellFormatScientific,
    CellFormatShown,
    CellFormatStarRating,
    CellFormatText,
    CellFormatUnknown,
)
from pybers._family import FamilyMember, checkFamily, listFamilyMembers

percentPath = findDocumentPath("13-number-percent")


def readPercentCell(address: str) -> pybers.Cell:
    """Return one cell of the percent measurement, as a fresh read finds it."""
    return pybers.open(percentPath).sheets[0].tables[0].cell(address)


def findFamilyName(cellFormat: CellFormat) -> str:
    """Return a format's family by matching each member, which mypy holds exhaustive."""
    match cellFormat:
        case CellFormatAutomatic():
            return "automatic"
        case CellFormatNumber():
            return "number"
        case CellFormatNumberCustom():
            return "number-custom"
        case CellFormatBoolean():
            return "boolean"
        case CellFormatCurrency():
            return "currency"
        case CellFormatPercent():
            return "percent"
        case CellFormatScientific():
            return "scientific"
        case CellFormatFraction():
            return "fraction"
        case CellFormatNumeralSystem():
            return "numeral-system"
        case CellFormatText():
            return "text"
        case CellFormatDateTime():
            return "date-time"
        case CellFormatDuration():
            return "duration"
        case CellFormatCheckbox():
            return "checkbox"
        case CellFormatStarRating():
            return "star-rating"
        case CellFormatUnknown():
            return "unknown"
        case _:
            assert_never(cellFormat)


def testAFormatAPersonChoseReadsAsItsFamily() -> None:
    assert readPercentCell("B1").presentation.format == CellFormatPercent()


def testAFormatNobodyChoseIsAutomaticHoldingTheOneNumbersPicked() -> None:
    assert readPercentCell("A1").presentation.format == CellFormatAutomatic(
        CellFormatNumber()
    )


def testEveryFamilyIsOneMemberAndEveryMemberAFamily() -> None:
    members = listFamilyMembers(CellFormat)
    assert sorted(member.formatFamily for member in members) == sorted(CellFormatFamily)
    for member in members:
        sample = member(None) if member is CellFormatUnknown else member()
        assert findFamilyName(sample) == member.formatFamily.value


def testAutomaticIsNeverAFormatItCouldHold() -> None:
    assert CellFormatAutomatic not in listFamilyMembers(CellFormatShown)


def testAFormatCannotBeExtended() -> None:
    with pytest.raises(TypeError, match="extends CellFormatPercent"):
        type("CellFormatPercentWide", (CellFormatPercent,), {})


def testAFamilyHoldingAnotherAliasIsCheckedThroughIt() -> None:
    class Shape(FamilyMember):
        __slots__ = ()

    @dataclass(frozen=True, slots=True)
    class Square(Shape):
        side: int

    @dataclass(frozen=True, slots=True)
    class Circle(Shape):
        radius: int

    type ShapeFlat = Square
    type ShapeAny = ShapeFlat
    with pytest.raises(TypeError, match="disagree on .*Circle"):
        checkFamily(Shape, ShapeAny, "shapeType")


def testAScriptFindsEveryCellShownAsAPercentage() -> None:
    table = pybers.open(percentPath).sheets[0].tables[0]
    percents = []
    for cell in table.cells.values():
        match cell.presentation.format:
            case CellFormatPercent() | CellFormatAutomatic(shown=CellFormatPercent()):
                percents.append(str(cell.address))
    assert percents == ["B1", "C1", "D1", "E1", "F1", "G1"]


def testACommandLinePrintsAChosenFormatAndAnAutomaticOne() -> None:
    result = runShowCommand(percentPath, "*::Table 1::A1:B1")
    formats = [value for label, value in listShownFields(result.stdout)
               if label == "Format"]
    assert formats == ["automatic (shown number)", "percent"]
