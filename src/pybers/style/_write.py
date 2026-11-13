#!/usr/bin/env python3
"""\
A cell's style composed as a variation, registered in its stylesheet, and pooled.

A variation keeps every property pybers does not model, a border stroke among them,
so replacing a cell's box leaves the rest of its style as it was. Cells whose
variations would match share one entry, as Numbers shares them. See
findings-09-cell-records.md.

Private. The archive half of the style feature.

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

from collections.abc import Sequence
from typing import Literal

from google.protobuf.message import Message

from pybers._generated import TSPMessages_pb2 as tsp
from pybers._generated import TSSArchives_pb2 as tss
from pybers._generated import TSTArchives_pb2 as tst
from pybers._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from pybers._persistence import decodeRecord
from pybers._persistence.cells import applySlotValue, cellStyleSlot, findSlotValue
from pybers._persistence.index import ArchiveIndex, generateUuid
from pybers._persistence.metadata import PackageRegistry, composeArchive
from pybers._persistence.pool import EntryPool
from pybers._persistence.types import findArchiveTypeId
from pybers.color._archive import composeColor
from pybers.color.colors import Color
from pybers.errors import WriteError
from pybers.style.cells import (
    CellStyle,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
)
from pybers.style.fills import FillNone

# A variation's identity in its table's pool: its parent and its serialized properties.
type CellStyleKey = tuple[int, bytes]

boxFields: tuple[
    Literal["cell_fill", "padding", "vertical_alignment", "text_wrap"], ...
] = ("cell_fill", "padding", "vertical_alignment", "text_wrap")
verticalAlignValues: frozendict[CellStyleVerticalAlign, int] = frozendict({
    CellStyleVerticalAlign.TOP: 0, CellStyleVerticalAlign.MIDDLE: 1,
    CellStyleVerticalAlign.BOTTOM: 2,
})


def addStyles(
    index: ArchiveIndex, registry: PackageRegistry, stylesheetId: int,
    styles: Sequence[tuple[int, Message]], children: Sequence[tuple[int, int]],
) -> None:
    """Register created styles in their stylesheet, each child under its parent."""
    stylesheet = index.resolve(
        tsp.Reference(identifier=stylesheetId), tss.StylesheetArchive
    )
    componentId = registry.componentRequire(stylesheetId)
    for identifier, body in styles:
        archive = composeArchive(identifier, body, weak={stylesheetId})
        registry.archiveAdd(componentId, archive, body)
        stylesheet.styles.add(identifier=identifier)
        registry.objectUuidAdd(componentId, identifier, generateUuid())
    for parent, child in children:
        entry = next(
            (
                entry for entry in stylesheet.parent_to_children_style_map
                if entry.parent.identifier == parent
            ),
            None,
        )
        if entry is None:
            entry = stylesheet.parent_to_children_style_map.add()
            entry.parent.identifier = parent
        entry.children.add(identifier=child)
    references = registry.strongReferencesOf(stylesheetId)
    references.extend(
        identifier for identifier, _ in styles if identifier not in references
    )
    registry.archiveReplace(stylesheetId, stylesheet, references)


def composeCellProperties(
    cellStyle: CellStyle, carried: tstStyles.CellStylePropertiesArchive
) -> tstStyles.CellStylePropertiesArchive:
    """Return a variation's properties: the box a cell asked for, the rest carried."""
    properties = tstStyles.CellStylePropertiesArchive()
    properties.CopyFrom(carried)
    for name in boxFields:
        properties.ClearField(name)
    match cellStyle.background:
        case None:
            pass
        case Color() as color:
            properties.cell_fill.color.CopyFrom(composeColor(color))
        case FillNone():
            properties.cell_fill.SetInParent()
        case other:
            raise WriteError(
                f"pybers cannot write a {other.fillType} fill, which it reads and "
                "carries but does not yet compose. Nothing was written."
            )
    padding = cellStyle.padding
    if isinstance(padding, tuple):
        raise WriteError(
            "A cell's padding is one length for every side, as Numbers offers it, "
            f"and was given {len(padding)} sides. Nothing was written."
        )
    if padding is not None:
        # Numbers omits a side of zero, as `31-style-inset-2pt` stores 0pt.
        side = float(padding)
        properties.padding.SetInParent()
        if side:
            box = properties.padding
            box.left = box.top = box.right = box.bottom = side
    if cellStyle.verticalAlign is not None:
        properties.vertical_alignment = verticalAlignValues[cellStyle.verticalAlign]
    if cellStyle.textWrap is not None:
        properties.text_wrap = cellStyle.textWrap is CellStyleTextWrap.WRAP
    return properties


def composeCellStyleArchive(
    stylesheetId: int, properties: tstStyles.CellStylePropertiesArchive,
    parent: int | None = None,
) -> tst.CellStyleArchive:
    """Return a cell style holding these properties, a variation of `parent` if given.

    The one place a cell style is composed. Its `override_count` is how many
    properties it states, since Numbers ignores the properties of a style whose count
    says it states none, as findings-06 measured.
    """
    style = tst.CellStyleArchive(override_count=len(properties.ListFields()))
    if parent is not None:
        style.super.parent.identifier = parent
        style.super.is_variation = True
    style.super.stylesheet.identifier = stylesheetId
    style.cell_properties.CopyFrom(properties)
    return style


def readStylePool(
    index: ArchiveIndex, registry: PackageRegistry, store: tst.DataStore
) -> EntryPool[CellStyleKey]:
    """Return a table's `styleTable`, each cell style variation stored by its identity.

    A paragraph style is counted and never stored, so no cell style shares one.
    """
    dataList = index.resolve(store.styleTable, tst.TableDataList)
    cellStyleType = findArchiveTypeId(tst.CellStyleArchive)
    stored: dict[int, CellStyleKey] = {}
    for entry in dataList.entries:
        if index.typeOf(entry.reference) != cellStyleType:
            continue
        style = index.resolve(entry.reference, tst.CellStyleArchive)
        if style.super.is_variation:
            stored[int(entry.key)] = (
                int(style.super.parent.identifier),
                style.cell_properties.SerializeToString(deterministic=True),
            )

    def writeEntry(entry: tst.TableDataList.ListEntry, key: CellStyleKey) -> None:
        """Point an entry at a new variation holding the properties `key` serializes."""
        parent, serialized = key
        parentStyle = index.identifierResolve(parent, tst.CellStyleArchive)
        stylesheetId = int(parentStyle.super.stylesheet.identifier)
        properties = tstStyles.CellStylePropertiesArchive.FromString(serialized)
        identifier = registry.identifierAllocate()
        addStyles(
            index, registry, stylesheetId,
            [(identifier, composeCellStyleArchive(stylesheetId, properties, parent))],
            [(parent, identifier)],
        )
        entry.reference.identifier = identifier

    return EntryPool(dataList=dataList, noun="style", write=writeEntry, stored=stored)


def writeStylePool(
    index: ArchiveIndex, registry: PackageRegistry, store: tst.DataStore,
    pool: EntryPool[CellStyleKey],
) -> None:
    """Write a table's style list, declaring each style it names.

    Numbers loads no style its list leaves undeclared, so it drew none of the fills
    pybers wrote until the list declared them, as `99` showed.
    """
    identifier = store.styleTable.identifier
    declared = registry.referencesReconcile(identifier, pool.dataList)
    index.archiveWrite(identifier, pool.dataList, declared)


def applyCellStyle(
    index: ArchiveIndex, pool: EntryPool[CellStyleKey], raw: bytes,
    asked: CellStyle | None, parent: int,
) -> bytes:
    """Return a record naming a variation of `parent` for the box asked, or none.

    The box replaces the one the record's style holds, every other property carried.
    A record left stating nothing names no style.
    """
    previous = findSlotValue(decodeRecord(0, raw), cellStyleSlot)
    entry = None if previous is None else pool.entryFind(previous)
    carried = tstStyles.CellStylePropertiesArchive()
    if entry is not None:
        carried.CopyFrom(
            index.resolve(entry.reference, tst.CellStyleArchive).cell_properties
        )
    properties = composeCellProperties(asked or CellStyle(), carried)
    if not properties.ListFields():
        if previous is not None:
            pool.release(previous)
        return applySlotValue(raw, cellStyleSlot, None)
    key = pool.keyFor(
        (parent, properties.SerializeToString(deterministic=True)), previous
    )
    return applySlotValue(raw, cellStyleSlot, key)


__all__ = [
    "CellStyleKey",
    "addStyles",
    "applyCellStyle",
    "composeCellProperties",
    "composeCellStyleArchive",
    "readStylePool",
    "writeStylePool",
]
