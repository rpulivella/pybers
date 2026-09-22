#!/usr/bin/env python3
"""\
A table's rows and columns added or removed, carried into every archive indexed by one.

The orchestration of one structural edit's archives, from the line maps `_lines`
derives. Here: the UID map, the header buckets and their counts, the bands,
hidden state, the declared counts, the layout cache and the merge store. Borders
move in `_strokes`, conditional highlighting in `_conditions`, and tiles in the
tile pass of `_write`, where the lists a removed record releases are already
open. The calculation engine is re-registered by the document writer, which
knows what every formula reads.

Private. The table feature offers `Table.rowAdd` and its siblings.

UPDATES
2026-09-21  Line maps and borders moved to `_lines` and `_strokes`.
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

from .._generated import TSTArchives_pb2 as tst
from .._persistence import IWAFile, chooseOffsetUnit, decodeRow
from .._persistence.index import ArchiveIndex, originOffset, readUuidValue
from .._persistence.metadata import PackageRegistry
from ._conditions import ConditionalPlan, buildConditionalPlan
from ._create import assignUids
from ._lines import (
    GridMaps,
    LineMap,
    findDisplacedLine,
    listAddedLines,
)
from ._read import readLineIdentities
from ._strokes import applyStrokeLayers, listStrokeLayers
from .cells import Table


def countBands(lines: LineMap, leading: int, trailing: int) -> tuple[int, int]:
    """Return what a leading and a trailing band hold after the edit.

    A band covers a stretch of lines rather than a count, so a line added inside
    one grows it and a line removed from one shrinks it. A line added at the
    trailing band's own first line lands inside it, measured 2026-09-21 in
    `57-bands-row-inserted-before-footer`, where a footer of one became two.
    """
    held = len(lines.lines)
    removedLeading = sum(
        1 for line in range(leading) if lines.lines[line] is None
    )
    removedTrailing = sum(
        1 for line in range(held - trailing, held) if lines.lines[line] is None
    )
    addedLeading = addedTrailing = 0
    for line in listAddedLines(lines):
        displaced = findDisplacedLine(lines, line)
        boundary = held if displaced is None else displaced
        addedLeading += boundary < leading
        addedTrailing += trailing > 0 and boundary >= held - trailing
    return (
        leading - removedLeading + addedLeading,
        trailing - removedTrailing + addedTrailing,
    )


def applyBandCounts(model: tst.TableModelArchive, maps: GridMaps) -> None:
    """Grow or shrink each band by the lines the edit added to or took from it.

    A count is written only when it changed, because a field set to the zero it
    already held is a byte a table without bands never carried.
    """
    headerRows, footerRows = countBands(
        maps.rows, model.number_of_header_rows, model.number_of_footer_rows
    )
    headerColumns = countBands(
        maps.columns, model.number_of_header_columns, 0
    )[0]
    for name, count in (
        ("number_of_header_rows", headerRows),
        ("number_of_footer_rows", footerRows),
        ("number_of_header_columns", headerColumns),
    ):
        if getattr(model, name) != count:
            setattr(model, name, count)


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


# The rows one bucket of row headers holds, measured 2026-09-21: in a table of
# 100,000 rows, row 65,536 sits in the first bucket and row 65,537 in the second.
rowsPerBucket: int = 65536


def remapHeaders(
    buckets: list[tst.HeaderStorageBucket], lines: LineMap, counts: Counter[int]
) -> None:
    """Move each line's header to its new index and bucket, recounting its cells.

    A line added carries no header, which is how Numbers writes one at the default
    size, and a removed line's header goes with it. A header lands in the bucket
    its index falls in, and a table keeping one bucket keeps every header there:
    rows added past 65,536 left `58-buckets-created` with one bucket, where setting
    the row count had created sixteen.
    """
    placed: list[list[tst.HeaderStorageBucket.Header]] = [[] for _ in buckets]
    for bucket in buckets:
        for header in bucket.headers:
            moved = lines.lineMap(header.index)
            if moved is None:
                continue
            copy = tst.HeaderStorageBucket.Header()
            copy.CopyFrom(header)
            copy.index = moved
            copy.numberOfCells = counts[moved]
            placed[min(moved // rowsPerBucket, len(buckets) - 1)].append(copy)
    for bucket, headers in zip(buckets, placed, strict=True):
        del bucket.headers[:]
        bucket.headers.extend(sorted(headers, key=lambda header: header.index))


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
    registry: PackageRegistry,
    owners: dict[int, IWAFile],
    table: Table,
    info: tst.TableInfoArchive,
    infoIdentifier: int,
    model: tst.TableModelArchive,
    maps: GridMaps,
) -> ConditionalPlan | None:
    """Carry a structural edit into every archive of the table indexed by a line.

    The table model and its info are mutated for the caller to serialize, and the
    archives it points at are written here.
    """
    store = model.base_data_store
    rowCounts, columnCounts = countSurvivingCells(index, store, maps)
    # Read before the UID map is rewritten, since a broken rule records the lines
    # as they were stored.
    storedRows, storedColumns = readLineIdentities(index, model)
    plan = buildConditionalPlan(
        index, registry, owners, store, maps, table.identifier,
        storedRows, storedColumns,
    )

    uidReference = model.base_column_row_uids
    uids = index.resolve(uidReference, tst.ColumnRowUIDMapArchive)
    assignUids(uids, table)
    writeArchive(owners, uidReference.identifier, uids.SerializeToString())

    rowBuckets = [
        index.resolve(reference, tst.HeaderStorageBucket)
        for reference in store.rowHeaders.buckets
    ]
    remapHeaders(rowBuckets, maps.rows, rowCounts)
    for reference, bucket in zip(store.rowHeaders.buckets, rowBuckets, strict=True):
        writeArchive(owners, reference.identifier, bucket.SerializeToString())
    columnBucket = index.resolve(store.columnHeaders, tst.HeaderStorageBucket)
    remapHeaders([columnBucket], maps.columns, columnCounts)
    writeArchive(
        owners, store.columnHeaders.identifier, columnBucket.SerializeToString()
    )

    # Resolved once, because the layer pass rewrites this archive and a second
    # copy would carry the list of layers as it was before that.
    sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
    applyStrokeLayers(index, registry, owners, sidecar, maps)
    sidecar.row_count = table.rowCount
    sidecar.column_count = table.colCount
    writeArchive(
        owners, model.stroke_sidecar.identifier, sidecar.SerializeToString(),
        listStrokeLayers(sidecar),
    )

    model.number_of_rows = table.rowCount
    model.number_of_columns = table.colCount
    applyBandCounts(model, maps)
    removeHiddenStates(model, table)
    remapMergeStore(model, maps)

    # A cache Numbers refills, measured holding column indices that an edit makes
    # stale. A created table carries it empty, which Numbers already accepts.
    cache = info.layout_engine.width_height_cache
    del cache.rows_fitting_entries[:]
    cache.columns_count = table.colCount
    writeArchive(owners, infoIdentifier, info.SerializeToString())
    return plan


def writeArchive(
    owners: dict[int, IWAFile],
    identifier: int,
    data: bytes,
    references: list[int] | None = None,
) -> None:
    """Write one archive's first message back into the file holding it.

    `references` replaces what the archive declares it points at. A body that
    loses or gains one has to say so, because the registry registers what a
    component reaches from those declarations rather than from the body.
    """
    owners[identifier].messageReplace(identifier, 0, data, references)


def listModelFormulas(table: Table) -> list[tuple[int, int]]:
    """Return every cell of the model holding a formula, in stored coordinates."""
    return sorted(
        (reference.row - originOffset, reference.col - originOffset)
        for reference, cell in table.cells.items()
        if cell.formula is not None
    )


__all__ = ["applyGridStructure", "listModelFormulas"]
