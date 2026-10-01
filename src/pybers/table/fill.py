#!/usr/bin/env python3
"""A block of cells repeated across a range, each filled cell a copy of its source.

The block repeats from its own top-left corner, so a range reaching past the
block in any direction takes the source cell at the matching position, and the
block itself keeps what it holds. Everything is checked before any cell changes,
so a refused fill leaves the table exactly as it was.

Each filled cell names the record of the cell it copied, which a save duplicates
whole, so a record's style, format and highlighting fill with its value. Numbers'
drag repeats the same way except where a column continues a series, the case
`CONTINUE_SERIES` covers, in any one direction. See findings-03-structure.md.

UPDATES
2026-10-01  A filled cell copies its source's record description, for PYB-141.
2026-09-30  `CONTINUE_SERIES` continues each column that begins a series, for
            PYB-137.
2026-09-29  A filled cell's copy says it draws no border, which a paste does,
            for PYB-136.
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
from pybers.table.kinds import CellKind
from pybers.table.relocation import findBlockCorners, toRelocationRule
from pybers.table.series import SeedValue, findSeriesContinuation

if TYPE_CHECKING:
    from pybers.table.cells import Cell, Table


# Numbers repeats rather than continues a line holding either of these.
seriesBreakingKinds: frozenset[CellKind] = frozenset(
    {CellKind.ERROR, CellKind.RICH_TEXT}
)


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


def findSeriesValues(
    table: Table, extent: CellRange, targets: list[CellReference]
) -> dict[CellReference, SeedValue]:
    """Return each filled cell's continued value, refusing a range not in line with it.

    A block continues down or up its columns, or right or left along its rows, and
    each line of seeds decides for itself whether it begins a series.
    """
    top, left, bottom, right = findBlockCorners(extent)
    down = all(left <= target.col <= right for target in targets)
    across = all(top <= target.row <= bottom for target in targets)
    if not (down or across):
        raise ReferenceError(
            f"A series continues down or up the columns of {extent}, or along its "
            "rows, and the range asks for both."
        )
    lines = (
        [[CellReference(row, column) for row in range(top, bottom + 1)]
         for column in range(left, right + 1)]
        if down else
        [[CellReference(row, column) for column in range(left, right + 1)]
         for row in range(top, bottom + 1)]
    )
    values: dict[CellReference, SeedValue] = {}
    for line in lines:
        cells = [table.cell(reference) for reference in line]
        if any(
            cell.formula is not None or cell.description.kind in seriesBreakingKinds
            for cell in cells
        ):
            continue
        continuation = findSeriesContinuation([cell.value for cell in cells])
        if continuation is None:
            continue
        for target in targets:
            if down and target.col == line[0].col:
                values[target] = continuation(target.row - top)
            elif across and target.row == line[0].row:
                values[target] = continuation(target.col - left)
    return values


def copyCellContent(
    target: Cell, source: Cell, namedCell: bool, borders: bool
) -> None:
    """Give a cell everything another holds, its formulas under the rule named."""
    from pybers.table.cells import CellCopy

    target.value = source.value
    target.style = source.style
    target._stored = source._stored
    target._storedValue = source._storedValue
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
    # A copy of a pending copy duplicates the record that one will duplicate, and
    # draws only the borders that one will draw.
    pending = source._copiedFrom
    target._copiedFrom = (
        CellCopy(source, borders) if pending is None
        else CellCopy(pending.source, borders and pending.borders)
    )


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
    rule = toValueRule(values)
    extent = table.rangeSingle(source, "fill")
    refuseMergeInBlock(table, extent)
    targets = [
        position for position in listRangePositions(table, through)
        if not extent.covers(position)
    ]
    continued = (
        findSeriesValues(table, extent, targets)
        if rule is CellValueFill.CONTINUE_SERIES else {}
    )
    for position in targets:
        cell = table.cell(position)
        copyCellContent(
            cell,
            table.cell(findSourcePosition(extent, position)),
            namedCell,
            borders=False,
        )
        if position in continued:
            cell.value = continued[position]
    return len(targets)


__all__ = ["CellValueFill", "fillCells"]
