#!/usr/bin/env python3
"""Rows and columns added to and removed from a table, with everything naming them.

One edit moves four things together: the cells past the edit, the merges, every
formula in the document that reaches into the table, and the identity each line
carries. Everything is computed before anything is assigned, so a refused edit
leaves the table and the document exactly as they were.

**A line keeps its identity wherever it moves**, which is how a row hidden before
an edit is still hidden after it: Numbers keys hidden state by that identity, not
by position. An added line gets a fresh one. Measured 2026-09-18 across
`56-structure-base` and all six of its edited copies.

**A merge grows when an insertion lands inside it** and does not copy into the new
line, measured in `56f-row-inserted-in-merge`. Numbers widens a selection until it
covers whole merges, so an edit made from a selected row never cuts one: only a
single selected cell does, which is what `56f` and `56g` were made from.

**A merged value outlives the line its anchor sat on**, and a merge left one cell
is unmerged rather than kept, both measured in `57-anchors-*` and `57-collapse-*`.

UPDATES
2026-09-24  A cell's highlighting conditions follow the edit too, for PYB-18.
2026-09-18  Written for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/18"

import uuid
from typing import TYPE_CHECKING

from pybers.addressing.lines import GridEdit
from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import (
    CellReference,
    ReferenceError,
    lastColumn,
    lastRow,
    toColumnNumber,
)
from pybers.formula.nodes import Formula
from pybers.formula.restructure import FormulaRestructure, mapFormula

if TYPE_CHECKING:
    from pybers.table.cells import Cell, Table
    from pybers.table.merges import MergeRange


def generateLineIdentities(count: int) -> list[int]:
    """Return fresh identities for new rows or columns, as Numbers gives each one."""
    return [uuid.uuid4().int for _ in range(count)]


def toLineNumber(line: int | str, rows: bool) -> int:
    """Return a row number, or a column number from a number or a letter label."""
    if not rows and isinstance(line, str):
        return toColumnNumber(line)
    if isinstance(line, int) and not isinstance(line, bool):
        return line
    axis = "row" if rows else "column"
    raise ReferenceError(f"A {axis} is named by a number, and {line!r} is not one.")


def buildGridEdit(
    table: Table, line: int | str, count: int, *, rows: bool, removing: bool
) -> GridEdit:
    """Return the edit a caller asked for, refusing one the table cannot take.

    Added lines may go anywhere from the first line to just past the last. Removed
    lines must all exist, and at least one line has to remain, since Numbers keeps
    no table without one.
    """
    at = toLineNumber(line, rows)
    axis = "rows" if rows else "columns"
    held = table.rowCount if rows else table.colCount
    limit = lastRow if rows else lastColumn
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ReferenceError(
            f"A structural edit adds or removes one or more {axis}, and {count!r} "
            "is not such a count."
        )
    if removing:
        if at < 1 or at + count - 1 > held:
            raise ReferenceError(
                f"{table.name!r} holds {held} {axis}, so {count} starting at {at} "
                "cannot be removed."
            )
        if count >= held:
            raise ReferenceError(
                f"Removing {count} of the {held} {axis} in {table.name!r} would leave "
                "none, and a Numbers table always keeps at least one."
            )
    else:
        if not 1 <= at <= held + 1:
            raise ReferenceError(
                f"{table.name!r} holds {held} {axis}, so new ones go in from 1 to "
                f"{held + 1}, and {at} is outside that."
            )
        if held + count > limit:
            raise ReferenceError(
                f"{table.name!r} would hold {held + count} {axis}, past the {limit} a "
                "Numbers table can hold."
            )
    return GridEdit(rows=rows, at=at, count=count, removing=removing)


def mapCell(reference: CellReference, edit: GridEdit) -> CellReference | None:
    """Return where a cell lands, or None when the edit removes its line."""
    if edit.rows:
        row = edit.lineMap(reference.row)
        return None if row is None else CellReference(row, reference.col)
    col = edit.lineMap(reference.col)
    return None if col is None else CellReference(reference.row, col)


def mapMerge(merge: MergeRange, edit: GridEdit) -> MergeRange | None:
    """Return where a merge lands, or None when it stops being a merge.

    **A merge left one cell is unmerged, and keeps its value**, measured
    2026-09-21 in `57-collapse-row-deleted`, and one losing every line it
    covered is unmerged as well.
    """
    from pybers.table.merges import MergeRange

    startRow, startCol, endRow, endCol = merge.bounds
    begin, end = (startRow, endRow) if edit.rows else (startCol, endCol)
    mapped = edit.spanMap(begin, end)
    if mapped is None:
        return None
    if edit.rows:
        extent = CellRange(mapped[0], startCol, mapped[1], endCol)
    else:
        extent = CellRange(startRow, mapped[0], endRow, mapped[1])
    if extent.start == extent.end:
        return None
    return MergeRange(extent)


def findMergeAnchorMoves(
    table: Table, edit: GridEdit
) -> dict[CellReference, CellReference]:
    """Return where each merge whose anchor line goes carries its value.

    **The merged value survives its anchor's line**, measured 2026-09-21 in
    `57-anchors-anchor-row-deleted`, where deleting the row the anchor sat on left
    the merge one row shorter, still holding its text at the top of what remained.
    """
    moves: dict[CellReference, CellReference] = {}
    if not edit.removing:
        return moves
    for merge in table.mergeRanges:
        startRow, startCol, endRow, endCol = merge.bounds
        begin, end = (startRow, endRow) if edit.rows else (startCol, endCol)
        if not edit.at <= begin <= edit.last:
            continue
        mapped = edit.spanMap(begin, end)
        if mapped is None:
            continue
        anchor = (
            CellReference(mapped[0], startCol) if edit.rows
            else CellReference(startRow, mapped[0])
        )
        moves[merge.anchor] = anchor
    return moves


def countBrokenReferences(formula: Formula | None) -> int:
    """Return how many references in a formula point nowhere."""
    if formula is None:
        return 0
    return sum(1 for reference in formula.references if reference.broken)


def editGrid(table: Table, edit: GridEdit) -> list[Cell]:
    """Apply one structural edit, and return each cell it left newly broken.

    The document's other tables are rewritten too, since a formula there can
    reach into this one by identity.
    """
    rowIdentities = list(table._rowIdentities)
    columnIdentities = list(table._columnIdentities)
    held = table.rowCount if edit.rows else table.colCount
    identities = rowIdentities if edit.rows else columnIdentities
    if len(identities) != held:
        raise ReferenceError(
            f"{table.name!r} declares {held} {'rows' if edit.rows else 'columns'} and "
            f"identifies {len(identities)}, so which line is which cannot be told."
        )

    merges: list[MergeRange] = []
    for merge in table.mergeRanges:
        mergeMoved = mapMerge(merge, edit)
        if mergeMoved is not None:
            merges.append(mergeMoved)

    tables = (
        [table] if table.document is None
        else [other for sheet in table.document.sheets for other in sheet.tables]
    )
    formulas: dict[int, Formula] = {}
    conditions: dict[int, tuple[Formula, ...]] = {}
    broken: list[Cell] = []
    for host in tables:
        rows, columns = edit.axisMaps()
        change = FormulaRestructure(
            rows=rows,
            columns=columns,
            hostEdited=host is table,
            hostIdentity=host.identifier,
            targetTable=table.identifier,
            rowIdentities=rowIdentities,
            columnIdentities=columnIdentities,
        )
        for reference, cell in host.cells.items():
            if host is table and mapCell(reference, edit) is None:
                continue
            if host is table and cell._conditions:
                conditions[id(cell)] = tuple(
                    mapFormula(condition, reference, change)
                    for condition in cell._conditions
                )
            if cell.formula is None:
                continue
            rewritten = mapFormula(cell.formula, reference, change)
            if rewritten is cell.formula:
                continue
            formulas[id(cell)] = rewritten
            if countBrokenReferences(rewritten) > countBrokenReferences(cell.formula):
                broken.append(cell)

    carried = findMergeAnchorMoves(table, edit)
    cells: dict[CellReference, Cell] = {}
    for reference, cell in table.cells.items():
        moved = carried.get(reference) or mapCell(reference, edit)
        if moved is not None:
            cells[moved] = cell

    for host in tables:
        for cell in host.cells.values():
            if id(cell) in formulas:
                cell.formula = formulas[id(cell)]
            if id(cell) in conditions:
                cell._conditions = conditions[id(cell)]
    for reference, cell in cells.items():
        cell.reference = reference
    table.cells = cells
    table.mergeRanges = merges
    start = edit.at - 1
    if edit.removing:
        del identities[start:start + edit.count]
    else:
        identities[start:start] = generateLineIdentities(edit.count)
    if edit.rows:
        table._rowIdentities = identities
        table.rowCount = len(identities)
    else:
        table._columnIdentities = identities
        table.colCount = len(identities)
    return broken
