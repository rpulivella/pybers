#!/usr/bin/env python3
"""\
What a check of a document found, holding nothing the document contains unless asked.

A report is meant to be posted publicly when the document cannot be, so every
field of `Check` is a version, a type identifier, a count, a size, or a location in
pybers's own source. Every sheet and table name is WITHHELD unless a caller asks
for names, which are never meant for posting. A face is named, since its name is the
font's and not the document's.

UPDATES
2026-11-24  Every face the document uses, and whether pybers knows it, for PYB-315.
2026-11-23  Only a sheet or a table has a name, for PYB-307.
2026-11-03  Every check carries the sheets and tables, each table its unrecognized
            cells, names withheld unless asked for, replacing `CheckNames`, for
            PYB-223.
2026-10-12  A missing part states why it is missing, for PYB-190.
2026-10-11  Both type tables are frozendict, so a Check cannot change, for PYB-189.
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

from dataclasses import dataclass, field

from ..absence import UNDETERMINED, WITHHELD
from ..font.faces import FontSource


@dataclass(frozen=True, slots=True)
class NumbersVersion:
    """A release of Numbers, as its version and the build that carries it."""

    version: str
    build: str


@dataclass(frozen=True, slots=True)
class CheckEnvironment:
    """What pybers is running on. `pybersVersion` is UNDETERMINED when not installed."""

    pybersVersion: str | UNDETERMINED
    pythonVersion: str
    protobufVersion: str
    operatingSystem: str


@dataclass(frozen=True, slots=True)
class CheckFailure:
    """Why pybers could not open a document, and where in pybers it stopped.

    `message` is WITHHELD for an error pybers does not raise itself, because its
    text was never audited and may quote the document. `error` is the exception itself,
    left out of `repr` and equality, so a caller can raise it with its traceback.
    """

    errorType: str
    message: str | WITHHELD
    frames: tuple[str, ...]
    error: BaseException | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class CheckCell:
    """A cell of a type pybers does not recognize, by its address in its table."""

    address: str
    typeCode: int


@dataclass(frozen=True, slots=True)
class CheckTable:
    """One table, its name WITHHELD unless asked for, its size, unrecognized cells."""

    name: str | WITHHELD
    rowCount: int
    colCount: int
    unrecognizedCells: tuple[CheckCell, ...] = ()


@dataclass(frozen=True, slots=True)
class CheckSheet:
    """One sheet, its name WITHHELD unless asked for, its tables in its own order."""

    name: str | WITHHELD
    tables: tuple[CheckTable, ...]


@dataclass(frozen=True, slots=True)
class CheckFace:
    """One face a document uses: its PostScript name, and where pybers knows it, None
    where neither the catalog nor this machine does."""

    postScriptName: str
    source: FontSource | None


@dataclass(frozen=True, slots=True)
class Check:
    """Whether pybers can read a document, and what a bug report about it needs.

    Both type tables count archives or cells by type identifier. Cell types and
    `sheets` are UNDETERMINED when the document could not be opened.
    `savedBy` is None when the document records no Numbers, and UNDETERMINED when its
    record cannot be read.
    """

    environment: CheckEnvironment
    savedBy: NumbersVersion | UNDETERMINED | None
    failure: CheckFailure | None
    untestedArchiveTypes: frozendict[int, int]
    unrecognizedCellTypes: frozendict[int, int] | UNDETERMINED
    sheets: tuple[CheckSheet, ...] | UNDETERMINED
    faces: tuple[CheckFace, ...] | UNDETERMINED


__all__ = [
    "Check",
    "CheckCell",
    "CheckEnvironment",
    "CheckFace",
    "CheckFailure",
    "CheckSheet",
    "CheckTable",
    "NumbersVersion",
]
