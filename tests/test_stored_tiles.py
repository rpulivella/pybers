#!/usr/bin/env python3
"""\
The one walk over a table's stored rows, placing each row by its tile.

UPDATES
2026-10-29  Written for PYB-278.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/29"

from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence.rows import StoredTiles


def buildTile(*localRows: int) -> tst.Tile:
    tile = tst.Tile()
    for local in localRows:
        tile.rowInfos.add(tile_row_index=local)
    return tile


def testARowIsPlacedByItsTileAndItsLocalIndex() -> None:
    tiles = StoredTiles(256, ((0, buildTile(3)), (2, buildTile(0, 5))))

    assert [walked.row for walked in tiles] == [3, 512, 517]


def testTilesAreWalkedInTheOrderTheListNamesThem() -> None:
    tiles = StoredTiles(256, ((1, buildTile(0)), (0, buildTile(0))))

    assert [walked.row for walked in tiles] == [256, 0]


def testATileHoldingNoRowsYieldsNothing() -> None:
    assert list(StoredTiles(256, ((0, buildTile()),))) == []
