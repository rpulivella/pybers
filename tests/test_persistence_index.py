#!/usr/bin/env python3
"""\
One save reads every archive as it was last written, through one index.

Each pass of a save reads what an earlier pass wrote. These tests pin that at the
index, where the defect lived: a write replaced the member's archive while the
index kept the old one, and every resolve parsed its own copy.

UPDATES
2026-09-22  Written for PYB-109.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/22"

from pathlib import Path

import pytest

import pybers
from conftest import allDocuments, findDocumentPath
from pybers._generated import TSPArchiveMessages_pb2 as tspArchive
from pybers._generated import TSPMessages_pb2 as tsp
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import readPackage, writePackage
from pybers._persistence.index import ArchiveIndex
from pybers._persistence.iwa import createArchive
from pybers._persistence.metadata import PackageRegistry, createSiblingArchive
from pybers._persistence.types import parseArchive, readArchiveTypeId
from pybers.errors import ReadError

tableModelTypeId: int = 6001
tileTypeId: int = 6002


def findArchiveOfType(index: ArchiveIndex, typeId: int) -> int:
    """Return the identifier of the first archive carrying a type."""
    return next(
        identifier for identifier, archive in index.byIdentifier.items()
        if readArchiveTypeId(archive) == typeId
    )


def readBaseline() -> tuple[ArchiveIndex, int]:
    """Return an index over `00-baseline` and its table model's identifier."""
    index = ArchiveIndex(readPackage(findDocumentPath("00-baseline")))
    return index, findArchiveOfType(index, tableModelTypeId)


def readModel(index: ArchiveIndex, identifier: int) -> tst.TableModelArchive:
    """Return a table model through the index."""
    return index.resolve(tsp.Reference(identifier=identifier), tst.TableModelArchive)


def saveAndReadModel(
    index: ArchiveIndex, identifier: int, tmp_path: Path
) -> tst.TableModelArchive:
    """Write the index's package out, and return the table model read back from it."""
    destination = tmp_path / "saved.numbers"
    writePackage(index.package, destination)
    return readModel(ArchiveIndex(readPackage(destination)), identifier)


def testAReadAfterAWriteReturnsWhatWasWritten() -> None:
    index, identifier = readBaseline()
    replacement = tst.TableModelArchive()
    replacement.CopyFrom(readModel(index, identifier))
    replacement.table_name = "written"

    index.archiveWrite(identifier, replacement)

    assert readModel(index, identifier).table_name == "written"
    assert parseArchive(index.archive(identifier)) == replacement


def testTwoReadsOfOneArchiveAreOneMessage() -> None:
    index, identifier = readBaseline()

    assert readModel(index, identifier) is readModel(index, identifier)


def testTwoPassesWritingOneArchiveBothReachTheSavedFile(tmp_path: Path) -> None:
    index, identifier = readBaseline()
    first = readModel(index, identifier)
    first.table_name = "first pass"
    index.archiveWrite(identifier, first)
    second = readModel(index, identifier)
    second.number_of_footer_rows = 1
    index.archiveWrite(identifier, second)

    saved = saveAndReadModel(index, identifier, tmp_path)
    assert saved.table_name == "first pass"
    assert saved.number_of_footer_rows == 1


def testTwoPassesHoldingOneArchiveAtOnceBothReachTheSavedFile(tmp_path: Path) -> None:
    index, identifier = readBaseline()
    first = readModel(index, identifier)
    second = readModel(index, identifier)
    second.number_of_footer_rows = 1
    index.archiveWrite(identifier, second)
    first.table_name = "first pass"
    index.archiveWrite(identifier, first)

    saved = saveAndReadModel(index, identifier, tmp_path)
    assert saved.table_name == "first pass"
    assert saved.number_of_footer_rows == 1


def testALaterPassChangingTheSameFieldKeepsItsOwnValue(tmp_path: Path) -> None:
    index, identifier = readBaseline()
    first = readModel(index, identifier)
    first.table_name = "first pass"
    index.archiveWrite(identifier, first)
    second = readModel(index, identifier)
    second.table_name = "second pass"
    index.archiveWrite(identifier, second)

    assert saveAndReadModel(index, identifier, tmp_path).table_name == "second pass"


def testACreatedArchiveReadsAsTheBodyItWasCreatedWith() -> None:
    index = ArchiveIndex(readPackage(findDocumentPath("00-baseline")))
    registry = PackageRegistry(index)
    body = tst.Tile(maxColumn=0, maxRow=0, numCells=0, numrows=0)

    created = createSiblingArchive(
        registry, findArchiveOfType(index, tileTypeId), body
    )

    assert index.resolve(tsp.Reference(identifier=created), tst.Tile) is body


def testACreatedComponentRootReadsAsTheBodyItWasCreatedWith() -> None:
    index = ArchiveIndex(readPackage(findDocumentPath("00-baseline")))
    registry = PackageRegistry(index)
    identifier = registry.identifierAllocate()
    body = tst.Tile(maxColumn=0, maxRow=0, numCells=0, numrows=0)
    info = tspArchive.ArchiveInfo(identifier=identifier)
    info.message_infos.add(type=tileTypeId, length=0)

    registry.componentAdd(
        createArchive(info, [body.SerializeToString()]), "Tables/Tile", body
    )

    assert index.resolve(tsp.Reference(identifier=identifier), tst.Tile) is body


def testACreatedArchiveReadsLikeAnyOtherAfterASave(tmp_path: Path) -> None:
    index = ArchiveIndex(readPackage(findDocumentPath("00-baseline")))
    registry = PackageRegistry(index)
    body = tst.Tile(maxColumn=0, maxRow=0, numCells=3, numrows=0)
    created = createSiblingArchive(
        registry, findArchiveOfType(index, tileTypeId), body
    )
    registry.save()
    destination = tmp_path / "saved.numbers"
    writePackage(index.package, destination)

    reread = ArchiveIndex(readPackage(destination))
    assert reread.resolve(tsp.Reference(identifier=created), tst.Tile) == body


def testReadingAnArchiveThisSaveRemovedRaisesNamingIt() -> None:
    index = ArchiveIndex(readPackage(findDocumentPath("00-baseline")))
    registry = PackageRegistry(index)
    identifier = findArchiveOfType(index, tileTypeId)
    index.resolve(tsp.Reference(identifier=identifier), tst.Tile)

    registry.archiveRemove(identifier)

    with pytest.raises(ReadError, match=f"archive {identifier}, which this save"):
        index.resolve(tsp.Reference(identifier=identifier), tst.Tile)
    with pytest.raises(ReadError, match=f"archive {identifier}, which this save"):
        index.typeOf(tsp.Reference(identifier=identifier))


def testWritingAnArchiveThisSaveRemovedRaisesNamingIt() -> None:
    index = ArchiveIndex(readPackage(findDocumentPath("00-baseline")))
    registry = PackageRegistry(index)
    identifier = findArchiveOfType(index, tileTypeId)
    body = index.resolve(tsp.Reference(identifier=identifier), tst.Tile)
    registry.archiveRemove(identifier)

    with pytest.raises(ReadError, match=f"archive {identifier}, which this save"):
        index.archiveWrite(identifier, body)


def testReadingAnArchiveTheDocumentNeverHeldStillSaysSo() -> None:
    index = ArchiveIndex(readPackage(findDocumentPath("00-baseline")))

    with pytest.raises(ReadError, match="999999999, which is not in this document"):
        index.archive(999_999_999)


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def testAnUnchangedSaveRewritesNoMember(path: Path, tmp_path: Path) -> None:
    document = pybers.open(path)
    document.save(tmp_path / f"{path.stem}-saved.numbers")

    assert document._package is not None
    assert [
        iwaFile.name for iwaFile in document._package.iwaFiles if iwaFile.modified
    ] == []
