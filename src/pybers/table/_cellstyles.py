#!/usr/bin/env python3
"""\
A table's cell styles: what each region's style resolves to, and a cell's written.

A cell's style is a variation of the style of its region, the corner taking the
higher region, as findings-03-structure.md measured in `40-table-bands`. A variation
never inherits from a variation, so where the region's style is one, as a table pybers
creates holds, the cell's inherits from the first style that is not, its region's
properties copied in, as `99-cell-fill-in-a-created-table` measured.

Private. Part of the table feature's archive half.

UPDATES
2026-11-13  A cell's variation inherits from its region's first non-variation
            style, for PYB-265.
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

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .._generated import TSTArchives_pb2 as tst
from .._persistence.index import ArchiveIndex
from .._persistence.pool import EntryPool
from ..absence import UNCHANGED
from ..style._read import readCellStyle, readInheritedCellStyle
from ..style._write import CellStyleKey, applyCellStyle
from ..style.cells import CellStyle, findOverrides
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


@dataclass(frozen=True, slots=True)
class RegionVariation:
    """A region's style as a cell's variation sees it: its root and what it copies."""

    root: int
    copied: CellStyle


def readRegionVariations(
    index: ArchiveIndex, model: tst.TableModelArchive
) -> frozendict[TableRegion, RegionVariation]:
    """Return each region's first non-variation style and what its variations state."""
    found = {}
    for region, slot in regionStyleSlots.items():
        if not model.HasField(slot):
            continue
        identifier = int(getattr(model, slot).identifier)
        stated: list[CellStyle] = []
        archive = index.identifierResolve(identifier, tst.CellStyleArchive)
        while archive.super.is_variation:
            stated.append(readCellStyle(archive))
            identifier = int(archive.super.parent.identifier)
            archive = index.identifierResolve(identifier, tst.CellStyleArchive)
        found[region] = RegionVariation(identifier, mergeCellStyles(*stated))
    return frozendict(found)


def mergeCellStyles(*styles: CellStyle) -> CellStyle:
    """Return one style stating each property the first of `styles` to state it does."""
    return CellStyle(
        background=next((each.background for each in styles if each.background), None),
        padding=next(
            (each.padding for each in styles if each.padding is not None), None
        ),
        verticalAlign=next(
            (each.verticalAlign for each in styles if each.verticalAlign), None
        ),
        textWrap=next((each.textWrap for each in styles if each.textWrap), None),
    )


def readOwnCellStyles(
    cellStyles: Mapping[int, CellStyle],
    variations: Mapping[TableRegion, RegionVariation],
) -> frozendict[TableRegion, Mapping[int, CellStyle]]:
    """Return each region's cell styles less what they copy from its variation.

    A region whose style is no variation hands back the very styles read, so every
    cell naming one archive keeps one object.
    """
    return frozendict({
        region: cellStyles if variation.copied == CellStyle() else {
            key: findOverrides(stated, variation.copied) or CellStyle()
            for key, stated in cellStyles.items()
        }
        for region, variation in variations.items()
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
    variation = readRegionVariations(index, model)[region]
    copied = None if asked is None else mergeCellStyles(asked, variation.copied)
    return applyCellStyle(index, pool, raw, copied, variation.root)


__all__ = [
    "RegionVariation", "mergeCellStyles", "readOwnCellStyles", "readRegionCellStyles",
    "readRegionVariations", "regionStyleSlots", "writeAskedCellStyle",
]
