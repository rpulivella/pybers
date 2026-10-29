#!/usr/bin/env python3
"""\
The top of the JSON form: its version, and which part of a document it holds.

Five shapes, each writing keys no other writes, so a reader knows which it holds
from its keys alone. A table, a range and a cell carry the name of their sheet, or
null for a table on none, and every part carries the directory of its document's
tables, against which its formulas' text is read.

Private. Part of the JSON form's mechanism.

UPDATES
2026-10-28  Version 2, a document carrying its locale identifier, for PYB-272.
2026-10-24  Written for PYB-259.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/24"

from dataclasses import dataclass, field
from typing import Final

from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import CellAddress
from pybers.document._form import DocumentForm, SheetForm, TableEntry
from pybers.interchange._tree import jsonFormConst
from pybers.table._form import TableForm

# Any change to the form's shape is a new version, recorded in `docs/decisions.md`.
jsonFormVersion: Final[int] = 2


@dataclass(frozen=True, slots=True)
class DocumentJsonForm:
    """A whole document."""

    jsonFormVersion: int = field(metadata={jsonFormConst: jsonFormVersion})
    document: DocumentForm


@dataclass(frozen=True, slots=True)
class SheetJsonForm:
    """One sheet and its tables."""

    jsonFormVersion: int = field(metadata={jsonFormConst: jsonFormVersion})
    sheet: SheetForm
    documentTables: tuple[TableEntry, ...]


@dataclass(frozen=True, slots=True)
class TableJsonForm:
    """One table, and the sheet it sits on."""

    jsonFormVersion: int = field(metadata={jsonFormConst: jsonFormVersion})
    sheetName: str | None
    table: TableForm
    documentTables: tuple[TableEntry, ...]


@dataclass(frozen=True, slots=True)
class RangeJsonForm:
    """The cells of one range, inside the table holding them."""

    jsonFormVersion: int = field(metadata={jsonFormConst: jsonFormVersion})
    sheetName: str | None
    extent: CellRange
    table: TableForm
    documentTables: tuple[TableEntry, ...]


@dataclass(frozen=True, slots=True)
class CellJsonForm:
    """One cell, inside the table holding it."""

    jsonFormVersion: int = field(metadata={jsonFormConst: jsonFormVersion})
    sheetName: str | None
    cell: CellAddress
    table: TableForm
    documentTables: tuple[TableEntry, ...]


type JsonForm = (
    DocumentJsonForm | SheetJsonForm | TableJsonForm | RangeJsonForm | CellJsonForm
)

__all__ = [
    "CellJsonForm",
    "DocumentJsonForm",
    "JsonForm",
    "RangeJsonForm",
    "SheetJsonForm",
    "TableJsonForm",
    "jsonFormVersion",
]
