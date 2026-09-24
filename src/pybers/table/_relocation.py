#!/usr/bin/env python3
"""\
Cells moved as a block, carried into the tiles, headers and borders that hold them.

**The move is derived, never recorded**, as a structural edit is. Each cell read
from the file remembers where its record sat, so comparing that, after any rows
or columns an edit added or removed, with where the cell is now gives every move.

**A record moves whole**, so its style, format, highlighting and formula keys go
with it, measured 2026-09-23 in `61-move-*`. A row left holding nothing is dropped,
and each line's header counts the records it holds, dropped when it holds none and
carries nothing else, as Numbers left them in `61b-move-styles-cut-pasted`.

Private. Part of the table feature's archive half.

UPDATES
2026-09-23  Written for PYB-18.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/23"

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .._generated import TSTArchives_pb2 as tst
from .._persistence import chooseOffsetUnit, decodeRow
from .._persistence.cells import CellRecord, carriesFormula, offsetWidth
from .._persistence.index import ArchiveIndex
from .._persistence.metadata import PackageRegistry
from ..addressing.reference import originOffset
from ..errors import WriteError
from ._lines import GridMaps
from ._strokes import listStrokeLayers, moveStrokeEdges
from ._structure import rowsPerBucket
from ._tiles import buildTileRange, createRowStorage, rewriteRow, writeTileRange
from .cells import Table

# A stored (row, column), counted from zero, mapped to where its cell now sits.
type CellMoves = dict[tuple[int, int], tuple[int, int]]


def findCellMoves(table: Table, maps: GridMaps) -> CellMoves:
    """Return every cell whose record sits elsewhere than the cell, after any edit.

    A cell whose stored line an edit removed has no record left to move, which is
    how a merged value carried off its anchor's line is written afresh.
    """
    moves: CellMoves = {}
    for reference, cell in table.cells.items():
        origin = cell._origin
        if origin is None:
            continue
        row = maps.rows.lineMap(origin.row - originOffset)
        column = maps.columns.lineMap(origin.col - originOffset)
        if row is None or column is None:
            continue
        landed = (reference.row - originOffset, reference.col - originOffset)
        if (row, column) != landed:
            moves[(row, column)] = landed
    return moves


@dataclass(frozen=True, slots=True)
class RecordMoves:
    """What moving the records changed: formulas moved, and every line touched."""

    formulas: list[tuple[tuple[int, int], tuple[int, int]]]
    rows: frozenset[int]
    columns: frozenset[int]


def moveCellRecords(
    index: ArchiveIndex,
    registry: PackageRegistry,
    store: tst.DataStore,
    moves: Mapping[tuple[int, int], tuple[int, int]],
) -> RecordMoves:
    """Lift every moved record, then set each down where its cell landed.

    Lifted before any is placed, so a block overlapping where it was never
    overwrites a record it has yet to move.
    """
    tileSize = store.tiles.tile_size
    tileRange = buildTileRange(index, registry, store)
    lifted: dict[tuple[int, int], CellRecord] = {}
    for tileid, tile in tileRange.tiles.items():
        for rowInfo in tile.rowInfos:
            row = tileid * tileSize + rowInfo.tile_row_index
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                if (row, record.column) in moves:
                    lifted[(row, record.column)] = record

    removals: dict[int, set[int]] = {}
    placements: dict[int, dict[int, bytes]] = {}
    for (row, column), record in lifted.items():
        removals.setdefault(row, set()).add(column)
        newRow, newColumn = moves[(row, column)]
        placements.setdefault(newRow, {})[newColumn] = record.raw

    created = False
    for row in sorted(set(removals) | set(placements)):
        tileid = row // tileSize
        created |= tileid not in tileRange.tiles
        tile = tileRange.tileFor(tileid)
        if not any(held.tile_row_index == row % tileSize for held in tile.rowInfos):
            createRowStorage(tile, row % tileSize)
        # Found after creation, because a repeated field stores a copy of its input.
        rowInfo = next(
            held for held in tile.rowInfos if held.tile_row_index == row % tileSize
        )
        placed = placements.get(row, {})
        slots = len(rowInfo.cell_offsets) // offsetWidth
        beyond = [column for column in placed if column >= slots]
        if beyond:
            raise WriteError(
                f"A record would move to column {min(beyond) + originOffset}, past the "
                f"{slots} offset slots row {row + originOffset} carries."
            )
        unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
        rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRow(
            rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit, placed,
            frozenset(removals.get(row, set()) - placed.keys()),
        )
        rowInfo.cell_count = len(
            decodeRow(rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit)
        )
        if not rowInfo.cell_count:
            tile.rowInfos.remove(rowInfo)
        tile.numrows = len(tile.rowInfos)

    spent = {
        tileid for tileid, tile in tileRange.tiles.items()
        if tileid and not tile.rowInfos
    }
    if created or spent:
        writeTileRange(registry, store, tileRange.tiles, spent)
    return RecordMoves(
        formulas=[
            (stored, moves[stored])
            for stored, record in lifted.items() if carriesFormula(record)
        ],
        rows=frozenset(
            line for stored, landed in moves.items() for line in (stored[0], landed[0])
        ),
        columns=frozenset(
            line for stored, landed in moves.items() for line in (stored[1], landed[1])
        ),
    )


def countLineRecords(
    index: ArchiveIndex, store: tst.DataStore
) -> tuple[Counter[int], Counter[int]]:
    """Return how many records each row and each column holds."""
    tileSize = store.tiles.tile_size
    rows: Counter[int] = Counter()
    columns: Counter[int] = Counter()
    for entry in store.tiles.tiles:
        tile = index.resolve(entry.tile, tst.Tile)
        for rowInfo in tile.rowInfos:
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                rows[entry.tileid * tileSize + rowInfo.tile_row_index] += 1
                columns[record.column] += 1
    return rows, columns


def carriesOnlyCount(header: tst.HeaderStorageBucket.Header) -> bool:
    """Report whether a header says nothing beyond how many cells its line holds."""
    return (
        header.size == 0
        and header.hidingState == 0
        and not header.HasField("cell_style")
        and not header.HasField("text_style")
    )


def updateHeaderCounts(
    buckets: list[tst.HeaderStorageBucket], lines: Iterable[int], counts: Counter[int]
) -> None:
    """Recount the headers of the lines a move touched, adding or dropping them."""
    for line in lines:
        bucket = buckets[min(line // rowsPerBucket, len(buckets) - 1)]
        header = next((held for held in bucket.headers if held.index == line), None)
        if header is None:
            if counts[line]:
                bucket.headers.add(
                    index=line, size=0, hidingState=0, numberOfCells=counts[line]
                )
        elif counts[line] or not carriesOnlyCount(header):
            header.numberOfCells = counts[line]
        else:
            bucket.headers.remove(header)
    for bucket in buckets:
        bucket.headers.sort(key=lambda held: held.index)


def applyCellMoves(
    index: ArchiveIndex,
    registry: PackageRegistry,
    model: tst.TableModelArchive,
    moves: Mapping[tuple[int, int], tuple[int, int]],
) -> RecordMoves:
    """Carry every moved cell into its records, headers and borders."""
    store = model.base_data_store
    moved = moveCellRecords(index, registry, store, moves)
    rowCounts, columnCounts = countLineRecords(index, store)
    rowBuckets = [
        index.resolve(reference, tst.HeaderStorageBucket)
        for reference in store.rowHeaders.buckets
    ]
    updateHeaderCounts(rowBuckets, sorted(moved.rows), rowCounts)
    for reference, bucket in zip(store.rowHeaders.buckets, rowBuckets, strict=True):
        index.archiveWrite(reference.identifier, bucket)
    columnBucket = index.resolve(store.columnHeaders, tst.HeaderStorageBucket)
    updateHeaderCounts([columnBucket], sorted(moved.columns), columnCounts)
    index.archiveWrite(store.columnHeaders.identifier, columnBucket)

    sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
    moveStrokeEdges(index, registry, sidecar, moves)
    index.archiveWrite(
        model.stroke_sidecar.identifier, sidecar, listStrokeLayers(sidecar)
    )
    return moved


__all__ = ["CellMoves", "RecordMoves", "applyCellMoves", "findCellMoves"]
