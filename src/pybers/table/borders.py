#!/usr/bin/env python3
"""\
A cell's borders, and the table's store of every stroke drawn on a cell's side.

Numbers keeps four strokes per cell and no position, so the store holds one stroke
per side of a cell, keyed by the identities of its row and column, which move with
their lines. Of two facing strokes that disagree, Numbers draws the one with the
higher `order`. See findings-06-styles.md and findings-03-structure.md.

UPDATES
2026-11-17  Written for PYB-266, taking over the rules `_strokes` applied to the
            archive at save time.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/17"

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from pybers.addressing.reference import CellAddress
from pybers.color.colors import Color
from pybers.style.strokes import (
    Stroke,
    StrokeCap,
    StrokeDash,
    StrokeEmpty,
    StrokeJoin,
    StrokeSolid,
)

if TYPE_CHECKING:
    from pybers.addressing.ranges import CellRange
    from pybers.table.cells import Table

# What Numbers draws for a line style given alone, the gridline's own stroke.
borderWidthOffered: Decimal = Decimal("0.35")
# The order Numbers' first save leaves a table at, so its first border draws at 3.
borderOrderInitial: int = 2


class CellBorderSide(StrEnum):
    """One side of a cell, in CSS order."""

    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    LEFT = "left"


# The side of the neighboring cell that faces each side, and the step to reach it.
facingSides: frozendict[CellBorderSide, tuple[CellBorderSide, int, int]] = frozendict({
    CellBorderSide.TOP: (CellBorderSide.BOTTOM, -1, 0),
    CellBorderSide.RIGHT: (CellBorderSide.LEFT, 0, 1),
    CellBorderSide.BOTTOM: (CellBorderSide.TOP, 1, 0),
    CellBorderSide.LEFT: (CellBorderSide.RIGHT, 0, -1),
})
# The sides a row's own layer holds, the rest running along a column.
rowSides: frozenset[CellBorderSide] = frozenset({
    CellBorderSide.TOP, CellBorderSide.BOTTOM,
})

class CellBorderPosition(StrEnum):
    """The part of a block of cells a border draws, never stored."""

    ALL = "all"
    OUTER = "outer"
    OUTER_TOP = "outer-top"
    OUTER_RIGHT = "outer-right"
    OUTER_BOTTOM = "outer-bottom"
    OUTER_LEFT = "outer-left"
    BETWEEN = "between"
    BETWEEN_ROWS = "between-rows"
    BETWEEN_COLUMNS = "between-columns"


class CellBorderStyle(StrEnum):
    """A cell border's line, named as CSS names a table's border styles.

    `HIDDEN` draws nothing and hides the table's line there, as Numbers' No Border.
    """

    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    HIDDEN = "hidden"


def buildBorderStroke(
    style: CellBorderStyle, width: Decimal | int, color: Color
) -> Stroke:
    """Return the stroke Numbers 15.4 stores for a line style, as `100b-lines` shows."""
    match style:
        case CellBorderStyle.SOLID:
            return Stroke(width=Decimal(width), color=color, pattern=StrokeSolid())
        case CellBorderStyle.DASHED:
            return Stroke(
                width=Decimal(width), color=color,
                pattern=StrokeDash(lengths=(Decimal(2), Decimal(2))),
            )
        case CellBorderStyle.DOTTED:
            return Stroke(
                width=Decimal(width), color=color,
                pattern=StrokeDash(lengths=(Decimal("0.001"), Decimal(2))),
                cap=StrokeCap.ROUND, join=StrokeJoin.ROUND,
            )
        case CellBorderStyle.HIDDEN:
            return Stroke(width=Decimal(0), color=Color.black, pattern=StrokeEmpty())


def listDrawnSides(
    position: CellBorderPosition, top: bool, bottom: bool, left: bool, right: bool
) -> list[CellBorderSide]:
    """Return the sides a position draws of a cell, by the block lines it is on.

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


# A side of a cell, by the identity of its row and of its column.
type BorderEdgeKey = tuple[int, int, CellBorderSide]


@dataclass(frozen=True, slots=True)
class BorderEdge:
    """One stroke stored on one side of one cell, and the order it was drawn in.

    `stored` is the archive it was read from, so a brush or frame is carried.
    """

    stroke: Stroke
    order: int
    stored: bytes | None = None


@dataclass(frozen=True, slots=True)
class CellBorder:
    """A side of a cell: the stroke the cell stores, and the one its neighbor stores."""

    stroke: Stroke | None
    neighborStroke: Stroke | None

    @property
    def disagrees(self) -> bool:
        """Report whether both cells store a stroke here and the two differ."""
        return (
            self.stroke is not None and self.neighborStroke is not None
            and self.stroke != self.neighborStroke
        )


@dataclass(frozen=True, slots=True)
class CellBorders:
    """A cell's four sides in CSS order, each None where neither cell stores one."""

    top: CellBorder | None = None
    right: CellBorder | None = None
    bottom: CellBorder | None = None
    left: CellBorder | None = None


@dataclass(slots=True)
class TableBorders:
    """Every stroke a table stores on a side of a cell, and the highest order drawn."""

    edges: dict[BorderEdgeKey, BorderEdge] = field(default_factory=dict)
    maxOrder: int = borderOrderInitial

    def cellBordersRead(
        self, rowIdentities: Sequence[int], columnIdentities: Sequence[int],
        row: int, column: int,
    ) -> CellBorders:
        """Return the four sides of the cell at a row and column counted from one."""
        sides: dict[str, CellBorder | None] = {}
        for side, (facing, down, across) in facingSides.items():
            own = self.edges.get(
                (rowIdentities[row - 1], columnIdentities[column - 1], side)
            )
            neighborRow, neighborColumn = row + down, column + across
            neighbor = None
            if (1 <= neighborRow <= len(rowIdentities)
                    and 1 <= neighborColumn <= len(columnIdentities)):
                neighbor = self.edges.get((
                    rowIdentities[neighborRow - 1],
                    columnIdentities[neighborColumn - 1], facing,
                ))
            sides[side.value] = (
                None if own is None and neighbor is None else CellBorder(
                    None if own is None else own.stroke,
                    None if neighbor is None else neighbor.stroke,
                )
            )
        return CellBorders(**sides)

    def edgesDraw(
        self, rowIdentities: Sequence[int], columnIdentities: Sequence[int],
        sides: Iterable[tuple[int, int, CellBorderSide]], stroke: Stroke | None,
    ) -> bool:
        """Draw a stroke on each side named and the neighbor's side facing it.

        Rows and columns count from one, and None removes both. Every side takes
        one new order, so it prevails over anything drawn before. Returns whether
        anything changed, and changes nothing when every side already holds it.
        """
        keys: list[BorderEdgeKey] = []
        for row, column, side in sides:
            keys.append((rowIdentities[row - 1], columnIdentities[column - 1], side))
            facing, down, across = facingSides[side]
            neighborRow, neighborColumn = row + down, column + across
            if (1 <= neighborRow <= len(rowIdentities)
                    and 1 <= neighborColumn <= len(columnIdentities)):
                keys.append((
                    rowIdentities[neighborRow - 1],
                    columnIdentities[neighborColumn - 1], facing,
                ))
        held = [self.edges.get(key) for key in keys]
        if stroke is None and all(edge is None for edge in held):
            return False
        if stroke is not None and all(
            edge is not None and edge.stroke == stroke for edge in held
        ):
            return False
        if stroke is None:
            for key in keys:
                self.edges.pop(key, None)
            return True
        self.maxOrder += 1
        drawn = BorderEdge(stroke, self.maxOrder)
        for key in keys:
            self.edges[key] = drawn
        return True

    def linesRemove(self, rows: bool, removed: Iterable[int]) -> None:
        """Drop every stroke on a side of a cell in a removed line."""
        gone = frozenset(removed)
        self.edges = {
            key: edge for key, edge in self.edges.items()
            if (key[0] if rows else key[1]) not in gone
        }

    def linesAdd(
        self, rows: bool, added: Sequence[int], previous: int | None,
        displaced: int | None, crossing: Sequence[int],
    ) -> None:
        """Give added lines the strokes Numbers gives them, as `57-borders-*` measured.

        A line's own sides copy the line it displaced, so an inserted column arrives
        with its neighbor's border. A side running across the lines continues
        through them where the lines on either side store the same stroke, as one
        run spanning an insertion grows.
        """
        ownSides = rowSides if rows else frozenset(CellBorderSide) - rowSides
        placed: dict[BorderEdgeKey, BorderEdge] = {}
        for other in crossing:
            for side in CellBorderSide:
                before = None if previous is None else self.edges.get(
                    self.keyBuild(rows, previous, other, side)
                )
                after = None if displaced is None else self.edges.get(
                    self.keyBuild(rows, displaced, other, side)
                )
                carried = after if side in ownSides else (
                    after if before is not None and before == after else None
                )
                if carried is None:
                    continue
                for line in added:
                    placed[self.keyBuild(rows, line, other, side)] = carried
        self.edges.update(placed)

    @staticmethod
    def keyBuild(
        rows: bool, line: int, other: int, side: CellBorderSide
    ) -> BorderEdgeKey:
        """Return a side's key, from its line's identity on the edited axis."""
        return (line, other, side) if rows else (other, line, side)

    def cellsCarry(
        self, carries: Sequence[tuple[tuple[int, int], tuple[int, int]]], keep: bool
    ) -> None:
        """Carry each cell's four sides to another, by row and column identity.

        A move lifts each source's strokes, as `61-move-*` measured, and a copy keeps
        them and gives each destination exactly its source's, removing any the
        source lacks, as `64d` and `64f` measured.
        """
        lifted = {
            (target, side): self.edges.get((*source, side))
            for source, target in carries for side in CellBorderSide
        }
        if not keep:
            for source, _ in carries:
                for side in CellBorderSide:
                    self.edges.pop((*source, side), None)
        for (target, side), edge in lifted.items():
            key = (*target, side)
            if edge is not None:
                self.edges[key] = edge
            elif keep:
                self.edges.pop(key, None)


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


__all__ = [
    "BorderEdge", "BorderEdgeKey", "CellBorder", "CellBorderPosition",
    "CellBorderSide", "CellBorderStyle", "CellBorders", "TableBorders",
    "borderOrderInitial", "borderWidthOffered", "buildBorderStroke",
    "applyBlockBorders", "facingSides", "findBlockRing",
    "listDrawnSides", "rowSides",
]
