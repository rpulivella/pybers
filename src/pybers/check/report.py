#!/usr/bin/env python3
"""\
What a check of a document found, holding nothing the document contains unless asked.

A report is meant to be posted publicly when the document cannot be, so every
field of `Check` is a version, a type identifier, a count, or a location in
pybers's own source. `CheckNames` is the one exception, present only when a
caller asks for names, and never meant for posting.

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

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class NumbersVersion:
    """A release of Numbers, as its version and the build that carries it."""

    version: str
    build: str


@dataclass(frozen=True, slots=True)
class CheckEnvironment:
    """What pybers is running on. `pybersVersion` is None when not installed."""

    pybersVersion: str | None
    pythonVersion: str
    protobufVersion: str
    operatingSystem: str


@dataclass(frozen=True, slots=True)
class CheckFailure:
    """Why pybers could not open a document, and where in pybers it stopped.

    `message` is None for an error pybers does not raise itself, because its text
    was never audited and may quote the document. `error` is the exception itself,
    left out of `repr` and equality, so a caller can raise it with its traceback.
    """

    errorType: str
    message: str | None
    frames: tuple[str, ...]
    error: BaseException | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class CheckTable:
    """One table by name, with its size."""

    name: str
    rowCount: int
    colCount: int


@dataclass(frozen=True, slots=True)
class CheckSheet:
    """One sheet by name, with its tables in the sheet's own order."""

    name: str
    tables: tuple[CheckTable, ...]


@dataclass(frozen=True, slots=True)
class CheckCell:
    """Where a cell of an unrecognized type sits."""

    sheetName: str
    tableName: str
    address: str
    typeCode: int


@dataclass(frozen=True, slots=True)
class CheckNames:
    """The document's own names, for the person holding it. Never for posting.

    Both parts are None when the document could not be opened.
    """

    sheets: tuple[CheckSheet, ...] | None
    unrecognizedCells: tuple[CheckCell, ...] | None


@dataclass(frozen=True, slots=True)
class Check:
    """Whether pybers can read a document, and what a bug report about it needs.

    Both type tables count archives or cells by type identifier. Cell types are
    None when the document could not be opened, and `names` is None unless asked
    for.
    """

    environment: CheckEnvironment
    savedBy: NumbersVersion | None
    failure: CheckFailure | None
    untestedArchiveTypes: dict[int, int]
    unrecognizedCellTypes: dict[int, int] | None
    names: CheckNames | None


__all__ = [
    "Check",
    "CheckCell",
    "CheckEnvironment",
    "CheckFailure",
    "CheckNames",
    "CheckSheet",
    "CheckTable",
    "NumbersVersion",
]
