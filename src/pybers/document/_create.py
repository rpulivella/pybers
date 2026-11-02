#!/usr/bin/env python3
"""\
Create the archives of a sheet the model gained, and register them.

A created sheet is composed field by field in the pybers reset: printed 1:1 with
autofit off, margins of 72 pt top and bottom and 54 pt left and right, and six empty
headers and footers, since Numbers rebuilding them puts a page number in the center
footer. Its background is the document's own sheet style, because Numbers can make no
sheet without one. Numbers rebuilds its guides. See docs/decisions.md and
findings-10-creation.md.

UPDATES
2026-11-02  Composed field by field rather than copied from a template, and the
            guides left for Numbers to rebuild, for PYB-276.
2026-09-22  A random UUID comes from the index module, shared with table creation, for
            PYB-113.
2026-09-22  Type identifiers are asked of the registry by class, for PYB-113.
2026-09-22  Created on the save's one index, for PYB-109.
2026-09-14  Written for PYB-63.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/14"

from dataclasses import dataclass

from .._generated import TNArchives_pb2 as tn
from .._generated import TSKArchives_pb2 as tsk
from .._generated import TSWPArchives_pb2 as tswp
from .._persistence.index import ArchiveIndex, findRoot, generateUuid
from .._persistence.metadata import (
    PackageRegistry,
    composeArchive,
    documentComponentId,
)
from .._persistence.types import findArchiveTypeId
from ..errors import WriteError
from .sheets import Document, Sheet

# The reset's page setup, see docs/decisions.md.
marginTopBottom: float = 72.0
marginLeftRight: float = 54.0
headerFooterInset: float = 18.0
headerFooterCount: int = 3


@dataclass(frozen=True, slots=True)
class SheetStyles:
    """The document's sheet style, and the text styles its headers name."""

    sheet: int
    stylesheet: int
    paragraph: int
    listStyle: int


def findSheetStyles(index: ArchiveIndex, root: tn.DocumentArchive) -> SheetStyles:
    """Return the styles the first sheet already uses, which a created sheet shares."""
    if not root.sheets:
        raise WriteError("This document holds no sheet to take styles from.")
    first = index.resolve(root.sheets[0], tn.SheetArchive)
    if not first.headers:
        raise WriteError(
            f"{first.name!r} carries no header storage to take text styles from."
        )
    header = index.resolve(first.headers[0], tswp.StorageArchive)
    if not header.table_para_style.entries or not header.table_list_style.entries:
        raise WriteError(
            f"The header storage of {first.name!r} names no paragraph or list style."
        )
    return SheetStyles(
        sheet=first.style.identifier,
        stylesheet=header.style_sheet.identifier,
        paragraph=header.table_para_style.entries[0].object.identifier,
        listStyle=header.table_list_style.entries[0].object.identifier,
    )


def composeStorage(styles: SheetStyles) -> tswp.StorageArchive:
    """Return an empty header or footer, as `49-sheet-inserted` holds one.

    Every one is of kind HEADER, footers included, as Numbers writes them.
    """
    storage = tswp.StorageArchive(kind=tswp.StorageArchive.HEADER, in_document=True)
    storage.style_sheet.identifier = styles.stylesheet
    storage.table_para_style.entries.add(character_index=0).object.identifier = (
        styles.paragraph
    )
    storage.table_list_style.entries.add(character_index=0).object.identifier = (
        styles.listStyle
    )
    for table in (
        storage.table_para_data, storage.table_para_starts, storage.table_para_bidi
    ):
        table.entries.add(character_index=0, first=0, second=0)
    return storage


def composeSheet(
    name: str, styles: SheetStyles, headers: list[int], footers: list[int]
) -> tn.SheetArchive:
    """Return a sheet in the reset's page setup, naming its headers and footers.

    `is_autofit_on` and `show_page_numbers` are stated although false, since Numbers
    reads either absent as true. Measured 2026-11-02, findings-10-creation.md.
    """
    sheet = tn.SheetArchive(
        name=name,
        in_portrait_page_orientation=True,
        show_page_numbers=False,
        is_autofit_on=False,
        content_scale=1.0,
        using_start_page_number=True,
        start_page_number=1,
        page_header_inset=headerFooterInset,
        page_footer_inset=headerFooterInset,
        print_backgrounds=True,
    )
    margins = sheet.print_margins
    margins.top = margins.bottom = marginTopBottom
    margins.left = margins.right = marginLeftRight
    for identifier in headers:
        sheet.headers.add(identifier=identifier)
    for identifier in footers:
        sheet.footers.add(identifier=identifier)
    sheet.style.identifier = styles.sheet
    return sheet


def createSheet(registry: PackageRegistry, sheet: Sheet, styles: SheetStyles) -> int:
    """Create one sheet's archives and return the sheet's identifier."""
    sheetId = registry.identifierAllocate()
    headers, footers = (
        [registry.identifierAllocate() for _ in range(headerFooterCount)]
        for _ in range(2)
    )
    for identifier in (*headers, *footers):
        storage = composeStorage(styles)
        registry.archiveAdd(
            documentComponentId,
            composeArchive(identifier, storage, weak={styles.stylesheet}),
            storage,
        )
    body = composeSheet(sheet.name, styles, headers, footers)
    registry.archiveAdd(documentComponentId, composeArchive(sheetId, body), body)
    for identifier in (sheetId, *headers, *footers):
        registry.objectUuidAdd(documentComponentId, identifier, generateUuid())
    return sheetId


def createSidebarNode(registry: PackageRegistry, sheetIdentifier: int) -> int:
    """Create the sidebar tree entry for a sheet, and return its identifier."""
    identifier = registry.identifierAllocate()
    node = tsk.TreeNode()
    node.object.identifier = sheetIdentifier
    registry.archiveAdd(documentComponentId, composeArchive(identifier, node), node)
    return identifier


def createSheets(document: Document, registry: PackageRegistry) -> None:
    """Create every sheet the model gained, and list each where the model has it.

    A sheet removed or moved is refused before anything is written, since neither
    is supported. The tables a created sheet holds are created afterward.
    """
    index = registry.index
    root = findRoot(index)
    stored = [reference.identifier for reference in root.sheets]
    kept = [
        sheet._identifier for sheet in document.sheets
        if sheet._identifier is not None
    ]
    if kept != stored:
        raise WriteError(
            "The model's existing sheets are not the document's sheets in the "
            "document's order. Removing or reordering a sheet is not supported."
        )
    created = [sheet for sheet in document.sheets if sheet._identifier is None]
    if not created:
        return
    styles = findSheetStyles(index, root)
    sidebar = index.resolve(root.sidebar_order, tsk.TreeNode)
    nodes = list(sidebar.children)
    nodeFor = {
        index.resolve(node, tsk.TreeNode).object.identifier: node.identifier
        for node in nodes
    }
    if sorted(nodeFor) != sorted(stored):
        raise WriteError(
            "The sidebar does not list exactly this document's sheets, so a sheet "
            "cannot be placed in it without disturbing what else it lists."
        )
    for sheet in created:
        identifier = createSheet(registry, sheet, styles)
        nodeFor[identifier] = createSidebarNode(registry, identifier)
        sheet._identifier = identifier

    order: list[int] = []
    for sheet in document.sheets:
        if sheet._identifier is None:
            raise WriteError(f"{sheet.name!r} was left without an archive.")
        order.append(sheet._identifier)
    del root.sheets[:]
    for identifier in order:
        root.sheets.add(identifier=identifier)
    rootIdentifier = next(
        identifier for identifier, archive in index.byIdentifier.items()
        if archive.messages
        and archive.messages[0].typeId == findArchiveTypeId(tn.DocumentArchive)
    )
    rootReferences = registry.strongReferencesOf(rootIdentifier)
    rootReferences.extend(
        identifier for identifier in order if identifier not in rootReferences
    )
    registry.archiveReplace(rootIdentifier, root, rootReferences)

    del sidebar.children[:]
    for identifier in order:
        sidebar.children.add(identifier=nodeFor[identifier])
    registry.archiveReplace(
        root.sidebar_order.identifier,
        sidebar,
        [nodeFor[identifier] for identifier in order],
    )


__all__ = ["createSheets"]
