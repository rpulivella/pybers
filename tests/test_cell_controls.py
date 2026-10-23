#!/usr/bin/env python3
"""\
A cell's control, read from its spec beside the format that shows its value.

`81-control-formats` labels each control's kind, range and the format under it, and
`11-value-types-noformats` holds one of each control over its plain value.

UPDATES
2026-10-22  Written for PYB-255.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/22"

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
from test_cell_value_kinds import openFirstTable

import pybers
from conftest import copyDocument, findDocumentPath
from pybers import (
    UNDETERMINED,
    CellControlCheckbox,
    CellControlPopUpMenu,
    CellControlSlider,
    CellControlStarRating,
    CellControlStepper,
    CellControlUnknown,
    CellFormat,
    CurrencyAmount,
)
from pybers._family import FamilyMember, checkFamily
from pybers._generated import TSTArchives_pb2 as tst
from pybers.table._controls import readControl


def readPresentation(stem: str, reference: str) -> pybers.CellPresentation:
    """Return how one cell shows its value, as a fresh read finds it."""
    return openFirstTable(findDocumentPath(stem))[1].cell(reference).presentation


@pytest.mark.parametrize(("reference", "control", "shownAs"), [
    ("A1", CellControlSlider(Decimal(0), Decimal(200), Decimal(5)), CellFormat.NUMBER),
    ("B1", CellControlStepper(Decimal(-10), Decimal(10), Decimal("0.5")),
     CellFormat.NUMBER),
    ("C1", CellControlSlider(Decimal(0), Decimal(100), Decimal(1)),
     CellFormat.CURRENCY),
    ("D1", CellControlSlider(Decimal(0), Decimal(1), Decimal("0.05")),
     CellFormat.PERCENT),
    ("I1", CellControlPopUpMenu(("Item 1", "Item 2", "Item 3"), False),
     CellFormat.TEXT),
    ("J1", CellControlStarRating(), CellFormat.STAR_RATING),
    ("K1", CellControlCheckbox(), CellFormat.CHECKBOX),
])
def testEachControlReadsAsItsLabelSaysOverTheFormatShowingIt(
    reference: str, control: pybers.CellControl, shownAs: CellFormat
) -> None:
    presentation = readPresentation("81-control-formats", reference)
    assert (presentation.control, presentation.format) == (control, shownAs)


def testARangeBoundReadsAsTheNumberNumbersShows() -> None:
    control = readPresentation("11-value-types-noformats", "G1").control
    assert isinstance(control, CellControlSlider)
    assert [str(bound) for bound in (control.minimum, control.maximum)] == ["1", "100"]


def testAPopUpMenuStartingWithItsFirstItemSaysSo() -> None:
    control = readPresentation("11-value-types-noformats", "I1").control
    assert control == CellControlPopUpMenu(("Item 1", "Item 2", "Item 3"), True)


def testACellWithNoControlReadsNone() -> None:
    assert readPresentation("11-value-types-noformats", "A1").control is None


def testAnUnmeasuredControlIsCarriedByItsInteractionType() -> None:
    spec = tst.CellSpecArchive(interaction_type=99)
    assert readControl(None, spec) == CellControlUnknown(99)  # type: ignore[arg-type]


def testAControlShowingTheNewValueIsKeptBeforeTheSave(tmp_path: Path) -> None:
    _, table = openFirstTable(copyDocument("11-value-types-noformats", tmp_path))
    cell = table.cell("G1")
    cell.value = Decimal(51)
    assert isinstance(cell.presentation.control, CellControlSlider)


def testAControlThatCannotShowTheValueGoesWithItsFormat(tmp_path: Path) -> None:
    _, table = openFirstTable(copyDocument("11-value-types-noformats", tmp_path))
    cell = table.cell("F1")
    cell.value = Decimal(7)
    presentation = cell.presentation
    assert (presentation.control, presentation.format) == (None, UNDETERMINED)
    assert not presentation.formatChosen


def testAKindChangeDropsTheControl(tmp_path: Path) -> None:
    _, table = openFirstTable(copyDocument("11-value-types-noformats", tmp_path))
    cell = table.cell("G1")
    cell.value = "words"
    assert cell.presentation.control is None


def testASavedControlIsReadAgainFromWhatTheSaveKept(tmp_path: Path) -> None:
    working = copyDocument("11-value-types-noformats", tmp_path)
    document, table = openFirstTable(working)
    table.cell("G1").value = Decimal(51)
    table.cell("H1").value = Decimal(500)
    document.save()
    assert isinstance(table.cell("G1").presentation.control, CellControlSlider)
    assert table.cell("H1").presentation.control is None


def testAScriptFindsEverySliderInATable() -> None:
    _, table = openFirstTable(findDocumentPath("81-control-formats"))
    sliders = [str(cell.address) for cell in table.cells.values()
               if isinstance(cell.presentation.control, CellControlSlider)]
    assert sliders == ["A1", "C1", "D1", "E1", "F1"]


def testAControlCannotBeExtended() -> None:
    with pytest.raises(TypeError, match="extends CellControlSlider"):
        type("CellControlWideSlider", (CellControlSlider,), {})


def testAFamilyMissingAMemberStopsTheImport() -> None:
    class Shape(FamilyMember):
        __slots__ = ()

    @dataclass(frozen=True, slots=True)
    class Square(Shape):
        side: int

    @dataclass(frozen=True, slots=True)
    class Circle(Shape):
        radius: int

    type ShapeAny = Square
    with pytest.raises(TypeError, match="disagree on .*Circle"):
        checkFamily(Shape, ShapeAny)


def testAMutableMemberStopsTheImport() -> None:
    class Shape(FamilyMember):
        __slots__ = ()

    @dataclass(slots=True)
    class Square(Shape):
        side: int

    type ShapeAny = Square
    with pytest.raises(TypeError, match="Square is not a frozen, slotted dataclass"):
        checkFamily(Shape, ShapeAny)


@pytest.mark.parametrize(("value", "shown"), [
    (Decimal(50), True), (Decimal(101), False),
    (CurrencyAmount(Decimal(100), "USD"), True),
    (CurrencyAmount(Decimal(101), "USD"), False), ("words", True),
])
def testASliderShowsOnlyANumberWithinItsRange(value: object, shown: bool) -> None:
    slider = CellControlSlider(Decimal(0), Decimal(100), Decimal(1))
    assert slider.showsValue(value) is shown  # type: ignore[arg-type]


def testAPopUpMenuShowsOnlyOneOfItsItems() -> None:
    menu = CellControlPopUpMenu(("Item 1", "Item 2"), True)
    assert (menu.showsValue("Item 2"), menu.showsValue("Banana")) == (True, False)


def testACurrencySliderIsDroppedForAnAmountOutsideItsRange(tmp_path: Path) -> None:
    working = copyDocument("81-control-formats", tmp_path)
    document, table = openFirstTable(working)
    table.cell("C1").value = CurrencyAmount(Decimal(500), "USD")
    document.save()
    assert table.cell("C1").presentation.control is None
