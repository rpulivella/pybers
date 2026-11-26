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
2026-11-26  A folder of font files as FILE shows its fonts, for PYB-268.
2026-11-24  Progress shows on stderr while a document or the typefaces are read,
            and each font file skipped is composed, for PYB-319.
2026-11-24  `typefaces` as FILE shows the typefaces pybers knows, for PYB-318.
2026-11-24  `fonts` or a font file as FILE shows fonts, one per line, for PYB-315.
2026-11-23  Declared for Click, SELECTOR completing to sheets and tables, for
            PYB-304.
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-20  A cell prints its computed box beside its own, for PYB-291.
2026-11-17  A table's lines, as CSS declarations under its own line, for PYB-266.
2026-11-17  A cell's borders, after its cell style, for PYB-266.
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
from itertools import groupby
from pathlib import Path

import click
from rich.console import Group, RenderableType
from rich.text import Text

import pybers
from pybers.cli._common import listSelectorCompletions, reportPybersErrors
from pybers.cli._console import showProgress, statusConsole
from pybers.cli._formats import OutputFormat, outputFormatOption, printResult
from pybers.cli._help import PybersArgument, PybersCommand
from pybers.cli._report import (
    childIndent,
    fieldGap,
    formatCount,
    formatCountShown,
    formatFields,
    formatLine,
    formatListed,
    formatParts,
    formatSegments,
    formatSkip,
    formatYesNo,
    listChildren,
)

type DocumentPart = pybers.Document | pybers.Sheet | pybers.Table | pybers.Cell

# The FILE showing the typefaces pybers knows, so a file of that name is `./typefaces`.
typefacesFile: str = "typefaces"


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


def formatCell(cell: pybers.Cell, indent: int = 0) -> Group:
    """Return a cell's fields of its JSON form, in its order, folded onto lines."""
    presentation = cell.presentation
    text, typeCode = cell.formulaText, cell.unrecognizedTypeCode
    table = cell.table
    computed = None if table is None else table.cellStyleComputed(cell.address)
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
        formatFields(inner, ("Cell style computed", formatCellStyle(computed))),
        formatFields(inner, ("Borders", pybers.formatCellBorders(cell) or "none")),
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
    """Return a table's size, headers, merges and cell count, its lines, then cells."""
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
        formatTableStyleLines(table.tableStyle, indent + childIndent),
        *listChildren([formatCell(cell, indent + childIndent) for cell in cells]),
    )


def formatTableStyleLines(tableStyle: pybers.TableStyle, indent: int) -> Group:
    """Return a table's lines as CSS declarations, one per line under their label.

    Each line pastes back into `pybers set --table-style`.
    """
    return formatListed("Table style", pybers.formatTableStyle(tableStyle), indent)


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
    raise AssertionError(f"The match {match!r} belongs to no table.")


def formatShownPart(part: ShownPart) -> RenderableType:
    """Return one part as `show` prints it alone, a range as its narrowed table."""
    if isinstance(part, tuple):
        return formatRange(*part)
    return formatPart(part)


def formatShownParts(parts: list[ShownPart]) -> Group:
    """Return each part as it prints alone, a blank line between each."""
    return formatParts([formatShownPart(part) for part in parts])


def formatFont(font: pybers.TypefaceFont) -> Text:
    """Return a font as a part's line, its PostScript name and then its fields."""
    shown = formatSegments(childIndent, "Font", font.postScriptName)
    return shown.append(fieldGap).append_text(formatFields(
        0, ("Name", font.name), ("Weight", str(font.weight)),
        ("Slant", font.slant.value), ("Source", font.source.value),
    ))


def formatFonts(fonts: Sequence[pybers.TypefaceFont]) -> Group:
    """Return each typeface and its font count, its fonts one line each beneath."""
    grouped = [
        (typeface, list(each))
        for typeface, each in groupby(fonts, key=lambda font: font.typeface)
    ]
    families = [
        Group(
            formatSegments(
                0, "Typeface", typeface, formatCount(len(each), "font")
            ),
            *(formatFont(font) for font in each),
        )
        for typeface, each in grouped
    ]
    return formatParts(families)


def isFontPath(path: Path) -> bool:
    """Return whether FILE is a font file or a folder of them, never a package."""
    suffix = path.suffix.lower()
    return suffix in pybers.fontSuffixes or (path.is_dir() and suffix != ".numbers")


def showTypefaces(file: str, selector: str | None, outputFormat: OutputFormat) -> None:
    """Print the fonts a selector matches, and each font file skipped on stderr."""
    with showProgress() as onProgress:
        typefaces = pybers.openTypefaces(
            None if file == typefacesFile else file, onProgress=onProgress
        )
    if selector is not None:
        typefaces = pybers.Typefaces(typefaces.select(selector), typefaces.skipped)
    for skip in typefaces.skipped:
        statusConsole.print(formatSkip(skip))
    printResult(typefaces, outputFormat, lambda shown: formatFonts(shown.fonts))


@click.command("show", cls=PybersCommand)
@click.argument(
    "file", cls=PybersArgument, type=click.Path(),
    help="The .numbers document, `typefaces` for the typefaces pybers knows, or a font "
    "file or a folder of them.",
)
@click.argument(
    "selector", cls=PybersArgument, required=False,
    shell_complete=listSelectorCompletions,
    help="What to show: `Budget`, `Budget::Q3`, `::Q3::B2:D5`, `::B4` or "
    "`Budget::Q*[kind=number]`, each match as it shows alone, or for typefaces "
    "`Avenir Next::*Demi*` or `*[weight>=600]`.",
)
@outputFormatOption
@click.pass_context
def runShow(
    context: click.Context, file: str, selector: str | None, outputFormat: OutputFormat
) -> None:
    """Show a whole document, or every part SELECTOR matches, or the typefaces."""
    with reportPybersErrors(context):
        if file == typefacesFile or isFontPath(Path(file)):
            showTypefaces(file, selector, outputFormat)
            return
        with showProgress() as onProgress:
            document = pybers.open(Path(file), onProgress=onProgress)
        if selector is None:
            printResult(document, outputFormat, formatPart)
            return
        parts = [findPart(document, each) for each in document.select(selector)]
    printResult(parts, outputFormat, formatShownParts)

__all__ = ["runShow"]
