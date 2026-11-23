#!/usr/bin/env python3
"""\
The box each section of a table shows: read, set, written alone, and as text.

`98c-cell-box-regions` gives row 1 to the header, gray in the Blank theme, and B1 there
states its own No Fill, which a cell carries as a copy of its section's style.

UPDATES
2026-11-20  Written for PYB-291.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/20"

import dataclasses
from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from conftest import copyDocument, findDocumentPath
from pybers import (
    CellStyle,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
    Color,
    FillGradient,
    FillNone,
    TableStyleError,
)
from pybers.style.cells import createdCellStyle, numbersCellStyle

yellow: Color = Color.parse("#ffd60aff")


def buildHeaderStyle(table: pybers.Table, **changes: object) -> pybers.TableStyle:
    """Return the table's style with its header rows' box changed as given."""
    held = table.tableStyle
    return dataclasses.replace(
        held,
        headerRowsCellStyle=dataclasses.replace(held.headerRowsCellStyle, **changes),
    )


def testATableReadsTheBoxEachSectionShows() -> None:
    style = pybers.open(findDocumentPath("98c-cell-box-regions")).table().tableStyle
    assert style.bodyCellStyle == numbersCellStyle
    assert isinstance(style.headerRowsCellStyle.background, Color)


def testACreatedTableShowsTheResetInEverySection() -> None:
    table = pybers.create("en_US").sheet().tableAdd("T", rows=3, cols=3)
    style = table.tableStyle
    boxes = {style.bodyCellStyle, style.headerRowsCellStyle,
             style.headerColumnsCellStyle, style.footerRowsCellStyle}
    assert boxes == {createdCellStyle}


def testAHeaderBoxSetOnANumbersFileReadsBackAndReachesItsCells(tmp_path: Path) -> None:
    working = copyDocument("98c-cell-box-regions", tmp_path)
    document = pybers.open(working)
    table = document.table()
    middle = CellStyleVerticalAlign.MIDDLE
    assert table.tableStyleSet(
        buildHeaderStyle(table, background=yellow, verticalAlign=middle)
    ).changed
    document.save()
    reopened = pybers.open(working).table()
    assert reopened.tableStyle.headerRowsCellStyle == dataclasses.replace(
        table.tableStyle.headerRowsCellStyle
    )
    assert reopened.cellStyleComputed("A1").background == yellow
    assert reopened.tableStyle.bodyCellStyle == numbersCellStyle


def testACellStatingItsOwnStyleTakesItsSectionsNewBox(tmp_path: Path) -> None:
    working = copyDocument("98c-cell-box-regions", tmp_path)
    document = pybers.open(working)
    table = document.table()
    middle = CellStyleVerticalAlign.MIDDLE
    table.tableStyleSet(buildHeaderStyle(table, verticalAlign=middle))
    document.save()
    reopened = pybers.open(working).table()
    assert reopened.cell("B1").cellStyle == CellStyle(background=FillNone())
    computed = reopened.cellStyleComputed("B1")
    assert computed.verticalAlign is CellStyleVerticalAlign.MIDDLE
    assert computed.background == FillNone()


def testABoxSetOnOneTableLeavesAnotherSharingItsStyle(tmp_path: Path) -> None:
    document = pybers.create("en_US")
    first = document.sheet().tableAdd("First", rows=3, cols=3)
    document.sheet().tableAdd("Second", rows=3, cols=3)
    first.headersSet(headerRows=1)
    first.tableStyleSet(buildHeaderStyle(first, background=yellow))
    path = tmp_path / "two.numbers"
    document.save(path)
    reopened = pybers.open(path).sheet()
    assert reopened.table("First").tableStyle.headerRowsCellStyle.background == yellow
    assert reopened.table("Second").tableStyle.headerRowsCellStyle == createdCellStyle


def testSettingTheBoxATableHoldsWritesNothing(tmp_path: Path) -> None:
    working = copyDocument("98c-cell-box-regions", tmp_path)
    document = pybers.open(working)
    table = document.table()
    assert not table.tableStyleSet(table.tableStyle).changed


@pytest.mark.parametrize(("box", "reason"), [
    (CellStyle(background=yellow), "stating every property"),
    (dataclasses.replace(numbersCellStyle, background=FillGradient()),
     "gradient fill is read and carried"),
    ("background: yellow", "stating every property"),
])
def testABoxPybersCannotHoldIsRefusedChangingNothing(box: object, reason: str) -> None:
    table = pybers.create("en_US").sheet().tableAdd("T", rows=3, cols=3)
    held = table.tableStyle
    with pytest.raises(TableStyleError, match=reason):
        table.tableStyleSet(dataclasses.replace(held, bodyCellStyle=box))
    assert table.tableStyle == held


def testEachSectionsBoxPrintsAsOneDeclarationPerProperty() -> None:
    style = pybers.open(findDocumentPath("98c-cell-box-regions")).table().tableStyle
    printed = pybers.formatTableStyle(style)
    assert printed[-16:-12] == [
        "body-background: none", "body-padding: 4pt", "body-vertical-align: top",
        "body-text-wrap: wrap",
    ]
    assert printed[-1] == "footer-rows-text-wrap: wrap"


def testADeclarationChangesOnePropertyOfASectionsBox() -> None:
    style = pybers.open(findDocumentPath("98c-cell-box-regions")).table().tableStyle
    parsed = pybers.parseTableStyle("body-padding: 6pt; body-text-wrap: nowrap", style)
    assert parsed.bodyCellStyle == dataclasses.replace(
        numbersCellStyle, padding=Decimal(6), textWrap=CellStyleTextWrap.NOWRAP
    )
    assert parsed.headerRowsCellStyle == style.headerRowsCellStyle


def testEveryPrintedDeclarationReadsBackUnchanged() -> None:
    style = pybers.open(findDocumentPath("98c-cell-box-regions")).table().tableStyle
    text = "; ".join(pybers.formatTableStyle(style))
    assert pybers.parseTableStyle(text, style) == style


@pytest.mark.parametrize(("text", "reason"), [
    ("body-padding: 6", "The padding '6' is not a length in points"),
    ("body-margin: 6pt", "The closest is body-padding"),
])
def testADeclarationPybersCannotReadIsRefused(text: str, reason: str) -> None:
    style = pybers.create("en_US").sheet().tableAdd("T", rows=3, cols=3).tableStyle
    with pytest.raises(TableStyleError, match=reason):
        pybers.parseTableStyle(text, style)


@pytest.mark.parametrize(
    "stem", ["98c-cell-box-regions", "104b-bands-merged-on", "40-table-bands"]
)
def testADocumentRebuiltFromJsonComputesEveryCellAsItsSource(
    stem: str, tmp_path: Path
) -> None:
    source = pybers.open(findDocumentPath(stem))
    path = tmp_path / "rebuilt.numbers"
    pybers.parseJsonForm(pybers.formatJsonForm(source)).save(path)
    rebuilt = pybers.open(path)
    for before, after in zip(
        (table for sheet in source.sheets for table in sheet.tables),
        (table for sheet in rebuilt.sheets for table in sheet.tables), strict=True,
    ):
        assert [before.cellStyleComputed(each) for each in before.extent] == [
            after.cellStyleComputed(each) for each in after.extent
        ]
