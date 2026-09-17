#!/usr/bin/env python3
"""\
Every reference a document's formulas make, as places rather than as values.

A walk over `Document.cellsIterate` finds the cells; this finds the references
inside them. A reference is one node of a postfix array, so nothing shorter than
a cell and a node position identifies which one a caller means when a formula
holds four.

**A location is a view, not a copy.** It names a cell and a node position and reads
the reference through them, so shifting one writes back to the cell that holds it
and a second location on the same formula sees the result. Copying the reference out
would give a caller something to edit that nothing would ever store.

**Every location has a target, and a table-local reference targets its own table.**
Reporting `None` for the local case would put an `if` in every loop that filters
by table, and the answer it would be hiding is one this already knows.

UPDATES
2026-09-08  Written for #13.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import cast

from pybers.document.sheets import Document, SelectionError, Sheet
from pybers.formula.nodes import (
    Formula,
    FormulaError,
    FormulaNode,
    FormulaRange,
    FormulaReference,
)
from pybers.formula.render import addressText, shortestNames
from pybers.table.cells import Cell, Table


@dataclass(frozen=True, slots=True)
class ReferenceLocation:
    """One reference inside one cell's formula, and the table it points at.

    A live view: `content` is read from the cell every time and `shift` writes
    back through it. `sheet` and `table` are where the formula lives, `target` is
    the table it points into, which for a table-local reference is `table` again.
    """

    cell: Cell
    index: int
    sheet: Sheet
    table: Table
    target: Table

    @property
    def content(self) -> FormulaReference | FormulaRange:
        """The reference as it stands now, read from the cell rather than copied."""
        return cast("FormulaReference | FormulaRange", self.node.content)

    @property
    def node(self) -> FormulaNode:
        """The formula node this location names, raising when it no longer holds one."""
        formula = self.cell.formula
        node = (
            None
            if formula is None or self.index >= len(formula)
            else formula.nodes[self.index]
        )
        if node is None or not isinstance(
            node.content, FormulaReference | FormulaRange
        ):
            raise FormulaError(
                f"Node {self.index} of {self.cell.reference} is no longer the "
                "reference this location names. A location views a formula rather than "
                "holding one, so replacing that formula invalidates it."
            )
        return node

    @property
    def crossTable(self) -> bool:
        """Report whether this reference points outside the table holding it."""
        return self.content.crossTable

    @property
    def broken(self) -> bool:
        """Report whether this reference points nowhere, which Numbers shows as #REF."""
        content = self.content
        return isinstance(content, FormulaReference) and content.broken

    @property
    def text(self) -> str:
        """This reference as Numbers spells it, `Table 2::A1`, qualified as needed."""
        return addressText(
            self.node, self.cell.reference, shortestNames(self.cell.tableNames)
        )

    def shift(self, *, rows: int = 0, cols: int = 0) -> bool:
        """Move what this reference points at, and report whether anything moved.

        It reports False and writes nothing when there was nothing to move: a
        broken reference, a locked axis, an unbounded one, or a shift of zero.
        Each location moves alone, so an interrupted walk leaves what it reached
        correct.
        """
        node = self.node
        content = self.content
        moved = content.shifted(rows=rows, cols=cols)
        if moved is content:
            return False
        formula = self.cell.formula
        assert formula is not None
        nodes = list(formula.nodes)
        # The bytes as read travel with it, so a node carrying fields this model
        # does not interpret survives a shift the same as it survives a rewrite.
        nodes[self.index] = FormulaNode(node.nodeType, moved, node.raw)
        self.cell.formula = Formula(tuple(nodes))
        return True


def tablesByIdentity(document: Document) -> dict[str, Table]:
    """Return every table in a document, keyed by what a formula names it by.

    A table built by hand has no identity until a document gives it one, and one
    that has none is left out rather than filed under the empty string.
    """
    return {
        table.identifier: table
        for sheet in document.sheets
        for table in sheet.tables
        if table.identifier
    }


def targetFor(
    content: FormulaReference | FormulaRange,
    host: Table,
    tables: Mapping[str, Table],
) -> Table:
    """Return the table a reference points into, the host's own when it is local."""
    if content.tableId is None:
        return host
    target = tables.get(content.tableId)
    if target is None:
        raise SelectionError(
            f"A formula in {host.name!r} reaches into table {content.tableId}, "
            "which this document does not hold."
        )
    return target


def iterateReferences(document: Document) -> Iterator[ReferenceLocation]:
    """Yield a location for every reference and every range in every formula."""
    tables = tablesByIdentity(document)
    for sheet, table, cell in document.cellsIterate():
        formula = cell.formula
        if formula is None:
            continue
        for index, node in enumerate(formula.nodes):
            content = node.content
            if not isinstance(content, FormulaReference | FormulaRange):
                continue
            yield ReferenceLocation(
                cell, index, sheet, table, targetFor(content, table, tables)
            )


__all__ = [
    "ReferenceLocation",
    "iterateReferences",
    "tablesByIdentity",
    "targetFor",
]
