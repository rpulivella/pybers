#!/usr/bin/env python3
"""\
Rows and columns added and removed, against six edits Numbers made itself.

`56-structure-base` carries labeled formulas, merges placed before, across and
beyond each edit, a hidden row and column, and a second table reading the first.
Each of `56b` through `56g` is that document with one edit made in Numbers, so a
pybers edit is compared against Numbers' own result rather than against a
description of it.

UPDATES
2026-09-18  Written for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/18"

from collections.abc import Callable
from pathlib import Path

import pytest

import pybers
from conftest import findDocumentPath
from pybers._engine import findCalculationEngine, readTableOwnerEntries
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSCEArchives_pb2 as tsce
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import chooseOffsetUnit, decodeRow, readPackage
from pybers._persistence.difference import listPackageDifferences
from pybers._persistence.index import ArchiveIndex, findRoot, readUuidValue
from pybers.addressing.reference import ReferenceError as CellReferenceError
from pybers.errors import WriteError

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
}

# Where Numbers stored a newly broken formula as an error and pybers keeps the
# result it last cached, for Numbers to recompute on open as it does every moved
# formula. Named so a further difference fails.
recomputedOnOpen: dict[str, set[tuple[str, int, int]]] = {
    "56c-row-deleted": {("Table 1", 7, 1)},
    "56e-column-deleted": {("Table 1", 11, 1), ("Table 2", 2, 0)},
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
        rowBucket = index.resolve(store.rowHeaders.buckets[0], tst.HeaderStorageBucket)
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
            "rowHeaders": [(h.index, h.numberOfCells) for h in rowBucket.headers],
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


@pytest.mark.parametrize("name", sorted(measuredEdits))
def testAnEditReachesTheModelNumbersReached(name: str) -> None:
    """PYB-17 AC 1 to 4: sizes, merges, every formula node and every plain value."""
    document = openBase()
    measuredEdits[name](document.sheets[0].table("Table 1"))
    assert reduceModel(document) == reduceModel(pybers.open(findDocumentPath(name)))


@pytest.mark.parametrize("name", sorted(measuredEdits))
def testASavedEditWritesTheArchivesNumbersWrote(name: str, tmp_path: Path) -> None:
    """PYB-17 AC 1, 2 and 5, down to what the engine says each formula reads."""
    document = openBase()
    measuredEdits[name](document.sheets[0].table("Table 1"))
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    ours = readTableFacts(target)
    theirs = readTableFacts(findDocumentPath(name))
    expected = recomputedOnOpen.get(name, set())
    for tableName, facts in theirs.items():
        for key, value in facts.items():
            if key == "records":
                assert isinstance(value, dict)
                cached = {
                    (row, column) for table, row, column in expected
                    if table == tableName
                }
                assert {
                    position: kind for position, kind in value.items()
                    if position not in cached
                } == {
                    position: kind for position, kind in ours[tableName][key].items()
                    if position not in cached
                }, tableName
                continue
            assert ours[tableName][key] == value, (tableName, key)


def testARangeGrowingPastTheInsertionMovesOnlyItsFarEnd() -> None:
    """PYB-17 AC 2.i, the ticket's own example on a table built by hand."""
    table = pybers.Table("Ledger", rowCount=30, colCount=4)
    table.cell("D1").formulaText = "=SUM(C3:C25)"
    table.rowAdd(10)
    assert table.cell("D1").formulaText == "=SUM(C3:C26)"


def testAReferenceWhollyBeforeTheInsertionIsNotRewritten() -> None:
    """PYB-17 AC 2.ii: `B4` reads `A1`, and an insertion at row 5 leaves it alone."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    before = table.cell("B4").formula
    table.rowAdd(5)
    assert table.cell("B4").formula is before


def testAMovedFormulaStillReadsTheCellBeforeTheInsertion() -> None:
    """`B4` moves to `B5` and its offset grows, so it still names `A1`."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    table.rowAdd(3)
    assert table.cell("B5").formulaText == "=A1"


def testALockedReferenceFollowsTheLineItNames() -> None:
    """Locking survives a drag, not the grid changing under it, as `56b` measured."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    table.rowAdd(2, 2)
    assert table.cell("B4").formulaText == "=SUM($A$1:$A$12)"
    assert table.cell("B7").formulaText == "=$A$10"


def testMergesGrowMoveOrStayWithAnInsertion() -> None:
    """PYB-17 AC 3, one of each, as `56f` holds them."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    table.rowAdd(3)
    extents = {str(merge.extent) for merge in table.mergeRanges}
    assert {"C1:D1", "C2:D4", "C9:D9"} <= extents


def testRemovingAReferencedRowReportsTheCellItBroke() -> None:
    """PYB-17 AC 4: `B10` read rows 2 and 3, and says so rather than repointing."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    lost = table._rowIdentities[1:3]
    broken = table.rowRemove(2, 2)
    assert [str(cell.reference) for cell in broken] == ["B8"]
    formula = table.cell("B8").formula
    assert formula is not None
    reference = formula.references[0]
    assert reference.broken
    assert reference.loss is not None and reference.loss.rows == tuple(lost)
    assert table.cell("B8").formulaText == "=SUM(#REF!)"


def testRemovingAReferencedColumnBreaksAFormulaInAnotherTable() -> None:
    """A formula elsewhere names this table by identity, and follows it too."""
    document = openBase()
    broken = document.sheets[0].table("Table 1").columnRemove("C", 5)
    found = {
        (cell.table.name, str(cell.reference)) for cell in broken if cell.table
    }
    assert found == {("Table 1", "B12"), ("Table 2", "A3")}


def testHiddenLinesStayHiddenAcrossASave(tmp_path: Path) -> None:
    """PYB-17 AC 5: row 9 and column H, wherever the edit moved them."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    table.rowAdd(1)
    table.columnAdd("A")
    target = tmp_path / "hidden.numbers"
    document.save(target)
    assert readTableFacts(target)["Table 1"]["hidden"] == [(0, 8), (1, 9)]


def testAddingThenRemovingTheSameRowSavesTheDocumentUnchanged(tmp_path: Path) -> None:
    """The identity a row gains goes with it, so nothing reads as changed."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    table.rowAdd(4)
    table.rowRemove(4)
    target = tmp_path / "unchanged.numbers"
    document.save(target)
    differences = listPackageDifferences(readPackage(baseFixture), readPackage(target))
    assert [
        difference for difference in differences if difference.identifier is not None
    ] == []


def testRowsCrossTileBoundariesInALargeTable(tmp_path: Path) -> None:
    """`27-big-table` spans eight tiles, so every row past the edit changes tile."""
    document = pybers.open(findDocumentPath("27-big-table"))
    table = document.sheets[0].tables[0]
    before = [table.cell(row=row, col=1).value for row in (1, 256, 257, 2001)]
    table.rowAdd(1)
    target = tmp_path / "big.numbers"
    document.save(target)
    reopened = pybers.open(target).sheets[0].tables[0]
    assert reopened.rowCount == 2002
    after = [reopened.cell(row=row, col=1).value for row in (2, 257, 258, 2002)]
    assert after == before
    assert reopened.cell(row=1, col=1).value is None


@pytest.mark.parametrize(
    ("name", "edit"),
    [
        ("27b-rows-inserted-into-a-new-tile",
         lambda table: table.rowAdd(100, 60)),
        ("27c-rows-deleted-emptying-a-tile",
         lambda table: table.rowRemove(1, 300)),
    ],
)
def testTilesAreCreatedAndDroppedAsNumbersDoes(
    name: str, edit: Callable[[pybers.Table], object], tmp_path: Path
) -> None:
    """`27-big-table` spans eight tiles, and an edit crossing them moves every row."""
    document = pybers.open(findDocumentPath("27-big-table"))
    edit(document.sheets[0].tables[0])
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    ours = readTableFacts(target)["Table 1"]
    theirs = readTableFacts(findDocumentPath(name))["Table 1"]
    for key in (
        "size", "sidecar", "records", "rowHeaders", "columnHeaders",
        "tiles", "rowTileTree", "nextRowStripID",
    ):
        assert ours[key] == theirs[key], key


# One edit each against the table of `57-structure-refusals-base` it belongs to,
# with the measurement Numbers made of the same edit.
refusalMeasurements: dict[str, tuple[str, Callable[[pybers.Table], object]]] = {
    "57-borders-row-inserted": ("Borders", lambda table: table.rowAdd(3)),
    "57-borders-row-deleted": ("Borders", lambda table: table.rowRemove(3)),
    "57-borders-column-inserted": ("Borders", lambda table: table.columnAdd(3)),
    "57-borders-column-deleted": ("Borders", lambda table: table.columnRemove(3)),
    "57-bands-header-row-inserted": ("Bands", lambda table: table.rowAdd(2)),
    "57-bands-header-row-deleted": ("Bands", lambda table: table.rowRemove(1)),
    "57-bands-row-inserted-before-footer": ("Bands", lambda table: table.rowAdd(8)),
    "57-bands-footer-row-deleted": ("Bands", lambda table: table.rowRemove(8)),
    "57-bands-column-inserted-before-header": (
        "Bands", lambda table: table.columnAdd(1)
    ),
    "57-bands-header-column-deleted": ("Bands", lambda table: table.columnRemove(1)),
}


@pytest.mark.parametrize("name", sorted(refusalMeasurements))
def testBordersBandsAndSpillsFollowTheEdit(name: str, tmp_path: Path) -> None:
    """PYB-17: the state that has no cells of its own, against Numbers' own edit."""
    table, edit = refusalMeasurements[name]
    document = pybers.open(findDocumentPath("57-structure-refusals-base"))
    edit(document.sheet(1).table(table))
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    ours = readTableFacts(target)[table]
    theirs = readTableFacts(findDocumentPath(name))[table]
    for key in ("size", "sidecar", "bands", "strokes", "records", "spills"):
        assert ours[key] == theirs[key], key


def testATableHoldingASpillIsRefused(tmp_path: Path) -> None:
    """Numbers re-flows a spill rather than moving it, which means evaluating it."""
    document = pybers.open(findDocumentPath("57-structure-refusals-base"))
    document.sheet(1).table("Engine").rowAdd(2)
    with pytest.raises(WriteError, match="spills into the cells under it"):
        document.save(tmp_path / "refused.numbers")


def testATableWithConditionalHighlightingIsRefused(tmp_path: Path) -> None:
    """Numbers rewrites the rules themselves, which no ticket has covered."""
    document = pybers.open(findDocumentPath("57-structure-refusals-base"))
    document.sheet(1).table("Conditions").rowAdd(3)
    with pytest.raises(WriteError, match="conditional highlighting"):
        document.save(tmp_path / "refused.numbers")


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda table: table.rowAdd(0), "from 1 to 13"),
        (lambda table: table.rowAdd(14), "from 1 to 13"),
        (lambda table: table.rowAdd(3, 0), "one or more rows"),
        (lambda table: table.rowAdd(True), "named by a number"),
        (lambda table: table.rowRemove(12, 2), "cannot be removed"),
        (lambda table: table.rowRemove(1, 12), "would leave none"),
        (lambda table: table.rowRemove(2), "anchor of the merge C2:D3"),
        (lambda table: table.columnRemove("D"), "one cell"),
        (lambda table: table.columnAdd("LEDGER"), "past column"),
        (lambda table: table.rowAdd(1, 1000000), "past the 1000000"),
    ],
)
def testARefusedEditLeavesTheDocumentAsItWas(
    edit: Callable[[pybers.Table], object], message: str
) -> None:
    """Every refusal is checked before anything moves."""
    document = openBase()
    before = reduceModel(document)
    with pytest.raises(CellReferenceError, match=message):
        edit(document.sheets[0].table("Table 1"))
    assert reduceModel(document) == before


def testRemovingALineThatLeavesAMergeOneCellIsRefused() -> None:
    """A merge cannot be one cell, and Numbers' answer here is unmeasured."""
    table = pybers.Table("Merged", rowCount=3, colCount=3)
    table.mergeAdd("A2:A3")
    with pytest.raises(CellReferenceError, match="one cell"):
        table.rowRemove(3)


def testATableAddedAndEditedBeforeItsFirstSaveWritesItsIdentities(
    tmp_path: Path,
) -> None:
    """A created table writes the model's identities, so the edit needs no replay."""
    document = openBase()
    table = document.sheets[0].tableAdd("Fresh", rows=3, cols=2)
    table.rowAdd(2)
    target = tmp_path / "created.numbers"
    document.save(target)
    reopened = pybers.open(target).sheets[0].table("Fresh")
    assert reopened.rowCount == 4
    assert reopened._rowIdentities == table._rowIdentities


def testAScriptAuthorInsertsARowAndSaves(tmp_path: Path) -> None:
    """The few lines a script writes: open, insert, save, and read it back."""
    document = pybers.open(baseFixture)
    document.sheet(1).table("Table 1").rowAdd(3)
    document.save(tmp_path / "scripted.numbers")
    table = pybers.open(tmp_path / "scripted.numbers").sheet(1).table("Table 1")
    assert table.cell("B1").formulaText == "=SUM(A1:A11)"


def testACommandLineRemovesAColumnByLetterAndReportsWhatBroke() -> None:
    """A CLI passes the column as typed and prints the cells now reading #REF!."""
    arguments = ["Table 1", "E"]
    document = pybers.open(baseFixture)
    broken = document.sheet(1).table(arguments[0]).columnRemove(arguments[1])
    assert [f"{cell.reference}" for cell in broken] == ["B12"]


goldenDirectory: Path = Path(__file__).resolve().parent / "golden"

# Each golden and the edit that made it. An added line takes a random identity, as
# Numbers gives one, so the UID map is the one archive allowed to differ.
goldenEdits: dict[str, tuple[Callable[[pybers.Table], object], set[str]]] = {
    "56-row-added-by-pybers": (
        lambda table: table.rowAdd(3), {"TST.ColumnRowUIDMapArchive"}
    ),
    "56-row-removed-by-pybers": (lambda table: table.rowRemove(8), set()),
    "56-column-added-by-pybers": (
        lambda table: table.columnAdd("E"), {"TST.ColumnRowUIDMapArchive"}
    ),
    "56-column-removed-by-pybers": (lambda table: table.columnRemove("E"), set()),
}


@pytest.mark.parametrize("name", sorted(goldenEdits))
def testTheStructureGoldensMatchWhatThisLibraryProduces(
    name: str, tmp_path: Path
) -> None:
    """PYB-17 AC 6: each edit again, against the file Numbers confirmed."""
    edit, allowed = goldenEdits[name]
    expected = goldenDirectory / f"{name}.numbers"
    document = openBase()
    table = document.sheet(1).table("Table 1")
    stored = set(table._rowIdentities) | set(table._columnIdentities)
    edit(table)
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    differences = listPackageDifferences(readPackage(expected), readPackage(target))
    assert {
        difference.typeName for difference in differences
        if difference.identifier is not None
    } <= allowed
    golden = pybers.open(expected).sheet(1).table("Table 1")
    for ours, theirs in (
        (table._rowIdentities, golden._rowIdentities),
        (table._columnIdentities, golden._columnIdentities),
    ):
        assert [line for line in ours if line in stored] == [
            line for line in theirs if line in stored
        ]
