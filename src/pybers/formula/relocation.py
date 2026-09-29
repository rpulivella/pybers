#!/usr/bin/env python3
"""The rule a caller names for what every reference keeps when cells change address.

**Numbers performs both rules**, measured 2026-09-23 in `60-move-*`. Dragging a
block keeps each reference on the cell it named, and cut and paste keeps each
reference's offset from its formula. Neither is a default, so every operation
relocating cells takes one from its caller.

**A moved range reaching past its table ends at the table's edge**, the one rewrite
cut and paste makes: `SUM(A1:A12)` pasted six rows lower in a table of twelve rows
was stored as `SUM(E7:E12)`, not `SUM(E7:E18)`. A single reference past the edge is
kept, and shows an error.

UPDATES
2026-09-29  A formula keeps its named cells from a new host with no block moved,
            which is how a fill copies one, for PYB-118.
2026-09-23  Written for PYB-18.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/23"

from dataclasses import dataclass
from enum import StrEnum

from pybers.addressing.reference import CellReference
from pybers.formula.nodes import (
    Coordinate,
    Formula,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    Span,
)


class FormulaReferenceRelocation(StrEnum):
    """What each reference a relocation touches keeps: its named cell or its offset."""

    PRESERVE_NAMED_CELL = "named-cell"
    PRESERVE_RELATIVE_POSITION = "relative-position"


@dataclass(frozen=True, slots=True)
class FormulaBlockMove:
    """A block of one table moved, as a formula anywhere has to see it.

    `targetTable` names that table as a reference does, so a local reference
    reaches it only from a formula inside it. Corners count from one.
    """

    targetTable: str
    top: int
    left: int
    bottom: int
    right: int
    rowShift: int
    columnShift: int

    def covers(self, row: int, column: int) -> bool:
        """Report whether a cell of the moved table lies inside the block."""
        return self.top <= row <= self.bottom and self.left <= column <= self.right

    def reaches(self, tableId: str | None, hostInTarget: bool) -> bool:
        """Report whether a reference naming this table reaches the moved one."""
        return hostInTarget if tableId is None else tableId == self.targetTable


def placeCoordinate(
    coordinate: Coordinate, target: int, host: int
) -> Coordinate:
    """Return an axis naming `target` from a formula at `host`, in its own form."""
    value = target if coordinate.absolute else target - host
    if value == coordinate.value:
        return coordinate
    return Coordinate(value, coordinate.absolute)


def placeSpan(span: Span, begin: int, end: int, host: int) -> Span:
    """Return a range axis covering `begin` to `end` from a formula at `host`."""
    shift = 0 if span.absolute else host
    last = None if span.end is None else end - shift
    moved = Span(begin - shift, last, span.absolute)
    return span if moved == span else moved


def relocateReference(
    reference: FormulaReference,
    host: CellReference,
    landed: CellReference,
    move: FormulaBlockMove | None,
    hostInTarget: bool,
) -> FormulaReference:
    """Return a reference naming the cell it named, from a formula now at `landed`."""
    if reference.broken:
        return reference
    row = None if reference.row is None else reference.row.resolve(host.row)
    column = None if reference.column is None else reference.column.resolve(host.col)
    if (
        move is not None and row is not None and column is not None
        and move.reaches(reference.tableId, hostInTarget)
        and move.covers(row, column)
    ):
        row, column = row + move.rowShift, column + move.columnShift
    placedRow = None if reference.row is None or row is None else placeCoordinate(
        reference.row, row, landed.row
    )
    placedColumn = (
        None if reference.column is None or column is None
        else placeCoordinate(reference.column, column, landed.col)
    )
    if placedRow is reference.row and placedColumn is reference.column:
        return reference
    return FormulaReference(placedColumn, placedRow, reference.tableId)


def relocateRange(
    extent: FormulaRange,
    host: CellReference,
    landed: CellReference,
    move: FormulaBlockMove | None,
    hostInTarget: bool,
) -> FormulaRange:
    """Return a range following the block only when it lies wholly inside it."""
    rows = None if extent.rows is None else extent.rows.resolve(host.row)
    columns = None if extent.columns is None else extent.columns.resolve(host.col)
    rowShift = columnShift = 0
    if (
        move is not None and rows is not None and columns is not None
        and move.reaches(extent.tableId, hostInTarget)
        and move.covers(rows[0], columns[0]) and move.covers(rows[1], columns[1])
    ):
        rowShift, columnShift = move.rowShift, move.columnShift
    placedRows = None if extent.rows is None or rows is None else placeSpan(
        extent.rows, rows[0] + rowShift, rows[1] + rowShift, landed.row
    )
    placedColumns = None if extent.columns is None or columns is None else placeSpan(
        extent.columns, columns[0] + columnShift, columns[1] + columnShift, landed.col
    )
    if placedRows is extent.rows and placedColumns is extent.columns:
        return extent
    return FormulaRange(placedColumns, placedRows, extent.tableId)


def relocateFormula(
    formula: Formula,
    host: CellReference,
    landed: CellReference,
    move: FormulaBlockMove | None,
    hostInTarget: bool,
) -> Formula:
    """Return a formula whose references name the cells they named before the move.

    `host` is where the formula sat and `landed` where it sits now. A reference
    into the block follows it, and a range follows only when wholly inside, as
    `60c-move-dragged` left `SUM(B1:B6)` where it was. With no `move`, every
    reference keeps the cell it named.
    """
    nodes = []
    for node in formula.nodes:
        content = node.content
        moved: object = content
        if isinstance(content, FormulaReference):
            moved = relocateReference(content, host, landed, move, hostInTarget)
        elif isinstance(content, FormulaRange):
            moved = relocateRange(content, host, landed, move, hostInTarget)
        if moved is not content:
            assert isinstance(moved, FormulaReference | FormulaRange)
            node = FormulaNode(node.nodeType, moved, node.raw)
        nodes.append(node)
    if all(new is old for new, old in zip(nodes, formula.nodes, strict=True)):
        return formula
    return Formula(tuple(nodes))


def clampSpan(span: Span | None, host: int, count: int) -> Span | None:
    """Return one axis of a range ending no further than the table's last line."""
    if span is None:
        return None
    begin, end = span.resolve(host)
    if end <= count or begin > count:
        return span
    shift = 0 if span.absolute else host
    return Span(begin - shift, None if begin == count else count - shift, span.absolute)


def clampFormulaRanges(
    formula: Formula, host: CellReference, rowCount: int, columnCount: int
) -> Formula:
    """Return a formula whose ranges in its own table stop at that table's edge."""
    nodes = []
    for node in formula.nodes:
        content = node.content
        if isinstance(content, FormulaRange) and content.tableId is None:
            clamped = FormulaRange(
                clampSpan(content.columns, host.col, columnCount),
                clampSpan(content.rows, host.row, rowCount),
                content.tableId,
            )
            if clamped != content:
                node = FormulaNode(node.nodeType, clamped, node.raw)
        nodes.append(node)
    if all(new is old for new, old in zip(nodes, formula.nodes, strict=True)):
        return formula
    return Formula(tuple(nodes))


__all__ = [
    "FormulaBlockMove",
    "FormulaReferenceRelocation",
    "clampFormulaRanges",
    "relocateFormula",
]
