#!/usr/bin/env python3
"""\
A range checked against a table's declared grid, before any cell is touched.

Its own module so that copying, filling and moving import it at the top: the table
needs these too, and reaching them through `cells` made each a cycle.

UPDATES
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
from pybers.addressing.reference import CellReference, ReferenceError

if TYPE_CHECKING:
    from pybers.table.cells import Table


def listRangePositions(table: Table, address: CellRangeLike) -> list[CellReference]:
    """Return the positions ranges cover, checking every range before returning any."""
    extent = table.extent
    items = []
    for item in toCellRanges(address):
        if item.rowsUnbounded or item.colsUnbounded:
            if extent is None:
                continue
            item = item.boundedBy(extent)
        refuseRangeOutside(table, item)
        items.append(item)
    return [
        reference.asUnlocked() for item in items for reference in item
        if table.addressable(reference)
    ]


def refuseRangeOutside(table: Table, item: CellRange) -> None:
    """Refuse a bounded range with a corner outside a table's declared grid."""
    extent = table.extent
    if extent is None or not all(
        corner is not None and extent.covers(corner)
        for corner in (item.start, item.end)
    ):
        raise ReferenceError(
            f"{item} reaches outside {table.name!r}, which is {table.rowCount} "
            f"rows by {table.colCount} columns."
        )
