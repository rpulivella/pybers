#!/usr/bin/env python3
"""\
A table's stored rows, and the one walk over them.

**The tile list is authoritative.** Its `tileid` gives a tile's block of rows, and the
archive identifiers are not in row order, so nothing may iterate the archives as found.
**`tile_row_index` is local to its tile**, so a row is the tile's id times the tile size
plus the local index. Reading it as a table row gives eight different rows on an
eight-tile table and raises nothing. See findings-03-structure.md.

Private. Used by the table feature's reader and writer alike.

UPDATES
2026-10-29  Written for PYB-278, from the walks the reader and the writer each kept.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/29"

from collections.abc import Iterator
from dataclasses import dataclass

from .._generated import TSTArchives_pb2 as tst
from .cells import CellRecord, chooseOffsetUnit, decodeRow
from .index import ArchiveIndex


@dataclass(frozen=True, slots=True)
class TileRow:
    """One row a tile stores: its row counted from zero, its tile and its storage."""

    row: int
    tile: tst.Tile
    info: tst.TileRowInfo

    @property
    def unit(self) -> int:
        """Return the bytes one offset of this row counts."""
        return chooseOffsetUnit(
            self.info.has_wide_offsets, self.tile.should_use_wide_rows
        )

    @property
    def records(self) -> list[CellRecord]:
        """Return the records the row holds now, decoded afresh after a rewrite."""
        return decodeRow(
            self.info.cell_offsets, self.info.cell_storage_buffer, self.unit
        )


def iterateTileRows(tileid: int, tile: tst.Tile, tileSize: int) -> Iterator[TileRow]:
    """Yield every row one tile stores, each at its row in the table."""
    for info in tile.rowInfos:
        yield TileRow(tileid * tileSize + info.tile_row_index, tile, info)


@dataclass(frozen=True, slots=True)
class StoredTiles:
    """A table's tiles in the order its tile list names them, walked row by row."""

    tileSize: int
    tiles: tuple[tuple[int, tst.Tile], ...]

    def __iter__(self) -> Iterator[TileRow]:
        """Walk every stored row of every tile, tile by tile."""
        for tileid, tile in self.tiles:
            yield from iterateTileRows(tileid, tile, self.tileSize)


def readStoredTiles(index: ArchiveIndex, store: tst.DataStore) -> StoredTiles:
    """Return a table's tiles, resolved in the order its tile list names them."""
    return StoredTiles(
        store.tiles.tile_size,
        tuple(
            (int(entry.tileid), index.resolve(entry.tile, tst.Tile))
            for entry in store.tiles.tiles
        ),
    )


__all__ = ["StoredTiles", "TileRow", "iterateTileRows", "readStoredTiles"]
