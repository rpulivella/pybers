#!/usr/bin/env python3
"""\
Create the archives of a sheet the model gained, and register them.

A created sheet is the template under `_templates/sheet`, taken from
`49-sheet-inserted` and set to the pybers reset: printed 1:1 with autofit off,
margins of 72 pt top and bottom and 54 pt left and right, and every header and
footer empty, including the page number Numbers puts in the center footer. Its
background is the document's own sheet style, because Numbers can make no sheet
without one. See docs/decisions.md.

UPDATES
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

import uuid
from pathlib import Path

from .._generated import TNArchives_pb2 as tn
from .._generated import TSKArchives_pb2 as tsk
from .._generated import TSPArchiveMessages_pb2 as tspArchive
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSWPArchives_pb2 as tswp
from .._persistence import createArchive
from .._persistence.index import ArchiveIndex, findRoot
from .._persistence.metadata import PackageRegistry, documentComponentId
from .._persistence.template import ArchiveTemplate, copyTemplates, readTemplates
from .._persistence.types import findArchiveTypeId
from ..errors import WriteError
from .sheets import Document, Sheet

sheetTemplateDirectory: Path = Path(__file__).resolve().parent / "_templates" / "sheet"

# The objects the sheet template names in `49-sheet-inserted` that belong to the
# document rather than to the sheet, and which each is bound to in the target.
templateSheetStyle: int = 903871
templateStylesheet: int = 905039
templateParagraphStyle: int = 903900
templateListStyle: int = 903872

treeNodeVersion: tuple[int, ...] = (1, 0, 5)

# The archives whose UUIDs Numbers records in the document component, by role.
uuidRoles: tuple[str, ...] = (
    "sheet",
    "guides",
    "header-left",
    "header-center",
    "header-right",
    "footer-left",
    "footer-center",
    "footer-right",
)


def generateUuid() -> tsp.UUID:
    """Return a random UUID in the two-halves form the file stores."""
    value = uuid.uuid4().int
    return tsp.UUID(lower=value & 0xFFFFFFFFFFFFFFFF, upper=value >> 64)


def bindSheetObjects(index: ArchiveIndex, root: tn.DocumentArchive) -> dict[int, int]:
    """Bind the template's document objects to those the first sheet already uses.

    Taken from an existing sheet rather than from the theme, so a created sheet shares
    the style and the header text styles its neighbors have.
    """
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
    return {
        templateSheetStyle: first.style.identifier,
        templateStylesheet: header.style_sheet.identifier,
        templateParagraphStyle: header.table_para_style.entries[0].object.identifier,
        templateListStyle: header.table_list_style.entries[0].object.identifier,
    }


def createSheet(
    index: ArchiveIndex,
    registry: PackageRegistry,
    templates: list[ArchiveTemplate],
    sheet: Sheet,
    bindings: dict[int, int],
) -> int:
    """Create one sheet's archives and return the sheet's identifier."""
    copies = copyTemplates(registry, templates, bindings)
    body = copies["sheet"].body
    if not isinstance(body, tn.SheetArchive):
        raise WriteError("The sheet template does not hold a TN.SheetArchive.")
    body.name = sheet.name
    copies.place(registry, {"Document": documentComponentId})
    for role in uuidRoles:
        registry.objectUuidAdd(
            documentComponentId, copies[role].identifier, generateUuid()
        )
    return copies["sheet"].identifier


def createSidebarNode(registry: PackageRegistry, sheetIdentifier: int) -> int:
    """Create the sidebar tree entry for a sheet, and return its identifier."""
    identifier = registry.identifierAllocate()
    info = tspArchive.ArchiveInfo(identifier=identifier)
    message = info.message_infos.add(
        type=findArchiveTypeId(tsk.TreeNode), length=0
    )
    message.version.extend(treeNodeVersion)
    message.object_references.append(sheetIdentifier)
    node = tsk.TreeNode()
    node.object.identifier = sheetIdentifier
    registry.archiveAdd(
        documentComponentId, createArchive(info, [node.SerializeToString()]), node
    )
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
    templates = readTemplates(sheetTemplateDirectory)
    bindings = bindSheetObjects(index, root)
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
        identifier = createSheet(index, registry, templates, sheet, bindings)
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
