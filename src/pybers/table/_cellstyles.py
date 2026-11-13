#!/usr/bin/env python3
"""\
A table's cell styles: what each region's style resolves to, and a cell's written.

A cell's style is a variation of the style of its region, the corner taking the
higher region, as findings-03-structure.md measured in `40-table-bands`.

Private. Part of the table feature's archive half.

UPDATES
2026-11-12  Written for PYB-265.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/12"

from typing import TYPE_CHECKING, Literal

from .._generated import TSTArchives_pb2 as tst
from .._persistence.index import ArchiveIndex
from .._persistence.pool import EntryPool
from ..absence import UNCHANGED
from ..style._read import readInheritedCellStyle
from ..style._write import CellStyleKey, applyCellStyle
from ..style.cells import CellStyle
from .headers import TableRegion

if TYPE_CHECKING:
    from .cell import Cell
    from .cells import Table

type RegionStyleSlot = Literal[
    "body_cell_style", "header_row_style", "header_column_style", "footer_row_style"
]

# The table model's cell style slot each region inherits from.
regionStyleSlots: frozendict[TableRegion, RegionStyleSlot] = frozendict({
    TableRegion.BODY: "body_cell_style",
    TableRegion.HEADER_ROW: "header_row_style",
    TableRegion.HEADER_COLUMN: "header_column_style",
    TableRegion.FOOTER_ROW: "footer_row_style",
})


def readRegionCellStyles(
    index: ArchiveIndex, model: tst.TableModelArchive
) -> frozendict[TableRegion, CellStyle]:
    """Return what each region's cell style resolves to, for the regions it names."""
    return frozendict({
        region: readInheritedCellStyle(index, getattr(model, slot).identifier)
        for region, slot in regionStyleSlots.items()
        if model.HasField(slot)
    })


def writeAskedCellStyle(
    index: ArchiveIndex, pool: EntryPool[CellStyleKey], model: tst.TableModelArchive,
    table: Table, raw: bytes, cell: Cell,
) -> bytes:
    """Return a record naming the cell style its cell asked for, or as it was."""
    asked = cell._cellStyleAsked
    if asked is UNCHANGED:
        return raw
    region = table.headers.regionFind(cell.address, table.rowCount)
    return applyCellStyle(
        index, pool, raw, asked,
        int(getattr(model, regionStyleSlots[region]).identifier),
    )


__all__ = [
    "readRegionCellStyles", "regionStyleSlots", "writeAskedCellStyle",
]
