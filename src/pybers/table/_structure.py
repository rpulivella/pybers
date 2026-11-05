#!/usr/bin/env python3
"""\
A table's rows and columns added or removed, carried into every archive indexed by one.

The orchestration of one structural edit's archives, from the line maps `_lines`
derives. Here: the UID map, the header buckets and their counts, hidden state, the
declared counts and the layout cache. Borders move in `_strokes`, conditional
highlighting in `_conditions`, the merge store in `_merges`, and tiles in the tile
pass of `_edits`, where the lists a removed record releases are already open. The
calculation engine is re-registered by the table save in `_write`, which knows what
every formula reads.

Private. The table feature offers `Table.rowAdd` and its siblings.

UPDATES
2026-11-03  Header and footer counts are the model's, moved by the edit and
            written by the table's save, for PYB-223.
2026-11-02  A table with no stroke sidecar or layout cache, as a created one is,
            gains neither from a structural edit, for PYB-276.
2026-10-29  One `countLineRecords`, mapped or not, for PYB-278.
2026-09-22  The merge store moves in `_merges`, for PYB-113.
2026-09-22  Nothing is imported from table creation: the UID map is written by `_lines`,
            for PYB-113.
2026-09-22  Archives written through the save's index, for PYB-109.
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
from .._persistence.index import ArchiveIndex, readUuidValue
from .._persistence.metadata import PackageRegistry
from .._persistence.rows import readStoredTiles
from ..addressing.reference import originOffset
from ._conditions import ConditionalPlan, buildConditionalPlan
from ._lines import GridMaps, LineMap, assignUids
from ._merges import remapMergeStore
from ._read import readLineIdentities
from ._strokes import applyStrokeLayers, listStrokeLayers
from .cells import Table


def countLineRecords(
    index: ArchiveIndex, store: tst.DataStore, maps: GridMaps | None = None
) -> tuple[Counter[int], Counter[int]]:
    """Return how many records each row and each column holds, through `maps` if given.

    A record on a line the maps remove is not counted.
    """
    rows: Counter[int] = Counter()
    columns: Counter[int] = Counter()
    for stored in readStoredTiles(index, store):
        row = stored.row if maps is None else maps.rows.lineMap(stored.row)
        if row is None:
            continue
        for record in stored.records:
            column = (
                record.column if maps is None else maps.columns.lineMap(record.column)
            )
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


def applyGridStructure(
    index: ArchiveIndex,
    registry: PackageRegistry,
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
    rowCounts, columnCounts = countLineRecords(index, store, maps)
    # Read before the UID map is rewritten, since a broken rule records the lines
    # as they were stored.
    storedRows, storedColumns = readLineIdentities(index, model)
    plan = buildConditionalPlan(
        index, registry, store, maps, table.identifier,
        storedRows, storedColumns,
    )

    uidReference = model.base_column_row_uids
    uids = index.resolve(uidReference, tst.ColumnRowUIDMapArchive)
    assignUids(uids, table)
    index.archiveWrite(uidReference.identifier, uids)

    rowBuckets = [
        index.resolve(reference, tst.HeaderStorageBucket)
        for reference in store.rowHeaders.buckets
    ]
    remapHeaders(rowBuckets, maps.rows, rowCounts)
    for reference, bucket in zip(store.rowHeaders.buckets, rowBuckets, strict=True):
        index.archiveWrite(reference.identifier, bucket)
    columnBucket = index.resolve(store.columnHeaders, tst.HeaderStorageBucket)
    remapHeaders([columnBucket], maps.columns, columnCounts)
    index.archiveWrite(store.columnHeaders.identifier, columnBucket)

    # A created table has no sidecar until Numbers saves it, so no border to move.
    if model.HasField("stroke_sidecar"):
        sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
        applyStrokeLayers(index, registry, sidecar, maps)
        sidecar.row_count = table.rowCount
        sidecar.column_count = table.colCount
        index.archiveWrite(
            model.stroke_sidecar.identifier, sidecar, listStrokeLayers(sidecar)
        )

    model.number_of_rows = table.rowCount
    model.number_of_columns = table.colCount
    removeHiddenStates(model, table)
    remapMergeStore(model, maps)

    # A cache Numbers refills, measured holding column indices that an edit makes
    # stale. A created table carries none, which Numbers rebuilds.
    if info.HasField("layout_engine"):
        cache = info.layout_engine.width_height_cache
        del cache.rows_fitting_entries[:]
        cache.columns_count = table.colCount
        index.archiveWrite(infoIdentifier, info)
    return plan


def listModelFormulas(table: Table) -> list[tuple[int, int]]:
    """Return every cell of the model holding a formula, in stored coordinates."""
    return sorted(
        (reference.row - originOffset, reference.col - originOffset)
        for reference, cell in table.cells.items()
        if cell.formula is not None
    )


__all__ = ["applyGridStructure", "listModelFormulas"]
