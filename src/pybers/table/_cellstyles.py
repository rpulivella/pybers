#!/usr/bin/env python3
"""\
A table's cell styles: what each section's style resolves to, and a cell's written.

A cell's style is a variation of the style of its section, the corner taking the
higher section, as findings-03-structure.md measured in `40-table-bands`. A variation
never inherits from a variation, so where the section's style is one, as a table pybers
creates holds, the cell's inherits from the first style that is not, its section's
properties copied in, as `99-cell-fill-in-a-created-table` measured.

Private. Part of the table feature's archive half.

UPDATES
2026-11-20  `writeSectionCellStyles`, a changed section box written as a variation
            for that table alone, its cells' copies rewritten, for PYB-291.
2026-11-20  Each section's box read by its `TableStyle` field, from a table or a
            theme's preset, for PYB-291.
2026-11-19  `updateCellStyles` moved to the style model, for PYB-290.
2026-11-19  A table's parts are sections, for PYB-301.
2026-11-18  Combining styles is an update, for PYB-290.
2026-11-13  A cell's variation inherits from its section's first non-variation
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
from .._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from .._persistence.index import ArchiveIndex
from .._persistence.metadata import PackageRegistry
from .._persistence.pool import EntryPool
from ..absence import UNCHANGED
from ..style._read import readCellStyle, readInheritedCellStyle
from ..style._write import (
    CellStyleKey,
    addStyles,
    applyCellStyle,
    composeCellProperties,
    composeCellStyleArchive,
)
from ..style.cells import CellStyle, findOverrides, numbersCellStyle, updateCellStyles
from .headers import TableSection
from .tablestyle import sectionCellStyleFields

if TYPE_CHECKING:
    from .cell import Cell
    from .cells import Table

type SectionStyleSlot = Literal[
    "body_cell_style", "header_row_style", "header_column_style", "footer_row_style"
]

# The table model's cell style slot each section inherits from.
sectionStyleSlots: frozendict[TableSection, SectionStyleSlot] = frozendict({
    TableSection.BODY: "body_cell_style",
    TableSection.HEADER_ROW: "header_row_style",
    TableSection.HEADER_COLUMN: "header_column_style",
    TableSection.FOOTER_ROW: "footer_row_style",
})


def readSectionCellStyles(
    index: ArchiveIndex, holder: tst.TableModelArchive | tst.TableStyleNetworkArchive
) -> dict[str, CellStyle]:
    """Return the box each section's cells inherit, by its `TableStyle` field.

    A table's model and a theme's table preset name the same four slots, and a slot
    left empty shows Numbers' own box.
    """
    return {
        sectionCellStyleFields[section]: (
            readInheritedCellStyle(index, getattr(holder, slot).identifier)
            if holder.HasField(slot) else numbersCellStyle
        )
        for section, slot in sectionStyleSlots.items()
    }


@dataclass(frozen=True, slots=True)
class SectionVariation:
    """A section's style as a cell's variation sees it: its root and what it copies."""

    root: int
    copied: CellStyle


def readSectionVariations(
    index: ArchiveIndex, model: tst.TableModelArchive
) -> frozendict[TableSection, SectionVariation]:
    """Return each section's first non-variation style and what its variations state."""
    found = {}
    for section, slot in sectionStyleSlots.items():
        if not model.HasField(slot):
            continue
        identifier = int(getattr(model, slot).identifier)
        stated: list[CellStyle] = []
        archive = index.identifierResolve(identifier, tst.CellStyleArchive)
        while archive.super.is_variation:
            stated.append(readCellStyle(archive))
            identifier = int(archive.super.parent.identifier)
            archive = index.identifierResolve(identifier, tst.CellStyleArchive)
        found[section] = SectionVariation(identifier, updateCellStyles(*stated))
    return frozendict(found)


def readOwnCellStyles(
    cellStyles: Mapping[int, CellStyle],
    variations: Mapping[TableSection, SectionVariation],
) -> frozendict[TableSection, Mapping[int, CellStyle]]:
    """Return each section's cell styles less what they copy from its variation.

    A section whose style is no variation hands back the very styles read, so every
    cell naming one archive keeps one object.
    """
    return frozendict({
        section: cellStyles if variation.copied == CellStyle() else {
            key: findOverrides(stated, variation.copied) or CellStyle()
            for key, stated in cellStyles.items()
        }
        for section, variation in variations.items()
    })


def writeAskedCellStyle(
    index: ArchiveIndex, pool: EntryPool[CellStyleKey],
    variations: Mapping[TableSection, SectionVariation], table: Table, raw: bytes,
    cell: Cell,
) -> bytes:
    """Return a record naming the cell style its cell asked for, or as it was."""
    asked = cell._cellStyleAsked
    if asked is UNCHANGED:
        return raw
    variation = variations[table.headers.sectionFind(cell.address, table.rowCount)]
    copied = None if asked is None else updateCellStyles(asked, variation.copied)
    return applyCellStyle(index, pool, raw, copied, variation.root)


def writeSectionCellStyles(
    index: ArchiveIndex, registry: PackageRegistry, modelId: int,
    model: tst.TableModelArchive, table: Table,
) -> None:
    """Point each section whose box changed at a variation stating it, and restyle.

    A new variation of the section's first non-variation style, never an edit in
    place, since Numbers shares a section's style between tables. Each cell stating
    its own style copies its section's properties, as `98c-cell-box-regions`
    measured, so every such cell in a changed section is written again.
    """
    held = readSectionCellStyles(index, model)
    variations = readSectionVariations(index, model)
    changed: set[TableSection] = set()
    for section, slot in sectionStyleSlots.items():
        field = sectionCellStyleFields[section]
        wanted: CellStyle = getattr(table.tableStyle, field)
        if held[field] == wanted or section not in variations:
            continue
        changed.add(section)
        rootId = variations[section].root
        root = index.identifierResolve(rootId, tst.CellStyleArchive)
        current = index.identifierResolve(
            int(getattr(model, slot).identifier), tst.CellStyleArchive
        )
        overrides = findOverrides(wanted, readInheritedCellStyle(index, rootId))
        if overrides is None:
            getattr(model, slot).identifier = rootId
            continue
        carried = (
            current.cell_properties if current.super.is_variation
            else tstStyles.CellStylePropertiesArchive()
        )
        stylesheetId = int(root.super.stylesheet.identifier)
        identifier = registry.identifierAllocate()
        variation = composeCellStyleArchive(
            stylesheetId, composeCellProperties(overrides, carried), parent=rootId
        )
        addStyles(index, registry, stylesheetId, [(identifier, variation)],
                  [(rootId, identifier)])
        getattr(model, slot).identifier = identifier
    if not changed:
        return
    index.archiveWrite(modelId, model, registry.referencesReconcile(modelId, model))
    for address, cell in table.cells.items():
        section = table.headers.sectionFind(address, table.rowCount)
        if section in changed and cell._cellStyleAsked is UNCHANGED:
            cell._cellStyleAsked = cell.cellStyle


__all__ = [
    "SectionVariation", "readOwnCellStyles", "writeSectionCellStyles",
    "readSectionCellStyles", "readSectionVariations", "sectionStyleSlots",
    "writeAskedCellStyle",
]
