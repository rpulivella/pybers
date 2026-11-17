#!/usr/bin/env python3
"""\
A cell's four borders, read from the file and from the model between edits.

Measured against `100b-lines`, whose Border buttons write both facing sides of an
inner line and one side of an outer one, and `63d-fill-border-base`, where C3 and D3
store disagreeing strokes on the edge they share.

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

import pybers
from conftest import findDocumentPath
from pybers import (
    CellBorder,
    CellBorders,
    Color,
    FormulaReferenceRelocation,
    Stroke,
    StrokeSolid,
)

gridline = Stroke(width=Decimal("0.35"), color=Color.black, pattern=StrokeSolid())


def isStrokeless(borders: CellBorders) -> bool:
    """Report whether a cell stores no stroke of its own on any side."""
    return all(
        side is None or side.stroke is None
        for side in (borders.top, borders.right, borders.bottom, borders.left)
    )


def openTable(stem: str, table: str = "Table 1") -> pybers.Table:
    """Return one table of a document read from the test documents."""
    return pybers.open(findDocumentPath(stem)).sheet(1).table(table)


def test_a_cell_with_no_border_reads_none_on_every_side() -> None:
    assert openTable("100b-lines").cell("G2").borders == CellBorders()


def test_an_outer_side_is_stored_on_the_selected_cell_alone() -> None:
    borders = openTable("100b-lines", "Positions Top").cell("A1").borders
    assert borders.left == CellBorder(gridline, None)
    assert borders.top == CellBorder(gridline, None)
    assert borders.right is None


def test_an_inner_line_is_stored_on_both_facing_sides() -> None:
    borders = openTable("100b-lines", "Positions Top").cell("C1").borders
    assert borders.right == CellBorder(gridline, gridline)
    assert not borders.right.disagrees


def test_two_facing_strokes_that_differ_are_reported() -> None:
    right = openTable("63d-fill-border-base").cell("C3").borders.right
    assert right is not None
    assert right.stroke is not None and right.stroke.width == 3
    assert right.neighborStroke is not None and right.neighborStroke.width == 5
    assert right.disagrees


def test_a_row_added_above_a_border_moves_it_before_any_save() -> None:
    table = openTable("61-move-styles-base")
    before = table.cell("C3").borders
    table.rowAdd(2)
    assert table.cell("C4").borders == before
    assert isStrokeless(table.cell("C3").borders)


def test_a_removed_row_takes_its_borders_with_it() -> None:
    table = openTable("61-move-styles-base")
    table.rowRemove(3)
    assert all(isStrokeless(cell.borders) for cell in table.gridIterate())


def test_a_moved_block_carries_its_borders() -> None:
    table = openTable("61-move-styles-base")
    before = table.cell("C3").borders
    table.cellsMove(
        "C3", "G9", references=FormulaReferenceRelocation.PRESERVE_NAMED_CELL
    )
    assert table.cell("G9").borders == before
    assert isStrokeless(table.cell("C3").borders)


def test_a_copied_block_draws_its_borders_at_both() -> None:
    table = openTable("61-move-styles-base")
    before = table.cell("C3").borders
    table.cellsCopy(
        "C3", "G9", references=FormulaReferenceRelocation.PRESERVE_NAMED_CELL
    )
    assert table.cell("G9").borders == before == table.cell("C3").borders


def test_borders_read_the_same_after_a_save(tmp_path: Path) -> None:
    document = pybers.open(findDocumentPath("61-move-styles-base"))
    table = document.sheet(1).table("Table 1")
    table.rowAdd(2)
    table.cellsCopy(
        "C4", "G9", references=FormulaReferenceRelocation.PRESERVE_NAMED_CELL
    )
    expected = {cell.address: cell.borders for cell in table.gridIterate()}
    target = tmp_path / "edited.numbers"
    document.save(target)
    reread = pybers.open(target).sheet(1).table("Table 1")
    assert {cell.address: cell.borders for cell in reread.gridIterate()} == expected
