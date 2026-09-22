#!/usr/bin/env python3
"""\
The fact readers every structural-edit test compares Numbers against.

Each reads what one kind of archive says about a table, in a form two documents
can be compared by: the one pybers saved and the one Numbers made of the same edit.

UPDATES
2026-09-21  Split out of `test_structure` for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/21"

from collections.abc import Callable
from pathlib import Path

import pybers
from conftest import findDocumentPath
from pybers._engine import findCalculationEngine, readTableOwnerEntries
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSCEArchives_pb2 as tsce
from pybers._generated import TSPArchiveMessages_pb2 as tspArchive
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import chooseOffsetUnit, decodeRow, readPackage
from pybers._persistence.cells import conditionalSlot, findSlotValue, matchSlot
from pybers._persistence.index import ArchiveIndex, findRoot, readUuidValue

baseFixture: Path = findDocumentPath("56-structure-base")

# Each measured edit, as the one pybers call that reproduces it. Rows 2 and 3 and
# columns C to G went together in `56b` to `56e` because Numbers widens a selected
# row or column to cover every merge it touches.
measuredEdits: dict[str, Callable[[pybers.Table], object]] = {
    "56b-row-inserted": lambda table: table.rowAdd(2, 2),
    "56c-row-deleted": lambda table: table.rowRemove(2, 2),
    "56d-column-inserted": lambda table: table.columnAdd("C", 5),
    "56e-column-deleted": lambda table: table.columnRemove("C", 5),
    "56f-row-inserted-in-merge": lambda table: table.rowAdd(3),
    "56g-row-deleted-in-merge": lambda table: table.rowRemove(3),
    "56h-row-8-deleted": lambda table: table.rowRemove(8),
}

# Where Numbers stored a newly broken formula as an error and pybers keeps the
# result it last cached, for Numbers to recompute on open as it does every moved
# formula. Named so a further difference fails.
recomputedOnOpen: dict[str, set[tuple[str, int, int]]] = {
    "56c-row-deleted": {("Table 1", 7, 1)},
    "56e-column-deleted": {("Table 1", 11, 1), ("Table 2", 2, 0)},
    "56h-row-8-deleted": {("Table 1", 4, 1), ("Table 1", 5, 1), ("Table 2", 0, 0)},
}


def openBase() -> pybers.Document:
    """Return a fresh copy of the base document."""
    return pybers.open(baseFixture)


def reduceModel(document: pybers.Document) -> dict[str, object]:
    """Return each table's size, merges, formulas as nodes, and plain values."""
    reduced: dict[str, object] = {}
    for table in document.sheets[0].tables:
        cells: dict[str, object] = {}
        for reference, cell in table.cells.items():
            if cell.formula is not None:
                cells[str(reference)] = tuple(
                    (node.nodeType, node.content) for node in cell.formula
                )
            elif cell.value is not None:
                cells[str(reference)] = cell.value
        reduced[table.name] = (
            table.rowCount,
            table.colCount,
            sorted(str(merge.extent) for merge in table.mergeRanges),
            cells,
        )
    return reduced


def readStrokeLayers(
    index: ArchiveIndex, model: tst.TableModelArchive
) -> dict[str, list[object]]:
    """Return every border of a table, as the layer and run Numbers stores."""
    sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
    described: dict[str, list[object]] = {}
    for label, references in (
        ("left", sidecar.left_column_stroke_layers),
        ("right", sidecar.right_column_stroke_layers),
        ("top", sidecar.top_row_stroke_layers),
        ("bottom", sidecar.bottom_row_stroke_layers),
    ):
        described[label] = [
            (
                layer.row_column_index,
                [
                    (run.origin, run.length, round(run.stroke.width, 3))
                    for run in layer.stroke_runs
                ],
            )
            for layer in (
                index.resolve(reference, tst.StrokeLayerArchive)
                for reference in references
            )
        ]
    return described


def readVolatileCells(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
) -> dict[str, list[tuple[int, int]]]:
    """Return every cell the engine recalculates on its own, per kind."""
    volatile = dependencies.volatile_dependencies
    found: dict[str, list[tuple[int, int]]] = {}
    for name in ("volatile_time_cells", "volatile_random_cells"):
        found[name] = sorted(
            (extent.range_begin, entry.column)
            for entry in getattr(volatile, name).column_entries
            for extent in entry.row_set.entries
        )
    return found


def readTableFacts(path: Path) -> dict[str, dict[str, object]]:
    """Return what every archive indexed by a line says, per table.

    Everything a structural edit has to carry: records by position, header counts,
    hidden lines, merges, the declared and sidecar counts, and each formula the
    engine registers with what it reads.
    """
    index = ArchiveIndex(readPackage(path))
    sheet = index.resolve(findRoot(index).sheets[0], tn.SheetArchive)
    owners = readTableOwnerEntries(index, findCalculationEngine(index))
    facts: dict[str, dict[str, object]] = {}
    for drawable in sheet.drawable_infos:
        info = index.resolve(drawable, tst.TableInfoArchive)
        model = index.resolve(info.tableModel, tst.TableModelArchive)
        store = model.base_data_store
        records = {}
        for entry in store.tiles.tiles:
            tile = index.resolve(entry.tile, tst.Tile)
            for rowInfo in tile.rowInfos:
                row = entry.tileid * store.tiles.tile_size + rowInfo.tile_row_index
                unit = chooseOffsetUnit(
                    rowInfo.has_wide_offsets, tile.should_use_wide_rows
                )
                for record in decodeRow(
                    rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
                ):
                    records[(row, record.column)] = record.typeByte
        uids = index.resolve(model.base_column_row_uids, tst.ColumnRowUIDMapArchive)
        rows = [
            readUuidValue(uids.sorted_row_uids[at]) for at in uids.row_uid_for_index
        ]
        columns = [
            readUuidValue(uids.sorted_column_uids[at])
            for at in uids.column_uid_for_index
        ]
        hidden = []
        for states in model.hidden_states_owner.hidden_states:
            for order, extent in (
                (rows, states.row_hidden_state_extent),
                (columns, states.column_hidden_state_extent),
            ):
                hidden.extend(
                    (extent.row_or_column_direction,
                     order.index(readUuidValue(state.row_or_column_uid)))
                    for state in extent.base_hidden_states
                )
        tiles = [
            (entry.tileid, index.resolve(entry.tile, tst.Tile).numrows)
            for entry in store.tiles.tiles
        ]
        declaredInfo = tspArchive.ArchiveInfo()
        declaredInfo.ParseFromString(index.archive(info.tableModel.identifier).infoBytes)
        declared = list(declaredInfo.message_infos[0].object_references)
        tileIdentifiers = [entry.tile.identifier for entry in store.tiles.tiles]
        rowBuckets = [
            index.resolve(reference, tst.HeaderStorageBucket)
            for reference in store.rowHeaders.buckets
        ]
        columnBucket = index.resolve(store.columnHeaders, tst.HeaderStorageBucket)
        sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
        dependencies = owners[drawable.identifier].dependencies
        facts[model.table_name] = {
            "size": (model.number_of_rows, model.number_of_columns),
            "sidecar": (sidecar.row_count, sidecar.column_count),
            "records": records,
            "tiles": tiles,
            "rowTileTree": [
                (node.key, node.value) for node in store.rowTileTree.nodes
            ],
            "nextRowStripID": store.nextRowStripID,
            "declared": (
                [identifier in declared for identifier in tileIdentifiers],
                [target for target in declared if target not in tileIdentifiers],
            ),
            "rowHeaders": [
                [(h.index, h.numberOfCells) for h in bucket.headers]
                for bucket in rowBuckets
            ],
            "bands": (
                model.number_of_header_rows, model.number_of_header_columns,
                model.number_of_footer_rows,
            ),
            "strokes": readStrokeLayers(index, model),
            "spills": [
                (spill.coordinate.row, spill.coordinate.column,
                 spill.spill_size.num_rows, spill.spill_size.num_columns)
                for spill in dependencies.spill_range_sizes.spills
            ],
            "volatile": readVolatileCells(dependencies),
            "columnHeaders": [(h.index, h.numberOfCells) for h in columnBucket.headers],
            "hidden": sorted(hidden),
            "merges": sorted(
                str(node.AST_colon_tract)
                for pair in model.merge_owner.formula_store.formulas
                for node in pair.formula.AST_node_array.AST_node
                if node.HasField("AST_colon_tract")
            ),
            "registered": sorted(
                (
                    record.row, record.column,
                    tuple(record.expanded_edges.edge_without_owner_rows),
                    tuple(record.expanded_edges.edge_without_owner_columns),
                )
                for record in dependencies.cell_dependencies.cell_record
            ),
            "ranges": sorted(
                (
                    entry.cell_coord_row, entry.cell_coord_column,
                    str(entry.internal_range_reference.range),
                )
                for entry in dependencies.range_dependencies.back_dependency
            ),
        }
    return facts


def readConditionalRules(path: Path, tableName: str) -> tuple[object, object]:
    """Return each cell's rule, whether its rule matched, and every rule's refcount.

    A rule is compared by its content rather than its key, since Numbers numbers
    the copies of a broken rule in no order the cells follow.
    """
    index = ArchiveIndex(readPackage(path))
    for sheet in findRoot(index).sheets:
        for drawable in index.resolve(sheet, tn.SheetArchive).drawable_infos:
            info = index.resolve(drawable, tst.TableInfoArchive)
            model = index.resolve(info.tableModel, tst.TableModelArchive)
            if model.table_name != tableName:
                continue
            store = model.base_data_store
            rules = {
                entry.key: (
                    entry.refcount,
                    index.resolve(
                        entry.reference, tst.ConditionalStyleSetArchive
                    ).SerializeToString(deterministic=True),
                )
                for entry in index.resolve(
                    store.conditionalstyletable, tst.TableDataList
                ).entries
            }
            cells = {}
            for entry in store.tiles.tiles:
                tile = index.resolve(entry.tile, tst.Tile)
                for rowInfo in tile.rowInfos:
                    unit = chooseOffsetUnit(
                        rowInfo.has_wide_offsets, tile.should_use_wide_rows
                    )
                    for record in decodeRow(
                        rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
                    ):
                        key = findSlotValue(record, conditionalSlot)
                        cells[(rowInfo.tile_row_index, record.column)] = (
                            record.typeByte,
                            rules[key][1] if key in rules else key,
                            findSlotValue(record, matchSlot),
                        )
            return cells, sorted(rules.values())
    raise AssertionError(f"{path.name} holds no table {tableName!r}")
