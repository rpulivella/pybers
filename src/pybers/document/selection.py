#!/usr/bin/env python3
"""\
The sheet, table, range or cell a selector names, read the way `pybers set` reads one.

A selector is one to three names joined by `::`, the last of them a cell or a range
when it reads as one. Every reading that could hold is tried widest first, a sheet
before a table and a table before its cells, so each narrower part stays reachable by
naming more of its path. A selector naming nothing is refused by the call that would
have found it, so its message lists what the document holds, as every other refusal
of a name does.

UPDATES
2026-10-27  Written for PYB-260.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/27"

from dataclasses import replace

from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import (
    CellReference,
    ReferenceError,
    tableNameSeparator,
)
from pybers.document.sheets import Document, SelectionError, Sheet, listPresent
from pybers.table.bounds import refuseRangeOutside
from pybers.table.cell import Cell
from pybers.table.cells import Table

# The parts a selector names, widest first, for a refusal saying how one reads.
selectorForms: str = "`Sheet 1`, `Table 1`, `Table 1::B3:D9` or `Sheet 1::Table 1::B3`"


def selectPart(document: Document, selector: str) -> Sheet | Table | CellRange | Cell:
    """Return the sheet, table, range or cell a selector names, or refuse it."""
    match selector.strip().split(tableNameSeparator):
        case [name]:
            return selectNamed(document, name)
        case [first, second]:
            return selectPair(document, first, second)
        case [sheetName, tableName, cellsText]:
            table = document.sheet(sheetName).table(tableName)
            cells = readCells(cellsText) or CellRange.parse(cellsText)
            return selectCells(table, cells)
    raise SelectionError(
        f"{selector!r} names more than a sheet, a table and its cells. A selector "
        f"reads {selectorForms}."
    )


def selectNamed(document: Document, name: str) -> Sheet | Table:
    """Return the sheet a name names, or else the one table it names."""
    sheet = document._sheetFind(name)
    if sheet is not None:
        return sheet
    table = document._tableFind(name)
    if table is not None:
        return table
    if readCells(name) is not None:
        raise SelectionError(
            f"{name} names no table. A selector reads `Table 1::{name}` or "
            f"`Sheet 1::Table 1::{name}`."
        )
    sheetNames = [each.name for each in document.sheets]
    raise SelectionError(
        f"No sheet or table in this document is named {name!r}. "
        f"{listPresent('sheet', sheetNames)} "
        f"{listPresent('table', document._tableNamesList())}"
    )


def selectPair(
    document: Document, first: str, second: str
) -> Table | CellRange | Cell:
    """Return the table a sheet and a name name, or else the cells of a named table."""
    sheet = document._sheetFind(first)
    table = None if sheet is None else sheet._tableFind(second)
    if table is not None:
        return table
    cells = readCells(second)
    if cells is None:
        return (document.sheet(first) if sheet is None else sheet).table(second)
    table = document._tableFind(first)
    if table is not None:
        return selectCells(table, cells)
    if sheet is not None:
        raise SelectionError(
            f"{first}{tableNameSeparator}{second} names a sheet and its cells, and a "
            f"sheet holds only tables. "
            f"{listPresent('table', [each.name for each in sheet.tables])}"
        )
    return selectCells(document._tableRequire(first), cells)


def readCells(text: str) -> CellReference | CellRange | None:
    """Return the cell or the range text names, or None when it names neither."""
    for parse in (CellReference.parse, CellRange.parse):
        try:
            return parse(text)
        except ReferenceError:
            continue
    return None


def selectCells(table: Table, cells: CellReference | CellRange) -> CellRange | Cell:
    """Return one cell of a table, or a range of it naming the table and its sheet."""
    if isinstance(cells, CellReference):
        return table.cell(cells)
    refuseRangeOutside(table, cells)
    return replace(cells, table=table.reference)


__all__ = ["selectPart"]
