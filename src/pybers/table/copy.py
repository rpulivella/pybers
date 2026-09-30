#!/usr/bin/env python3
"""A block of cells copied to a new anchor in its table, carrying its merges.

Everything is checked before anything is copied, so a refused copy leaves the
table exactly as it was. Each copied cell names the record of the cell it copies,
which a save duplicates whole, and each position of the block takes its source's
borders exactly, as Numbers' paste did in `64b` and `64d`.
No formula outside the copy changes, under either rule. See findings-03-structure.md.

**A copy never overwrites**, its own source included, so the source reads
afterward exactly as it did before.

UPDATES
2026-09-29  Written for PYB-136.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/29"

from typing import TYPE_CHECKING

from pybers.addressing.ranges import CellRange, RangeAddress
from pybers.addressing.reference import CellAddress, ReferenceError, toCellReference
from pybers.formula.relocation import FormulaReferenceRelocation, clampFormulaRanges
from pybers.table.fill import copyCellContent
from pybers.table.merges import MergeRange
from pybers.table.relocation import (
    CellsMove,
    findBlockCorners,
    refuseMergeCut,
    refuseOccupied,
    toRelocationRule,
)

if TYPE_CHECKING:
    from pybers.table.cells import Table


def copyCells(
    table: Table,
    source: RangeAddress,
    anchor: CellAddress,
    references: FormulaReferenceRelocation,
) -> CellRange:
    """Copy a block so its top-left lands on `anchor`, and return where it landed."""
    from pybers.table.cells import Cell, refuseRangeOutside

    rule = toRelocationRule(references)
    named = rule is FormulaReferenceRelocation.PRESERVE_NAMED_CELL
    extent = table.rangeSingle(source, "copy")
    landing = toCellReference(anchor).asUnlocked()
    startRow, startCol, _, _ = findBlockCorners(extent)
    copy = CellsMove(extent, landing.row - startRow, landing.col - startCol)
    destination = copy.destination
    refuseRangeOutside(table, destination)
    if any(extent.covers(reference) for reference in destination):
        raise ReferenceError(
            f"{destination} overlaps {extent}, and a copy never overwrites its own "
            "source."
        )
    refuseMergeCut(table, copy, "copy")
    refuseOccupied(table, copy, "copy")

    # Every position, empty ones included, since a paste gives each its source's
    # borders and one holding nothing else may still hold a border, as `64d` shows.
    copied = [
        table.cell(reference) for reference in extent
        if table.addressable(reference)
    ]
    for reference in destination:
        table.cells.pop(reference, None)
    for cell in copied:
        target = Cell(reference=copy.cellMap(cell.reference), table=table)
        copyCellContent(target, cell, named, borders=True)
        if target.formula is not None and not named:
            target.formula = clampFormulaRanges(
                target.formula, target.reference, table.rowCount, table.colCount
            )
        table.cells[target.reference] = target
    table.mergeRanges.extend(
        MergeRange(CellRange.fromReferences(
            copy.cellMap(merge.anchor), copy.cellMap(merge.extent.end or merge.anchor)
        ))
        for merge in list(table.mergeRanges) if extent.covers(merge.anchor)
    )
    return destination


__all__ = ["copyCells"]
