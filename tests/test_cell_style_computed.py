#!/usr/bin/env python3
"""\
A cell's computed box: every property it displays, beside the style it states itself.

`98c-cell-box-regions` gives row 1 to the header, where Numbers fills a header cell
gray, and B1 states No Fill. `102b-bands-on` and `104b-bands-merged-on` band their
body rows.

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

import pytest

import pybers
from conftest import findDocumentPath
from pybers import (
    CellStyle,
    CellStyleProperty,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
    Color,
    FillNone,
)

boxedHeader: pybers.Table = pybers.open(
    findDocumentPath("98c-cell-box-regions")
).table()


def testEveryPropertyOfAComputedStyleIsStated() -> None:
    computed = boxedHeader.cellStyleComputed("A1")
    assert None not in [getattr(computed, each.fieldName) for each in CellStyleProperty]


def testACellWithNoStyleOfItsOwnShowsItsSections() -> None:
    computed = boxedHeader.cellStyleComputed("A1")
    assert boxedHeader.cell("A1").cellStyle is None
    assert isinstance(computed.background, Color)
    assert computed == CellStyle(
        background=computed.background, padding=Decimal(4),
        verticalAlign=CellStyleVerticalAlign.TOP, textWrap=CellStyleTextWrap.WRAP,
    )


def testAPropertyACellStatesPrevailsOverItsSections() -> None:
    assert boxedHeader.cellStyleComputed("B1").background == FillNone()
    assert boxedHeader.cell("B1").cellStyle == CellStyle(background=FillNone())


def testAHeaderAndABodyCellComputeTheirOwnSectionsFill() -> None:
    header, body = (boxedHeader.cellStyleComputed(each) for each in ("C1", "A2"))
    assert isinstance(header.background, Color)
    assert body.background == FillNone()


def testAComputedStyleTakesItsFillFromTheBand() -> None:
    table = pybers.open(findDocumentPath("102b-bands-on")).table("Sheet 1::Table 1")
    for address in ("C4", "C8", "B4"):
        computed = table.cellStyleComputed(address)
        assert computed.background == table.cellFillComputed(address)


@pytest.mark.parametrize("address", ["C3", "C4", "D5"])
def testACoveredCellComputesWhatItsMergesAnchorDoes(address: str) -> None:
    table = pybers.open(findDocumentPath("104b-bands-merged-on")).table()
    merge = table.mergeFind(address)
    assert merge is not None
    assert table.cellStyleComputed(address) == table.cellStyleComputed(merge.anchor)


def testACreatedTableComputesItsOwnDefaultRatherThanNumbers() -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("T", rows=3, cols=3)
    assert table.cellStyleComputed("B2").textWrap is CellStyleTextWrap.NOWRAP


def testAnUpdateChangesTheComputedPropertyAndLeavesTheRest() -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("T", rows=3, cols=3)
    before = table.cellStyleComputed("B2")
    document.cellStyleUpdate("Sheet 1::T::B2", CellStyle(padding=Decimal(12)))
    assert table.cellStyleComputed("B2") == dataclasses.replace(
        before, padding=Decimal(12)
    )
    assert table.cell("B2").cellStyle == CellStyle(padding=Decimal(12))
