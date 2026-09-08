#!/usr/bin/env python3
"""\
What has to be told to the calculation engine when a document is written back.

There are three registers, none of them optional, and each one is silent when
it is wrong.

**The engine keeps its own register of which cells hold a formula, stored TWICE**,
and a cell missing from either is never evaluated. Updating only the first shows
the formula in the formula bar beside the cell's old value, which is the most
misleading state available, because the cell looks correct to anyone who clicks
it. Measured for PYB-42, and recorded in findings-02-formulas.md.

**Numbers does not recalculate on open**, so an edited cell has to be named in
`refs_to_dirty` or its dependents keep showing what they last computed. Naming
only the cells that changed is enough: Numbers walks its own dependency graph
from there, across tables and across sheets.

**A merge is stored as a formula**, shaped like `SUM($A$1:$B$1)` and evaluated by
nothing. The shape is how a merged region is expressed.

UPDATES
2026-09-08  Split out of `pybers.writer` for #45, unchanged.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from google.protobuf.internal.containers import RepeatedCompositeFieldContainer

from ._generated import TSCEArchives_pb2 as tsce
from ._generated import TSPMessages_pb2 as tsp
from ._generated import TSTArchives_pb2 as tst
from ._persistence import IWAFile
from ._persistence.types import archiveTypeId, parseArchive
from .archives import (
    ArchiveIndex,
    WriteError,
    calculationEngineTypeId,
    originOffset,
    wordBits,
    wordMask,
)
from .model import MergeRange
from .readengine import (
    TableOwner,
    tableOwnerEntries,
)

# A merge is written as `SUM($A$1:$B$1)`, so it carries SUM's index in Apple's own
# function table. The number is theirs and is not derivable from the schemas.
sumFunctionIndex: int = 168

# The calculation engine tiles its register of formula-bearing cells 32 columns
# wide. Measured 2026-09-04: `40-table-bands` carries eight tiles beginning at
# columns 0, 32, 64 and so on to 224, and every tile in the corpus begins at row
# zero, so the row extent of a tile is not established and is never assumed here.
dependencyTileColumns: int = 32

# The generated container both copies of that register are held in. Named so the
# one function updating either can say what it takes.
type CellRecordList = RepeatedCompositeFieldContainer[
    tsce.CellRecordExpandedArchive
]

def rewriteCellRecords(
    records: CellRecordList,
    added: list[tuple[int, int]],
    removed: list[tuple[int, int]],
) -> None:
    """Add and drop entries in one register of formula-bearing cells."""
    dropping = set(removed)
    kept = [
        record for record in records
        if (record.row, record.column) not in dropping
    ]
    present = {(record.row, record.column) for record in kept}
    del records[:]
    for record in kept:
        records.add().CopyFrom(record)
    for row, column in added:
        if (row, column) in present:
            continue
        fresh = records.add()
        fresh.column = column
        fresh.row = row
        # An empty edge set, which is what every entry in the corpus carries.
        fresh.expanded_edges.SetInParent()


def registerFormulaCells(
    index: ArchiveIndex,
    owner: TableOwner,
    added: list[tuple[int, int]],
    removed: list[tuple[int, int]],
) -> dict[int, bytes]:
    """Tell the calculation engine which cells hold formulas now, and report a change.

    **Not optional, and its absence fails silently.** Setting the record flag and
    pooling the archive leaves a formula that is never evaluated, and the register is
    stored TWICE so both copies have to agree. Updating only `cell_dependencies`
    shows the formula in Numbers' formula bar while the cell keeps its old value.
    See findings-02-formulas.md, which records all three attempts.

    Coordinates count from zero here. Returns the archives that changed, since the
    tiles are not part of the owner entry.
    """
    if not added and not removed:
        return {}
    rewriteCellRecords(owner.dependencies.cell_dependencies.cell_record,
                       added, removed)
    changed: dict[int, bytes] = {}
    for reference in owner.dependencies.tiled_cell_dependencies.cell_record_tiles:
        tile = index.resolve(reference, tsce.CellRecordTileArchive)
        band = range(
            tile.tile_column_begin,
            tile.tile_column_begin + dependencyTileColumns,
        )
        inTile = [
            (row, column) for row, column in added
            if column in band and row >= tile.tile_row_begin
        ]
        outTile = [
            (row, column) for row, column in removed
            if column in band and row >= tile.tile_row_begin
        ]
        if not inTile and not outTile:
            continue
        rewriteCellRecords(tile.cell_records, inTile, outTile)
        changed[reference.identifier] = tile.SerializeToString()

    placed = {
        (row, column)
        for reference in owner.dependencies.tiled_cell_dependencies.cell_record_tiles
        for row, column in added
        if column
        in range(
            index.resolve(reference, tsce.CellRecordTileArchive).tile_column_begin,
            index.resolve(reference, tsce.CellRecordTileArchive).tile_column_begin
            + dependencyTileColumns,
        )
    }
    missing = sorted(set(added) - placed)
    if missing:
        raise WriteError(
            f"No dependency tile covers {missing}, so a formula written there would "
            "be registered in one of the engine's two registers and not the other. "
            "Creating a tile has never been measured."
        )
    changed[owner.identifier] = owner.dependencies.SerializeToString()
    return changed


def buildDirtySet(
    edits: dict[int, list[tuple[int, int]]]
) -> tsce.ReferencesToDirtyArchive:
    """Return the archive naming every cell that moved, grouped as Numbers groups them.

    Owners hold columns, columns hold a set of row ranges. Contiguous rows collapse
    into one range, which is how Numbers writes its own, and a run of one omits
    `range_end` rather than repeating the beginning.
    """
    dirty = tsce.ReferencesToDirtyArchive()
    for ownerId, cells in sorted(edits.items()):
        dirty.to_dirty_owner_ids.entries.add(range_begin=ownerId)
        owner = dirty.to_dirty_cells.owner_entries.add()
        owner.owner_id = ownerId
        byColumn: dict[int, list[int]] = {}
        for row, column in sorted(set(cells)):
            byColumn.setdefault(column, []).append(row)
        for column, rows in sorted(byColumn.items()):
            entry = owner.coord_set.column_entries.add()
            entry.column = column
            runs: list[list[int]] = []
            for row in rows:
                if runs and row == runs[-1][1] + 1:
                    runs[-1][1] = row
                else:
                    runs.append([row, row])
            for begin, end in runs:
                added = entry.row_set.entries.add(range_begin=begin)
                if end != begin:
                    added.range_end = end
    return dirty


def ownerEntryFor(
    entries: dict[int, TableOwner],
    identifier: int,
    name: str,
) -> TableOwner:
    """Return one table's dependency entry, or refuse naming the table."""
    entry = entries.get(identifier)
    if entry is None:
        raise WriteError(
            f"{name!r} has no calculation-engine owner entry, so neither its merges "
            "nor its edited cells can be written. Every table in the fixture corpus "
            "has one."
        )
    return entry


def tableOwnerIds(
    index: ArchiveIndex, engine: tsce.CalculationEngineArchive
) -> dict[int, int]:
    """Return each table's internal owner id, keyed by its own archive."""
    return {
        identifier: owner.dependencies.internal_formula_owner_id
        for identifier, owner in tableOwnerEntries(index, engine).items()
    }


def writeMergeFormula(
    store: tst.FormulaStoreArchive, merge: MergeRange, ownerUid: tsp.UUID
) -> None:
    """Add one merged region to a table's merge store, as the formula Numbers writes.

    **A merge is stored as a formula, not as a flag on a cell.** Each region is a
    complete formula shaped like `SUM($A$1:$B$1)`: a colon-tract node carrying the
    rectangle with all four sticky bits set, then the function node for SUM. Nothing
    evaluates it; the shape is how a merge is expressed.

    The tract's table identifier is the table's own `formula_owner_uid`, split from
    two 64-bit halves into four 32-bit words, which is a different spelling of the
    same value in a different archive. Measured 2026-09-02 against `22-merge-2x2`.
    """
    pair = store.formulas.add()
    pair.formula_index = len(store.formulas) - 1

    node = pair.formula.AST_node_array.AST_node.add()
    node.AST_node_type = tsce.ASTNodeArrayArchive.COLON_TRACT_NODE
    identifier = node.AST_cross_table_reference_extra_info.table_id
    identifier.uuid_w0 = ownerUid.lower & wordMask
    identifier.uuid_w1 = ownerUid.lower >> wordBits
    identifier.uuid_w2 = ownerUid.upper & wordMask
    identifier.uuid_w3 = ownerUid.upper >> wordBits
    node.AST_sticky_bits.begin_row_is_absolute = True
    node.AST_sticky_bits.begin_column_is_absolute = True
    node.AST_sticky_bits.end_row_is_absolute = True
    node.AST_sticky_bits.end_column_is_absolute = True

    startRow, startCol, endRow, endCol = merge.bounds
    tract = node.AST_colon_tract
    columns = tract.absolute_column.add()
    columns.range_begin = startCol - originOffset
    rows = tract.absolute_row.add()
    rows.range_begin = startRow - originOffset
    # `range_end` is omitted for a span of one rather than repeating the beginning,
    # which is how Numbers writes its own and how the reader expects to find them.
    if endCol != startCol:
        columns.range_end = endCol - originOffset
    if endRow != startRow:
        rows.range_end = endRow - originOffset
    tract.preserve_rectangular = True

    function = pair.formula.AST_node_array.AST_node.add()
    function.AST_node_type = tsce.ASTNodeArrayArchive.FUNCTION_NODE
    function.AST_function_node_index = sumFunctionIndex
    function.AST_function_node_numArgs = 1


def requestRecalculation(
    index: ArchiveIndex,
    owners: dict[int, IWAFile],
    written: dict[int, list[tuple[int, int]]],
) -> int:
    """Tell Numbers which cells moved, so it recalculates whatever depends on them.

    **A formula caches its result and opening the document does not refresh it**, so a
    save without this displays arithmetic that disagrees with its own operands, with
    no prompt. Naming the edited cells is enough: Numbers walks its own graph from
    there, transitively and across sheets, which is why this library never evaluates.
    Measured 2026-09-02 both broadly and minimally, in findings-02-formulas.md.
    """
    if not written:
        return 0
    engineArchive = next(
        (
            archive for archive in index.byIdentifier.values()
            if archiveTypeId(archive) == calculationEngineTypeId
        ),
        None,
    )
    if engineArchive is None:
        raise WriteError(
            "This document has no TSCE.CalculationEngineArchive, so Numbers cannot "
            "be asked to recalculate and the saved file would display stale formula "
            "results. Every document in the fixture corpus carries one."
        )
    engine = parseArchive(engineArchive)
    if not isinstance(engine, tsce.CalculationEngineArchive):
        raise WriteError(
            f"Archive {engineArchive.identifier} carries the calculation engine's "
            f"type but parsed as {type(engine).__name__}."
        )
    if not engine.HasField("refs_to_dirty"):
        raise WriteError(
            "The calculation engine carries no refs_to_dirty reference, so the cells "
            "that changed cannot be marked and the saved file would display stale "
            "formula results."
        )

    ownerIds = tableOwnerIds(index, engine)
    edits: dict[int, list[tuple[int, int]]] = {}
    for tableIdentifier, cells in written.items():
        ownerId = ownerIds.get(tableIdentifier)
        if ownerId is None:
            raise WriteError(
                f"The table in archive {tableIdentifier} has no calculation-engine "
                "owner id, so the cells edited in it cannot be marked for "
                "recalculation and the saved file would display stale results."
            )
        edits.setdefault(ownerId, []).extend(cells)

    target = engine.refs_to_dirty.identifier
    owners[target].messageReplace(target, 0, buildDirtySet(edits).SerializeToString())
    return sum(len(cells) for cells in edits.values())


__all__ = [
    "buildDirtySet",
    "ownerEntryFor",
    "registerFormulaCells",
    "requestRecalculation",
    "tableOwnerIds",
    "writeMergeFormula",
]
