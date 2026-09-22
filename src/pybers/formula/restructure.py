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

from pybers.addressing.lines import GridEdit
from pybers.addressing.reference import CellReference
from pybers.formula.nodes import (
    Coordinate,
    Formula,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FormulaReferenceLoss,
    Span,
    brokenReferenceNodeType,
)


@dataclass(frozen=True, slots=True)
class FormulaRestructure:
    """One structural edit, as a formula anywhere in the document has to see it.

    `hostEdited` says the formula lives in the edited table, and `targetTable`
    names that table the way a reference does, so a local reference matches it
    only from inside. The identities are the edited table's lines
    before the edit, which is what a broken reference records.
    """

    edit: GridEdit
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
    formula: Formula, host: CellReference, change: FormulaRestructure
) -> Formula:
    """Return a formula whose references follow the edit, or the same one unchanged.

    `host` is where the formula sat before the edit.
    """
    nodes = [mapFormulaNode(node, host, change) for node in formula.nodes]
    if all(new is old for new, old in zip(nodes, formula.nodes, strict=True)):
        return formula
    return Formula(tuple(nodes))


def mapFormulaNode(
    node: FormulaNode, host: CellReference, change: FormulaRestructure
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


def mapHostLine(line: int, change: FormulaRestructure) -> int:
    """Return where the formula's own row or column lands."""
    if not change.hostEdited:
        return line
    moved = change.edit.lineMap(line)
    if moved is None:
        raise RuntimeError(
            f"Line {line} is removed, and a removed cell has no formula to move."
        )
    return moved


def mapFormulaReference(
    reference: FormulaReference, host: CellReference, change: FormulaRestructure
) -> FormulaReference | None:
    """Return a single-cell reference after the edit, None when its cell is gone."""
    edit = change.edit
    coordinate = reference.row if edit.rows else reference.column
    if coordinate is None:
        return reference
    hostLine = host.row if edit.rows else host.col
    target = coordinate.resolve(hostLine)
    if change.targets(reference.tableId):
        mapped = edit.lineMap(target)
        if mapped is None:
            return None
        target = mapped
    newHost = mapHostLine(hostLine, change)
    value = target if coordinate.absolute else target - newHost
    if value == coordinate.value:
        return reference
    moved = Coordinate(value, coordinate.absolute)
    if edit.rows:
        return FormulaReference(reference.column, moved, reference.tableId)
    return FormulaReference(moved, reference.row, reference.tableId)


def mapFormulaRange(
    extent: FormulaRange, host: CellReference, change: FormulaRestructure
) -> FormulaRange | None:
    """Return a range after the edit, each end moving alone, None when all is gone."""
    edit = change.edit
    span = extent.rows if edit.rows else extent.columns
    if span is None:
        return extent
    hostLine = host.row if edit.rows else host.col
    begin, end = span.resolve(hostLine)
    if change.targets(extent.tableId):
        mapped = edit.spanMap(begin, end)
        if mapped is None:
            return None
        begin, end = mapped
    newHost = mapHostLine(hostLine, change)
    shift = 0 if span.absolute else newHost
    # A span of one line omits its end, as `56g` stores the range it shrank to one.
    moved = Span(
        begin - shift, None if begin == end else end - shift, span.absolute
    )
    if moved == span:
        return extent
    if edit.rows:
        return FormulaRange(extent.columns, moved, extent.tableId)
    return FormulaRange(moved, extent.rows, extent.tableId)


def findReferenceLoss(
    content: FormulaReference | FormulaRange,
    host: CellReference,
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
