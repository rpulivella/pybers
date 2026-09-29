#!/usr/bin/env python3
"""A block of cells repeated across a range, each filled cell a copy of its source.

The block repeats from its own top-left corner, so a range reaching past the
block in any direction takes the source cell at the matching position, and the
block itself keeps what it holds. Everything is checked before any cell changes,
so a refused fill leaves the table exactly as it was.

Each filled cell names the record of the cell it copied, which a save duplicates
whole, so a record's style, format and highlighting fill with its value. Numbers'
drag repeats the same way except where a column continues a series, the case
`CONTINUE_SERIES` covers. See findings-03-structure.md.

UPDATES
2026-09-29  Written for PYB-118, replacing `Table.formulaFill`.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/29"

from enum import StrEnum
from typing import TYPE_CHECKING

from pybers.addressing.ranges import CellRange, RangeAddress
from pybers.addressing.reference import CellReference, ReferenceError
from pybers.formula.relocation import FormulaReferenceRelocation, relocateFormula
from pybers.table.relocation import findBlockCorners, toRelocationRule

if TYPE_CHECKING:
    from pybers.table.cells import Cell, Table


class CellValueFill(StrEnum):
    """What each filled value becomes: its source's value, or the series continued."""

    REPEAT_SOURCE_VALUE = "source-value"
    CONTINUE_SERIES = "series"


def toValueRule(values: str) -> CellValueFill:
    """Return the value rule a caller named, refusing one not yet supported."""
    try:
        rule = CellValueFill(values)
    except ValueError as exc:
        spelled = ", ".join(repr(rule.value) for rule in CellValueFill)
        raise ReferenceError(
            f"{values!r} is not a value rule. A fill names one of {spelled}."
        ) from exc
    if rule is CellValueFill.CONTINUE_SERIES:
        raise ReferenceError(
            f"Continuing a series is not supported yet, so no fill takes "
            f"{rule.value!r}."
        )
    return rule


def refuseMergeInBlock(table: Table, extent: CellRange) -> None:
    """Refuse a source block holding any part of a merge, which a fill cannot copy."""
    for merge in table.mergeRanges:
        if any(extent.covers(reference) for reference in merge.extent):
            raise ReferenceError(
                f"{extent} holds part of the merge {merge.extent}, and a fill copies "
                "no merge."
            )


def findSourcePosition(extent: CellRange, target: CellReference) -> CellReference:
    """Return the block position a target takes, repeating from the block's corner."""
    top, left, bottom, right = findBlockCorners(extent)
    height, width = bottom - top + 1, right - left + 1
    return CellReference(
        top + (target.row - top) % height, left + (target.col - left) % width
    )


def copyCellContent(target: Cell, source: Cell, namedCell: bool) -> None:
    """Give a cell everything another holds, its formulas under the rule named."""
    target.value = source.value
    target.errored = source.errored
    target.style = source.style
    target._formatChosen = source._formatChosen
    formula, conditions = source.formula, source._conditions
    if namedCell:
        formula = formula and relocateFormula(
            formula, source.reference, target.reference, None, True
        )
        conditions = tuple(
            relocateFormula(condition, source.reference, target.reference, None, True)
            for condition in conditions
        )
    target.formula = formula
    target._conditions = conditions
    # A copy of a pending copy duplicates the record that one will duplicate.
    target._copiedFrom = source._copiedFrom or source


def fillCells(
    table: Table,
    source: RangeAddress,
    through: RangeAddress,
    references: FormulaReferenceRelocation,
    values: CellValueFill,
) -> int:
    """Repeat a block across a range, and return how many cells were filled."""
    from pybers.table.cells import listRangePositions

    namedCell = (
        toRelocationRule(references) is FormulaReferenceRelocation.PRESERVE_NAMED_CELL
    )
    toValueRule(values)
    extent = table.rangeSingle(source, "fill")
    refuseMergeInBlock(table, extent)
    targets = [
        position for position in listRangePositions(table, through)
        if not extent.covers(position)
    ]
    for position in targets:
        copyCellContent(
            table.cell(position),
            table.cell(findSourcePosition(extent, position)),
            namedCell,
        )
    return len(targets)


__all__ = ["CellValueFill", "fillCells"]
