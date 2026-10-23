#!/usr/bin/env python3
"""\
Check a document: read its package, open it, and count what pybers has not met.

**An archive type is untested when no test document holds it.** The read registry
in `pybers._persistence.types` is curated to stay incomplete, and a blank
document holds 26 types outside it, so the registry cannot tell a maintainer what
is new. `testedArchiveTypes` is the union over every test document instead, and a
test keeps it equal to that union.

**Cells and names come from the document the reader built**, which keeps the type
of any record it does not recognize, so nothing is decoded twice. A document that
cannot be opened therefore leaves both unknown.

**A failure is reported without the document's words.** A `PybersError` keeps its
message, because pybers's own read path names archives by identifier. Any other
error keeps only its type and where pybers raised it.

UPDATES
2026-10-13  Six archive types a Numbers 15.4 template holds count as tested, for
            PYB-139.
2026-10-12  Each missing part of a check names why it is missing, for PYB-190.
2026-10-11  Type counts are built as frozendict, for PYB-189.
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
from pathlib import Path

from .._persistence import NumbersPackage, readPackage
from .._persistence.types import readArchiveTypeId
from ..absence import NOT_REQUESTED, UNDETERMINED, WITHHELD
from ..document._read import readDocument
from ..document.sheets import Document
from ..errors import PybersError
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

# Every archive type the test documents hold, kept equal to their union by a test.
testedArchiveTypes: frozenset[int] = frozenset({
    1, 2, 205, 210, 212, 213, 219, 222, 401, 601, 633, 634,
    2001, 2011, 2021, 2022, 2023, 2024, 2025, 2043,
    3005, 3006, 3009, 3016, 3045, 3047, 3056, 3061, 3091, 3097,
    4000, 4003, 4004, 4008, 4009, 4010, 4011,
    5020, 5021, 5022, 5023, 5024, 5025, 5026, 5027, 5028, 5029, 5030,
    6000, 6001, 6002, 6003, 6004, 6005, 6006, 6008, 6010, 6030, 6204, 6206, 6218,
    6220, 6247, 6267, 6283, 6305, 6306, 6316, 6317, 6318, 6365, 6366, 6372, 6373,
    6383,
    10024, 11006, 11008, 11011, 11014, 11015, 12006, 12009, 12026, 12028, 12050,
})

# Numbers appends one entry per build that saves; a template or an import names
# its origin instead, so only an `M` entry is a version.
buildHistoryMember: str = "Metadata/BuildVersionHistory.plist"
savedBuildPattern: re.Pattern[str] = re.compile(r"M(\d+(?:\.\d+)*)-(.+)")

pybersDirectory: Path = Path(__file__).resolve().parent.parent


def readSavedVersion(
    package: NumbersPackage,
) -> NumbersVersion | UNDETERMINED | None:
    """Return the Numbers that last saved a package, or None when it records none.

    An unreadable history is UNDETERMINED rather than an error, because the rest of
    a check is still worth reporting.
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
        return UNDETERMINED
    if not isinstance(history, list):
        return UNDETERMINED
    for entry in reversed(history):
        found = savedBuildPattern.fullmatch(entry) if isinstance(entry, str) else None
        if found:
            return NumbersVersion(version=found[1], build=found[2])
    return None


def countUntestedArchiveTypes(package: NumbersPackage) -> frozendict[int, int]:
    """Return how many archives of each type no test document holds."""
    counts = Counter(
        readArchiveTypeId(archive)
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
        if archive.messages
    )
    return frozendict({
        typeId: count
        for typeId, count in sorted(counts.items())
        if typeId not in testedArchiveTypes
    })


def listUnrecognizedCells(document: Document) -> list[CheckCell]:
    """Return each cell the reader kept a type for because it did not recognize it."""
    return [
        CheckCell(sheet.name, table.name, str(reference), unrecognized)
        for sheet in document.sheets
        for table in sheet.tables
        for reference, cell in table.cells.items()
        if (unrecognized := cell.unrecognizedTypeCode) is not None
    ]


def readCheckSheets(document: Document) -> tuple[CheckSheet, ...]:
    """Return every sheet by name, with its tables and their sizes."""
    return tuple(
        CheckSheet(sheet.name, tuple(
            CheckTable(table.name, table.rowCount, table.colCount)
            for table in sheet.tables
        ))
        for sheet in document.sheets
    )


def listPybersFrames(error: BaseException) -> tuple[str, ...]:
    """Return where in pybers an error passed, as `module path:line in function`."""
    frames: list[str] = []
    for frame in traceback.extract_tb(error.__traceback__):
        path = Path(frame.filename).resolve()
        if path.is_relative_to(pybersDirectory):
            location = path.relative_to(pybersDirectory).as_posix()
            frames.append(f"{location}:{frame.lineno} in {frame.name}")
    return tuple(frames)


def openForCheck(
    package: NumbersPackage, source: Path
) -> Document | CheckFailure:
    """Open a package as `pybers.open` would, or return why it could not be."""
    try:
        return readDocument(package, source)
    except PybersError as exc:
        return CheckFailure(
            type(exc).__name__, str(exc), listPybersFrames(exc), error=exc
        )
    except Exception as exc:
        # Reported rather than raised, since a check exists to describe this failure.
        return CheckFailure(
            type(exc).__name__, WITHHELD, listPybersFrames(exc), error=exc
        )


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
    opened = openForCheck(package, source)
    document = opened if isinstance(opened, Document) else None
    cells = None if document is None else listUnrecognizedCells(document)
    return Check(
        environment=readCheckEnvironment(),
        savedBy=readSavedVersion(package),
        failure=opened if isinstance(opened, CheckFailure) else None,
        untestedArchiveTypes=countUntestedArchiveTypes(package),
        unrecognizedCellTypes=UNDETERMINED if cells is None else frozendict(
            sorted(Counter(cell.typeCode for cell in cells).items())
        ),
        names=NOT_REQUESTED if not names else CheckNames(
            UNDETERMINED if document is None else readCheckSheets(document),
            UNDETERMINED if cells is None else tuple(cells),
        ),
    )


__all__ = ["checkDocument", "testedArchiveTypes"]
