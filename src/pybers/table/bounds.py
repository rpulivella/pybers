#!/usr/bin/env python3
"""\
A range checked against a table's declared grid, before any cell is touched.

Its own module so that copying, filling and moving import it at the top: the table
needs these too, and reaching them through `cells` made each a cycle.

UPDATES
2026-11-03  `findCellsMiss`, the one rule for whether a table holds a cell or a
            range, for PYB-223.
2026-10-27  A whole row or column is checked on its bounded axis, and a range
            naming another table refused, for PYB-260.
2026-10-14  Moved here from `cells.py`, for PYB-193.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/14"

from typing import TYPE_CHECKING

from pybers.addressing.ranges import CellRange, CellRangeLike, toCellRanges
from pybers.addressing.reference import CellAddress, ReferenceError

if TYPE_CHECKING:
    from pybers.table.cells import Table


def listRangePositions(table: Table, address: CellRangeLike) -> list[CellAddress]:
    """Return the positions ranges cover, checking every range before returning any."""
    extent = table.extent
    items = []
    for named in toCellRanges(address):
        item = table._rangeResolve(named)
        if item.rowsUnbounded or item.colsUnbounded:
            if extent is None:
                continue
            item = item.boundedBy(extent)
        refuseRangeOutside(table, item)
        items.append(item)
    return [
        position for item in items for position in item if table.addressable(position)
    ]


def findCellsMiss(table: Table, cells: CellAddress | CellRange) -> str | None:
    """Return why a table holds no such cell or range, or None when it does.

    The one place that decides it, for a selection, `table.cell` and a move alike. A
    whole row or column is bounded by the grid first, so only its bounded axis can
    reach outside, and a position a merge covers is no cell.
    """
    extent = table.extent
    rows = "row" if table.rowCount == 1 else "rows"
    columns = "column" if table.colCount == 1 else "columns"
    size = f"{table.rowCount} {rows} by {table.colCount} {columns}"
    if isinstance(cells, CellAddress):
        if extent is None or not extent.covers(cells):
            return f"{cells} is outside {table.name!r}, which is {size}."
        merge = table.mergeCovering(cells)
        if merge is not None and merge.anchor != cells:
            return (
                f"{cells} is covered by the merge {merge.extent}, whose anchor is "
                f"{merge.anchor}."
            )
        return None
    bounded = cells if extent is None else cells.boundedBy(extent)
    if extent is None or not all(
        corner is not None and extent.covers(corner)
        for corner in (bounded.start, bounded.end)
    ):
        return f"{cells} reaches outside {table.name!r}, which is {size}."
    return None


def refuseRangeOutside(table: Table, item: CellRange) -> None:
    """Refuse a range with a corner outside a table's declared grid."""
    miss = findCellsMiss(table, item)
    if miss is not None:
        raise ReferenceError(miss)
