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
from enum import StrEnum

from pybers.style.strokes import Stroke


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
    maxOrder: int = 0

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


__all__ = [
    "BorderEdge", "BorderEdgeKey", "CellBorder", "CellBorderSide", "CellBorders",
    "TableBorders", "facingSides", "rowSides",
]
