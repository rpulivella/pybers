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
def test_cell_reports_what_its_own_style_states(
    address: str, expected: CellStyle
) -> None:
    assert readBoxCells()[address].cellStyle == expected


@pytest.mark.parametrize("address", ["A1", "G1", "H1"])
def test_cell_with_no_cell_style_reads_none(address: str) -> None:
    assert readBoxCells()[address].cellStyle is None


def test_style_present_and_default_differs_from_no_style() -> None:
    archive = tst.CellStyleArchive()
    archive.cell_properties.padding.SetInParent()
    archive.cell_properties.vertical_alignment = 0
    assert readCellStyle(archive) == CellStyle(
        padding=Decimal(0), verticalAlign=CellStyleVerticalAlign.TOP
    )
    assert readCellStyle(tst.CellStyleArchive()) == CellStyle()


def test_cells_naming_one_archive_share_one_object() -> None:
    cells = readBoxCells()
    assert cells["B1"].cellStyle is cells["I1"].cellStyle is cells["J1"].cellStyle


def test_shared_cell_style_cannot_be_edited_through_one_cell() -> None:
    style = readBoxCells()["B1"].cellStyle
    with pytest.raises(dataclasses.FrozenInstanceError):
        style.padding = Decimal(8)  # type: ignore[misc]


def test_uneven_imported_padding_reads_each_side() -> None:
    archive = tst.CellStyleArchive()
    padding = archive.cell_properties.padding
    padding.left, padding.right, padding.bottom = 2, 2, 2
    sides = (Decimal(0), Decimal(2), Decimal(2), Decimal(2))
    assert readCellStyle(archive).padding == sides


@pytest.mark.parametrize(("field", "expected"), [
    ("gradient", FillGradient()),
    ("image", FillImage()),
])
def test_fill_other_than_color_reads_by_its_type(field: str, expected: object) -> None:
    archive = tsd.FillArchive()
    getattr(archive, field).SetInParent()
    assert readFill(archive) == expected


def test_empty_fill_reads_as_no_fill() -> None:
    assert readFill(tsd.FillArchive()) == FillNone()


@pytest.mark.parametrize("stored", [3, 9])
def test_vertical_alignment_a_cell_never_takes_refuses(stored: int) -> None:
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
def test_cell_style_text_form_states_each_property_as_css(
    cellStyle: CellStyle, text: str
) -> None:
    assert pybers.formatCellStyle(cellStyle) == text
