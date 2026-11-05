#!/usr/bin/env python3
"""\
Create the archives of a table the model gained, in the pybers reset, and register them.

A created table holds only what Numbers needs, each field composed as Numbers writes
it: the info, the model, its data store, the row and column UIDs, and one engine owner
of kind 1 carrying its identity alone. Numbers rebuilds everything else on its next
save, the other ten owners, the summary model, the category order and the hidden
states among them. Found one group at a time, 2026-11-02, findings-10-creation.md.

Its styles are the reset in docs/decisions.md, created by `_reset`.

UPDATES
2026-11-02  Composed field by field to the least Numbers needs, rather than copied
            from a template, for PYB-276.
2026-09-22  The reset's styles moved to `_reset`, for PYB-113.
2026-09-22  A random UUID comes from the index module, shared with sheet creation, for
            PYB-113.
2026-09-22  The UID map is written by `_lines`, as a structural edit writes it, for
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

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .._generated import TNArchives_pb2 as tn
from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSTArchives_pb2 as tst
from .._persistence.index import (
    ArchiveIndex,
    assignUuid,
    assignUuidWords,
    generateUuid,
)
from .._persistence.metadata import PackageRegistry, composeArchive
from .._persistence.types import bncDataListVersion, findArchiveTypeId
from ..errors import WriteError
from ..geometry import Position
from ._lines import assignUids
from ._reset import (
    DocumentStyles,
    ResetStyles,
    createResetStyles,
    findDocumentStyles,
    findSlotStyle,
)
from .cells import Table, generateOwnerIdentity

if TYPE_CHECKING:
    # Guarded because the document feature imports this one to create its tables.
    from ..document.sheets import Document, Sheet


resetRowHeight: float = 24.0
resetColumnWidth: float = 72.0
tableGap: float = resetRowHeight
# Numbers' own convention for a created table's stored frame: the content plus 4 pt.
geometryFrame: float = 4.0

# The drawable flags and text wrap Numbers states on an inserted table, neither of
# which it restores as written when absent.
geometryFlags: int = 3
wrapType: int = 4
wrapDirection: int = 2
wrapFitType: int = 1
wrapMargin: float = 12.0
wrapAlphaThreshold: float = 0.5

tileSize: int = 256
tileStorageVersion: int = 5
bucketHashFunction: int = 1
firstStripId: int = 1

# Measured across the documents holding one, three and nine tables: each adds four.
formulasPerTable: int = 4

type ListKind = tst.TableDataList.ListType.ValueType

# The six lists a created data store names: four the schema requires, the control
# specs without which Numbers drops every formula, and the format list pybers names
# a value's Automatic format in. The last two are the BNC lists.
storeLists: tuple[tuple[str, ListKind, bool], ...] = (
    ("stringTable", tst.TableDataList.STRING, False),
    ("styleTable", tst.TableDataList.STYLE, False),
    ("formula_table", tst.TableDataList.FORMULA, False),
    ("format_table_pre_bnc", tst.TableDataList.FORMAT, False),
    ("control_cell_spec_table", tst.TableDataList.CONTROL_CELL_SPEC, True),
    ("format_table", tst.TableDataList.FORMAT, True),
)

modelFields: frozenset[str] = frozenset(tst.TableModelArchive.DESCRIPTOR.fields_by_name)


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
class EngineState:
    """The calculation engine a created table's owner registers in."""

    identifier: int
    engine: tsce.CalculationEngineArchive


def findEngineState(index: ArchiveIndex, registry: PackageRegistry) -> EngineState:
    """Find the calculation engine and its archive identifier."""
    engineId = registry.componentNamed("CalculationEngine")
    return EngineState(
        identifier=engineId,
        engine=index.resolve(
            tsp.Reference(identifier=engineId), tsce.CalculationEngineArchive
        ),
    )


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


def composeInfo(
    table: Table, sheetId: int, modelId: int, origin: Position
) -> tst.TableInfoArchive:
    """Return the drawable a table sits on its sheet as, at its place and size."""
    info = tst.TableInfoArchive()
    drawable = info.super
    drawable.geometry.position.x = origin.x
    drawable.geometry.position.y = origin.y
    drawable.geometry.size.width = table.colCount * resetColumnWidth + geometryFrame
    drawable.geometry.size.height = table.rowCount * resetRowHeight + geometryFrame
    drawable.geometry.flags = geometryFlags
    drawable.parent.identifier = sheetId
    wrap = drawable.exterior_text_wrap
    wrap.type = wrapType
    wrap.direction = wrapDirection
    wrap.fit_type = wrapFitType
    wrap.margin = wrapMargin
    wrap.alpha_threshold = wrapAlphaThreshold
    info.tableModel.identifier = modelId
    return info


def composeModel(
    table: Table,
    styles: DocumentStyles,
    reset: ResetStyles,
    parts: dict[str, int],
) -> tst.TableModelArchive:
    """Return a table's model: its size, name, reset styles, and the parts it names.

    Every style slot the theme's preset fills is filled, since Numbers leaves an
    absent one absent rather than restoring it.
    """
    model = tst.TableModelArchive(
        table_id=renderIdentityText(table.identifier),
        number_of_rows=table.rowCount,
        number_of_columns=table.colCount,
        table_name=table.name,
        header_rows_frozen=True,
        header_columns_frozen=True,
        repeating_header_rows_enabled=True,
        repeating_header_columns_enabled=True,
        default_row_height=resetRowHeight,
        default_column_width=resetColumnWidth,
    )
    store = model.base_data_store
    store.rowHeaders.bucketHashFunction = bucketHashFunction
    store.rowHeaders.buckets.add(identifier=parts["rowHeaders"])
    store.columnHeaders.identifier = parts["columnHeaders"]
    store.tiles.tiles.add(tileid=0).tile.identifier = parts["tile"]
    store.tiles.tile_size = tileSize
    for field, _, _ in storeLists:
        getattr(store, field).identifier = parts[field]
    store.nextRowStripID = firstStripId
    store.nextColumnStripID = 0
    store.rowTileTree.nodes.add(key=0, value=0)
    store.columnTileTree.SetInParent()
    for descriptor, _ in styles.network.ListFields():
        if descriptor.message_type is not None and descriptor.name in modelFields:
            slot = getattr(model, descriptor.name)
            slot.identifier = findSlotStyle(descriptor.name, styles, reset)
    model.base_column_row_uids.identifier = parts["uids"]
    model.table_style_preset.identifier = styles.preset
    return model


def composeOwner(
    base: int, internalId: int, infoId: int
) -> tsce.FormulaOwnerDependenciesArchive:
    """Return a table's owner of kind 1, carrying its identity and nothing else."""
    owner = tsce.FormulaOwnerDependenciesArchive(
        internal_formula_owner_id=internalId, owner_kind=1
    )
    assignUuid(owner.formula_owner_uid, base)
    owner.formula_owner.identifier = infoId
    return owner


def composeTile() -> tst.Tile:
    """Return the empty first tile a table's rows are written into."""
    return tst.Tile(
        maxColumn=0, maxRow=0, numCells=0, numrows=0,
        storage_version=tileStorageVersion, last_saved_in_BNC=True,
    )


def createTable(
    registry: PackageRegistry,
    table: Table,
    sheetId: int,
    origin: Position,
    styles: DocumentStyles,
    reset: ResetStyles,
    state: EngineState,
) -> int:
    """Create one table's archives and its engine owner, and return its info archive."""
    if not table.identifier:
        table.identifier = generateOwnerIdentity()
    base = readIdentityValue(table.identifier)
    infoId, modelId, ownerId = (registry.identifierAllocate() for _ in range(3))
    parts = {
        name: registry.identifierAllocate()
        for name in (
            "tile", "rowHeaders", "columnHeaders", "uids",
            *(field for field, _, _ in storeLists),
        )
    }

    tile = composeTile()
    registry.componentAdd(composeArchive(parts["tile"], tile), "Tables/Tile", tile)
    for name in ("rowHeaders", "columnHeaders"):
        bucket = tst.HeaderStorageBucket(bucketHashFunction=bucketHashFunction)
        registry.componentAdd(
            composeArchive(parts[name], bucket), "Tables/HeaderStorageBucket", bucket
        )
    for field, listType, bnc in storeLists:
        dataList = tst.TableDataList(listType=listType, nextListID=1)
        if bnc:
            dataList.is_new_for_bnc = True
        registry.componentAdd(
            composeArchive(
                parts[field], dataList, version=bncDataListVersion if bnc else None
            ),
            "Tables/DataList",
            dataList,
        )

    uids = tst.ColumnRowUIDMapArchive()
    assignUids(uids, table)
    model = composeModel(table, styles, reset, parts)
    info = composeInfo(table, sheetId, modelId, origin)
    tracker = state.engine.dependency_tracker
    internalId = 1 + max(
        (entry.internal_owner_id for entry in tracker.owner_id_map.map_entry),
        default=0,
    )
    owner = composeOwner(base, internalId, infoId)
    for identifier, body, weak in (
        (parts["uids"], uids, ()),
        (modelId, model, (styles.preset,)),
        (infoId, info, (sheetId,)),
        (ownerId, owner, (infoId,)),
    ):
        registry.archiveAdd(
            state.identifier, composeArchive(identifier, body, weak=weak), body
        )
    for identifier in (infoId, modelId):
        registry.objectUuidAdd(state.identifier, identifier, generateUuid())
    registry.weakReferenceAdd(state.identifier, sheetId)
    registry.weakReferenceAdd(state.identifier, styles.preset)

    tracker.formula_owner_dependencies.add(identifier=ownerId)
    entry = tracker.owner_id_map.map_entry.add(internal_owner_id=internalId)
    assignUuidWords(entry.owner_id, base)
    tracker.number_of_formulas += formulasPerTable
    return infoId


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
            if index.typeOf(reference) == findArchiveTypeId(tst.TableInfoArchive)
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
    for sheet, sheetArchive, created in pending:
        sheetId = readSheetIdentifier(sheet)
        top = max(
            (
                measureTableBottom(
                    index, index.resolve(reference, tst.TableInfoArchive)
                )
                + tableGap
                for reference in sheetArchive.drawable_infos
                if index.typeOf(reference) == findArchiveTypeId(tst.TableInfoArchive)
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
                registry, table, sheetId, origin, styles, reset, state
            )
            table._identifier = identifier
            tableIds.append(identifier)
            sheetArchive.drawable_infos.add(identifier=identifier)
        references = registry.strongReferencesOf(sheetId)
        references.extend(tableIds)
        registry.archiveReplace(sheetId, sheetArchive, references)

    tracker = state.engine.dependency_tracker
    engineReferences = registry.strongReferencesOf(state.identifier)
    engineReferences.extend(
        reference.identifier for reference in tracker.formula_owner_dependencies
        if reference.identifier not in engineReferences
    )
    registry.archiveReplace(state.identifier, state.engine, engineReferences)


def readSheetIdentifier(sheet: Sheet) -> int:
    """Return a sheet's archive identifier, which every sheet has once created."""
    if sheet._identifier is None:
        raise WriteError(f"{sheet.name!r} has no archive to hold its tables.")
    return sheet._identifier


__all__ = ["createTables"]
