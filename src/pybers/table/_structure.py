#!/usr/bin/env python3
"""\
A table's rows and columns added or removed, carried into every archive indexed by one.

**The edit is derived, never recorded.** The stored UID map says which line held
which identity, and the model says where each identity is now, so comparing the
two gives the whole mapping from stored lines to new ones. That is the same
comparison against what is stored that merges and cell values already use.

What follows the mapping here: the UID map, the header buckets and their counts,
hidden state, the declared counts, the stroke sidecar's counts, the layout cache,
and the merge store. Tiles move in `_write`, where the lists a removed record
releases are already open, and the calculation engine is re-registered by the
document writer, which knows what every formula reads.

**Refused, not guessed:** an edit inside a header or footer band, a table with
borders or conditional highlighting, and engine state keyed by cell that nothing
here moves. None of those appears in `56-structure-base`, so none is measured.

Private. The table feature offers `Table.rowAdd` and its siblings.

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

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSTArchives_pb2 as tst
from .._persistence import IWAFile, chooseOffsetUnit, decodeRow
from .._persistence.index import ArchiveIndex, originOffset, readUuidValue
from ..errors import WriteError
from ._create import assignUids
from ._read import readLineIdentities
from .cells import Table


@dataclass(frozen=True, slots=True)
class LineMap:
    """Where each stored line of one axis lands, counted from zero, None if removed."""

    lines: tuple[int | None, ...]
    count: int

    @property
    def changed(self) -> bool:
        """Report whether any line moved, went, or arrived."""
        return self.count != len(self.lines) or any(
            line != moved for line, moved in enumerate(self.lines)
        )

    def lineMap(self, line: int) -> int | None:
        """Return where one stored line lands, or None when it was removed."""
        return self.lines[line] if line < len(self.lines) else None

    def spanMap(self, begin: int, end: int) -> tuple[int, int] | None:
        """Return where a span lands, its first and last surviving lines kept."""
        kept = [
            moved for moved in (self.lineMap(line) for line in range(begin, end + 1))
            if moved is not None
        ]
        if not kept:
            return None
        return (min(kept), max(kept))


@dataclass(frozen=True, slots=True)
class GridMaps:
    """Both axes of one table's structural change, stored lines to new ones."""

    rows: LineMap
    columns: LineMap

    @property
    def changed(self) -> bool:
        """Report whether either axis changed."""
        return self.rows.changed or self.columns.changed


def buildLineMap(
    stored: Sequence[int], wanted: Sequence[int], axis: str, name: str
) -> LineMap:
    """Return where each stored line went, refusing lines that changed order.

    Added and removed lines are the only edits this library makes, so every line
    both sides hold keeps its order, and an identity only the model holds is new.
    """
    position = {identity: at for at, identity in enumerate(wanted)}
    lines = tuple(position.get(identity) for identity in stored)
    kept = [line for line in lines if line is not None]
    if kept != sorted(kept):
        raise WriteError(
            f"The {axis} of {name!r} are in a different order from the file's, and "
            "only adding and removing them is written."
        )
    return LineMap(lines, len(wanted))


def buildGridMaps(
    index: ArchiveIndex, model: tst.TableModelArchive, table: Table
) -> GridMaps:
    """Return how the model's rows and columns relate to the stored ones."""
    rows, columns = readLineIdentities(index, model)
    if len(rows) != model.number_of_rows or len(columns) != model.number_of_columns:
        raise WriteError(
            f"{table.name!r} declares {model.number_of_rows} by "
            f"{model.number_of_columns} and its UID map holds {len(rows)} by "
            f"{len(columns)}, so which line is which cannot be told."
        )
    return GridMaps(
        buildLineMap(rows, table._rowIdentities, "rows", table.name),
        buildLineMap(columns, table._columnIdentities, "columns", table.name),
    )


def listTouchedLines(lines: LineMap) -> list[tuple[int, bool]]:
    """Return each stored line removed, and each stored line additions went before.

    An addition after the last line names the line count. Each carries whether it
    was a removal.
    """
    touched = [(line, True) for line, moved in enumerate(lines.lines) if moved is None]
    expected = 0
    for line, moved in enumerate(lines.lines):
        if moved is None:
            continue
        if moved != expected:
            touched.append((line, False))
        expected = moved + 1
    if expected != lines.count:
        touched.append((len(lines.lines), False))
    return touched


def refuseBandEdit(
    lines: LineMap, leading: int, trailing: int, axis: str, name: str
) -> None:
    """Refuse an edit touching a header or footer band, which is unmeasured.

    `leading` bands sit at the start of the axis and `trailing` at its end. Adding
    lines right after a leading band, or right before a trailing one, is body.
    """
    held = len(lines.lines)
    for line, removed in listTouchedLines(lines):
        inLeading = line < leading
        inTrailing = trailing > 0 and (
            line >= held - trailing if removed else line > held - trailing
        )
        if inLeading or inTrailing:
            raise WriteError(
                f"{name!r} has {axis} added or removed inside a header or footer "
                "band, and what Numbers does to a band then is not measured."
            )


def refuseUnmovableState(
    index: ArchiveIndex, model: tst.TableModelArchive, table: Table, maps: GridMaps
) -> None:
    """Refuse a structural edit on a table holding state keyed by a line index.

    Borders live in stroke layers by row and column, and conditional highlighting
    carries rules that name cells. Moving either is unmeasured, so a table holding
    one is left alone rather than saved with it pointing at the wrong lines.
    """
    refuseBandEdit(
        maps.rows, model.number_of_header_rows, model.number_of_footer_rows,
        "rows", table.name,
    )
    refuseBandEdit(
        maps.columns, model.number_of_header_columns, 0, "columns", table.name
    )
    store = model.base_data_store
    sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
    layers = (
        sidecar.left_column_stroke_layers, sidecar.right_column_stroke_layers,
        sidecar.top_row_stroke_layers, sidecar.bottom_row_stroke_layers,
    )
    if any(len(layer) for layer in layers):
        raise WriteError(
            f"{table.name!r} carries borders, which are stored by row and column, "
            "and moving them in a structural edit is not measured."
        )
    if store.HasField("conditionalstyletable"):
        conditions = index.resolve(store.conditionalstyletable, tst.TableDataList)
        if len(conditions.entries):
            raise WriteError(
                f"{table.name!r} carries conditional highlighting, whose rules name "
                "cells, and moving them in a structural edit is not measured."
            )
    if len(store.rowHeaders.buckets) != 1:
        raise WriteError(
            f"{table.name!r} keeps its row headers in {len(store.rowHeaders.buckets)} "
            "buckets, and only one has been measured."
        )


def countSurvivingCells(
    index: ArchiveIndex, store: tst.DataStore, maps: GridMaps
) -> tuple[Counter[int], Counter[int]]:
    """Return how many records each new row and each new column will hold."""
    tileSize = store.tiles.tile_size
    rows: Counter[int] = Counter()
    columns: Counter[int] = Counter()
    for entry in store.tiles.tiles:
        tile = index.resolve(entry.tile, tst.Tile)
        for rowInfo in tile.rowInfos:
            row = maps.rows.lineMap(entry.tileid * tileSize + rowInfo.tile_row_index)
            if row is None:
                continue
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                column = maps.columns.lineMap(record.column)
                if column is None:
                    continue
                rows[row] += 1
                columns[column] += 1
    return rows, columns


def remapHeaders(
    bucket: tst.HeaderStorageBucket, lines: LineMap, counts: Counter[int]
) -> None:
    """Move each line's header to its new index, and recount the cells it holds.

    A line added carries no header, which is how Numbers writes one at the default
    size, and a removed line's header goes with it.
    """
    kept = []
    for header in bucket.headers:
        moved = lines.lineMap(header.index)
        if moved is None:
            continue
        header.index = moved
        header.numberOfCells = counts[moved]
        kept.append(header)
    kept.sort(key=lambda header: header.index)
    copies = [tst.HeaderStorageBucket.Header() for _ in kept]
    for copy, header in zip(copies, kept, strict=True):
        copy.CopyFrom(header)
    del bucket.headers[:]
    bucket.headers.extend(copies)


def removeHiddenStates(model: tst.TableModelArchive, table: Table) -> None:
    """Drop the hidden state of every line the model no longer holds.

    Keyed by identity, so a line that moved keeps its state untouched.
    """
    identities = set(table._rowIdentities) | set(table._columnIdentities)
    for states in model.hidden_states_owner.hidden_states:
        extents = (states.row_hidden_state_extent, states.column_hidden_state_extent)
        for extent in extents:
            kept = [
                state for state in extent.base_hidden_states
                if readUuidValue(state.row_or_column_uid) in identities
            ]
            if len(kept) == len(extent.base_hidden_states):
                continue
            copies = [
                tst.HiddenStateExtentArchive.RowOrColumnState() for _ in kept
            ]
            for copy, state in zip(copies, kept, strict=True):
                copy.CopyFrom(state)
            del extent.base_hidden_states[:]
            extent.base_hidden_states.extend(copies)


def remapMergeStore(model: tst.TableModelArchive, maps: GridMaps) -> None:
    """Move each stored merge with its lines, as Numbers rewrote them in `23`.

    Kept in place rather than rebuilt, so a merge the edit only moved keeps its
    formula index and is not then mistaken for one the caller added.
    """
    if not model.HasField("merge_owner"):
        return
    store = model.merge_owner.formula_store
    kept = []
    for pair in store.formulas:
        tracts = [
            node.AST_colon_tract for node in pair.formula.AST_node_array.AST_node
            if node.HasField("AST_colon_tract")
        ]
        survives = True
        for tract in tracts:
            for axis, lines in (
                (tract.absolute_row, maps.rows), (tract.absolute_column, maps.columns)
            ):
                for span in axis:
                    begin = span.range_begin
                    end = span.range_end if span.HasField("range_end") else begin
                    mapped = lines.spanMap(begin, end)
                    if mapped is None:
                        survives = False
                        continue
                    span.range_begin = mapped[0]
                    if mapped[1] != mapped[0]:
                        span.range_end = mapped[1]
                    else:
                        span.ClearField("range_end")
        if survives:
            kept.append(pair)
    if len(kept) == len(store.formulas):
        return
    copies = [tst.FormulaStoreArchive.FormulaStorePair() for _ in kept]
    for copy, pair in zip(copies, kept, strict=True):
        copy.CopyFrom(pair)
    del store.formulas[:]
    store.formulas.extend(copies)


def applyGridStructure(
    index: ArchiveIndex,
    owners: dict[int, IWAFile],
    table: Table,
    info: tst.TableInfoArchive,
    infoIdentifier: int,
    model: tst.TableModelArchive,
    maps: GridMaps,
) -> None:
    """Carry a structural edit into every archive of the table indexed by a line.

    The table model and its info are mutated for the caller to serialize, and the
    archives it points at are written here.
    """
    refuseUnmovableState(index, model, table, maps)
    store = model.base_data_store
    rowCounts, columnCounts = countSurvivingCells(index, store, maps)

    uidReference = model.base_column_row_uids
    uids = index.resolve(uidReference, tst.ColumnRowUIDMapArchive)
    assignUids(uids, table)
    writeArchive(owners, uidReference.identifier, uids.SerializeToString())

    rowBucketReference = store.rowHeaders.buckets[0]
    rowBucket = index.resolve(rowBucketReference, tst.HeaderStorageBucket)
    remapHeaders(rowBucket, maps.rows, rowCounts)
    writeArchive(owners, rowBucketReference.identifier, rowBucket.SerializeToString())
    columnBucket = index.resolve(store.columnHeaders, tst.HeaderStorageBucket)
    remapHeaders(columnBucket, maps.columns, columnCounts)
    writeArchive(
        owners, store.columnHeaders.identifier, columnBucket.SerializeToString()
    )

    sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
    sidecar.row_count = table.rowCount
    sidecar.column_count = table.colCount
    writeArchive(owners, model.stroke_sidecar.identifier, sidecar.SerializeToString())

    model.number_of_rows = table.rowCount
    model.number_of_columns = table.colCount
    removeHiddenStates(model, table)
    remapMergeStore(model, maps)

    # A cache Numbers refills, measured holding column indices that an edit makes
    # stale. A created table carries it empty, which Numbers already accepts.
    cache = info.layout_engine.width_height_cache
    del cache.rows_fitting_entries[:]
    cache.columns_count = table.colCount
    writeArchive(owners, infoIdentifier, info.SerializeToString())


def writeArchive(owners: dict[int, IWAFile], identifier: int, data: bytes) -> None:
    """Write one archive's first message back into the file holding it."""
    owners[identifier].messageReplace(identifier, 0, data)


def refuseUnmovableEngineState(
    dependencies: tsce.FormulaOwnerDependenciesArchive, name: str
) -> None:
    """Refuse engine state keyed by cell that a structural edit does not move."""
    volatile = dependencies.volatile_dependencies
    held = [
        volatile.volatile_time_cells, volatile.volatile_random_cells,
        volatile.volatile_locale_cells, volatile.volatile_sheet_table_name_cells,
        volatile.volatile_remote_data_cells, volatile.volatile_geometry_cell_refs,
        dependencies.whole_owner_dependencies.dependent_cells,
        dependencies.spill_range_sizes,
    ]
    if any(part.ByteSize() for part in held):
        raise WriteError(
            f"{name!r} holds a formula that recalculates on its own, reads the whole "
            "table, or spills, and moving what the engine records for those is not "
            "measured."
        )


def remapOwnerCoordinates(
    dependencies: tsce.FormulaOwnerDependenciesArchive, maps: GridMaps, name: str
) -> None:
    """Move the engine's cell-keyed records that no formula registration rewrites.

    Errors follow their cells, or go with a removed one, and the table's own
    extent follows its size. The errors' text is left for the recalculation every
    moved formula is marked for.
    """
    refuseUnmovableEngineState(dependencies, name)
    for spanning in (
        dependencies.spanning_column_dependencies,
        dependencies.spanning_row_dependencies,
    ):
        for extent in (spanning.total_range_for_table, spanning.body_range_for_table):
            if not extent.ByteSize():
                continue
            extent.bottom_right_row += maps.rows.count - len(maps.rows.lines)
            extent.bottom_right_column += maps.columns.count - len(maps.columns.lines)
    errors = dependencies.cell_errors
    for field in ("errors", "enhanced_errors"):
        entries = getattr(errors, field)
        kept = []
        for entry in entries:
            row = maps.rows.lineMap(entry.coordinate.row)
            column = maps.columns.lineMap(entry.coordinate.column)
            if row is None or column is None:
                continue
            entry.coordinate.row = row
            entry.coordinate.column = column
            kept.append(entry)
        copies = [type(entry)() for entry in kept]
        for copy, entry in zip(copies, kept, strict=True):
            copy.CopyFrom(entry)
        del entries[:]
        entries.extend(copies)


def listRegisteredFormulas(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
) -> list[tuple[int, int]]:
    """Return every cell the engine registers a formula at, as stored."""
    return [
        (record.row, record.column)
        for record in dependencies.cell_dependencies.cell_record
    ]


def listModelFormulas(table: Table) -> list[tuple[int, int]]:
    """Return every cell of the model holding a formula, in stored coordinates."""
    return sorted(
        (reference.row - originOffset, reference.col - originOffset)
        for reference, cell in table.cells.items()
        if cell.formula is not None
    )


__all__ = [
    "GridMaps",
    "LineMap",
    "applyGridStructure",
    "buildGridMaps",
    "listModelFormulas",
    "listRegisteredFormulas",
    "remapOwnerCoordinates",
]
