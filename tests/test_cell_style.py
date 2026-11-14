#!/usr/bin/env python3
"""\
A cell's own cell style, read from what Numbers stored, one frozen object per archive.

UPDATES
2026-11-12  Written for PYB-265.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/12"

import dataclasses
from decimal import Decimal

import pytest

import pybers
from conftest import findDocumentPath
from pybers import (
    CellStyle,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
    Color,
    FillGradient,
    FillImage,
    FillNone,
)
from pybers._generated import TSDArchives_pb2 as tsd
from pybers._generated import TSTArchives_pb2 as tst
from pybers.style._read import readCellStyle, readFill

yellow = Color.parse("#ffd60aff")


def readBoxCells() -> dict[str, pybers.Cell]:
    """Return row 1 of `98b-cell-box-styles`, one styled cell per column, by column."""
    table = pybers.open(findDocumentPath("98b-cell-box-styles")).sheets[0].tables[0]
    return {f"{column}1": table.cell(f"{column}1") for column in "ABCDEFGHIJ"}


@pytest.mark.parametrize(("address", "expected"), [
    ("B1", CellStyle(background=yellow)),
    ("C1", CellStyle(background=Color.parse("#ff0000ff"))),
    ("D1", CellStyle(verticalAlign=CellStyleVerticalAlign.MIDDLE)),
    ("E1", CellStyle(textWrap=CellStyleTextWrap.NOWRAP)),
    ("F1", CellStyle(padding=Decimal(6))),
    ("I1", CellStyle(background=yellow)),
    ("J1", CellStyle(background=yellow)),
])
def testCellReportsWhatItsOwnStyleStates(
    address: str, expected: CellStyle
) -> None:
    assert readBoxCells()[address].cellStyle == expected


@pytest.mark.parametrize("address", ["A1", "G1", "H1"])
def testCellWithNoCellStyleReadsNone(address: str) -> None:
    assert readBoxCells()[address].cellStyle is None


def testStylePresentAndDefaultDiffersFromNoStyle() -> None:
    archive = tst.CellStyleArchive()
    archive.cell_properties.padding.SetInParent()
    archive.cell_properties.vertical_alignment = 0
    assert readCellStyle(archive) == CellStyle(
        padding=Decimal(0), verticalAlign=CellStyleVerticalAlign.TOP
    )
    assert readCellStyle(tst.CellStyleArchive()) == CellStyle()


def testCellsNamingOneArchiveShareOneObject() -> None:
    cells = readBoxCells()
    assert cells["B1"].cellStyle is cells["I1"].cellStyle is cells["J1"].cellStyle


def testSharedCellStyleCannotBeEditedThroughOneCell() -> None:
    style = readBoxCells()["B1"].cellStyle
    with pytest.raises(dataclasses.FrozenInstanceError):
        style.padding = Decimal(8)  # type: ignore[misc]


def testUnevenImportedPaddingReadsEachSide() -> None:
    archive = tst.CellStyleArchive()
    padding = archive.cell_properties.padding
    padding.left, padding.right, padding.bottom = 2, 2, 2
    sides = (Decimal(0), Decimal(2), Decimal(2), Decimal(2))
    assert readCellStyle(archive).padding == sides


@pytest.mark.parametrize(("field", "expected"), [
    ("gradient", FillGradient()),
    ("image", FillImage()),
])
def testFillOtherThanColorReadsByItsType(field: str, expected: object) -> None:
    archive = tsd.FillArchive()
    getattr(archive, field).SetInParent()
    assert readFill(archive) == expected


def testEmptyFillReadsAsNoFill() -> None:
    assert readFill(tsd.FillArchive()) == FillNone()


@pytest.mark.parametrize("stored", [3, 9])
def testVerticalAlignmentACellNeverTakesRefuses(stored: int) -> None:
    archive = tst.CellStyleArchive()
    archive.cell_properties.vertical_alignment = stored
    with pytest.raises(pybers.ReadError, match=f"vertical alignment {stored}"):
        readCellStyle(archive)


@pytest.mark.parametrize(("cellStyle", "text"), [
    (CellStyle(), ""),
    (CellStyle(background=yellow), "background: #ffd60aff"),
    (CellStyle(background=FillNone()), "background: none"),
    (CellStyle(background=FillGradient()), "background: gradient"),
    (CellStyle(padding=Decimal("6")), "padding: 6pt"),
    (CellStyle(padding=(Decimal(0), Decimal(2), Decimal(2), Decimal(2))),
     "padding: 0pt 2pt 2pt 2pt"),
    (CellStyle(background=yellow, padding=Decimal(6),
               verticalAlign=CellStyleVerticalAlign.MIDDLE,
               textWrap=CellStyleTextWrap.NOWRAP),
     "background: #ffd60aff; padding: 6pt; vertical-align: middle; text-wrap: nowrap"),
])
def testCellStyleTextFormStatesEachPropertyAsCss(
    cellStyle: CellStyle, text: str
) -> None:
    assert pybers.formatCellStyle(cellStyle) == text


def testNoFillOnAHeaderCellReadsAsAnExplicitFillNone() -> None:
    table = pybers.open(findDocumentPath("98c-cell-box-regions")).sheets[0].tables[0]
    assert table.cell("B1").cellStyle == CellStyle(background=FillNone())


@pytest.mark.parametrize("address", ["C1", "D1"])
def testAPropertySetBackToWhatTheCellInheritsLeavesNoStyle(address: str) -> None:
    table = pybers.open(findDocumentPath("98c-cell-box-regions")).sheets[0].tables[0]
    assert table.cell(address).cellStyle is None
