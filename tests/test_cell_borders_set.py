#!/usr/bin/env python3
"""\
Borders drawn on a block of cells at a position, checked against what Numbers drew.

`100-lines-base` is the document each block in `100b-lines` was bordered from, so
drawing the same position with pybers gives each cell of the block the side Numbers
gave it. pybers also writes the facing side of a neighbor outside the block, which
Numbers leaves to `order`, so a block's own cells are what the two share.

UPDATES
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

from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from conftest import findDocumentPath
from pybers import (
    CellBorder,
    CellBorderPosition,
    CellBorders,
    CellBorderStyle,
    Color,
    ColorSpace,
    Stroke,
    StrokeEmpty,
    StrokeSolid,
)
from pybers.errors import WriteError
from pybers.selection.matching import SelectionError

gridline = Stroke(width=Decimal("0.35"), color=Color.black, pattern=StrokeSolid())
positionBlocks: dict[CellBorderPosition, tuple[str, str]] = {
    CellBorderPosition.OUTER: ("Positions Top", "A1:B2"),
    CellBorderPosition.BETWEEN: ("Positions Top", "C1:D2"),
    CellBorderPosition.ALL: ("Positions Top", "E1:F2"),
    CellBorderPosition.OUTER_LEFT: ("Positions Middle", "A1:B2"),
    CellBorderPosition.BETWEEN_COLUMNS: ("Positions Middle", "C1:D2"),
    CellBorderPosition.OUTER_RIGHT: ("Positions Middle", "E1:F2"),
    CellBorderPosition.OUTER_TOP: ("Positions Bottom", "A1:B2"),
    CellBorderPosition.BETWEEN_ROWS: ("Positions Bottom", "C1:D2"),
    CellBorderPosition.OUTER_BOTTOM: ("Positions Bottom", "E1:F2"),
}


def readOwnStrokes(borders: CellBorders) -> tuple[Stroke | None, ...]:
    """Return the stroke a cell stores on each side, in CSS order."""
    return tuple(
        None if side is None else side.stroke
        for side in (borders.top, borders.right, borders.bottom, borders.left)
    )


def readBlockStrokes(
    table: pybers.Table, block: str
) -> list[tuple[Stroke | None, ...]]:
    """Return each cell of a block's own strokes, in row order."""
    return [
        readOwnStrokes(table.cell(address).borders)
        for address in pybers.CellRange.parse(block)
    ]


@pytest.mark.parametrize("position", list(CellBorderPosition))
def test_each_position_draws_the_sides_numbers_drew(
    position: CellBorderPosition,
) -> None:
    tableName, block = positionBlocks[position]
    document = pybers.open(findDocumentPath("100-lines-base"))
    document.cellBordersSet(f"::{tableName}::{block}", position)
    measured = pybers.open(findDocumentPath("100b-lines")).sheet(1).table(tableName)
    assert readBlockStrokes(document.sheet(1).table(tableName), block) == (
        readBlockStrokes(measured, block)
    )


@pytest.mark.parametrize(
    ("address", "style", "width", "color"),
    [
        ("B1", CellBorderStyle.DASHED, 1, None),
        ("D1", CellBorderStyle.DOTTED, 1, None),
        ("E1", CellBorderStyle.DOTTED, 5, None),
        ("F1", CellBorderStyle.SOLID, 1,
         Color(ColorSpace.SRGB, (1, 0, 0), Decimal("0.5"))),
    ],
)
def test_each_line_style_stores_the_stroke_numbers_stored(
    address: str, style: CellBorderStyle, width: int, color: Color | None
) -> None:
    document = pybers.open(findDocumentPath("100-lines-base"))
    document.cellBordersSet(
        f"::Table 1::{address}", CellBorderPosition.OUTER, style=style, width=width,
        color=color,
    )
    measured = pybers.open(findDocumentPath("100b-lines")).table("Table 1")
    assert readOwnStrokes(document.table("Table 1").cell(address).borders) == (
        readOwnStrokes(measured.cell(address).borders)
    )


def test_an_outer_side_is_written_to_the_neighbor_facing_it() -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Lines", rows=3, cols=3)
    document.cellBordersSet("::Lines::B2", CellBorderPosition.OUTER)
    drawn = CellBorder(gridline, gridline, prevails=True)
    assert table.cell("A2").borders.right == drawn
    assert table.cell("B1").borders.bottom == drawn


def test_hidden_states_an_empty_stroke_and_none_removes_both_sides() -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Lines", rows=2, cols=2)
    document.cellBordersSet("::Lines::A1:B2", CellBorderPosition.ALL,
                            style=CellBorderStyle.HIDDEN)
    hidden = table.cell("A1").borders.right
    assert hidden is not None and hidden.stroke is not None
    assert isinstance(hidden.stroke.pattern, StrokeEmpty)
    document.cellBordersSet("::Lines::A1:B2", CellBorderPosition.ALL, style=None)
    assert all(
        table.cell(address).borders == CellBorders()
        for address in ("A1", "A2", "B1", "B2")
    )


def test_drawing_what_a_block_already_holds_reports_no_change() -> None:
    document = pybers.create("en_US")
    document.sheet().tableAdd("Lines", rows=2, cols=2)
    assert document.cellBordersSet("::Lines::A1:B2", CellBorderPosition.ALL).changed
    table = document.table("Lines")
    order = table._borders.maxOrder
    again = document.cellBordersSet("::Lines::A1:B2", CellBorderPosition.ALL)
    assert not again.changed
    assert table._borders.maxOrder == order


def test_a_later_border_prevails_by_its_order() -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Lines", rows=1, cols=2)
    first = table._borders.maxOrder
    document.cellBordersSet("::Lines::A1:B1", CellBorderPosition.ALL)
    assert table._borders.maxOrder == first + 1
    assert first == 2


def test_borders_drawn_on_a_created_table_survive_a_save(tmp_path: Path) -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Lines", rows=3, cols=3)
    document.cellBordersSet("::Lines::A1:B2", CellBorderPosition.OUTER,
                            style=CellBorderStyle.DASHED, width=2)
    expected = {cell.address: cell.borders for cell in table.gridIterate()}
    target = tmp_path / "lines.numbers"
    document.save(target)
    reread = pybers.open(target).table("Lines")
    assert {cell.address: cell.borders for cell in reread.gridIterate()} == expected


@pytest.mark.parametrize(
    ("selector", "arguments", "error", "message"),
    [
        ("::Lines::A1", {"position": "outline"}, WriteError, "position is one of"),
        ("::Lines::A1", {"style": "brush"}, WriteError, "style is one of"),
        ("::Lines::A1", {"style": CellBorderStyle.HIDDEN, "width": 1}, WriteError,
         "draws no line, so it takes no width"),
        ("::Lines::A1", {"style": None, "color": Color.black}, WriteError,
         "removes the borders, so it takes no width"),
        ("::Lines::A1", {"width": True}, WriteError, "width is a Decimal or an int"),
        ("::Lines::A1", {"width": -1}, WriteError, "cannot be negative"),
        ("::Lines::A1, ::Lines::B2", {}, SelectionError, "one block of cells"),
        ("*::Lines", {}, SelectionError, "one block of cells"),
    ],
)
def test_a_border_numbers_cannot_draw_is_refused_before_anything_changes(
    selector: str, arguments: dict[str, object], error: type[Exception], message: str
) -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Lines", rows=2, cols=2)
    stated: dict[str, object] = {"position": CellBorderPosition.OUTER} | arguments
    with pytest.raises(error, match=message):
        document.cellBordersSet(selector, **stated)  # type: ignore[arg-type]
    assert not table._borders.edges
