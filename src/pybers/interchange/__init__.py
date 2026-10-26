#!/usr/bin/env python3
"""\
The JSON form: one structure for a document and its parts that every tool agrees on.

One serializer. `formatJsonForm` writes a document, a sheet, a table, a range or a
cell under the form's version, and any other value pybers returns, a `Check` or a
`CellChange`, by the same rules without one, so `--format json` and a script
never disagree. `parseJsonForm` reads the form back into a model equal to the one
written. The rules each value follows, and what change requires a new version, are
in `docs/decisions.md`, and `schema.json` beside this module describes the form.

A feature owns its own part of the form, `table/_form.py` and `document/_form.py`,
and this package owns only the mechanism, so a feature adding a field adds no code
here.

UPDATES
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

# Lazy, because `formula.nodes` reaches `_tree` while the model is still loading.
lazy from pybers.addressing.ranges import CellRange, CellRangeLike, toCellRanges
lazy from pybers.document._form import (
    buildDocument,
    buildDocumentForm,
    buildPart,
    buildSheet,
    buildSheetForm,
    listTableEntries,
)
lazy from pybers.document.sheets import Document, Sheet
lazy from pybers.interchange._envelope import (
    CellJsonForm,
    DocumentJsonForm,
    JsonForm,
    RangeJsonForm,
    SheetJsonForm,
    TableJsonForm,
    jsonFormVersion,
)
lazy from pybers.interchange._jsontext import readJsonText, writeJsonText
lazy from pybers.interchange._leaves import JsonFormError
lazy from pybers.interchange._tree import decodeTree, encodeTree
lazy from pybers.table._form import buildTableForm
lazy from pybers.table.cell import Cell
lazy from pybers.table.cells import Table


def formatJsonForm(subject: object, extent: CellRangeLike | None = None) -> str:
    """Return the JSON form of a document, sheet, table or cell, or any pybers value.

    `extent` narrows a table to the cells of one range.
    """
    return writeJsonText(encodeTree(buildJsonForm(subject, extent)))


def parseJsonForm(text: str) -> Document | Sheet | Table | tuple[Cell, ...] | Cell:
    """Return the document, sheet, table, cells or cell a JSON form describes."""
    tree = readJsonText(text)
    version = tree.get("jsonFormVersion") if isinstance(tree, dict) else None
    if version != jsonFormVersion:
        raise JsonFormError(
            f"The text is not version {jsonFormVersion} of the JSON form pybers "
            f"reads, its jsonFormVersion being {writeJsonText(version)}."
        )
    match decodeTree(tree, JsonForm, "$"):
        case DocumentJsonForm(document=document):
            return buildDocument(document, "$.document")
        case SheetJsonForm(sheet=sheet, documentTables=entries):
            return buildSheet(sheet, entries, "$.sheet")
        case TableJsonForm(sheetName=sheetName, table=table, documentTables=entries):
            return buildPart(table, sheetName, entries, "$.table")
        case RangeJsonForm(
            sheetName=sheetName, extent=extent, table=table, documentTables=entries
        ):
            built = buildPart(table, sheetName, entries, "$.table")
            outside = [each.address for each in table.cells
                       if not extent.covers(each.address)]
            if outside:
                raise JsonFormError(f"$.table holds {outside[0]}, outside {extent}.")
            return tuple(built.cells[each.address] for each in table.cells)
        case CellJsonForm(
            sheetName=sheetName, cell=cell, table=table, documentTables=entries
        ):
            if [each.address for each in table.cells] != [cell]:
                raise JsonFormError(f"$.table must hold the cell {cell} and no other.")
            return buildPart(table, sheetName, entries, "$.table").cells[cell]
    raise JsonFormError("The text holds no part of a document.")


def buildJsonForm(subject: object, extent: CellRangeLike | None) -> object:
    """Return the form a subject is written as, or the subject when it is a value."""
    if extent is not None and not isinstance(subject, Table):
        raise JsonFormError("Only a table is narrowed to a range of its cells.")
    match subject:
        case Document():
            return DocumentJsonForm(jsonFormVersion, buildDocumentForm(subject))
        case Sheet():
            entries = listTableEntries(subject.document)
            return SheetJsonForm(jsonFormVersion, buildSheetForm(subject), entries)
        case Table():
            sheetName = None if subject.sheet is None else subject.sheet.name
            entries = listTableEntries(subject.document)
            if extent is None:
                table = buildTableForm(subject)
                return TableJsonForm(jsonFormVersion, sheetName, table, entries)
            narrowed = findOneRange(extent)
            table = buildTableForm(subject, narrowed)
            return RangeJsonForm(jsonFormVersion, sheetName, narrowed, table, entries)
        case Cell(table=None):
            raise JsonFormError(
                f"The cell at {subject.address} belongs to no table, and a cell's "
                "form is written inside its table."
            )
        case Cell(table=owner) if owner is not None:
            sheetName = None if owner.sheet is None else owner.sheet.name
            only = CellRange.parse(str(subject.address))
            table = buildTableForm(owner, only)
            return CellJsonForm(
                jsonFormVersion, sheetName, subject.address, table,
                listTableEntries(owner.document),
            )
    return subject


def findOneRange(extent: CellRangeLike) -> CellRange:
    """Return the one range a table is narrowed to, refusing a list of several."""
    ranges = toCellRanges(extent)
    if len(ranges) != 1:
        raise JsonFormError(
            f"A table is narrowed to one range, and {extent} names {len(ranges)}."
        )
    return ranges[0]


__all__ = ["JsonFormError", "formatJsonForm", "jsonFormVersion", "parseJsonForm"]
