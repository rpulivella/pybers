#!/usr/bin/env python3
"""\
A table's lines, read from its table style and set as Numbers' controls set them.

`100-lines-base` holds one table per Gridlines and Table Outline control, and
`100b-lines` and `101b-outline` hold what each control wrote. Setting the same line
with pybers must write the variation Numbers wrote, overriding exactly its fields.

UPDATES
2026-11-18  `readOverrides` moved to `conftest.py`, which the band tests share, for
            PYB-267.
2026-11-17  Written for PYB-266.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/17"

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from conftest import findDocumentPath, readOverrides
from pybers import CellBorderSide, Color, Stroke, StrokeDash, StrokeSolid
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from pybers._persistence.container import readPackage, writePackage
from pybers._persistence.index import ArchiveIndex, findRoot
from pybers.table.tablestyle import (
    TableLine,
    TableStyle,
    TableStyleError,
    blankTableStyle,
    resetTableStyle,
)
from pybers.table.tablestyletext import formatTableStyle, parseTableStyle

dashed = Stroke(
    width=Decimal("0.35"), color=Color.black,
    pattern=StrokeDash(lengths=(Decimal(2), Decimal(2))),
)


def readTableStyleOf(stem: str, table: str) -> TableStyle:
    """Return the lines one table of a test document draws."""
    return pybers.open(findDocumentPath(stem)).table(table).tableStyle


@pytest.mark.parametrize(("table", "field"), [
    ("Body horizontal", "bodyHorizontalGridlines"),
    ("Body vertical", "bodyVerticalGridlines"),
    ("Header columns horizontal", "headerColumnsHorizontalGridlines"),
    ("Header rows vertical", "headerRowsVerticalGridlines"),
    ("Footer rows vertical", "footerRowsVerticalGridlines"),
])
def test_each_gridline_button_hides_its_one_line(table: str, field: str) -> None:
    measured = readTableStyleOf("100b-lines", table)
    # Numbers shows a table's title once a second table joins its sheet.
    assert measured == replace(
        blankTableStyle, tableTitle=True,
        **{field: replace(getattr(blankTableStyle, field), visible=False)},
    )


def test_an_outline_style_reads_as_the_outline_stroke() -> None:
    assert readTableStyleOf("100b-lines", "Outline dashed").tableOutline == (
        TableLine(True, dashed)
    )


def test_outline_none_hides_the_outline_and_keeps_its_stroke() -> None:
    outline = readTableStyleOf("101b-outline", "Outline then None").tableOutline
    assert not outline.visible
    assert isinstance(outline.stroke, Stroke) and outline.stroke.width == 2


def test_outline_table_title_reads_from_the_table() -> None:
    assert readTableStyleOf("100b-lines", "Outline title").tableOutlineTitle


@pytest.mark.parametrize(("table", "change"), [
    ("Body horizontal", {"bodyHorizontalGridlines": TableLine(
        False, blankTableStyle.bodyHorizontalGridlines.stroke)}),
    ("Footer rows vertical", {"footerRowsVerticalGridlines": TableLine(
        False, blankTableStyle.footerRowsVerticalGridlines.stroke)}),
    ("Outline dashed", {"tableOutline": TableLine(True, dashed)}),
])
def test_a_line_set_writes_the_variation_numbers_wrote(
    table: str, change: dict[str, TableLine], tmp_path: Path
) -> None:
    document = pybers.open(findDocumentPath("100-lines-base"))
    assert document.table(table).tableStyleSet(**change).changed
    target = tmp_path / "set.numbers"
    document.save(target)
    assert readOverrides(target, table) == readOverrides(
        findDocumentPath("100b-lines"), table
    )
    assert pybers.open(target).table(table).tableStyle == (
        readTableStyleOf("100b-lines", table)
    )


def test_setting_what_a_table_draws_changes_and_writes_nothing(tmp_path: Path) -> None:
    document = pybers.open(findDocumentPath("100b-lines"))
    table = document.table("Outline dashed")
    assert not table.tableStyleSet(table.tableStyle).changed
    target = tmp_path / "same.numbers"
    document.save(target)
    assert readOverrides(target, "Outline dashed") == readOverrides(
        findDocumentPath("100b-lines"), "Outline dashed"
    )


def test_a_style_equal_to_the_root_names_the_root(tmp_path: Path) -> None:
    document = pybers.open(findDocumentPath("100b-lines"))
    document.table("Outline dashed").tableStyleSet(blankTableStyle)
    target = tmp_path / "default.numbers"
    document.save(target)
    assert readOverrides(target, "Outline dashed") == []


def test_a_created_table_starts_from_the_reset_and_keeps_what_is_set(
    tmp_path: Path,
) -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Lines", rows=3, cols=3)
    assert table.tableStyle == resetTableStyle
    table.tableStyleSet(tableOutline=TableLine(True, dashed), tableOutlineTitle=True)
    expected = table.tableStyle
    target = tmp_path / "created.numbers"
    document.save(target)
    assert pybers.open(target).table("Lines").tableStyle == expected


@pytest.mark.parametrize(("lines", "message"), [
    ({"tableBorder": TableLine(True, dashed)}, "is not a table style field"),
    ({"tableOutline": "1pt solid black"}, "is not a TableLine"),
    ({"tableOutlineTitle": "yes"}, "'yes' is not a bool"),
])
def test_a_line_pybers_cannot_hold_is_refused(
    lines: dict[str, object], message: str
) -> None:
    table = pybers.create("en_US").sheet().tableAdd("Lines", rows=1, cols=1)
    with pytest.raises(TableStyleError, match=message):
        table.tableStyleSet(**lines)  # type: ignore[arg-type]
    assert table.tableStyle == resetTableStyle


def test_the_text_form_reads_back_what_it_prints() -> None:
    measured = readTableStyleOf("101b-outline", "Outline then None")
    text = "; ".join(formatTableStyle(measured))
    assert parseTableStyle(text, blankTableStyle) == measured


def test_a_longhand_changes_one_part_of_a_line() -> None:
    red = Color.parse("#ff0000ff")
    changed = parseTableStyle("table-outline-color: #ff0000ff", blankTableStyle)
    outline = changed.tableOutline
    assert isinstance(outline.stroke, Stroke)
    assert outline.stroke == replace(blankTableStyle.tableOutline.stroke, color=red)


@pytest.mark.parametrize(("text", "message"), [
    (
        "table-border: none",
        "is not a table style property. The closest is table-outline",
    ),
    ("table-outline: thick", "a width, a style and a color"),
    (
        "table-outline: 1pt brush black",
        "'brush' is not a line style. The choices are solid, dashed, dotted and none",
    ),
    ("table-outline-title: maybe", "'maybe' is not a table-outline-title value"),
    ("table-outline: none; table-outline: none", "table-outline is stated twice"),
])
def test_text_a_table_style_lacks_is_refused(text: str, message: str) -> None:
    with pytest.raises(TableStyleError, match=message):
        parseTableStyle(text, blankTableStyle)


separator = Stroke(width=Decimal("0.75"), color=Color.black, pattern=StrokeSolid())
gridline = Stroke(width=Decimal("0.35"), color=Color.black, pattern=StrokeSolid())


@pytest.mark.parametrize(("address", "side", "drawn"), [
    ("B2", CellBorderSide.BOTTOM, gridline),
    ("A2", CellBorderSide.BOTTOM, gridline),
    ("B1", CellBorderSide.BOTTOM, separator),
    ("B3", CellBorderSide.BOTTOM, separator),
    ("A2", CellBorderSide.RIGHT, separator),
    ("A1", CellBorderSide.RIGHT, gridline),
    ("A4", CellBorderSide.RIGHT, gridline),
    ("B1", CellBorderSide.RIGHT, gridline),
    ("B4", CellBorderSide.RIGHT, gridline),
    ("C2", CellBorderSide.RIGHT, gridline),
    ("B2", CellBorderSide.RIGHT, gridline),
])
def test_an_edge_with_no_border_shows_the_table_line_for_its_section(
    address: str, side: CellBorderSide, drawn: Stroke
) -> None:
    table = pybers.open(findDocumentPath("100-lines-base")).table("Untouched")
    assert table.cellBorderComputed(address, side) == drawn


@pytest.mark.parametrize(("table", "address", "side"), [
    ("Body horizontal", "B2", CellBorderSide.BOTTOM),
    ("Header columns horizontal", "A2", CellBorderSide.BOTTOM),
    ("Header rows vertical", "B1", CellBorderSide.RIGHT),
    ("Footer rows vertical", "B4", CellBorderSide.RIGHT),
    ("Header rows vertical", "A1", CellBorderSide.RIGHT),
    ("Footer rows vertical", "A4", CellBorderSide.RIGHT),
    ("Body vertical", "B2", CellBorderSide.RIGHT),
])
def test_a_hidden_table_line_shows_nothing_at_its_section(
    table: str, address: str, side: CellBorderSide
) -> None:
    measured = pybers.open(findDocumentPath("100b-lines")).table(table)
    assert measured.cellBorderComputed(address, side) is None


def test_of_two_facing_strokes_the_later_shows() -> None:
    table = pybers.open(findDocumentPath("63d-fill-border-base")).table("Table 1")
    shown = table.cellBorderComputed("C3", CellBorderSide.RIGHT)
    assert isinstance(shown, Stroke) and shown.width == 5


def test_a_hidden_border_shows_nothing_over_the_gridline() -> None:
    table = pybers.open(findDocumentPath("57-structure-refusals-base")).table(
        "Borders"
    )
    assert table.cellBorderComputed("A1", CellBorderSide.BOTTOM) is None


def test_a_line_inside_a_merge_shows_nothing() -> None:
    table = pybers.open(findDocumentPath("22-merge-2x2")).table("Table 1")
    assert table.cellBorderComputed("A1", CellBorderSide.RIGHT) is None


deepBands: Path = (
    Path(__file__).resolve().parent / "golden"
    / "00-created-table-lines-deep-bands-by-pybers.numbers"
)
redLine = Stroke(
    width=Decimal(1), color=Color.parse("#ff0000ff"), pattern=StrokeSolid()
)


@pytest.mark.parametrize(("table", "address", "side"), [
    ("Header rows horizontal", "C1", CellBorderSide.BOTTOM),
    ("Header rows horizontal", "A1", CellBorderSide.BOTTOM),
    ("Header columns vertical", "A3", CellBorderSide.RIGHT),
    ("Footer rows horizontal", "C6", CellBorderSide.BOTTOM),
    ("Footer rows horizontal", "A6", CellBorderSide.BOTTOM),
])
def test_an_edge_between_two_lines_of_a_band_shows_that_bands_line(
    table: str, address: str, side: CellBorderSide
) -> None:
    lined = pybers.open(deepBands).table(table)
    assert lined.cellBorderComputed(address, side) == redLine


@pytest.mark.parametrize("field", [
    "headerRowsHorizontalGridlines", "headerColumnsVerticalGridlines",
    "footerRowsHorizontalGridlines",
])
def test_a_line_no_control_hides_takes_a_stroke_but_not_none(field: str) -> None:
    table = pybers.create("en_US").sheet().tableAdd("Lines", rows=4, cols=4)
    with pytest.raises(TableStyleError, match="cannot be hidden, since they show"):
        table.tableStyleSet(**{field: TableLine(False, gridline)})
    assert table.tableStyleSet(**{field: TableLine(True, redLine)}).changed


def test_a_document_whose_theme_has_no_table_preset_still_opens(
    tmp_path: Path,
) -> None:
    source = tmp_path / "created.numbers"
    pybers.create("en_US").save(source)
    package = readPackage(source)
    index = ArchiveIndex(package)
    root = findRoot(index)
    theme = index.resolve(root.theme, tn.ThemeArchive)
    presets = theme.super.Extensions[tstStyles.ThemePresetsArchive.extension]
    del presets.table_style_presets[:]
    index.archiveWrite(root.theme.identifier, theme)
    stripped = tmp_path / "stripped.numbers"
    writePackage(package, stripped)
    added = pybers.open(stripped).sheet().tableAdd("Lines", rows=1, cols=1)
    assert added.tableStyle == resetTableStyle
