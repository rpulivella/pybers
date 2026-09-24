#!/usr/bin/env python3
"""A block of cells moved to a new anchor in its table, carrying its merges.

Everything is checked before anything moves, so a refused move leaves the table
exactly as it was. What each reference keeps is the caller's to name, since
Numbers performs both rules: see `pybers.formula.relocation`.

**A move never overwrites.** Numbers overwrote the occupied cells a drag landed
on without asking, measured 2026-09-23 in `60e-move-overwrite`, and pybers refuses
instead, since that discards a value nobody asked to lose.

UPDATES
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
from typing import TYPE_CHECKING

from pybers.addressing.ranges import CellRange, RangeAddress
from pybers.addressing.reference import (
    CellAddress,
    CellReference,
    ReferenceError,
    toCellReference,
)
from pybers.formula.nodes import Formula
from pybers.formula.relocation import (
    FormulaBlockMove,
    FormulaReferenceRelocation,
    clampFormulaRanges,
    relocateFormula,
)

if TYPE_CHECKING:
    from pybers.table.cells import Cell, Table


def findBlockCorners(extent: CellRange) -> tuple[int, int, int, int]:
    """Return a bounded block's corners as (startRow, startCol, endRow, endCol)."""
    startRow, startCol = extent.startRow, extent.startCol
    endRow, endCol = extent.endRow, extent.endCol
    if startRow is None or startCol is None or endRow is None or endCol is None:
        raise ReferenceError(f"{extent} is unbounded and moves no block.")
    return (startRow, startCol, endRow, endCol)


@dataclass(frozen=True, slots=True)
class CellsMove:
    """A bounded block and how far it travels, each axis counted in lines."""

    source: CellRange
    rowShift: int
    columnShift: int

    @property
    def destination(self) -> CellRange:
        """Return the block where it lands."""
        startRow, startCol, endRow, endCol = self.bounds
        return CellRange(
            startRow + self.rowShift, startCol + self.columnShift,
            endRow + self.rowShift, endCol + self.columnShift,
        )

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        """Return the source block's corners as (startRow, startCol, endRow, endCol)."""
        return findBlockCorners(self.source)

    def cellMap(self, reference: CellReference) -> CellReference:
        """Return where a cell lands: moved when the block holds it, else in place."""
        if not self.source.covers(reference):
            return reference
        return CellReference(
            reference.row + self.rowShift, reference.col + self.columnShift
        )


def toRelocationRule(references: str) -> FormulaReferenceRelocation:
    """Return the rule a caller named, accepting its spelling as text."""
    try:
        return FormulaReferenceRelocation(references)
    except ValueError as exc:
        spelled = ", ".join(repr(rule.value) for rule in FormulaReferenceRelocation)
        raise ReferenceError(
            f"{references!r} is not a reference rule. A move names one of {spelled}."
        ) from exc


def isCellOccupied(cell: Cell) -> bool:
    """Report whether a cell holds a value, a formula, or a record of formatting."""
    return (
        cell.value is not None or cell.formula is not None or cell._origin is not None
    )


def refuseMergeCut(table: Table, move: CellsMove) -> None:
    """Refuse a block cutting a merge, or landing on one it does not carry."""
    source, destination = move.source, move.destination
    for merge in table.mergeRanges:
        covered = list(merge.extent)
        inside = sum(1 for reference in covered if source.covers(reference))
        if 0 < inside < len(covered):
            raise ReferenceError(
                f"{source} cuts the merge {merge.extent} in two. Move the whole merge "
                "or none of it."
            )
        if inside == 0 and any(destination.covers(reference) for reference in covered):
            raise ReferenceError(
                f"{destination} lands on the merge {merge.extent}, which the move "
                "would overwrite."
            )


def refuseOccupied(table: Table, move: CellsMove) -> None:
    """Refuse a destination holding anything outside the block itself."""
    for reference in move.destination:
        if move.source.covers(reference):
            continue
        cell = table.cells.get(reference)
        if cell is not None and isCellOccupied(cell):
            raise ReferenceError(
                f"{reference} is occupied, and moving {move.source} onto "
                f"{move.destination} would overwrite it."
            )


def findNamedCellRewrites(
    table: Table, move: CellsMove
) -> dict[int, tuple[Cell, tuple[Formula | None, tuple[Formula, ...]]]]:
    """Return every formula and condition in the document rewritten to keep its cells.

    Worked out before any cell moves, from where each formula sits now. Only this
    table's highlighting is rewritten, since a rule reads only its own table.
    """
    top, left, bottom, right = move.bounds
    blockMove = FormulaBlockMove(
        table.identifier, top, left, bottom, right, move.rowShift, move.columnShift
    )
    tables = (
        [table] if table.document is None
        else [other for sheet in table.document.sheets for other in sheet.tables]
    )
    rewritten: dict[int, tuple[Cell, tuple[Formula | None, tuple[Formula, ...]]]] = {}
    for host in tables:
        inside = host is table
        for reference, cell in host.cells.items():
            landed = move.cellMap(reference) if inside else reference
            formula = cell.formula and relocateFormula(
                cell.formula, reference, landed, blockMove, inside
            )
            conditions = cell._conditions
            if inside:
                conditions = tuple(
                    relocateFormula(condition, reference, landed, blockMove, True)
                    for condition in conditions
                )
            if formula != cell.formula or conditions != cell._conditions:
                rewritten[id(cell)] = (cell, (formula, conditions))
    return rewritten


def moveCells(
    table: Table,
    source: RangeAddress,
    anchor: CellAddress,
    references: FormulaReferenceRelocation,
) -> list[Cell]:
    """Move a block so its top-left lands on `anchor`, and return what it strands."""
    from pybers.table.cells import MergeRange, refuseRangeOutside

    rule = toRelocationRule(references)
    extent = table.rangeSingle(source, "move")
    landing = toCellReference(anchor).asUnlocked()
    startRow, startCol, _, _ = findBlockCorners(extent)
    move = CellsMove(extent, landing.row - startRow, landing.col - startCol)
    refuseRangeOutside(table, move.destination)
    if move.rowShift == 0 and move.columnShift == 0:
        return []
    refuseMergeCut(table, move)
    refuseOccupied(table, move)
    rewritten = (
        findNamedCellRewrites(table, move)
        if rule is FormulaReferenceRelocation.PRESERVE_NAMED_CELL else {}
    )

    moving = [
        cell for reference, cell in table.cells.items() if extent.covers(reference)
    ]
    for cell in moving:
        del table.cells[cell.reference]
    for reference in move.destination:
        table.cells.pop(reference, None)
    for cell in moving:
        cell.reference = move.cellMap(cell.reference)
        table.cells[cell.reference] = cell
        if cell.formula is not None and not rewritten:
            cell.formula = clampFormulaRanges(
                cell.formula, cell.reference, table.rowCount, table.colCount
            )
    for cell, (formula, conditions) in rewritten.values():
        cell.formula = formula
        cell._conditions = conditions
    table.mergeRanges = [
        MergeRange(CellRange.fromReferences(
            move.cellMap(merge.anchor), move.cellMap(merge.extent.end or merge.anchor)
        )) if extent.covers(merge.anchor) else merge
        for merge in table.mergeRanges
    ]
    return []


__all__ = ["CellsMove", "moveCells"]
