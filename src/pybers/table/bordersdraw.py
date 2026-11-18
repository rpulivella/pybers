#!/usr/bin/env python3
"""\
A table's borders drawn at a position of a block, and the line each edge displays.

The operations on a table that its store of strokes serves: drawing one block, a
merge drawn whole, the line an edge shows, and a cell's borders as `pybers show`
prints them. See findings-06-styles.md.

UPDATES
2026-11-17  Split out of `borders` for PYB-266, keeping each module within its limit.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/17"

from typing import TYPE_CHECKING

from pybers.absence import MIXED
from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import CellAddress
from pybers.style.strokes import Stroke, StrokeEmpty, formatStroke
from pybers.table.borders import (
    CellBorderPosition,
    CellBorders,
    CellBorderSide,
    facingSides,
)
from pybers.table.tablestyle import findTableLine

if TYPE_CHECKING:
    from pybers.table.cell import Cell
    from pybers.table.cells import Table


def formatSpanStroke(stroke: Stroke | MIXED) -> str:
    """Return a side's stroke as CSS writes it, or `mixed` where positions differ."""
    return "mixed" if stroke is MIXED else formatStroke(stroke)


def formatCellBorders(cell: Cell) -> str:
    """Return the sides a cell stores as CSS, a neighbor's other stroke noted.

    `border: 1pt dashed #000000ff` where all four sides agree, else a longhand per
    side, `border-top: 1pt dashed #000000ff; border-left: hidden`, a side storing
    nothing left out.
    """
    borders = {side: getattr(cell.borders, side.value) for side in CellBorderSide}
    strokes = {
        None if border is None else border.stroke for border in borders.values()
    }
    shorthand = len(strokes) == 1 and None not in strokes
    declarations = []
    notes = []
    for side, border in borders.items():
        if border is None or border.stroke is None:
            continue
        if not shorthand:
            declarations.append(f"border-{side}: {formatSpanStroke(border.stroke)}")
        if border.disagrees and border.neighborStroke is not None:
            _, down, across = facingSides[side]
            neighbor = CellAddress(cell.address.row + down, cell.address.col + across)
            drawn = formatSpanStroke(border.neighborStroke)
            notes.append(
                f"({neighbor} draws {drawn}"
                + (f" on the {side})" if shorthand else ")")
            )
            if not shorthand:
                declarations[-1] += f" {notes.pop()}"
    if shorthand:
        stroke = strokes.pop()
        assert stroke is not None
        declarations.append(" ".join([f"border: {formatSpanStroke(stroke)}", *notes]))
    return "; ".join(declarations)


def listDrawnSides(
    position: CellBorderPosition, top: bool, bottom: bool, left: bool, right: bool
) -> list[CellBorderSide]:
    """Return the sides a position draws of a cell on the block's given outer lines.

    An inner line is drawn once, as the bottom or right of the cell before it, and
    `edgesDraw` gives the facing cell its side.
    """
    outer = {
        CellBorderSide.TOP: top, CellBorderSide.BOTTOM: bottom,
        CellBorderSide.LEFT: left, CellBorderSide.RIGHT: right,
    }
    between = {CellBorderSide.BOTTOM: not bottom, CellBorderSide.RIGHT: not right}
    match position:
        case CellBorderPosition.OUTER_TOP | CellBorderPosition.OUTER_RIGHT | (
            CellBorderPosition.OUTER_BOTTOM
        ) | CellBorderPosition.OUTER_LEFT:
            side = CellBorderSide(position.value.removeprefix("outer-"))
            return [side] if outer[side] else []
        case CellBorderPosition.OUTER:
            return [side for side, edge in outer.items() if edge]
        case CellBorderPosition.BETWEEN_ROWS:
            return [CellBorderSide.BOTTOM] if between[CellBorderSide.BOTTOM] else []
        case CellBorderPosition.BETWEEN_COLUMNS:
            return [CellBorderSide.RIGHT] if between[CellBorderSide.RIGHT] else []
        case CellBorderPosition.BETWEEN:
            return [side for side, edge in between.items() if edge]
        case CellBorderPosition.ALL:
            return list(CellBorderSide)


def findBlockRing(table: Table, block: CellRange) -> list[CellAddress]:
    """Return a block's cells and every cell in the grid beside it, in row order."""
    top, left, bottom, right = (
        block.startRow, block.startCol, block.endRow, block.endCol,
    )
    assert top is not None and left is not None
    assert bottom is not None and right is not None
    return [
        CellAddress(row, column)
        for row in range(max(1, top - 1), min(table.rowCount, bottom + 1) + 1)
        for column in range(max(1, left - 1), min(table.colCount, right + 1) + 1)
        if (top <= row <= bottom) or (left <= column <= right)
    ]


def isMergeInterior(
    table: Table, row: int, column: int, side: CellBorderSide
) -> bool:
    """Report whether a side lies between two positions of one merge."""
    _, down, across = facingSides[side]
    # A side on the table's own edge has no position beyond it.
    if row + down < 1 or column + across < 1:
        return False
    merge = table.mergeCovering(CellAddress(row, column))
    return merge is not None and merge.covers(
        CellAddress(row + down, column + across)
    )


def findMergedBlock(table: Table, block: CellRange) -> CellRange:
    """Return a block widened until it covers whole every merge it touches.

    Numbers widens a selection so, and a merged cell is bordered whole.
    """
    top, left, bottom, right = (
        block.startRow, block.startCol, block.endRow, block.endCol,
    )
    assert top is not None and left is not None
    assert bottom is not None and right is not None
    widened = True
    while widened:
        widened = False
        for merge in table.mergeRanges:
            extent = merge.extent
            mergeTop, mergeLeft = extent.startRow, extent.startCol
            mergeBottom, mergeRight = extent.endRow, extent.endCol
            assert mergeTop is not None and mergeLeft is not None
            assert mergeBottom is not None and mergeRight is not None
            touches = (mergeTop <= bottom and top <= mergeBottom
                       and mergeLeft <= right and left <= mergeRight)
            covered = (top <= mergeTop and mergeBottom <= bottom
                       and left <= mergeLeft and mergeRight <= right)
            if touches and not covered:
                top, left = min(top, mergeTop), min(left, mergeLeft)
                bottom, right = max(bottom, mergeBottom), max(right, mergeRight)
                widened = True
    return CellRange.fromReferences(CellAddress(top, left), CellAddress(bottom, right))


def applyBlockBorders(
    table: Table, block: CellRange, position: CellBorderPosition, stroke: Stroke | None
) -> list[CellAddress]:
    """Draw a stroke at a position of a bounded block, or remove it with None.

    Returns every cell whose borders may have changed, the block's and each
    neighbor facing it, in row order, or nothing when nothing changed.
    """
    top, left, bottom, right = (
        block.startRow, block.startCol, block.endRow, block.endCol,
    )
    assert top is not None and left is not None
    assert bottom is not None and right is not None
    sides = [
        (row, column, side)
        for row in range(top, bottom + 1) for column in range(left, right + 1)
        for side in listDrawnSides(
            position, row == top, row == bottom, column == left, column == right
        )
        # A line inside a merge is never drawn, as Numbers draws a merge whole.
        if not isMergeInterior(table, row, column, side)
    ]
    if not table._borders.edgesDraw(
        table._rowIdentities, table._columnIdentities, sides, stroke
    ):
        return []
    touched = {
        CellAddress(row + down, column + across)
        for row, column, side in sides
        for down, across in ((0, 0), facingSides[side][1:])
        if 1 <= row + down <= table.rowCount and 1 <= column + across <= table.colCount
    }
    touched.update(
        CellAddress(row, column)
        for row in range(top, bottom + 1) for column in range(left, right + 1)
    )
    return sorted(touched, key=lambda address: (address.row, address.col))


def findShownLine(
    table: Table, cell: CellAddress, side: CellBorderSide
) -> Stroke | MIXED | None:
    """Return the line one side of a cell displays, or None where it displays none.

    A stored stroke prevails, the later of two that disagree, and a hidden one draws
    nothing; else the table's own line for that edge, while it shows.
    """
    if isMergeInterior(table, cell.row, cell.col, side):
        return None
    drawn = table._borders.edgeShownFind(
        table._rowIdentities, table._columnIdentities, cell, side
    )
    if drawn is not None:
        return None if isinstance(drawn.pattern, StrokeEmpty) else drawn
    # The line before the edge: a top or left edge belongs to the one before.
    line = findTableLine(
        table.tableStyle, table.headers, table.rowCount, table.colCount,
        cell.row - (side is CellBorderSide.TOP),
        cell.col - (side is CellBorderSide.LEFT),
        side in (CellBorderSide.TOP, CellBorderSide.BOTTOM),
    )
    return line.stroke if line.visible else None


def findCellBordersByPosition(table: Table) -> dict[CellAddress, CellBorders]:
    """Return the borders of every cell storing or facing a stroke, by address.

    Keyed by position rather than line identity, which a table read from its JSON
    form does not share, so two tables drawing alike compare equal.
    """
    rows = {identity: at for at, identity in enumerate(table._rowIdentities, 1)}
    columns = {
        identity: at for at, identity in enumerate(table._columnIdentities, 1)
    }
    held: set[CellAddress] = set()
    for rowIdentity, columnIdentity, side in table._borders.edges:
        row, column = rows.get(rowIdentity), columns.get(columnIdentity)
        if row is None or column is None:
            continue
        _, down, across = facingSides[side]
        held.update(
            CellAddress(row + step * down, column + step * across)
            for step in (0, 1)
            if 1 <= row + step * down <= table.rowCount
            and 1 <= column + step * across <= table.colCount
        )
    return {
        address: table._bordersRead(address)
        for address in held if table.addressable(address)
    }


__all__ = [
    "applyBlockBorders", "findBlockRing", "findCellBordersByPosition",
    "findMergedBlock", "findShownLine", "formatCellBorders", "formatSpanStroke",
    "isMergeInterior", "listDrawnSides",
]
