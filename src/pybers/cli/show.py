#!/usr/bin/env python3
"""\
`pybers show`: a whole document, or every part a selector matches, in full.

The command opens the document, makes at most one `select` call, and never saves.
Each match prints in full, one after another with a blank line between: a range as its
table narrowed to it, as `formatJsonForm` writes one, and a cell the fields of its JSON
form, in that form's order and under its names, folded onto three lines. A selector's
JSON is always an array of those forms, which `parseJsonForm` reads back.
`tests/test_cli_show.py` fails when the form gains a field this command does not print.

UPDATES
2026-11-12  A cell's own cell style prints as its text form, for PYB-265.
2026-11-10  A control prints as its text form, as a format does, for PYB-145.
2026-11-10  A format prints as its text form, `(automatic)` after one Automatic chose,
            for PYB-145.
2026-11-09  A format prints its family and settings, Automatic the format it chose,
            replacing the chosen flag, for PYB-145.
2026-11-03  What a selector matches, read by the one resolver, each match as it
            prints alone, a document in full as its JSON is, and a table's
            headers, for PYB-223.
2026-10-28  A document's outline opens with its locale, for PYB-272.
2026-10-27  Written for PYB-260.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/27"

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Group, RenderableType
from rich.text import Text

import pybers
from pybers.cli._common import reportPybersErrors
from pybers.cli._formats import FormatOption, OutputFormat, printResult
from pybers.cli._report import formatCount, formatLine

type DocumentPart = pybers.Document | pybers.Sheet | pybers.Table | pybers.Cell

# How far a part's children sit under it, and what separates what one line holds.
childIndent: int = 2
segmentGap: str = "  "
fieldGap: str = "   "


def formatYesNo(flag: bool) -> str:
    """Return a flag as `yes` or `no`."""
    return "yes" if flag else "no"


def formatControl(control: pybers.CellControl | None) -> str:
    """Return a control as its text form, which `pybers set --cell-control` reads."""
    return "none" if control is None else pybers.formatCellControl(control)


def formatCellStyle(cellStyle: pybers.CellStyle | None) -> str:
    """Return a cell style as its text form, which `pybers set --cell-style` reads."""
    shown = None if cellStyle is None else pybers.formatCellStyle(cellStyle)
    return shown or "none"


def formatFormat(cellFormat: pybers.CellFormat | pybers.UNDETERMINED | None) -> str:
    """Return a format as its text form, which `pybers set --cell-format` reads."""
    return "none" if cellFormat is None else pybers.formatCellFormat(cellFormat)


def formatSegments(indent: int, label: str, name: str, *segments: str) -> Text:
    """Return a part's line: its label and name, then each segment holding something.

    An empty segment is left out, so a count of zero or an empty list never prints.
    """
    # A part's own label is full weight, as the tree in `check` draws one.
    shown = Text.assemble(" " * indent, (f"{label}: ", "value"), (name, "identifier"))
    for segment in segments:
        if segment:
            shown.append(segmentGap).append(segment, "value")
    return shown


def formatFields(indent: int, *fields: tuple[str, str]) -> Text:
    """Return several labeled fields folded onto one line."""
    shown = Text(" " * indent)
    for index, (label, value) in enumerate(fields):
        if index:
            shown.append(fieldGap)
        shown.append_text(formatLine(label, value))
    return shown


def formatCountShown(count: int, noun: str) -> str:
    """Return a count with its noun, or nothing when the count is zero."""
    return formatCount(count, noun) if count else ""


def listChildren(children: Sequence[RenderableType]) -> list[RenderableType]:
    """Return each child of a part, a blank line before each."""
    return [shown for child in children for shown in (Text(""), child)]


def formatCell(cell: pybers.Cell, indent: int = 0) -> Group:
    """Return a cell's fields of its JSON form, in its order, folded onto lines."""
    presentation = cell.presentation
    text, typeCode = cell.formulaText, cell.unrecognizedTypeCode
    inner = indent + childIndent
    return Group(
        formatSegments(indent, "Cell", str(cell.reference)),
        formatFields(
            inner,
            ("Value", pybers.formatCellValue(cell.value)),
            ("Kind", cell.kind.value),
            ("Formula text", "none" if text is None else text),
            ("Value cached", formatYesNo(cell.valueCached)),
        ),
        formatFields(
            inner,
            ("Format", formatFormat(presentation.format)),
            ("Control", formatControl(presentation.control)),
        ),
        formatFields(inner, ("Cell style", formatCellStyle(cell.cellStyle))),
        formatFields(
            inner,
            ("Unrecognized type code", "none" if typeCode is None else str(typeCode)),
        ),
    )


def listCells(
    table: pybers.Table, extent: pybers.CellRange | None = None
) -> list[pybers.Cell]:
    """Return the cells a table stores, within an extent when one is given, by row."""
    return [
        table.cells[address]
        for address in sorted(table.cells, key=lambda address: address.asRowColumn())
        if extent is None or extent.covers(address)
    ]


def formatTable(table: pybers.Table, indent: int = 0) -> Group:
    """Return a table's size, headers, merges and cell count, then each of its cells."""
    headers = table.headers
    cells = listCells(table)
    merges = ", ".join(str(merge.extent) for merge in table.mergeRanges)
    return Group(
        formatSegments(
            indent, "Table", str(table.reference),
            f"{formatCount(table.rowCount, 'row')} × "
            f"{formatCount(table.colCount, 'column')}",
            ", ".join(each for each in (
                formatCountShown(headers.headerRows, "header row"),
                formatCountShown(headers.headerColumns, "header column"),
                formatCountShown(headers.footerRows, "footer row"),
            ) if each),
            f"merges {merges}" if merges else "",
            formatCountShown(len(cells), "cell"),
        ),
        *listChildren([formatCell(cell, indent + childIndent) for cell in cells]),
    )


def formatRange(table: pybers.Table, extent: pybers.CellRange) -> Group:
    """Return a range, qualified by its table, then each cell stored within it."""
    cells = listCells(table, extent)
    return Group(
        formatSegments(0, "Range", str(extent), formatCountShown(len(cells), "cell")),
        *listChildren([formatCell(cell, childIndent) for cell in cells]),
    )


def formatSheet(sheet: pybers.Sheet) -> Group:
    """Return a sheet's name and table count, then each of its tables."""
    count = formatCountShown(len(sheet.tables), "table")
    return Group(
        formatSegments(0, "Sheet", sheet.name, count),
        *listChildren([formatTable(table, childIndent) for table in sheet.tables]),
    )


def formatPart(part: DocumentPart) -> RenderableType:
    """Return a document, sheet, table or cell as the lines a person reads."""
    match part:
        case pybers.Document():
            locale = part.localeIdentifier
            sheets = [formatSheet(each) for each in part.sheets]
            return Group(formatLine("Locale", locale or "none"), *listChildren(sheets))
        case pybers.Sheet():
            return formatSheet(part)
        case pybers.Table():
            return formatTable(part)
    return formatCell(part)


type ShownPart = DocumentPart | tuple[pybers.Table, pybers.CellRange]


def findPart(document: pybers.Document, match: pybers.SelectionMatch) -> ShownPart:
    """Return the part a match points at, a range as its table and that range."""
    match match:
        case pybers.SheetReference():
            return document.sheet(match.name)
        case pybers.TableReference():
            return document.table(match)
        case pybers.CellReference(table=table) if table is not None:
            return document.table(table).cell(match)
        case pybers.CellRange(table=table) if table is not None:
            return (document.table(table), match)
    raise AssertionError(f"A selection returned {match!r}, which names no table.")


def formatShownPart(part: ShownPart) -> RenderableType:
    """Return one part as `show` prints it alone, a range as its narrowed table."""
    if isinstance(part, tuple):
        return formatRange(*part)
    return formatPart(part)


def formatShownParts(parts: list[ShownPart]) -> Group:
    """Return each part as it prints alone, a blank line between each."""
    shown: list[RenderableType] = []
    for part in parts:
        shown += [Text(""), formatShownPart(part)] if shown else [formatShownPart(part)]
    return Group(*shown)


def runShow(
    context: typer.Context,
    documentPath: Annotated[
        Path,
        typer.Argument(
            metavar="FILE", help="The .numbers document.", show_default=False
        ),
    ],
    selector: Annotated[
        str | None,
        typer.Argument(
            metavar="SELECTOR",
            # A backslash keeps Rich from reading a condition as markup.
            help=(
                "What to show: `Budget`, `Budget::Q3`, `::Q3::B2:D5`, `::B4` or "
                "`Budget::Q*\\[kind=number]`, each match as it shows alone."
            ),
            show_default=False,
        ),
    ] = None,
    outputFormat: FormatOption = OutputFormat.TEXT,
) -> None:
    """Show a whole document, or every part SELECTOR matches."""
    with reportPybersErrors(context):
        document = pybers.open(documentPath)
        if selector is None:
            printResult(document, outputFormat, formatPart)
            return
        parts = [findPart(document, each) for each in document.select(selector)]
    printResult(parts, outputFormat, formatShownParts)

__all__ = ["runShow"]
