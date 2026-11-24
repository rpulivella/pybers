#!/usr/bin/env python3
"""\
`pybers set`: the cells and tables a selector matches, or a document's locale.

The command reads the text into a value and a format, makes one `cellSet` call, and
saves only
when a cell changed and the call was not a preview. Each cell written prints as
`pybers show` prints it, in text and JSON alike, and each part skipped prints why on
stderr.

UPDATES
2026-11-23  Declared for Click, SELECTOR completing to sheets and tables, for
            PYB-304.
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-22  `--table-style` lists each section's box, for PYB-291.
2026-11-19  `--cell-style-update` and `--cell-style-remove` change part of a
            cell's box, for PYB-290.
2026-11-19  `--locale` sets a document's language and region, for PYB-301.
2026-11-18  `--table-style` lists `banded-rows`, for PYB-267.
2026-11-17  `--table-style` sets the lines of each table matched, for PYB-266.
2026-11-17  `--border` draws borders on one block, with `--border-style`,
            `--border-width` and `--border-color`, for PYB-266.
2026-11-13  `--cell-style` sets a cell's whole box by its text form, `none`
            removing it, for PYB-265.
2026-11-10  `--cell-control` sets a control by its text form, `none` removing one,
            for PYB-145.
2026-11-10  `--cell-format` sets a format by its text form, VALUE now optional, and
            `--conflict` falls back to Automatic for a format that does not fit,
            for PYB-145.
2026-11-03  SELECTOR sets every cell it matches, reporting each skipped, for
            PYB-223. Each cell written prints as `pybers show` prints it.
2026-10-28  Where a write goes shared with `locale`, FILE itself unless `-o`
            names a new one, for PYB-272.
2026-10-27  Report lines shared with `show`, growth by one row reading `1 row`,
            for PYB-260.
2026-10-20  A date, a duration and a boolean, inferred or named, and the zone an
            aware date is written in, for PYB-144.
2026-10-20  Written for PYB-217.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/20"

from dataclasses import dataclass
from pathlib import Path

import click
from rich.text import Text

import pybers
from pybers.cli._common import (
    composeUsageChoiceRefusal,
    composeUsageRefusal,
    findSaveTarget,
    listSelectorCompletions,
    outputOption,
    previewOption,
    reportPybersErrors,
    reportWrite,
)
from pybers.cli._console import statusConsole
from pybers.cli._formats import OutputFormat, outputFormatOption, printResult
from pybers.cli._help import ChoiceOfValues, PybersArgument, PybersCommand
from pybers.cli._report import formatLine
from pybers.cli.show import ShownPart, formatShownParts

# Spelled out rather than read from the enums, so `--help` never loads the model;
# `test_cli_set_borders` holds each equal to its enum.
borderPositions: tuple[str, ...] = (
    "all", "outer", "outer-top", "outer-right", "outer-bottom", "outer-left",
    "between", "between-rows", "between-columns",
)
borderStyles: tuple[str, ...] = ("solid", "dashed", "dotted", "hidden")


@dataclass(frozen=True, slots=True)
class DocumentLocale:
    """A document's language and region, under the key its JSON form gives it."""

    localeIdentifier: str | None


def formatLocale(locale: DocumentLocale) -> Text:
    """Return a document's locale as `pybers show` prints it."""
    current = locale.localeIdentifier
    return formatLine("Locale", current or "none")


@click.command("set", cls=PybersCommand)
@click.argument(
    "file", cls=PybersArgument, type=click.Path(path_type=Path),
    help="The .numbers document.",
)
@click.argument(
    "selector", cls=PybersArgument, required=False,
    shell_complete=listSelectorCompletions,
    help=(
        "The cells to set, such as `Budget::Q3::B4`, `::Q3::B4` for B4 of "
        "every table named Q3, or `Budget::Q*::B2:B9[kind=number]`, left "
        "out with --locale."
    ),
)
@click.argument(
    "value", cls=PybersArgument, required=False,
    help=(
        "The value as text, such as 42, 42 EUR, TRUE, 2026-10-20 09:00, 1h 30m "
        "or any text, each cell keeping its value when it is left out."
    ),
)
@click.option(
    "--as", "kind",
    metavar="KIND",
    help=(
        "Read VALUE as this kind rather than inferring it: number, currency, "
        "boolean, date, duration or text."
    ),
)
@click.option(
    "--time-zone", "timeZone",
    metavar="ZONE",
    help=(
        "Write a date carrying an offset as the wall-clock time in ZONE, "
        "such as America/New_York, rather than the zone pybers is running in."
    ),
)
@click.option(
    "--cell-format", "cellFormat",
    metavar="FORMAT",
    help=(
        "The format each cell shows its value with, as `pybers show` prints "
        "one: automatic, number or text."
    ),
)
@click.option(
    "--cell-control", "cellControl",
    metavar="CONTROL",
    help=(
        "The control each cell presents its value through, as `pybers show` "
        "prints one, or none to remove it."
    ),
)
@click.option(
    "--cell-style", "cellStyle",
    metavar="STYLE",
    help=(
        "The box each cell is drawn in, replacing its whole box, as `pybers "
        "show` prints one: background, padding, vertical-align and text-wrap "
        "as CSS, or none to remove it."
    ),
)
@click.option(
    "--cell-style-update", "cellStyleUpdate",
    metavar="STYLE",
    help=(
        "The properties of each cell's box to change, written as for "
        "--cell-style, every property not given kept as it was."
    ),
)
@click.option(
    "--cell-style-remove", "cellStyleRemove",
    metavar="PROPERTY",
    help=(
        "One property to clear from each cell's box, so the cell shows what "
        "its table states: background, padding, vertical-align or text-wrap."
    ),
)
# Text rather than the enum, so `--help` never loads the model.
@click.option(
    "--border",
    metavar="POSITION",
    help=(
        "Draw borders on the one block SELECTOR selects, at this part of it: "
        "all, outer, outer-top, outer-right, outer-bottom, outer-left, "
        "between, between-rows or between-columns."
    ),
)
@click.option(
    "--border-style", "borderStyle",
    metavar="STYLE",
    help=(
        "The --border line, solid when left out: solid, dashed, dotted, hidden "
        "to draw nothing and hide the table's line, or none to remove the "
        "borders."
    ),
)
@click.option(
    "--border-width", "borderWidth",
    metavar="LENGTH",
    help="The --border line's width, such as 1pt, and 0.35pt when left out.",
)
@click.option(
    "--border-color", "borderColor",
    metavar="COLOR",
    help=(
        "The --border line's color, as `pybers show` prints one, such as "
        "#ff0000ff, and black when left out."
    ),
)
@click.option(
    "--table-style", "tableStyle",
    metavar="STYLE",
    help=(
        "The lines each table SELECTOR matches draws, as `pybers show` prints "
        "them: each `width style color` or none, its -width, -style or -color "
        "changing one part, for table-outline, "
        "body-horizontal-gridlines, body-vertical-gridlines, "
        "header-rows-horizontal-gridlines, header-rows-vertical-gridlines, "
        "header-columns-horizontal-gridlines, "
        "header-columns-vertical-gridlines, "
        "footer-rows-horizontal-gridlines, footer-rows-vertical-gridlines, "
        "header-rows-separator, header-columns-separator and "
        "footer-rows-separator; table-title and table-outline-title, yes "
        "or no; banded-rows, a color or none, with banded-rows-background "
        "its color alone; and the -background, -padding, -vertical-align and "
        "-text-wrap of body, header-rows, header-columns and footer-rows, the "
        "box their cells inherit."
    ),
)
@click.option(
    "--locale",
    metavar="LOCALE",
    help=(
        "The document's language and region, such as de_DE or en_GB, given "
        "with no SELECTOR."
    ),
)
@click.option(
    "--conflict",
    type=ChoiceOfValues(pybers.CellFormatConflict),
    default=pybers.CellFormatConflict.REFUSE, show_default=True,
    help=(
        "What a --cell-format that cannot show a cell's value does: refuse the "
        "write, or give that cell the Automatic format and say so."
    ),
)
@outputOption
@previewOption
@click.option(
    "--extend", is_flag=True,
    help="Grow the table when SELECTOR selects one cell lying outside it.",
)
@outputFormatOption
@click.pass_context
def runSet(
    context: click.Context,
    file: Path,
    selector: str | None,
    value: str | None,
    kind: str | None,
    timeZone: str | None,
    cellFormat: str | None,
    cellControl: str | None,
    cellStyle: str | None,
    cellStyleUpdate: str | None,
    cellStyleRemove: str | None,
    border: str | None,
    borderStyle: str | None,
    borderWidth: str | None,
    borderColor: str | None,
    tableStyle: str | None,
    locale: str | None,
    conflict: pybers.CellFormatConflict,
    extend: bool,
    output: Path | None,
    preview: bool,
    outputFormat: OutputFormat,
) -> None:
    """Set what SELECTOR matches, or with --locale the document's locale."""
    cellParts = (value, cellFormat, cellControl, cellStyle)
    styleParts = (cellStyle, cellStyleUpdate, cellStyleRemove)
    everyPart = (*cellParts, cellStyleUpdate, cellStyleRemove, border, tableStyle)
    if locale is not None:
        if selector is not None or any(part is not None for part in everyPart):
            raise composeUsageRefusal(
                "--locale", "sets the whole document, so it takes no SELECTOR and "
                "nothing else to set", "Give --locale alone", pybers.nothingWritten,
            )
        setLocale(context, file, locale, output, preview, outputFormat)
        return
    if selector is None:
        raise composeUsageRefusal(
            "SELECTOR", "is missing", "Give a SELECTOR, or --locale",
            pybers.nothingWritten,
        )
    if border is None and any(
        part is not None for part in (borderStyle, borderWidth, borderColor)
    ):
        raise composeUsageRefusal(
            "--border-style, --border-width and --border-color", "describe a "
            "--border, and none is given", "Give --border POSITION",
            pybers.nothingWritten,
        )
    if all(part is None for part in everyPart):
        raise composeUsageRefusal(
            "SELECTOR", "is given with nothing to set", "Give a VALUE, a "
            "--cell-format, a --cell-control, a --cell-style, a --cell-style-update, "
            "a --cell-style-remove, a --border or a --table-style",
            pybers.nothingWritten,
        )
    if sum(part is not None for part in styleParts) > 1:
        raise composeUsageRefusal(
            "--cell-style, --cell-style-update and --cell-style-remove", "cannot be "
            "given together, since the first replaces the whole box, the second "
            "changes part of it and the third clears one property", "Give one of them",
            pybers.nothingWritten,
        )
    styleProperties = [each.value for each in pybers.CellStyleProperty]
    if cellStyleRemove is not None and cellStyleRemove not in styleProperties:
        raise composeUsageChoiceRefusal(
            cellStyleRemove, "a cell style property", styleProperties, "set",
            pybers.nothingWritten,
        )
    if border is not None and border not in borderPositions:
        raise composeUsageChoiceRefusal(
            border, "a border position", borderPositions, "set", pybers.nothingWritten
        )
    if borderStyle is not None and borderStyle not in ("none", *borderStyles):
        raise composeUsageChoiceRefusal(
            borderStyle, "a border style", (*borderStyles, "none"), "set",
            pybers.nothingWritten,
        )
    target = findSaveTarget(file, output, preview)
    with reportPybersErrors(context):
        document = (
            pybers.open(file) if timeZone is None
            else pybers.open(file, timeZone=timeZone)
        )
        changes = pybers.CellChanges(())
        if any(part is not None for part in cellParts):
            changes = document.cellSet(
                selector,
                pybers.UNCHANGED if value is None
                else pybers.parseCellValue(value, kind),
                format=(
                    pybers.UNCHANGED if cellFormat is None
                    else pybers.parseCellFormat(cellFormat)
                ),
                control=(
                    pybers.UNCHANGED if cellControl is None
                    else pybers.parseCellControl(cellControl)
                ),
                cellStyle=(
                    pybers.UNCHANGED if cellStyle is None
                    else pybers.parseCellStyle(cellStyle)
                ),
                conflict=conflict,
                extend=extend,
            )
        partStyled = None
        if cellStyleUpdate is not None:
            stated = pybers.parseCellStyle(cellStyleUpdate)
            if stated is None:
                raise pybers.CellStyleError(pybers.composeRefusal(
                    "--cell-style-update", "changes properties, so it takes no none",
                    "Give --cell-style none to remove the whole box",
                    pybers.nothingWritten,
                ))
            partStyled = document.cellStyleUpdate(selector, stated, extend=extend)
        if cellStyleRemove is not None:
            partStyled = document.cellStylePropertyRemove(
                selector, pybers.CellStyleProperty(cellStyleRemove), extend=extend
            )
        if partStyled is not None:
            changes = pybers.CellChanges(
                changes.changes + partStyled.changes,
                changes.skipped + partStyled.skipped,
            )
        if border is not None:
            drawn = document.cellBordersSet(
                selector, pybers.CellBorderPosition(border),
                style=(
                    pybers.CellBorderStyle.SOLID if borderStyle is None
                    else None if borderStyle == "none"
                    else pybers.CellBorderStyle(borderStyle)
                ),
                width=(
                    None if borderWidth is None
                    else pybers.parseLength(borderWidth, "--border-width")
                ),
                color=None if borderColor is None else pybers.Color.parse(borderColor),
            )
            changes = pybers.CellChanges(
                changes.changes + drawn.changes, changes.skipped + drawn.skipped
            )
        # Each cell once, though a value and a border may both have changed it.
        shown: list[ShownPart] = [
            document.table(reference.table).cell(reference)
            for reference in dict.fromkeys(
                each.reference for each in changes.changes
            )
            if reference.table is not None
        ]
        skipped = [(str(skip.reference), skip.reason) for skip in changes.skipped]
        restyled = False
        if tableStyle is not None:
            for match in document.select(selector):
                if not isinstance(match, pybers.TableReference):
                    skipped.append((str(match), "not a table"))
                    continue
                table = document.table(match)
                if table.tableStyleSet(
                    pybers.parseTableStyle(tableStyle, table.tableStyle)
                ).changed:
                    restyled = True
                    shown.append(table)
        changed = changes.changed or restyled
        if target is not None and changed:
            document.save(target)
    printResult(shown, outputFormat, formatShownParts)
    for reference, reason in skipped:
        statusConsole.print(formatLine("Skipped", f"{reference}  {reason}"))
    reportWrite(changed, target, "already set")


def setLocale(
    context: click.Context, documentPath: Path, identifier: str, output: Path | None,
    preview: bool, outputFormat: OutputFormat,
) -> None:
    """Change a document's locale and print it, saving only a change."""
    target = findSaveTarget(documentPath, output, preview)
    with reportPybersErrors(context):
        document = pybers.open(documentPath)
        changed = document.localeSet(identifier).changed
        if target is not None and changed:
            document.save(target)
    printResult(DocumentLocale(document.localeIdentifier), outputFormat, formatLocale)
    reportWrite(changed, target, f"already {document.localeIdentifier}")


__all__ = ["runSet"]
