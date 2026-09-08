#!/usr/bin/env python3
"""\
Helpers shared by the tests that read a package rather than the model.

Comparing archive bodies is how the base contract is checked, and reading a
tile's own offsets is how a claim about what Numbers stored is separated from a
claim about what pybers decoded. Both had two copies before this module existed.

UPDATES
2026-09-07  Written for #54, holding what test_merge_covered and
            test_wide_columns had each defined for themselves.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/07"

from pathlib import Path

from pybers._generated import TSTArchives_pb2 as tst
from pybers.numbersfile import NumbersPackage, readPackage
from pybers.numbersfile.cells import decodeRow, offsetUnitFor
from pybers.numbersfile.types import archiveTypeId, archiveTypes
from pybers.reader import ArchiveIndex

tableModelType: int = next(
    key for key, value in archiveTypes.items() if value is tst.TableModelArchive
)


def archiveBodies(package: NumbersPackage) -> list[tuple[str, int, bytes]]:
    """Return every archive body in a package, in the order it stores them."""
    return [
        (iwaFile.name, archive.identifier, archive.messages[0].data)
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
    ]


def recordedRows(path: Path) -> dict[int, set[int]]:
    """Return the zero-based columns holding a record, per row of the first table."""
    index = ArchiveIndex(readPackage(path))
    for identifier in index.byIdentifier:
        archive = index.archive(identifier)
        if archiveTypeId(archive) != tableModelType:
            continue
        model = tst.TableModelArchive()
        model.ParseFromString(archive.messages[0].data)
        store = model.base_data_store
        recorded: dict[int, set[int]] = {}
        for entry in store.tiles.tiles:
            tile = index.resolve(entry.tile, tst.Tile)
            for info in tile.rowInfos:
                row = entry.tileid * store.tiles.tile_size + info.tile_row_index
                unit = offsetUnitFor(info.has_wide_offsets, tile.should_use_wide_rows)
                recorded[row] = {
                    record.column
                    for record in decodeRow(
                        info.cell_offsets, info.cell_storage_buffer, unit
                    )
                }
        return recorded
    raise AssertionError(f"No table model in {path.name}.")


def recordedColumns(path: Path, row: int) -> set[int]:
    """Return the zero-based columns holding a record in one row of one table."""
    recorded = recordedRows(path)
    if row not in recorded:
        raise AssertionError(f"No table in {path.name} holds row {row}.")
    return recorded[row]
