#!/usr/bin/env python3
"""\
A document and its sheets as the JSON form holds them, and the form built back.

A part of a document, a sheet, a table, a range or a cell, carries the document's
table directory beside it: every table's sheet, name, identity and size. Reading the
part back rebuilds every other table as an empty stand-in, so a formula's text is
parsed and shown against exactly the names and sizes it was written with. Whether
Numbers writes a table's name bare or with its sheet depends on every table in the
document, which is why the directory is whole rather than the tables a part reaches.

Private. The JSON form's half of the document feature, beside `_read` and `_write`.

UPDATES
2026-10-28  A document carries its locale identifier, for PYB-272.
2026-10-26  A directory entry carries its sheet's position, so two sheets sharing a
            name read back apart, for PYB-259.
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

from collections.abc import Sequence
from dataclasses import dataclass

from pybers.document.sheets import Document, Sheet, firstPosition
from pybers.table._form import TableForm, assignFormulas, buildTable, buildTableForm
from pybers.table.cells import Table

# A sheet being rebuilt, and each table built for it with its form and its path.
type BuiltSheet = tuple[Sheet, list[tuple[Table, TableForm, str]]]


@dataclass(frozen=True, slots=True)
class SheetForm:
    """One sheet as the JSON form holds it, its tables in the order Numbers keeps."""

    name: str
    tables: tuple[TableForm, ...]


@dataclass(frozen=True, slots=True)
class DocumentForm:
    """One document as the JSON form holds it, its language and region first."""

    localeIdentifier: str | None
    sheets: tuple[SheetForm, ...]


@dataclass(frozen=True, slots=True)
class TableEntry:
    """One table of the document a part came from, as its formulas name and size it.

    Its sheet's position as well as its name, since two sheets may share a name.
    """

    sheetPosition: int
    sheetName: str
    name: str
    identifier: str
    rowCount: int
    colCount: int


def buildDocumentForm(document: Document) -> DocumentForm:
    """Return a document's form."""
    return DocumentForm(
        localeIdentifier=document.localeIdentifier,
        sheets=tuple(buildSheetForm(sheet) for sheet in document.sheets),
    )


def buildSheetForm(sheet: Sheet) -> SheetForm:
    """Return a sheet's form."""
    return SheetForm(
        name=sheet.name, tables=tuple(buildTableForm(table) for table in sheet.tables)
    )


def listTableEntries(document: Document | None) -> tuple[TableEntry, ...]:
    """Return the directory of a document's tables, in the order its sheets hold."""
    if document is None:
        return ()
    return tuple(
        TableEntry(position, sheet.name, table.name, table.identifier,
                   table.rowCount, table.colCount)
        for position, sheet in enumerate(document.sheets, start=firstPosition)
        for table in sheet.tables
    )


def buildDocument(form: DocumentForm, path: str) -> Document:
    """Return the document a form describes."""
    document = buildStandInDocument([
        buildSheetTables(sheet, f"{path}.sheets[{index}]")
        for index, sheet in enumerate(form.sheets)
    ], ())
    document._localeAssign(form.localeIdentifier)
    return document


def buildSheet(form: SheetForm, entries: Sequence[TableEntry], path: str) -> Sheet:
    """Return the sheet a form describes, among stand-ins for its document's rest."""
    part = buildSheetTables(form, path)
    buildStandInDocument([part], entries)
    return part[0]


def buildPart(
    form: TableForm, sheetName: str | None, entries: Sequence[TableEntry], path: str
) -> Table:
    """Return the table a form describes, among stand-ins for the rest of its document.

    A table written from no sheet reads back on none, as it was.
    """
    table = buildTable(form, path)
    if sheetName is None:
        assignFormulas(table, form, path)
    else:
        buildStandInDocument([(Sheet(name=sheetName), [(table, form, path)])], entries)
    return table


def buildSheetTables(form: SheetForm, path: str) -> BuiltSheet:
    """Return a new sheet and the tables a sheet's form describes, not yet on it."""
    return Sheet(name=form.name), [
        (buildTable(table, f"{path}.tables[{index}]"), table, f"{path}.tables[{index}]")
        for index, table in enumerate(form.tables)
    ]


def buildStandInDocument(
    parts: Sequence[BuiltSheet], entries: Sequence[TableEntry]
) -> Document:
    """Return a document holding the built sheets among stand-ins for every other table.

    Sheets and tables follow the directory's order, a stand-in taking the place of each
    table not built. A built sheet takes the place of the sheet holding its tables,
    found by their identities, and every formula is parsed once the whole document is
    linked.
    """
    built = {table.identifier: table for _, tables in parts
             for table, _, _ in tables if table.identifier}
    owners = {table.identifier: sheet for sheet, tables in parts
              for table, _, _ in tables if table.identifier}
    bySheet: dict[int, list[TableEntry]] = {}
    for entry in entries:
        bySheet.setdefault(entry.sheetPosition, []).append(entry)
    document = Document()
    for group in bySheet.values():
        owner = next((owners[each.identifier] for each in group
                      if each.identifier in owners), None)
        sheet = Sheet(name=group[0].sheetName) if owner is None else owner
        document.sheets.append(sheet)
        sheet.tables.extend(findStandIn(built, each) for each in group)
    for sheet, tables in parts:
        if not any(each is sheet for each in document.sheets):
            document.sheets.append(sheet)
        sheet.tables.extend(
            table for table, _, _ in tables
            if not any(each is table for each in sheet.tables)
        )
    document._ownersLink()
    for _, tables in parts:
        for table, tableForm, where in tables:
            assignFormulas(table, tableForm, where)
    return document


def findStandIn(built: dict[str, Table], entry: TableEntry) -> Table:
    """Return the table built for a directory entry, or an empty stand-in for it."""
    table = built.get(entry.identifier)
    if table is not None:
        return table
    return Table(name=entry.name, rowCount=entry.rowCount, colCount=entry.colCount,
                 identifier=entry.identifier)


__all__ = [
    "DocumentForm",
    "SheetForm",
    "TableEntry",
    "buildDocument",
    "buildDocumentForm",
    "buildPart",
    "buildSheet",
    "buildSheetForm",
    "listTableEntries",
]
