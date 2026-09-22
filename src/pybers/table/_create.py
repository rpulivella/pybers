#!/usr/bin/env python3
"""\
Create the archives of a table the model gained, in the pybers reset, and register them.

A created table is the template under `_templates/table`, taken from
`48-table-inserted`: the 49 archives Numbers writes for an inserted table, its 11
calculation-engine owners and their two dependency tiles. Every name in it is renewed,
and each owner keeps its offset from the table's base UUID, as Numbers writes it. See
findings-10-creation.md.

Its styles are the reset in docs/decisions.md. The table style and the cell style are
variations of the theme's first table style preset, written as `52-table-reset-styled`
wrote them, and every text slot names `pybers-base`, the named paragraph style of
`53-paragraph-style-named`, created once per document and found again by name.

UPDATES
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from google.protobuf.message import Message

from .._generated import TNArchives_pb2 as tn
from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSKArchives_pb2 as tsk
from .._generated import TSPArchiveMessages_pb2 as tspArchive
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSSArchives_pb2 as tss
from .._generated import TSTArchives_pb2 as tst
from .._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from .._generated import TSWPArchives_pb2 as tswp
from .._persistence import createArchive
from .._persistence.index import (
    ArchiveIndex,
    assignUuid,
    findRoot,
    readUuidValue,
    wordBits,
    wordMask,
)
from .._persistence.metadata import PackageRegistry
from .._persistence.template import (
    ArchiveCopy,
    ArchiveTemplate,
    TemplateCopies,
    copyTemplates,
    readTemplates,
)
from .._persistence.types import readArchiveTypeId, tableInfoTypeId
from ..errors import WriteError
from ..geometry import Position
from .cells import Table, generateOwnerIdentity

if TYPE_CHECKING:
    # Guarded because the document feature imports this one to create its tables.
    from ..document.sheets import Document, Sheet

templateDirectory: Path = Path(__file__).resolve().parent / "_templates"

# The objects the templates name that belong to the document rather than to the
# table, as `48-table-inserted` numbered them.
templateSheet: int = 904532
templatePreset: int = 904099
templateStylesheet: int = 905039
templateListStyle: int = 903872
templateTableStyle: int = 904074
templateCellStyle: int = 904075

# The table template's base owner UUID, which its owner of kind 1 carries. Every other
# owner UUID in the template is this plus the owner's kind, and kinds reach 35.
templateOwnerBase: int = (2965606220279224969 << 64) | 8665371034051433512
ownerKindLimit: int = 0x100

# A UUID this small is a fixed value such as a root group, never an identity.
fixedUuidLimit: int = 1 << 32


ownerTypeId: int = 4008
paragraphStyleTypeId: int = 2022
treeNodeTypeId: int = 205
treeNodeVersion: tuple[int, ...] = (1, 0, 5)

baseStyleName: str = "pybers-base"
namedStyleKey: str = "text-{}-paragraphstyle"
resetRowHeight: float = 24.0
resetColumnWidth: float = 72.0
tableGap: float = resetRowHeight
# Numbers' own convention for a created table's stored frame: the content plus 4 pt.
geometryFrame: float = 4.0

headerNameOwnerKind: int = 200
# Measured across the documents holding one, three and nine tables: each adds four.
formulasPerTable: int = 4

ownerIdFields: frozenset[str] = frozenset(
    {"internal_formula_owner_id", "internal_owner_id_for_edge", "internal_owner_id"}
)


def readWordsValue(message: tsp.CFUUIDArchive) -> int:
    """Return a UUID's value from its four words."""
    return (
        message.uuid_w0
        | message.uuid_w1 << wordBits
        | message.uuid_w2 << 2 * wordBits
        | message.uuid_w3 << 3 * wordBits
    )


def assignWords(message: tsp.CFUUIDArchive, value: int) -> None:
    """Set a UUID's four words from a value."""
    message.uuid_w0 = value & wordMask
    message.uuid_w1 = value >> wordBits & wordMask
    message.uuid_w2 = value >> 2 * wordBits & wordMask
    message.uuid_w3 = value >> 3 * wordBits & wordMask


def readIdentityValue(identity: str) -> int:
    """Return the UUID a table's formula identity spells, four words low first."""
    words = [int(identity[start:start + 8], 16) for start in range(0, 32, 8)]
    return words[0] | words[1] << 32 | words[2] << 64 | words[3] << 96


def renderIdentityText(identity: str) -> str:
    """Return the canonical UUID a table's `table_id` spells its identity as.

    **`table_id` is how Numbers finds a table's calculation-engine owners.** A table
    carrying any other value is re-identified on open: Numbers mints a fresh owner
    family, drops every dependency tile, and the formulas in it are never evaluated.
    Measured 2026-09-16 for PYB-86, see findings-10-creation.md.
    """
    value = readIdentityValue(identity)
    return str(uuid.UUID(bytes=value.to_bytes(16, "little"))).upper()


@dataclass(slots=True)
class UuidRenewal:
    """Renews every UUID in a template set: owner UUIDs from a base, others fresh."""

    base: int
    fresh: dict[int, int] = field(default_factory=dict)

    def renewed(self, value: int) -> int:
        """Return what one template UUID becomes."""
        offset = value - templateOwnerBase
        if 0 <= offset < ownerKindLimit:
            return self.base + offset
        if value < fixedUuidLimit:
            return value
        return self.fresh.setdefault(value, uuid.uuid4().int)

    def apply(self, message: Message) -> None:
        """Renew every UUID a message holds, in place."""
        if isinstance(message, tsp.UUID):
            assignUuid(message, self.renewed(readUuidValue(message)))
            return
        if isinstance(message, tsp.CFUUIDArchive):
            if message.HasField("uuid_w0"):
                assignWords(message, self.renewed(readWordsValue(message)))
            return
        for descriptor, value in message.ListFields():
            if descriptor.message_type is None:
                continue
            items = list(value) if descriptor.is_repeated else [value]
            for item in items:
                self.apply(item)


def remapOwnerIds(message: Message, mapping: dict[int, int]) -> None:
    """Rewrite every internal owner id a message holds as an integer, in place."""
    for descriptor, value in message.ListFields():
        if descriptor.message_type is None:
            if descriptor.name not in ownerIdFields:
                continue
            if descriptor.is_repeated:
                value[:] = [mapping.get(item, item) for item in value]
            elif value in mapping:
                setattr(message, descriptor.name, mapping[value])
            continue
        items = list(value) if descriptor.is_repeated else [value]
        for item in items:
            remapOwnerIds(item, mapping)


def assignUids(uidMap: tst.ColumnRowUIDMapArchive, table: Table) -> None:
    """Write a table's row and column identities, in the order Numbers keeps.

    The UIDs are sorted by value, upper half first, and each index list is the
    permutation between that order and the table's own. Measured from `48`.
    """
    for axis, uids in (
        ("column", table._columnIdentities), ("row", table._rowIdentities)
    ):
        ordered = sorted(range(len(uids)), key=lambda position: uids[position])
        sortedField = getattr(uidMap, f"sorted_{axis}_uids")
        indexForUid = getattr(uidMap, f"{axis}_index_for_uid")
        uidForIndex = getattr(uidMap, f"{axis}_uid_for_index")
        del sortedField[:]
        del indexForUid[:]
        del uidForIndex[:]
        for position in ordered:
            assignUuid(sortedField.add(), uids[position])
        indexForUid.extend(ordered)
        rank = {position: slot for slot, position in enumerate(ordered)}
        uidForIndex.extend(rank[position] for position in range(len(uids)))


@dataclass(frozen=True, slots=True)
class DocumentStyles:
    """The theme's first table style preset, its network, and its stylesheet."""

    preset: int
    network: tst.TableStyleNetworkArchive
    stylesheet: int


@dataclass(frozen=True, slots=True)
class ResetStyles:
    """The three styles every text, cell and table slot of a created table names."""

    tableStyle: int
    cellStyle: int
    textStyle: int


def findTheme(index: ArchiveIndex) -> tuple[int, tn.ThemeArchive]:
    """Return the document's theme archive and its identifier."""
    root = findRoot(index)
    return root.theme.identifier, index.resolve(root.theme, tn.ThemeArchive)


def findDocumentStyles(index: ArchiveIndex) -> DocumentStyles:
    """Return the theme's first table style preset and the network it names."""
    _, theme = findTheme(index)
    presets = theme.super.Extensions[tstStyles.ThemePresetsArchive.extension]
    if not presets.table_style_presets:
        raise WriteError("This document's theme carries no table style preset.")
    presetReference = presets.table_style_presets[0]
    preset = index.resolve(presetReference, tstStyles.TableStylePresetArchive)
    network = index.resolve(preset.style_network, tst.TableStyleNetworkArchive)
    stylesheet = index.resolve(network.table_style, tst.TableStyleArchive)
    return DocumentStyles(
        preset=presetReference.identifier,
        network=network,
        stylesheet=stylesheet.super.stylesheet.identifier,
    )


def findNamedStyle(index: ArchiveIndex, stylesheetId: int) -> int | None:
    """Return the `pybers-base` paragraph style this document already holds, if any."""
    stylesheet = index.resolve(
        tsp.Reference(identifier=stylesheetId), tss.StylesheetArchive
    )
    for reference in stylesheet.styles:
        archive = index.byIdentifier.get(reference.identifier)
        if archive is None or readArchiveTypeId(archive) != paragraphStyleTypeId:
            continue
        style = index.resolve(reference, tswp.ParagraphStyleArchive)
        if style.super.name == baseStyleName:
            return int(reference.identifier)
    return None


def createResetStyles(
    index: ArchiveIndex, registry: PackageRegistry, styles: DocumentStyles
) -> ResetStyles:
    """Create the reset's two variations, and `pybers-base` unless it exists."""
    network = styles.network
    bodyText = index.resolve(network.body_text_style, tswp.ParagraphStyleArchive)
    templates = readTemplates(templateDirectory / "styles")
    existing = findNamedStyle(index, styles.stylesheet)
    if existing is not None:
        templates = [
            template for template in templates if template.role != "text-style"
        ]
    copies = copyTemplates(
        registry,
        templates,
        {
            templateStylesheet: styles.stylesheet,
            templateTableStyle: network.table_style.identifier,
            templateCellStyle: network.body_cell_style.identifier,
            templateListStyle: bodyText.para_properties.list_style.identifier,
        },
    )
    stylesheet = index.resolve(
        tsp.Reference(identifier=styles.stylesheet), tss.StylesheetArchive
    )
    keys = {entry.identifier for entry in stylesheet.identifier_to_style_map}
    if existing is None:
        textCopy = copies["text-style"]
        key = next(
            namedStyleKey.format(number)
            for number in range(len(keys) + 1)
            if namedStyleKey.format(number) not in keys
        )
        body = textCopy.body
        if not isinstance(body, tswp.ParagraphStyleArchive):
            raise WriteError("The text style template is not a paragraph style.")
        body.super.style_identifier = key
        stylesheet.identifier_to_style_map.add(
            identifier=key, style=tsp.Reference(identifier=textCopy.identifier)
        )
    reset = ResetStyles(
        tableStyle=copies["table-style"].identifier,
        cellStyle=copies["cell-style"].identifier,
        textStyle=copies["text-style"].identifier if existing is None else existing,
    )

    componentId = registry.componentRequire(styles.stylesheet)
    copies.place(registry, {"DocumentStylesheet": componentId})
    created = [copy.identifier for copy in copies.copies.values()]
    for identifier in created:
        stylesheet.styles.add(identifier=identifier)
        registry.objectUuidAdd(componentId, identifier, generateUuid())
    for parent, child in (
        (network.table_style.identifier, reset.tableStyle),
        (network.body_cell_style.identifier, reset.cellStyle),
    ):
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
    references = registry.strongReferencesOf(styles.stylesheet)
    references.extend(
        identifier for identifier in created if identifier not in references
    )
    registry.archiveReplace(
        styles.stylesheet, stylesheet, references
    )

    if existing is None:
        themeId, theme = findTheme(index)
        presets = theme.super.Extensions[tswp.ThemePresetsArchive.extension]
        presets.paragraph_style_presets.add(identifier=reset.textStyle)
        themeReferences = registry.strongReferencesOf(themeId)
        themeReferences.append(reset.textStyle)
        registry.archiveReplace(themeId, theme, themeReferences)
    return reset


def generateUuid() -> tsp.UUID:
    """Return a random UUID in the two-halves form the file stores."""
    message = tsp.UUID()
    assignUuid(message, uuid.uuid4().int)
    return message


def bindStyles(
    template: ArchiveTemplate, styles: DocumentStyles, reset: ResetStyles
) -> dict[int, int]:
    """Bind every style the table model template names to what the reset puts there.

    The table style, every cell style and every text style but the title's take the
    reset. The title's two styles take the theme's own, since a title stays hidden.
    """
    bindings: dict[int, int] = {}
    for descriptor in tst.TableStyleNetworkArchive.DESCRIPTOR.fields:
        if descriptor.message_type is None:
            continue
        name = descriptor.name
        if not template.body.HasField(name):
            continue
        if name == "table_style":
            target = reset.tableStyle
        elif name in ("table_name_style", "table_name_shape_style"):
            target = getattr(styles.network, name).identifier
        elif name.endswith("_text_style"):
            target = reset.textStyle
        else:
            target = reset.cellStyle
        source = getattr(template.body, name).identifier
        if bindings.setdefault(source, target) != target:
            raise WriteError(
                f"The table template names style {source} in two slots the reset "
                "fills differently."
            )
    return bindings


@dataclass(slots=True)
class EngineState:
    """The calculation engine and the archives creating a table rewrites in it."""

    identifier: int
    engine: tsce.CalculationEngineArchive
    headerNames: tst.HeaderNameMgrArchive
    headerOwner: tsce.FormulaOwnerDependenciesArchive
    headerOwnerId: int
    headerTile: tsce.CellRecordTileArchive
    headerTileId: int


def findEngineState(index: ArchiveIndex, registry: PackageRegistry) -> EngineState:
    """Find the engine, its header name manager, and that manager's owner."""
    engineId = registry.componentNamed("CalculationEngine")
    engine = index.resolve(
        tsp.Reference(identifier=engineId), tsce.CalculationEngineArchive
    )
    headerNames = index.resolve(engine.header_name_manager, tst.HeaderNameMgrArchive)
    for reference in engine.dependency_tracker.formula_owner_dependencies:
        owner = index.resolve(reference, tsce.FormulaOwnerDependenciesArchive)
        if owner.owner_kind != headerNameOwnerKind:
            continue
        tiles = owner.tiled_cell_dependencies.cell_record_tiles
        if len(tiles) != 1:
            raise WriteError(
                f"The header name owner holds {len(tiles)} dependency tiles, and "
                "every document measured holds one."
            )
        return EngineState(
            identifier=engineId,
            engine=engine,
            headerNames=headerNames,
            headerOwner=owner,
            headerOwnerId=reference.identifier,
            headerTile=index.resolve(tiles[0], tsce.CellRecordTileArchive),
            headerTileId=tiles[0].identifier,
        )
    raise WriteError("The calculation engine registers no header name owner.")


def addHeaderSlot(state: EngineState, base: int) -> None:
    """Give a table the next header name slot, and register it as a dependency."""
    slot = 1 + max(
        (entry.per_table_precedent.column for entry in state.headerNames.per_tables),
        default=0,
    )
    entry = state.headerNames.per_tables.add()
    assignUuid(entry.table_uid, base)
    entry.per_table_precedent.column = slot
    entry.per_table_precedent.row = 1
    for records in (
        state.headerOwner.cell_dependencies.cell_record,
        state.headerTile.cell_records,
    ):
        record = records.add(column=slot, row=1)
        # Every slot Numbers writes depends on the owner's own first cell, and a
        # slot without that edge is a table Numbers re-identifies on open.
        record.expanded_edges.edge_without_owner_rows.append(0)
        record.expanded_edges.edge_without_owner_columns.append(0)


def measureTableBottom(index: ArchiveIndex, info: tst.TableInfoArchive) -> float:
    """Return where a table's content ends on its sheet, from its row heights.

    The stored frame size is stale, so the height is the rows' own, taking the
    default wherever a row's stored size is 0. See findings-03-structure.md.
    """
    model = index.resolve(info.tableModel, tst.TableModelArchive)
    sized: dict[int, float] = {}
    for bucket in model.base_data_store.rowHeaders.buckets:
        for header in index.resolve(bucket, tst.HeaderStorageBucket).headers:
            if header.size > 0:
                sized[header.index] = header.size
    height = sum(
        sized.get(row, model.default_row_height) for row in range(model.number_of_rows)
    )
    return float(info.super.geometry.position.y) + height


def createTable(
    registry: PackageRegistry,
    templates: list[ArchiveTemplate],
    table: Table,
    sheetId: int,
    origin: Position,
    styles: DocumentStyles,
    reset: ResetStyles,
    state: EngineState,
) -> int:
    """Create one table's archives and engine entries, and return its info archive."""
    modelTemplate = next(template for template in templates if template.role == "model")
    bindings = {templateSheet: sheetId, templatePreset: styles.preset}
    bindings.update(bindStyles(modelTemplate, styles, reset))
    if not table.identifier:
        table.identifier = generateOwnerIdentity()
    copies = copyTemplates(registry, templates, bindings)

    base = readIdentityValue(table.identifier)
    renewal = UuidRenewal(base=base)
    owners = [
        copy for copy in copies.copies.values()
        if copy.template.info.message_infos[0].type == ownerTypeId
    ]
    registered = [
        entry.internal_owner_id
        for entry in state.engine.dependency_tracker.owner_id_map.map_entry
    ]
    nextOwnerId = 1 + max(registered, default=0)
    ownerIds: dict[int, int] = {}
    for copy in owners:
        body = readOwnerBody(copy)
        ownerIds[body.internal_formula_owner_id] = nextOwnerId
        nextOwnerId += 1
    for copy in copies.copies.values():
        renewal.apply(copy.body)
        remapOwnerIds(copy.body, ownerIds)

    shapeTable(copies, table, origin)
    copies.place(registry, {"CalculationEngine": state.identifier})
    for role in ("table-info", "caption", "title", "model"):
        registry.objectUuidAdd(
            state.identifier, copies[role].identifier, generateUuid()
        )
    registry.weakReferenceAdd(state.identifier, sheetId)
    registry.weakReferenceAdd(state.identifier, styles.preset)

    tracker = state.engine.dependency_tracker
    for copy in owners:
        body = readOwnerBody(copy)
        tracker.formula_owner_dependencies.add(identifier=copy.identifier)
        entry = tracker.owner_id_map.map_entry.add(
            internal_owner_id=body.internal_formula_owner_id
        )
        assignWords(entry.owner_id, readUuidValue(body.formula_owner_uid))
    tracker.number_of_formulas += formulasPerTable
    addHeaderSlot(state, base)
    return copies["table-info"].identifier


def readOwnerBody(copy: ArchiveCopy) -> tsce.FormulaOwnerDependenciesArchive:
    """Return an owner template's message, refusing a template of another type."""
    if not isinstance(copy.body, tsce.FormulaOwnerDependenciesArchive):
        raise WriteError(
            f"The {copy.template.role!r} template is not a formula owner."
        )
    return copy.body


def shapeTable(copies: TemplateCopies, table: Table, origin: Position) -> None:
    """Set a copied table's name, size and place, and every count its size decides."""
    model = copies["model"].body
    info = copies["table-info"].body
    sidecar = copies["model-stroke-sidecar"].body
    uids = copies["model-column-row-uids"].body
    owner = copies["owner-kind-1"].body
    if not (
        isinstance(model, tst.TableModelArchive)
        and isinstance(info, tst.TableInfoArchive)
        and isinstance(sidecar, tst.StrokeSidecarArchive)
        and isinstance(uids, tst.ColumnRowUIDMapArchive)
        and isinstance(owner, tsce.FormulaOwnerDependenciesArchive)
    ):
        raise WriteError("A table template holds an archive of an unexpected type.")
    model.table_name = table.name
    model.number_of_rows = table.rowCount
    model.number_of_columns = table.colCount
    model.default_row_height = resetRowHeight
    model.default_column_width = resetColumnWidth
    model.table_id = renderIdentityText(table.identifier)
    sidecar.row_count = table.rowCount
    sidecar.column_count = table.colCount
    assignUids(uids, table)
    cache = info.layout_engine.width_height_cache
    del cache.rows_fitting_entries[:]
    cache.columns_count = table.colCount
    geometry = info.super.geometry
    geometry.position.x = origin.x
    geometry.position.y = origin.y
    geometry.size.width = table.colCount * resetColumnWidth + geometryFrame
    geometry.size.height = table.rowCount * resetRowHeight + geometryFrame
    spans = (owner.spanning_column_dependencies, owner.spanning_row_dependencies)
    for dependencies in spans:
        extents = (
            dependencies.total_range_for_table, dependencies.body_range_for_table
        )
        for extent in extents:
            extent.bottom_right_column = table.colCount - 1
            extent.bottom_right_row = table.rowCount - 1


def addSidebarNodes(
    index: ArchiveIndex, registry: PackageRegistry, sheetId: int, tableIds: list[int]
) -> None:
    """List a sheet's created tables under it in the sidebar tree, in one rewrite."""
    root = findRoot(index)
    sidebar = index.resolve(root.sidebar_order, tsk.TreeNode)
    for reference in sidebar.children:
        node = index.resolve(reference, tsk.TreeNode)
        if node.object.identifier != sheetId:
            continue
        references = registry.strongReferencesOf(reference.identifier)
        for tableId in tableIds:
            identifier = registry.identifierAllocate()
            info = tspArchive.ArchiveInfo(identifier=identifier)
            message = info.message_infos.add(type=treeNodeTypeId, length=0)
            message.version.extend(treeNodeVersion)
            message.object_references.append(tableId)
            child = tsk.TreeNode()
            child.object.identifier = tableId
            registry.archiveAdd(
                registry.componentRequire(reference.identifier),
                createArchive(info, [child.SerializeToString()]),
                child,
            )
            node.children.add(identifier=identifier)
            references.append(identifier)
        registry.archiveReplace(
            reference.identifier, node, references
        )
        return
    raise WriteError(f"The sidebar lists no sheet {sheetId} to place a table under.")


def findPendingTables(
    index: ArchiveIndex, document: Document
) -> list[tuple[Sheet, tn.SheetArchive, list[Table]]]:
    """Return each sheet holding tables the model gained, refusing any other change.

    A table removed or moved is refused, since neither is supported.
    """
    pending: list[tuple[Sheet, tn.SheetArchive, list[Table]]] = []
    for sheet in document.sheets:
        if sheet._identifier is None:
            raise WriteError(f"{sheet.name!r} has no archive to hold its tables.")
        sheetArchive = index.resolve(
            tsp.Reference(identifier=sheet._identifier), tn.SheetArchive
        )
        stored = [
            reference.identifier for reference in sheetArchive.drawable_infos
            if index.typeOf(reference) == tableInfoTypeId
        ]
        kept = [
            table._identifier for table in sheet.tables
            if table._identifier is not None
        ]
        if kept != stored:
            raise WriteError(
                f"The tables of {sheet.name!r} are not the document's tables in the "
                "document's order. Removing or reordering a table is not supported."
            )
        created = sheet.tables[len(kept):]
        if any(table._identifier is not None for table in created):
            raise WriteError(
                f"A new table on {sheet.name!r} sits before a table already in the "
                "document. A created table is placed after the existing ones, so it "
                "has to be added after them."
            )
        for table in created:
            if table.extent is None:
                raise WriteError(
                    f"{table.name!r} on {sheet.name!r} declares {table.rowCount} rows "
                    f"by {table.colCount} columns, and a table holds at least one of "
                    "each."
                )
        if created:
            pending.append((sheet, sheetArchive, created))
    return pending


def createTables(document: Document, registry: PackageRegistry) -> None:
    """Create every table the model gained, on every sheet, once the sheets exist."""
    index = registry.index
    pending = findPendingTables(index, document)
    if not pending:
        return
    styles = findDocumentStyles(index)
    reset = createResetStyles(index, registry, styles)
    state = findEngineState(index, registry)
    templates = readTemplates(templateDirectory / "table")
    for sheet, sheetArchive, created in pending:
        sheetId = readSheetIdentifier(sheet)
        top = max(
            (
                measureTableBottom(
                    index, index.resolve(reference, tst.TableInfoArchive)
                )
                + tableGap
                for reference in sheetArchive.drawable_infos
                if index.typeOf(reference) == tableInfoTypeId
            ),
            default=0.0,
        )
        tableIds: list[int] = []
        for table in created:
            origin = table._origin
            if origin is None:
                origin = Position(0.0, top)
                top += table.rowCount * resetRowHeight + tableGap
            identifier = createTable(
                registry, templates, table, sheetId, origin, styles, reset, state
            )
            table._identifier = identifier
            tableIds.append(identifier)
            sheetArchive.drawable_infos.add(identifier=identifier)
        addSidebarNodes(index, registry, sheetId, tableIds)
        references = registry.strongReferencesOf(sheetId)
        references.extend(tableIds)
        registry.archiveReplace(sheetId, sheetArchive, references)

    tracker = state.engine.dependency_tracker
    engineReferences = registry.strongReferencesOf(state.identifier)
    engineReferences.extend(
        reference.identifier for reference in tracker.formula_owner_dependencies
        if reference.identifier not in engineReferences
    )
    registry.archiveReplace(
        state.identifier, state.engine, engineReferences
    )
    for identifier, message in (
        (state.engine.header_name_manager.identifier, state.headerNames),
        (state.headerOwnerId, state.headerOwner),
        (state.headerTileId, state.headerTile),
    ):
        registry.archiveReplace(identifier, message)


def readSheetIdentifier(sheet: Sheet) -> int:
    """Return a sheet's archive identifier, which every sheet has once created."""
    if sheet._identifier is None:
        raise WriteError(f"{sheet.name!r} has no archive to hold its tables.")
    return sheet._identifier


__all__ = ["createTables"]
