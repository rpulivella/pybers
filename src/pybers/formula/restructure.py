#!/usr/bin/env python3
"""A formula rewritten for rows or columns added to or removed from a table.

**A structural edit moves locked references too.** Locking pins a reference
against being dragged, not against the grid changing under it: inserting two rows
above row 2 turned `$A$1:$A$10` into `$A$1:$A$12` and `$A$8` into `$A$10`, measured
2026-09-18 in `56b-row-inserted`. Every reference is therefore resolved to real lines,
those lines are mapped, and the result is stored back in the form it came in.

**A range moves each end on its own**, which is what keeps `C3:C25` from losing
its first rows when a row goes in at 10. A reference whose lines are all removed
becomes `#REF!` and records the lines it lost, as Numbers does.

UPDATES
2026-10-29  A restructure walks the nodes through `mapFormulaNodes`, for PYB-278.
2026-09-21  Both axes follow a mapping, so several edits combined are followed
            too, which is what the archive half holds, for PYB-17.
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

from collections.abc import Sequence
from dataclasses import dataclass

from pybers.addressing.lines import LineMapping
from pybers.addressing.reference import CellAddress
from pybers.formula.nodes import (
    Coordinate,
    Formula,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FormulaReferenceLoss,
    Span,
    brokenReferenceNodeType,
    mapFormulaNodes,
)


@dataclass(frozen=True, slots=True)
class FormulaRestructure:
    """A structural change to one table, as a formula anywhere has to see it.

    `rows` and `columns` say where each line of the edited table lands, one edit
    or several combined. `hostEdited` says the formula lives in that table, and
    `targetTable` names it the way a reference does, so a local reference matches
    it only from inside. The identities are its lines before the change, which is
    what a broken reference records.
    """

    rows: LineMapping
    columns: LineMapping
    hostEdited: bool
    hostIdentity: str
    targetTable: str
    rowIdentities: Sequence[int]
    columnIdentities: Sequence[int]

    def targets(self, tableId: str | None) -> bool:
        """Report whether a reference naming this table reaches the edited one."""
        if tableId is None:
            return self.hostEdited
        return tableId == self.targetTable


def mapFormula(
    formula: Formula, host: CellAddress, change: FormulaRestructure
) -> Formula:
    """Return a formula whose references follow the edit, or the same one unchanged.

    `host` is where the formula sat before the edit.
    """
    return mapFormulaNodes(formula, lambda node: mapFormulaNode(node, host, change))


def mapFormulaNode(
    node: FormulaNode, host: CellAddress, change: FormulaRestructure
) -> FormulaNode:
    """Return one node following the edit, or the same node when nothing moves."""
    content = node.content
    if isinstance(content, FormulaReference) and not content.broken:
        moved: FormulaReference | FormulaRange | None = mapFormulaReference(
            content, host, change
        )
    elif isinstance(content, FormulaRange):
        moved = mapFormulaRange(content, host, change)
    else:
        return node
    if moved is content:
        return node
    if moved is None:
        return FormulaNode(
            brokenReferenceNodeType, findReferenceLoss(content, host, change)
        )
    # The bytes as read travel with it, so fields this model does not interpret
    # survive, the same as they survive a retarget.
    return FormulaNode(node.nodeType, moved, node.raw)


class LineLost:
    """The marker for a line an edit removed, as against one it left in place."""


lineLost: LineLost = LineLost()


def mapHostLine(line: int, lines: LineMapping, change: FormulaRestructure) -> int:
    """Return where the formula's own row or column lands."""
    if not change.hostEdited:
        return line
    moved = lines.lineMap(line)
    if moved is None:
        raise RuntimeError(
            f"Line {line} is removed, and a removed cell has no formula to move."
        )
    return moved


def mapCoordinate(
    coordinate: Coordinate | None,
    hostLine: int,
    lines: LineMapping,
    reaches: bool,
    change: FormulaRestructure,
) -> Coordinate | LineLost | None:
    """Return one axis of a reference after the change, or `lineLost`.

    The axis is resolved to a real line, that line is mapped when the reference
    reaches the changed table, and the result is stored in the form it came in.
    """
    if coordinate is None:
        return None
    target = coordinate.resolve(hostLine)
    if reaches:
        mapped = lines.lineMap(target)
        if mapped is None:
            return lineLost
        target = mapped
    newHost = mapHostLine(hostLine, lines, change)
    value = target if coordinate.absolute else target - newHost
    if value == coordinate.value:
        return coordinate
    return Coordinate(value, coordinate.absolute)


def mapFormulaReference(
    reference: FormulaReference, host: CellAddress, change: FormulaRestructure
) -> FormulaReference | None:
    """Return a single-cell reference after the change, None when its cell is gone."""
    reaches = change.targets(reference.tableId)
    column = mapCoordinate(reference.column, host.col, change.columns, reaches, change)
    row = mapCoordinate(reference.row, host.row, change.rows, reaches, change)
    if isinstance(column, LineLost) or isinstance(row, LineLost):
        return None
    if column is reference.column and row is reference.row:
        return reference
    return FormulaReference(column, row, reference.tableId)


def mapSpan(
    span: Span | None,
    hostLine: int,
    lines: LineMapping,
    reaches: bool,
    change: FormulaRestructure,
) -> Span | LineLost | None:
    """Return one axis of a range after the change, each end moving alone."""
    if span is None:
        return None
    begin, end = span.resolve(hostLine)
    if reaches:
        mapped = lines.spanMap(begin, end)
        if mapped is None:
            return lineLost
        begin, end = mapped
    shift = 0 if span.absolute else mapHostLine(hostLine, lines, change)
    # A span of one line omits its end, as `56g` stores the range it shrank to one.
    moved = Span(begin - shift, None if begin == end else end - shift, span.absolute)
    return span if moved == span else moved


def mapFormulaRange(
    extent: FormulaRange, host: CellAddress, change: FormulaRestructure
) -> FormulaRange | None:
    """Return a range after the change, None when it loses every line."""
    reaches = change.targets(extent.tableId)
    columns = mapSpan(extent.columns, host.col, change.columns, reaches, change)
    rows = mapSpan(extent.rows, host.row, change.rows, reaches, change)
    if isinstance(columns, LineLost) or isinstance(rows, LineLost):
        return None
    if columns is extent.columns and rows is extent.rows:
        return extent
    return FormulaRange(columns, rows, extent.tableId)


def findReferenceLoss(
    content: FormulaReference | FormulaRange,
    host: CellAddress,
    change: FormulaRestructure,
) -> FormulaReference:
    """Return the broken reference a lost one becomes, naming every line it covered.

    A broken range names its own table even from inside it, as `56c` wrote one. An
    axis the reference never named breaks as locked, as a whole-column rule's row
    did in `59-conditions-relative-column-a-deleted`.
    """
    if isinstance(content, FormulaRange):
        rows = findLineIdentities(content.rows, host.row, change.rowIdentities)
        columns = findLineIdentities(content.columns, host.col, change.columnIdentities)
        loss = FormulaReferenceLoss(
            columns, rows, True,
            content.columns is None or content.columns.absolute,
            content.rows is None or content.rows.absolute,
        )
        tableId = content.tableId or change.hostIdentity
        return FormulaReference(tableId=tableId, broken=True, loss=loss)
    rows = findLineIdentity(content.row, host.row, change.rowIdentities)
    columns = findLineIdentity(content.column, host.col, change.columnIdentities)
    loss = FormulaReferenceLoss(
        columns, rows, False,
        content.column is None or content.column.absolute,
        content.row is None or content.row.absolute,
    )
    return FormulaReference(tableId=content.tableId, broken=True, loss=loss)


# The identity a broken reference records for an axis it never named, as a
# whole-column highlighting rule recorded its row in
# `59-conditions-relative-column-a-deleted`.
unnamedLineIdentity: int = 0


def findLineIdentity(
    coordinate: Coordinate | None, hostLine: int, identities: Sequence[int]
) -> tuple[int, ...]:
    """Return the identity of the line a coordinate names, or a zero when unbounded."""
    if coordinate is None:
        return (unnamedLineIdentity,)
    return (identities[coordinate.resolve(hostLine) - 1],)


def findLineIdentities(
    span: Span | None, hostLine: int, identities: Sequence[int]
) -> tuple[int, ...]:
    """Return the identities of every line a span covers, or none when unbounded."""
    if span is None:
        return ()
    begin, end = span.resolve(hostLine)
    return tuple(identities[line - 1] for line in range(begin, end + 1))
