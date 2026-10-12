#!/usr/bin/env python3
"""\
`pybers.checkDocument`, the facts a bug report needs, reached without a command line.

Each unfamiliar document is made by retyping one archive or one cell record of a
real fixture, so a test names exactly what pybers has not met.

UPDATES
2026-10-12  Missing parts are asserted by the sentinel naming why, for PYB-190.
2026-10-07  Written for PYB-169.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/07"

import platform
import plistlib
import struct
from collections.abc import Callable
from dataclasses import replace
from importlib import metadata
from pathlib import Path

import pytest

import pybers
from conftest import findDocumentPath, testsDirectory
from pybers._generated import TSPArchiveMessages_pb2 as archiveMessages
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import (
    NumbersPackage,
    StoredMember,
    readPackage,
    writePackage,
)
from pybers._persistence.cells import chooseOffsetUnit, emptyOffset, offsetWidth
from pybers._persistence.types import findArchiveTypeId, readArchiveTypeId
from pybers.check import _read as checkRead

baselinePath: Path = findDocumentPath("00-baseline")
# A document whose table stores records, three of them empty.
recordsPath: Path = findDocumentPath("22e-merge-imported")
# Its empty records are ordinary cells, where 22e's sit under a merge the reader skips.
emptyCellsPath: Path = findDocumentPath("19-formula-dragged")
untestedType: int = 99999


def retypeArchive(package: NumbersPackage, fromType: int, toType: int) -> None:
    """Give the first archive of `fromType` the type `toType`."""
    for iwaFile in package.iwaFiles:
        for position, archive in enumerate(iwaFile.archives):
            if not archive.messages or readArchiveTypeId(archive) != fromType:
                continue
            info = archiveMessages.ArchiveInfo()
            info.ParseFromString(archive.infoBytes)
            info.message_infos[0].type = toType
            retyped = replace(archive.messages[0], typeId=toType)
            messages = (retyped, *archive.messages[1:])
            iwaFile.archives[position] = replace(
                archive, messages=messages, infoBytes=info.SerializeToString()
            )
            iwaFile.modified = True
            return
    raise AssertionError(f"No archive of type {fromType}")


def rewriteFirstRow(
    package: NumbersPackage, rewrite: Callable[[tst.TileRowInfo], bool]
) -> None:
    """Apply `rewrite` to rows holding records until it accepts one."""
    tileType = findArchiveTypeId(tst.Tile)
    for iwaFile in package.iwaFiles:
        for archive in iwaFile.archives:
            if not archive.messages or readArchiveTypeId(archive) != tileType:
                continue
            tile = tst.Tile()
            tile.ParseFromString(archive.messages[0].data)
            for rowInfo in tile.rowInfos:
                if rowInfo.cell_storage_buffer and rewrite(rowInfo):
                    iwaFile.messageReplace(
                        archive.identifier, 0, tile.SerializeToString()
                    )
                    return
    raise AssertionError("No row accepted the rewrite")


def findPopulatedOffsets(rowInfo: tst.TileRowInfo) -> list[tuple[int, int]]:
    """Return each populated column of a row with its byte offset."""
    count = len(rowInfo.cell_offsets) // offsetWidth
    unit = chooseOffsetUnit(rowInfo.has_wide_offsets, False)
    return [
        (slot, at * unit)
        for slot, at in enumerate(struct.unpack(f"<{count}H", rowInfo.cell_offsets))
        if at != emptyOffset
    ]


def retypeEmptyRecord(rowInfo: tst.TileRowInfo, toType: int) -> bool:
    """Retype the row's first empty record, which reads identically at any type."""
    buffer = bytearray(rowInfo.cell_storage_buffer)
    for _, at in findPopulatedOffsets(rowInfo):
        if buffer[at + 1] == 0:
            buffer[at + 1] = toType
            rowInfo.cell_storage_buffer = bytes(buffer)
            return True
    return False


def moveOffsetPastBuffer(rowInfo: tst.TileRowInfo) -> bool:
    """Point the row's first record past the end of its storage buffer."""
    offsets = bytearray(rowInfo.cell_offsets)
    slot, _ = findPopulatedOffsets(rowInfo)[0]
    struct.pack_into("<H", offsets, slot * offsetWidth, 0xFFFE)
    rowInfo.cell_offsets = bytes(offsets)
    return True


def writePackageCopy(package: NumbersPackage, tmp_path: Path) -> Path:
    """Write a package into the test's own directory and return its path."""
    target = tmp_path / "checked.numbers"
    writePackage(package, target)
    return target


def testAScriptChecksADocumentThroughImportPybers() -> None:
    check = pybers.checkDocument(baselinePath)
    assert check.failure is None
    assert check.savedBy == pybers.NumbersVersion("15.3.1", "7050.1.1-2")
    assert check.untestedArchiveTypes == {}
    assert check.unrecognizedCellTypes == {}
    assert check.names is pybers.NOT_REQUESTED


def testTheEnvironmentReportsWhatPybersRunsOn() -> None:
    found = pybers.checkDocument(baselinePath).environment
    assert found.pybersVersion == metadata.version("pybers")
    assert found.pythonVersion == platform.python_version()
    assert found.protobufVersion == metadata.version("protobuf")
    assert found.operatingSystem == platform.platform()


def testTestedArchiveTypesAreEveryTypeTheTestDocumentsHold() -> None:
    held = {
        readArchiveTypeId(archive)
        for path in testsDirectory.rglob("*.numbers")
        for iwaFile in readPackage(path).iwaFiles
        for archive in iwaFile.archives
        if archive.messages
    }
    assert checkRead.testedArchiveTypes == held


def testAnArchiveTypeNoTestDocumentHoldsIsCounted(tmp_path: Path) -> None:
    package = readPackage(baselinePath)
    retypeArchive(package, 210, untestedType)
    check = pybers.checkDocument(writePackageCopy(package, tmp_path))
    assert check.failure is None
    assert check.untestedArchiveTypes == {untestedType: 1}


def testACellTypePybersDoesNotRecognizeIsCounted(tmp_path: Path) -> None:
    package = readPackage(emptyCellsPath)
    rewriteFirstRow(package, lambda rowInfo: retypeEmptyRecord(rowInfo, 4))
    check = pybers.checkDocument(writePackageCopy(package, tmp_path))
    assert check.unrecognizedCellTypes == {4: 1}


def testTheReaderKeepsTheTypeOfARecordItDoesNotRecognize(tmp_path: Path) -> None:
    package = readPackage(emptyCellsPath)
    rewriteFirstRow(package, lambda rowInfo: retypeEmptyRecord(rowInfo, 4))
    document = pybers.open(writePackageCopy(package, tmp_path))
    found = [
        cell.description
        for sheet in document.sheets
        for table in sheet.tables
        for cell in table.cells.values()
        if cell.description.kind is pybers.CellKind.UNKNOWN
    ]
    assert [description.unrecognizedTypeCode for description in found] == [4]


def testAFailureKeepsItsErrorToRaise(tmp_path: Path) -> None:
    package = readPackage(baselinePath)
    retypeArchive(package, 1, untestedType)
    failure = pybers.checkDocument(writePackageCopy(package, tmp_path)).failure
    assert failure is not None
    assert isinstance(failure.error, pybers.ReadError)
    assert "error=" not in repr(failure)


def testNamesLocateEachUnrecognizedCell(tmp_path: Path) -> None:
    package = readPackage(emptyCellsPath)
    rewriteFirstRow(package, lambda rowInfo: retypeEmptyRecord(rowInfo, 4))
    names = pybers.checkDocument(writePackageCopy(package, tmp_path), names=True).names
    assert names is not pybers.NOT_REQUESTED
    assert names.unrecognizedCells is not pybers.UNDETERMINED
    [cell] = names.unrecognizedCells
    assert (cell.sheetName, cell.tableName, cell.typeCode) == ("Sheet 1", "Table 1", 4)


def testNamesListEachSheetAndTableWithItsSize() -> None:
    document = pybers.open(recordsPath)
    names = pybers.checkDocument(recordsPath, names=True).names
    assert names is not pybers.NOT_REQUESTED
    assert names.sheets == tuple(
        pybers.CheckSheet(sheet.name, tuple(
            pybers.CheckTable(table.name, table.rowCount, table.colCount)
            for table in sheet.tables
        ))
        for sheet in document.sheets
    )


def testNamesAreUnknownWhenTheDocumentCannotBeOpened(tmp_path: Path) -> None:
    package = readPackage(recordsPath)
    retypeArchive(package, 6005, untestedType)
    check = pybers.checkDocument(writePackageCopy(package, tmp_path), names=True)
    assert check.failure is not None
    assert check.names == pybers.CheckNames(pybers.UNDETERMINED, pybers.UNDETERMINED)
    assert check.unrecognizedCellTypes is pybers.UNDETERMINED


def testADocumentPybersCannotOpenReportsWhy(tmp_path: Path) -> None:
    package = readPackage(baselinePath)
    retypeArchive(package, 1, untestedType)
    failure = pybers.checkDocument(writePackageCopy(package, tmp_path)).failure
    assert failure is not None
    assert failure.errorType == "ReadError"
    assert failure.message == "Expected exactly one TN.DocumentArchive, found 0."
    assert any(frame.startswith("document/_read.py:") for frame in failure.frames)


def testARowThatFailsToDecodeNamesItsTableByIdentifier(
    tmp_path: Path,
) -> None:
    document = pybers.open(recordsPath)
    tableNames = [table.name for sheet in document.sheets for table in sheet.tables]
    package = readPackage(recordsPath)
    rewriteFirstRow(package, moveOffsetPastBuffer)
    check = pybers.checkDocument(writePackageCopy(package, tmp_path))
    assert check.failure is not None
    assert check.failure.message is not pybers.WITHHELD
    assert tableNames
    assert not any(name in check.failure.message for name in tableNames)
    assert check.unrecognizedCellTypes is pybers.UNDETERMINED


def testAnErrorPybersDoesNotRaiseWithholdsItsMessage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raiseQuotingTheDocument(*_: object) -> None:
        raise KeyError("Quarterly forecast")

    monkeypatch.setattr(checkRead, "readDocument", raiseQuotingTheDocument)
    check = pybers.checkDocument(baselinePath)
    assert check.failure == pybers.CheckFailure(
        "KeyError", pybers.WITHHELD, check.failure.frames if check.failure else ()
    )
    assert "Quarterly forecast" not in repr(check)
    assert any(frame.startswith("check/_read.py:") for frame in check.failure.frames)


@pytest.mark.parametrize(
    ("history", "expected"),
    [
        (["Template: Blank (dev/15.3)", "M15.3.1-7050.1.1-2"],
         pybers.NumbersVersion("15.3.1", "7050.1.1-2")),
        (["M14.0-7037.0.73-4", "csv"], pybers.NumbersVersion("14.0", "7037.0.73-4")),
        (["Template: Blank"], None),
        ([], None),
    ],
)
def testTheSavedVersionIsTheLastNumbersBuildInTheHistory(
    history: list[str], expected: pybers.NumbersVersion | None
) -> None:
    package = NumbersPackage(otherMembers=[
        StoredMember(checkRead.buildHistoryMember, plistlib.dumps(history))
    ])
    assert checkRead.readSavedVersion(package) == expected


def testTheSavedVersionIsNoneWithoutAHistory() -> None:
    assert checkRead.readSavedVersion(NumbersPackage()) is None


@pytest.mark.parametrize("stored", [b"not a plist", plistlib.dumps({"M15": "x"})])
def testTheSavedVersionIsUndeterminedWhenTheHistoryCannotBeRead(stored: bytes) -> None:
    garbled = NumbersPackage(
        otherMembers=[StoredMember(checkRead.buildHistoryMember, stored)]
    )
    assert checkRead.readSavedVersion(garbled) is pybers.UNDETERMINED


def testAFileThatIsNotADocumentRaisesAPybersError(tmp_path: Path) -> None:
    text = tmp_path / "notes.numbers"
    text.write_text("not a document")
    with pytest.raises(pybers.PybersError, match="not a zip archive"):
        pybers.checkDocument(text)


def testProgressHearsEachStepInOrder() -> None:
    heard: list[str] = []
    pybers.checkDocument(baselinePath, names=True, onProgress=heard.append)
    assert heard == ["reading the document…", "opening it…"]
