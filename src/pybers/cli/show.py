#!/usr/bin/env python3
"""\
`pybers show`: a document's sheets and tables, or the cells a selector names.

The command opens the document, makes one `partSelect` call, and never saves. A
range prints as its table narrowed to it, as `formatJsonForm` writes one. A cell
prints one line per field of its JSON form, in that form's order and under its names,
and a control prints every setting its form holds. `tests/test_cli_show.py` fails
when the form gains a field this command does not print.

UPDATES
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

import dataclasses
import re
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Group, RenderableType
from rich.text import Text

import pybers
from pybers.cli._common import reportPybersErrors
from pybers.cli._formats import FormatOption, OutputFormat, printResult
from pybers.cli._report import formatCount, formatLine, formatSheetTree, formatTableSize

type DocumentPart = pybers.Document | pybers.Sheet | pybers.Table | pybers.Cell

# Where a JSON key's next word starts, so `formulaText` reads `formula text`.
wordStart: re.Pattern[str] = re.compile(r"(?<!^)(?=[A-Z])")


def formatWords(key: str) -> str:
    """Return a JSON key as the lowercase words it joins, `starts with first item`."""
    return wordStart.sub(" ", key).lower()


def formatYesNo(flag: bool) -> str:
    """Return a flag as `yes` or `no`."""
    return "yes" if flag else "no"


def formatSettingValue(value: object) -> str:
    """Return one setting of a control as a report value."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return formatYesNo(value)
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, tuple | list):
        return f"[{', '.join(formatSettingValue(each) for each in value)}]"
    return str(value)


def formatControl(control: pybers.CellControl | None) -> str:
    """Return a control as its type, then each setting under its JSON form's name.

    The settings are the fields taking part in equality, which are what the form writes.
    """
    if control is None:
        return "none"
    settings = ", ".join(
        f"{formatWords(each.name)} {formatSettingValue(getattr(control, each.name))}"
        for each in dataclasses.fields(control)
        if each.compare and not each.name.startswith("_")
    )
    family = control.controlType.value
    return f"{family} ({settings})" if settings else family


def formatFormat(cellFormat: pybers.CellFormat | pybers.UNDETERMINED | None) -> str:
    """Return a format as its family, `unknown` until a save chooses one."""
    if cellFormat is None:
        return "none"
    if cellFormat is pybers.UNDETERMINED:
        return "unknown"
    return cellFormat.value


def formatCell(cell: pybers.Cell) -> Group:
    """Return a cell as one line per field of its JSON form, in the form's order."""
    presentation = cell.presentation
    text, typeCode = cell.formulaText, cell.unrecognizedTypeCode
    return Group(
        formatLine("Cell", (str(cell.reference), "identifier")),
        formatLine("Value", pybers.formatCellValue(cell.value)),
        formatLine("Kind", cell.kind.value),
        formatLine("Formula text", "none" if text is None else text),
        formatLine("Value cached", formatYesNo(cell.valueCached)),
        formatLine("Format", formatFormat(presentation.format)),
        formatLine("Format chosen", formatYesNo(presentation.formatChosen)),
        formatLine("Control", formatControl(presentation.control)),
        formatLine(
            "Unrecognized type code", "none" if typeCode is None else str(typeCode)
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


def formatCells(cells: list[pybers.Cell]) -> list[RenderableType]:
    """Return a count of cells, then each cell after a blank line."""
    shown: list[RenderableType] = [
        formatLine("Cells", formatCount(len(cells), "cell") if cells else "none")
    ]
    for cell in cells:
        shown += [Text(""), formatCell(cell)]
    return shown


def formatTable(table: pybers.Table) -> Group:
    """Return a table's name, size and merges, then each cell it holds."""
    merges = ", ".join(str(merge.extent) for merge in table.mergeRanges)
    return Group(
        formatLine("Table", (str(table.reference), "identifier")),
        formatLine("Size", formatTableSize(table)),
        formatLine("Merges", merges or "none"),
        *formatCells(listCells(table)),
    )


def formatRange(table: pybers.Table, extent: pybers.CellRange) -> Group:
    """Return a range, qualified by its table, then each cell stored within it."""
    return Group(
        formatLine("Range", (str(extent), "identifier")),
        *formatCells(listCells(table, extent)),
    )


def formatSheet(sheet: pybers.Sheet) -> Group:
    """Return a sheet's name, then each of its tables after a blank line."""
    tables = sheet.tables
    shown: list[RenderableType] = [
        formatLine("Sheet", (sheet.name, "identifier")),
        formatLine("Tables", formatCount(len(tables), "table") if tables else "none"),
    ]
    for table in sheet.tables:
        shown += [Text(""), formatTable(table)]
    return Group(*shown)


def formatPart(part: DocumentPart) -> RenderableType:
    """Return what a selector named as the lines a person reads."""
    match part:
        case pybers.Document():
            trees = [formatSheetTree(each) for each in part.sheets]
            return Group(Text("Sheets:", "label"), *trees)
        case pybers.Sheet():
            return formatSheet(part)
        case pybers.Table():
            return formatTable(part)
    return formatCell(part)


def findRangeTable(document: pybers.Document, extent: pybers.CellRange) -> pybers.Table:
    """Return the table a selected range names, with the sheet `partSelect` names."""
    named = extent.table
    if named is None or named.sheet is None:
        raise pybers.SelectionError(f"{extent} names no sheet and table.")
    return document.sheet(named.sheet.name).table(named.name)


def printRange(
    table: pybers.Table, extent: pybers.CellRange, outputFormat: OutputFormat
) -> None:
    """Print a range as its table narrowed to it, the form `formatJsonForm` writes."""
    printResult(
        table, outputFormat, lambda each: formatRange(each, extent), extent=extent
    )


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
            help=(
                "The sheet, table, range or cell: `Budget`, `Q3`, `Q3::B2:D5` or "
                "`Budget::Q3::B4`."
            ),
            show_default=False,
        ),
    ] = None,
    outputFormat: FormatOption = OutputFormat.TEXT,
) -> None:
    """Show a document's sheets and tables, or the cells SELECTOR names."""
    with reportPybersErrors(context):
        document = pybers.open(documentPath)
        part = document if selector is None else document.partSelect(selector)
        if isinstance(part, pybers.CellRange):
            printRange(findRangeTable(document, part), part, outputFormat)
            return
    printResult(part, outputFormat, formatPart)


__all__ = ["runShow"]
