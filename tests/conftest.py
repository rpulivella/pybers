#!/usr/bin/env python3
"""\
Helpers shared by the tests that read a package rather than the model.

Comparing archive bodies is how the base contract is checked, and reading a
tile's own offsets is how a claim about what Numbers stored is separated from a
claim about what pybers decoded. Both had two copies before this module existed.

UPDATES
2026-10-22  `--golden-write`, which writes each golden from its builder, for PYB-255.
2026-10-09  Nested sequences flattened by comprehension unpacking, for PYB-181.
2026-09-16  `allDocuments` and `findDocumentPath` gathered here for PYB-90, so a
            test finds a document without knowing whether it is an origin.
2026-09-08  `dataListBytes` gathered here for #13, so that two golden
            tests compare pooled lists through one reader.
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

import shutil
from pathlib import Path

import pytest

from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import NumbersPackage, readPackage
from pybers._persistence.cells import chooseOffsetUnit, decodeRow
from pybers._persistence.index import ArchiveIndex
from pybers._persistence.types import archiveTypes, readArchiveTypeId

testsDirectory: Path = Path(__file__).resolve().parent

# Origin and measurement differ in provenance only, so no test cares which holds a stem.
documentDirectories: tuple[Path, ...] = (
    testsDirectory / "fixtures",
    testsDirectory / "measurements",
)

allDocuments: list[Path] = sorted(
    (*directory.glob("*.numbers") for directory in documentDirectories),
    key=lambda path: path.name,
)


def findDocumentPath(stem: str) -> Path:
    """Return the one document named `stem`, failing rather than skipping."""
    found = [
        directory / f"{stem}.numbers"
        for directory in documentDirectories
        if (directory / f"{stem}.numbers").is_file()
    ]
    assert len(found) == 1, f"{stem}.numbers is in {len(found)} document directories"
    return found[0]


def copyDocument(stem: str, into: Path) -> Path:
    """Return a writable copy of a document, so a save never touches the original."""
    return Path(shutil.copy(findDocumentPath(stem), into / f"{stem}.numbers"))


tableModelType: int = next(
    key for key, value in archiveTypes.items() if value is tst.TableModelArchive
)

# TST.TableDataList, so a golden can be compared at its pooled lists rather than
# through the model, which would agree with itself while both halves were wrong.
dataListTypeId: int = 6005


def readDataListBytes(path: Path) -> dict[int, bytes]:
    """Return every pooled data list in a package, keyed by archive identifier."""
    package = readPackage(path)
    return {
        archive.identifier: b"".join(message.data for message in archive.messages)
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
        if readArchiveTypeId(archive) == dataListTypeId
    }


def readArchiveBodies(package: NumbersPackage) -> list[tuple[str, int, bytes]]:
    """Return every archive body in a package, in the order it stores them."""
    return [
        (iwaFile.name, archive.identifier, archive.messages[0].data)
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
    ]


def readRecordedRows(path: Path) -> dict[int, set[int]]:
    """Return the zero-based columns holding a record, per row of the first table."""
    index = ArchiveIndex(readPackage(path))
    for identifier in index.byIdentifier:
        archive = index.archive(identifier)
        if readArchiveTypeId(archive) != tableModelType:
            continue
        model = tst.TableModelArchive()
        model.ParseFromString(archive.messages[0].data)
        store = model.base_data_store
        recorded: dict[int, set[int]] = {}
        for entry in store.tiles.tiles:
            tile = index.resolve(entry.tile, tst.Tile)
            for info in tile.rowInfos:
                row = entry.tileid * store.tiles.tile_size + info.tile_row_index
                unit = chooseOffsetUnit(
                    info.has_wide_offsets, tile.should_use_wide_rows
                )
                recorded[row] = {
                    record.column
                    for record in decodeRow(
                        info.cell_offsets, info.cell_storage_buffer, unit
                    )
                }
        return recorded
    raise AssertionError(f"No table model in {path.name}.")


def readRecordedColumns(path: Path, row: int) -> set[int]:
    """Return the zero-based columns holding a record in one row of one table."""
    recorded = readRecordedRows(path)
    if row not in recorded:
        raise AssertionError(f"No table in {path.name} holds row {row}.")
    return recorded[row]


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add `--golden-write`, which writes each golden from its builder."""
    parser.addoption(
        "--golden-write", action="store_true",
        help="write each selected golden from tests/golden/builders.py",
    )
