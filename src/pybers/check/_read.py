#!/usr/bin/env python3
"""\
Check a document: read its package, open it, and count what pybers has not met.

**An archive type is untested when no test document holds it.** The read registry
in `pybers._persistence.types` is curated to stay incomplete, and a blank
document holds 26 types outside it, so the registry cannot tell a maintainer what
is new. `testedArchiveTypes` is the union over every test document instead, and a
test keeps it equal to that union.

**A failure is reported without the document's words.** A `PybersError` keeps its
message, because pybers's own read path names archives by identifier. Any other
error keeps only its type and where pybers raised it.

UPDATES
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

import plistlib
import re
import traceback
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from .._generated import TNArchives_pb2 as tn
from .._generated import TSTArchives_pb2 as tst
from .._persistence import NumbersPackage, readPackage
from .._persistence.index import ArchiveIndex, findRoot
from .._persistence.types import findArchiveTypeId, readArchiveTypeId
from ..document._read import readDocument
from ..errors import PybersError
from ..table._read import iterateCellRecords, storedKinds
from .environment import readCheckEnvironment
from .report import (
    Check,
    CheckCell,
    CheckFailure,
    CheckNames,
    CheckSheet,
    CheckTable,
    NumbersVersion,
)

# Every archive type the test documents hold, measured 2026-10-07 across 184.
testedArchiveTypes: frozenset[int] = frozenset({
    1, 2, 205, 210, 212, 213, 219, 222, 401, 601, 633, 634,
    2001, 2011, 2021, 2022, 2023, 2024, 2025, 2043,
    3005, 3006, 3009, 3016, 3045, 3047, 3056, 3061, 3091, 3097,
    4000, 4003, 4004, 4008, 4009, 4010, 4011,
    5020, 5022, 5024, 5026, 5028, 5030,
    6000, 6001, 6002, 6003, 6004, 6005, 6006, 6008, 6010, 6030, 6204, 6206, 6218,
    6220, 6247, 6267, 6283, 6305, 6306, 6316, 6317, 6318, 6365, 6366, 6372, 6373,
    6383,
    10024, 11006, 11008, 11011, 11014, 11015, 12009, 12026, 12028, 12050,
})

# Numbers appends one entry per build that saves; a template or an import names
# its origin instead, so only an `M` entry is a version.
buildHistoryMember: str = "Metadata/BuildVersionHistory.plist"
savedBuildPattern: re.Pattern[str] = re.compile(r"M(\d+(?:\.\d+)*)-(.+)")

pybersDirectory: Path = Path(__file__).resolve().parent.parent


def readSavedVersion(package: NumbersPackage) -> NumbersVersion | None:
    """Return the Numbers that last saved a package, or None when it records none.

    An unparseable history is treated as none recorded, because the rest of a
    check is still worth reporting.
    """
    member = next(
        (held for held in package.otherMembers if held.name == buildHistoryMember),
        None,
    )
    if member is None:
        return None
    try:
        history = plistlib.loads(member.data)
    except (plistlib.InvalidFileException, ValueError):
        return None
    if not isinstance(history, list):
        return None
    for entry in reversed(history):
        found = savedBuildPattern.fullmatch(entry) if isinstance(entry, str) else None
        if found:
            return NumbersVersion(version=found[1], build=found[2])
    return None


def countUntestedArchiveTypes(package: NumbersPackage) -> dict[int, int]:
    """Return how many archives of each type no test document holds."""
    counts = Counter(
        readArchiveTypeId(archive)
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
        if archive.messages
    )
    return {
        typeId: count
        for typeId, count in sorted(counts.items())
        if typeId not in testedArchiveTypes
    }


def listUnrecognizedCells(
    package: NumbersPackage, source: Path
) -> list[tuple[int, CheckCell]]:
    """Return each cell of a type pybers does not recognize, with its table model.

    Every table model is walked, attached to a sheet or not, since a record pybers
    does not recognize is worth naming wherever it sits. The sheet is left for
    `readCheckSheets` to supply.
    """
    index = ArchiveIndex(package)
    modelType = findArchiveTypeId(tst.TableModelArchive)
    found: list[tuple[int, CheckCell]] = []
    for identifier, archive in index.byIdentifier.items():
        if not archive.messages or readArchiveTypeId(archive) != modelType:
            continue
        model = index.identifierResolve(identifier, tst.TableModelArchive)
        for reference, record in iterateCellRecords(index, model, source):
            if record.typeByte not in storedKinds:
                cell = CheckCell(
                    None, model.table_name, str(reference), record.typeByte
                )
                found.append((identifier, cell))
    return found


def readCheckSheets(
    package: NumbersPackage,
) -> tuple[tuple[CheckSheet, ...], dict[int, str]]:
    """Return every sheet with its tables, and the sheet each table model sits on."""
    index = ArchiveIndex(package)
    tableType = findArchiveTypeId(tst.TableInfoArchive)
    sheets: list[CheckSheet] = []
    sheetNames: dict[int, str] = {}
    for sheetReference in findRoot(index).sheets:
        sheet = index.resolve(sheetReference, tn.SheetArchive)
        tables: list[CheckTable] = []
        for drawable in sheet.drawable_infos:
            if index.typeOf(drawable) != tableType:
                continue
            info = index.resolve(drawable, tst.TableInfoArchive)
            model = index.resolve(info.tableModel, tst.TableModelArchive)
            tables.append(CheckTable(
                model.table_name, model.number_of_rows, model.number_of_columns
            ))
            sheetNames[info.tableModel.identifier] = sheet.name
        sheets.append(CheckSheet(sheet.name, tuple(tables)))
    return tuple(sheets), sheetNames


def readCheckNames(
    package: NumbersPackage, cells: list[tuple[int, CheckCell]] | None
) -> CheckNames:
    """Return the document's sheets and tables by name, and where each cell sits."""
    sheets: tuple[CheckSheet, ...] | None
    try:
        sheets, sheetNames = readCheckSheets(package)
    except PybersError:
        sheets, sheetNames = None, {}
    located = None if cells is None else tuple(
        replace(cell, sheetName=sheetNames.get(model)) for model, cell in cells
    )
    return CheckNames(sheets, located)


def listPybersFrames(error: BaseException) -> tuple[str, ...]:
    """Return where in pybers an error passed, as `module path:line in function`."""
    frames: list[str] = []
    for frame in traceback.extract_tb(error.__traceback__):
        path = Path(frame.filename).resolve()
        if path.is_relative_to(pybersDirectory):
            location = path.relative_to(pybersDirectory).as_posix()
            frames.append(f"{location}:{frame.lineno} in {frame.name}")
    return tuple(frames)


def openForCheck(package: NumbersPackage, source: Path) -> CheckFailure | None:
    """Open a package as `pybers.open` would, and return why it failed, if it did."""
    try:
        readDocument(package, source)
    except PybersError as exc:
        return CheckFailure(type(exc).__name__, str(exc), listPybersFrames(exc))
    except Exception as exc:
        # Reported rather than raised, since a check exists to describe this failure.
        return CheckFailure(type(exc).__name__, None, listPybersFrames(exc))
    return None


def checkDocument(
    path: Path | str,
    *,
    names: bool = False,
    onProgress: Callable[[str], None] | None = None,
) -> Check:
    """Report whether pybers can read a document, and what a bug report needs.

    `names` adds the document's own names, which a public report must not hold, and
    `onProgress` hears each step as it starts. Raises `ContainerError` for a file
    that is missing, unreadable or not a Numbers document.
    """
    report = onProgress or (lambda _: None)
    source = Path(path)
    report("reading the document…")
    package = readPackage(source)
    report("opening it…")
    failure = openForCheck(package, source)
    report("walking its cells…")
    try:
        cells: list[tuple[int, CheckCell]] | None = listUnrecognizedCells(
            package, source
        )
    except PybersError:
        cells = None
    cellTypes = None if cells is None else dict(
        sorted(Counter(cell.typeId for _, cell in cells).items())
    )
    if names:
        report("reading its names…")
    return Check(
        environment=readCheckEnvironment(),
        savedBy=readSavedVersion(package),
        failure=failure,
        untestedArchiveTypes=countUntestedArchiveTypes(package),
        unrecognizedCellTypes=cellTypes,
        names=readCheckNames(package, cells) if names else None,
    )


__all__ = ["checkDocument", "testedArchiveTypes"]
