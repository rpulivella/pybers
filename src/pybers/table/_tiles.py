#!/usr/bin/env python3
"""\
A table's tiles: the rows they store, and rows moved between them by an edit.

A tile holds 256 rows, and a row's storage is an offset array over a buffer of
cell records. This is where a row is created, rebuilt, and dealt to the tile its
new number falls in. Cell values are patched in `_write`, which uses the row
primitives here.

**Tiles are sparse.** Only tiles holding rows exist, measured 2026-09-21 in a
table grown to 100,000 rows, so a tile is created where a row lands and removed
when it empties.

Private. Part of the table feature's archive half.

UPDATES
2026-09-21  Split out of `_write` for PYB-17.
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
from dataclasses import dataclass, field

from .._generated import TSTArchives_pb2 as tst
from .._persistence import IWAFile, chooseOffsetUnit, decodeRow
from .._persistence.cells import (
    CellRecord,
    conditionalSlot,
    emptyOffset,
    findSlotValue,
    offsetWidth,
)
from .._persistence.index import ArchiveIndex, originOffset
from .._persistence.metadata import PackageRegistry, createSiblingArchive
from ..addressing import CellReference
from ..errors import WriteError
from ._conditions import (
    ConditionalPlan,
    buildInheritedRecord,
    rewriteConditionalRecord,
)
from ._lines import GridMaps, LineMap, findDisplacedLine, listAddedLines
from .cells import Table

# A first row written into an empty tile carries 255 narrow offset slots, measured in
# `01-text-plain`, `11-value-types-noformats` and `18-formula-literals` alike.
narrowRowSlots: int = 255

def createRowStorage(tile: tst.Tile, tileRowIndex: int) -> tst.TileRowInfo:
    """Add an empty row to a tile, shaped like the rows already in it.

    The offset array's length is copied from a sibling rather than computed: a
    narrow row carries a fixed 255 slots whatever the column count, and the one
    wide row measured carries one slot per column, so a rule fitted to that single
    sample would be a guess. A tile holding no row takes the narrow shape Numbers
    writes for a first row, which the caller allows only where 255 slots suffice.

    `numrows` is corrected because Numbers keeps it accurate, and `numCells`,
    `maxRow` and `maxColumn` are left alone because Numbers writes zero in all
    three on tiles full of data.
    """
    sibling = tile.rowInfos[0] if tile.rowInfos else None
    slots = (
        len(sibling.cell_offsets) // offsetWidth if sibling is not None
        else narrowRowSlots
    )
    empty = emptyOffset.to_bytes(offsetWidth, "little") * slots
    created = tst.TileRowInfo()
    created.tile_row_index = tileRowIndex
    created.cell_count = 0
    created.cell_storage_buffer_pre_bnc = b""
    created.cell_offsets_pre_bnc = empty
    created.storage_version = (
        sibling.storage_version if sibling is not None else tile.storage_version
    )
    created.cell_storage_buffer = b""
    created.cell_offsets = empty
    if sibling is not None and sibling.has_wide_offsets:
        created.has_wide_offsets = True

    at = len(tile.rowInfos)
    for position, existing in enumerate(tile.rowInfos):
        if existing.tile_row_index > tileRowIndex:
            at = position
            break
    tile.rowInfos.insert(at, created)
    tile.numrows = len(tile.rowInfos)
    return created


def rewriteRow(
    offsets: bytes,
    buffer: bytes,
    offsetUnit: int,
    replacements: dict[int, bytes],
    removals: frozenset[int] = frozenset(),
) -> tuple[bytes, bytes]:
    """Rebuild one row's offset array and storage buffer, replacing and dropping.

    The whole row is rebuilt rather than patched in place because a record's offset
    is where the previous ones ended, so a record that changes length moves every
    record after it. Untouched records are re-emitted from the bytes they were read
    from, so a row with one edit differs in exactly one record.

    A dropped column takes the same empty offset a column that never held anything
    takes, which is what a cell swallowed by a merge looks like in the file: no
    record at all rather than an empty one.
    """
    slots = len(offsets) // offsetWidth
    existing = {
        record.column: record for record in decodeRow(offsets, buffer, offsetUnit)
    }

    rebuiltOffsets = bytearray()
    rebuiltBuffer = bytearray()
    for column in range(slots):
        record = existing.get(column)
        body = replacements.get(column)
        if body is None and record is not None:
            body = record.raw
        # A replacement for a column with no record CREATES one, which is how a
        # formula reaches a cell that was empty. The offset array already carries a
        # slot for every column, so nothing grows.
        if body is None or column in removals:
            rebuiltOffsets += emptyOffset.to_bytes(offsetWidth, "little")
            continue
        # A row counting offsets in words can only name a position the unit
        # divides, so a record of any other length would silently move every
        # record after it. Refuse rather than write a row that reads back wrong.
        if len(rebuiltBuffer) % offsetUnit:
            raise WriteError(
                f"Column {column} would start at byte {len(rebuiltBuffer)} of the "
                f"row buffer, which is not a multiple of the {offsetUnit}-byte "
                "unit this row counts its offsets in."
            )
        rebuiltOffsets += (len(rebuiltBuffer) // offsetUnit).to_bytes(
            offsetWidth, "little"
        )
        rebuiltBuffer += body
    return bytes(rebuiltOffsets), bytes(rebuiltBuffer)


def moveGridRecords(
    store: tst.DataStore,
    tileRange: TileRange,
    maps: GridMaps,
    table: Table,
    release: Callable[[CellRecord, CellReference], bool],
    plan: ConditionalPlan | None = None,
) -> set[int]:
    """Move every stored row and record to its new line, releasing the removed ones.

    A row keeps its bytes and only its index changes, so a record moved rather than
    edited is the record Numbers wrote. Rows are dealt back to tiles by their new
    row number, which is what carries a row over a tile boundary. Returns the tile
    ids left holding nothing, tile 0 aside, which a table always keeps.
    """
    tileSize = store.tiles.tile_size
    tiles = dict(tileRange.tiles)
    moved: list[tuple[int, tst.TileRowInfo, tst.Tile]] = []
    storedRecords: dict[int, list[CellRecord]] = {}
    for tileid, tile in tiles.items():
        for rowInfo in tile.rowInfos:
            stored = tileid * tileSize + rowInfo.tile_row_index
            row = maps.rows.lineMap(stored)
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            records = decodeRow(rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit)
            storedRecords[stored] = records
            for record in records:
                column = maps.columns.lineMap(record.column)
                if row is None or column is None:
                    reference = CellReference(
                        stored + originOffset, record.column + originOffset
                    )
                    release(record, reference)
            if row is None:
                continue
            # Rules first, while each record still sits where it was stored, since a
            # relative rule is worked out from the cell it colors.
            if plan is not None:
                rewriteConditionalRow(rowInfo, unit, stored, plan)
            if maps.columns.changed:
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRowColumns(
                    rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit,
                    maps.columns, table.colCount,
                )
            rowInfo.cell_count = len(
                decodeRow(rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit)
            )
            moved.append((row, rowInfo, tile))

    copies: dict[int, list[tst.TileRowInfo]] = {tileid: [] for tileid in tiles}
    for row, rowInfo, _ in moved:
        # A row carries its own offset width, so it may sit in any tile.
        tileRange.tileFor(row // tileSize)
        copies.setdefault(row // tileSize, [])
        copy = tst.TileRowInfo()
        copy.CopyFrom(rowInfo)
        copy.tile_row_index = row % tileSize
        copies[row // tileSize].append(copy)
    for tileid, tile in tileRange.tiles.items():
        del tile.rowInfos[:]
        tile.rowInfos.extend(
            sorted(copies.get(tileid, []), key=lambda rowInfo: rowInfo.tile_row_index)
        )
        tile.numrows = len(tile.rowInfos)
    if plan is not None:
        addInheritedRecords(tileRange, tileSize, maps, storedRecords, plan)
    return {
        tileid for tileid, tile in tileRange.tiles.items()
        if tileid and not tile.rowInfos
    }


def rewriteConditionalRow(
    rowInfo: tst.TileRowInfo, unit: int, row: int, plan: ConditionalPlan
) -> None:
    """Point every record of one stored row at the rule its old rule became."""
    replacements = {}
    for record in decodeRow(rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit):
        rewritten = rewriteConditionalRecord(record, row, plan)
        if rewritten is not None:
            replacements[record.column] = rewritten
    if replacements:
        rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRow(
            rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit, replacements
        )


def addInheritedRecords(
    tileRange: TileRange,
    tileSize: int,
    maps: GridMaps,
    storedRecords: dict[int, list[CellRecord]],
    plan: ConditionalPlan,
) -> None:
    """Give each added line the highlighting of the line it displaced.

    The added cells take empty records naming the displaced cells' rules, which is
    what `57-conditions-row-inserted` and `-column-inserted` hold. A cell whose
    displaced neighbor names no rule receives nothing.
    """
    inherited: dict[tuple[int, int], bytes] = {}
    for row in listAddedLines(maps.rows):
        displaced = findDisplacedLine(maps.rows, row)
        if displaced is None:
            continue
        for record in storedRecords.get(displaced, []):
            key = findSlotValue(record, conditionalSlot)
            column = maps.columns.lineMap(record.column)
            if key is not None and column is not None:
                inherited[(row, column)] = buildInheritedRecord(
                    plan.keyFor(key, displaced, record.column)[0]
                )
    for column in listAddedLines(maps.columns):
        displaced = findDisplacedLine(maps.columns, column)
        if displaced is None:
            continue
        for stored, records in storedRecords.items():
            movedRow = maps.rows.lineMap(stored)
            if movedRow is None:
                continue
            for record in records:
                key = findSlotValue(record, conditionalSlot)
                if record.column == displaced and key is not None:
                    inherited[(movedRow, column)] = buildInheritedRecord(
                        plan.keyFor(key, stored, displaced)[0]
                    )
    byRow: dict[int, dict[int, bytes]] = {}
    for (row, column), raw in inherited.items():
        byRow.setdefault(row, {})[column] = raw
    for row, placed in sorted(byRow.items()):
        tile = tileRange.tileFor(row // tileSize)
        if not any(held.tile_row_index == row % tileSize for held in tile.rowInfos):
            createRowStorage(tile, row % tileSize)
        # Found again rather than taken from the creation, because a repeated field
        # stores a copy of what is inserted into it.
        rowInfo = next(
            held for held in tile.rowInfos if held.tile_row_index == row % tileSize
        )
        unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
        rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRow(
            rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit, placed
        )
        rowInfo.cell_count = len(
            decodeRow(rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit)
        )


@dataclass
class TileRange:
    """A table's tiles, creating one only when a row lands where none exists.

    **Tiles are sparse**, measured 2026-09-21 in a table grown to 100,000 rows with
    values scattered through it: only the tiles holding rows exist, ids 0 to 7 then
    15, 16, 24 and on. A created tile takes its shape from an existing one, since a
    tile's own fields say nothing about which rows it holds.
    """

    index: ArchiveIndex
    registry: PackageRegistry
    owners: dict[int, IWAFile]
    store: tst.DataStore
    tiles: dict[int, tst.Tile] = field(default_factory=dict)

    def tileFor(self, tileid: int) -> tst.Tile:
        """Return the tile holding a block of rows, creating it if the file lacks it."""
        if tileid in self.tiles:
            return self.tiles[tileid]
        last = max(self.tiles)
        sibling = self.index.archive(
            next(entry.tile.identifier for entry in self.store.tiles.tiles
                 if entry.tileid == last)
        )
        created = tst.Tile()
        created.maxColumn = 0
        created.maxRow = 0
        created.numCells = 0
        created.numrows = 0
        created.storage_version = self.tiles[last].storage_version
        created.last_saved_in_BNC = self.tiles[last].last_saved_in_BNC
        created.should_use_wide_rows = self.tiles[last].should_use_wide_rows
        entry = self.store.tiles.tiles.add()
        entry.tileid = tileid
        entry.tile.identifier = createSiblingArchive(
            self.registry, self.index, self.owners, sibling.identifier,
            created.SerializeToString(),
        )
        self.tiles[tileid] = created
        return created


def buildTileRange(
    index: ArchiveIndex,
    registry: PackageRegistry,
    owners: dict[int, IWAFile],
    store: tst.DataStore,
) -> TileRange:
    """Return a table's tiles as stored, ready to create any a moved row needs."""
    return TileRange(
        index, registry, owners, store,
        {
            entry.tileid: index.resolve(entry.tile, tst.Tile)
            for entry in store.tiles.tiles
        },
    )


def writeTileRange(
    registry: PackageRegistry,
    store: tst.DataStore,
    tiles: dict[int, tst.Tile],
    spent: set[int],
) -> None:
    """Rewrite the tile list and the row tree, dropping a tile holding nothing.

    `rowTileTree` maps each tile's first row to its id, and `nextRowStripID` is the
    highest tile id plus one: 391 for a sparse table of 18 tiles whose last is 390.
    """
    tileSize = store.tiles.tile_size
    identifiers = {entry.tileid: entry.tile.identifier for entry in store.tiles.tiles}
    kept = sorted(tileid for tileid in tiles if tileid not in spent)
    del store.tiles.tiles[:]
    for tileid in kept:
        entry = store.tiles.tiles.add()
        entry.tileid = tileid
        entry.tile.identifier = identifiers[tileid]
    del store.rowTileTree.nodes[:]
    for tileid in kept:
        node = store.rowTileTree.nodes.add()
        node.key = tileid * tileSize
        node.value = tileid
    store.nextRowStripID = max(kept) + 1
    for tileid in spent:
        registry.archiveRemove(identifiers[tileid])


def rewriteRowColumns(
    offsets: bytes, buffer: bytes, unit: int, columns: LineMap, colCount: int
) -> tuple[bytes, bytes]:
    """Rebuild one row with each record in its new column and removed ones dropped.

    A row carrying one offset slot per column grows or shrinks with the table; the
    narrow shape keeps its fixed 255 slots, so a record past them is refused.
    """
    slots = len(offsets) // offsetWidth
    if slots == len(columns.lines) and slots != narrowRowSlots:
        slots = colCount
    placed: dict[int, bytes] = {}
    for record in decodeRow(offsets, buffer, unit):
        column = columns.lineMap(record.column)
        if column is None:
            continue
        if column >= slots:
            raise WriteError(
                f"A record would move to column {column + originOffset}, past the "
                f"{slots} offset slots its row carries."
            )
        placed[column] = record.raw
    empty = emptyOffset.to_bytes(offsetWidth, "little") * slots
    return rewriteRow(empty, b"", unit, placed)


__all__ = [
    "TileRange",
    "buildTileRange",
    "createRowStorage",
    "moveGridRecords",
    "narrowRowSlots",
    "rewriteRow",
    "writeTileRange",
]
