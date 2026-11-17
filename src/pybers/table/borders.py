#!/usr/bin/env python3
"""\
A cell's borders, and the table's store of every stroke drawn on a cell's side.

Numbers keeps four strokes per cell and no position, so the store holds one stroke
per side of a cell, keyed by the identities of its row and column, which move with
their lines. Of two facing strokes that disagree, Numbers draws the one with the
higher `order`. See findings-06-styles.md and findings-03-structure.md.

UPDATES
2026-11-17  Written for PYB-266, taking over the rules `_strokes` applied to the
            archive at save time. Drawing and reading on a table is in
            `bordersdraw`.
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

from pybers.absence import MIXED
from pybers.addressing.reference import CellAddress
from pybers.color.colors import Color
from pybers.style.strokes import (
    Stroke,
    StrokeEmpty,
    cellStrokePresets,
)

if TYPE_CHECKING:
    pass

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
    if style is CellBorderStyle.HIDDEN:
        return Stroke(width=Decimal(0), color=Color.black, pattern=StrokeEmpty())
    pattern, cap, join = cellStrokePresets[style.value]
    return Stroke(
        width=Decimal(width), color=color, pattern=pattern, cap=cap, join=join
    )


# A side of a cell, by the identity of its row and of its column.
type BorderEdgeKey = tuple[int, int, CellBorderSide]


@dataclass(frozen=True, slots=True)
class BorderEdge:
    """One stroke stored on one side of one cell, and the order in which it was drawn.

    `stored` is the archive it was read from, so a brush or frame is carried, and
    `run` the stored run holding it, None for one pybers drew since.
    """

    stroke: Stroke
    order: int
    stored: bytes | None = None
    run: int | None = field(default=None, compare=False)


@dataclass(frozen=True, slots=True)
class CellBorder:
    """A side of a cell: the stroke the cell stores, and the one its neighbor stores."""

    stroke: Stroke | MIXED | None
    neighborStroke: Stroke | MIXED | None
    # Whether this cell's stroke is the one drawn, as the later of the two.
    prevails: bool = False

    @property
    def disagrees(self) -> bool:
        """Report whether both cells store a stroke here and the two differ."""
        return (
            self.stroke is not None and self.neighborStroke is not None
            and (self.stroke is MIXED or self.stroke != self.neighborStroke)
        )


@dataclass(frozen=True, slots=True)
class CellBorders:
    """A cell's four sides in CSS order, each None where neither cell stores one."""

    top: CellBorder | None = None
    right: CellBorder | None = None
    bottom: CellBorder | None = None
    left: CellBorder | None = None


def findSpanStroke(edges: Sequence[BorderEdge | None]) -> Stroke | MIXED | None:
    """Return the one stroke every position of a side stores, None, or `MIXED`."""
    strokes = {None if edge is None else edge.stroke for edge in edges}
    if len(strokes) > 1:
        return MIXED
    return strokes.pop()


@dataclass(slots=True)
class TableBorders:
    """Every stroke a table stores on a side of a cell, and the highest order drawn."""

    edges: dict[BorderEdgeKey, BorderEdge] = field(default_factory=dict)
    maxOrder: int = borderOrderInitial

    def cellBordersRead(
        self, rowIdentities: Sequence[int], columnIdentities: Sequence[int],
        top: int, left: int, bottom: int, right: int,
    ) -> CellBorders:
        """Return the four sides of a cell spanning rows and columns counted from one.

        A merged cell's side runs along every position of it, and reads `MIXED` where
        the strokes stored along it differ.
        """
        spans = {
            CellBorderSide.TOP: [(top, column) for column in range(left, right + 1)],
            CellBorderSide.BOTTOM: [
                (bottom, column) for column in range(left, right + 1)
            ],
            CellBorderSide.LEFT: [(row, left) for row in range(top, bottom + 1)],
            CellBorderSide.RIGHT: [(row, right) for row in range(top, bottom + 1)],
        }
        sides: dict[str, CellBorder | None] = {}
        for side, (facing, down, across) in facingSides.items():
            owns, neighbors = [], []
            for row, column in spans[side]:
                owns.append(self.edges.get(
                    (rowIdentities[row - 1], columnIdentities[column - 1], side)
                ))
                neighborRow, neighborColumn = row + down, column + across
                inside = (1 <= neighborRow <= len(rowIdentities)
                          and 1 <= neighborColumn <= len(columnIdentities))
                neighbors.append(None if not inside else self.edges.get((
                    rowIdentities[neighborRow - 1],
                    columnIdentities[neighborColumn - 1], facing,
                )))
            if all(edge is None for edge in (*owns, *neighbors)):
                sides[side.value] = None
                continue
            sides[side.value] = CellBorder(
                findSpanStroke(owns), findSpanStroke(neighbors),
                all(
                    own is not None
                    and (neighbor is None or own.order >= neighbor.order)
                    for own, neighbor in zip(owns, neighbors, strict=True)
                ),
            )
        return CellBorders(**sides)

    def edgeShownFind(
        self, rowIdentities: Sequence[int], columnIdentities: Sequence[int],
        cell: CellAddress, side: CellBorderSide,
    ) -> Stroke | None:
        """Return the stroke stored at a cell's side that Numbers draws, the later one.

        Of two facing strokes, the higher order prevails, as `63d` measured.
        """
        facing, down, across = facingSides[side]
        own = self.edges.get(
            (rowIdentities[cell.row - 1], columnIdentities[cell.col - 1], side)
        )
        row, column = cell.row + down, cell.col + across
        neighbor = None
        if 1 <= row <= len(rowIdentities) and 1 <= column <= len(columnIdentities):
            neighbor = self.edges.get(
                (rowIdentities[row - 1], columnIdentities[column - 1], facing)
            )
        held = [edge for edge in (own, neighbor) if edge is not None]
        if not held:
            return None
        return max(held, key=lambda edge: edge.order).stroke

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
        through them where the lines on either side lie in one run, as a run
        spanning an insertion grows and two runs Numbers split do not.
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
                # A run spanning the insertion grows over it, so both sides share one.
                continued = (
                    before is not None and after is not None and before == after
                    and before.run == after.run
                )
                carried = after if side in ownSides or continued else None
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

    def facingPairsLift(
        self, rowIdentities: Sequence[int], columnIdentities: Sequence[int],
        moves: Sequence[tuple[CellAddress, CellAddress]],
    ) -> list[tuple[BorderEdgeKey, BorderEdge]]:
        """Lift each facing side outside a moving block that pairs a side inside it.

        A pair is the same stroke at the same order, as pybers writes both sides of
        an edge, so it moves with the block. A side a neighbor drew for itself stays.
        Returns where each lifted side lands, beside the block's destination.
        """
        moving = {source for source, _ in moves}
        rows, columns = len(rowIdentities), len(columnIdentities)

        def keyFind(
            row: int, column: int, side: CellBorderSide
        ) -> BorderEdgeKey | None:
            if not (1 <= row <= rows and 1 <= column <= columns):
                return None
            return (rowIdentities[row - 1], columnIdentities[column - 1], side)

        lifted: list[tuple[BorderEdgeKey, BorderEdge]] = []
        for source, target in moves:
            for side, (facing, down, across) in facingSides.items():
                row, column = source.row + down, source.col + across
                if (row, column) in {(each.row, each.col) for each in moving}:
                    continue
                own = self.edges.get((
                    rowIdentities[source.row - 1], columnIdentities[source.col - 1],
                    side,
                ))
                held = keyFind(row, column, facing)
                if own is None or held is None or self.edges.get(held) != own:
                    continue
                del self.edges[held]
                landed = keyFind(target.row + down, target.col + across, facing)
                if landed is not None:
                    lifted.append((landed, own))
        return lifted

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


__all__ = [
    "BorderEdge", "BorderEdgeKey", "CellBorder", "CellBorderPosition",
    "CellBorderSide", "CellBorderStyle", "CellBorders", "TableBorders",
    "borderOrderInitial", "borderWidthOffered", "buildBorderStroke", "facingSides",
    "findSpanStroke", "rowSides",
]
