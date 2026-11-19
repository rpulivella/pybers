#!/usr/bin/env python3
"""\
`pybers set`: the cells and tables a selector matches, or a document's locale.

The command reads the text into a value and a format, makes one `cellSet` call, and
saves only
when a cell changed and the call was not a preview. Each cell written prints as
`pybers show` prints it, in text and JSON alike, and each part skipped prints why on
stderr.

UPDATES
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
from typing import Annotated

import typer
from rich.text import Text

import pybers
from pybers.cli._common import (
    OutputOption,
    PreviewOption,
    findSaveTarget,
    reportPybersErrors,
    reportWrite,
)
from pybers.cli._console import statusConsole
from pybers.cli._formats import FormatOption, OutputFormat, printResult
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
    return formatLine("Locale", (current, "identifier") if current else "none")


def runSet(
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
            metavar="[SELECTOR]",
            # A backslash keeps Rich from reading a condition as markup.
            help=(
                "The cells to set: `Budget::Q3::B4`, `::Q3::B4` for B4 of every table "
                "named Q3, or `Budget::Q*::B2:B9\\[kind=number]`. Left out with "
                "--locale."
            ),
            show_default=False,
        ),
    ] = None,
    value: Annotated[
        str | None,
        typer.Argument(
            metavar="[VALUE]",
            help=(
                "The value as text: 42, 42 EUR, TRUE, 2026-10-20 09:00, 1h 30m, or any "
                "text. Left out, each cell keeps its value."
            ),
            show_default=False,
        ),
    ] = None,
    kind: Annotated[
        str | None,
        typer.Option(
            "--as",
            metavar="KIND",
            help=(
                "Read VALUE as this kind rather than inferring it. One of: number, "
                "currency, boolean, date, duration, text."
            ),
        ),
    ] = None,
    timeZone: Annotated[
        str | None,
        typer.Option(
            "--time-zone",
            metavar="ZONE",
            help=(
                "Write a date carrying an offset as the wall-clock time in ZONE, "
                "such as America/New_York, rather than the zone pybers is running in."
            ),
        ),
    ] = None,
    cellFormat: Annotated[
        str | None,
        typer.Option(
            "--cell-format",
            metavar="FORMAT",
            help=(
                "The format each cell shows its value with, as `pybers show` prints "
                "one: automatic, number or text."
            ),
        ),
    ] = None,
    cellControl: Annotated[
        str | None,
        typer.Option(
            "--cell-control",
            metavar="CONTROL",
            help=(
                "The control each cell presents its value through, as `pybers show` "
                "prints one, or none to remove it."
            ),
        ),
    ] = None,
    cellStyle: Annotated[
        str | None,
        typer.Option(
            "--cell-style",
            metavar="STYLE",
            help=(
                "The box each cell is drawn in, as `pybers show` prints one: "
                "background, padding, vertical-align and text-wrap as CSS, or none to "
                "remove it. The style given replaces the whole box."
            ),
        ),
    ] = None,
    # Text rather than the enum, so `--help` never loads the model.
    border: Annotated[
        str | None,
        typer.Option(
            "--border",
            metavar="POSITION",
            help=(
                "Draw borders on the one block SELECTOR names, at this part of it: "
                "all, outer, outer-top, outer-right, outer-bottom, outer-left, "
                "between, between-rows or between-columns."
            ),
        ),
    ] = None,
    borderStyle: Annotated[
        str | None,
        typer.Option(
            "--border-style",
            metavar="STYLE",
            help=(
                "The --border line: solid, dashed, dotted, hidden to draw nothing and "
                "hide the table's line, or none to remove the borders. Solid when "
                "left out."
            ),
        ),
    ] = None,
    borderWidth: Annotated[
        str | None,
        typer.Option(
            "--border-width",
            metavar="LENGTH",
            help="The --border line's width, such as 1pt. 0.35pt when left out.",
        ),
    ] = None,
    borderColor: Annotated[
        str | None,
        typer.Option(
            "--border-color",
            metavar="COLOR",
            help=(
                "The --border line's color, as `pybers show` prints one, such as "
                "#ff0000ff. Black when left out."
            ),
        ),
    ] = None,
    tableStyle: Annotated[
        str | None,
        typer.Option(
            "--table-style",
            metavar="STYLE",
            help=(
                "The lines each table SELECTOR matches draws, as `pybers show` prints "
                "them, each `width style color` or none: table-outline, "
                "body-horizontal-gridlines, body-vertical-gridlines, "
                "header-rows-horizontal-gridlines, header-rows-vertical-gridlines, "
                "header-columns-horizontal-gridlines, "
                "header-columns-vertical-gridlines, "
                "footer-rows-horizontal-gridlines, footer-rows-vertical-gridlines, "
                "header-rows-separator, header-columns-separator and "
                "footer-rows-separator; table-title and table-outline-title, yes "
                "or no; and banded-rows, a color or none, with "
                "banded-rows-background its color alone. A line's -width, -style "
                "or -color changes one part."
            ),
        ),
    ] = None,
    locale: Annotated[
        str | None,
        typer.Option(
            "--locale",
            metavar="LOCALE",
            help=(
                "The document's language and region, such as de_DE or en_GB, given "
                "with no SELECTOR."
            ),
        ),
    ] = None,
    conflict: Annotated[
        pybers.CellFormatConflict,
        typer.Option(
            "--conflict",
            help=(
                "What a --cell-format that cannot show a cell's value does: refuse the "
                "write, or give that cell the Automatic format and say so."
            ),
        ),
    ] = pybers.CellFormatConflict.REFUSE,
    output: OutputOption = None,
    preview: PreviewOption = False,
    extend: Annotated[
        bool,
        typer.Option(
            "--extend",
            help="Grow the table when SELECTOR names one cell lying outside it.",
        ),
    ] = False,
    outputFormat: FormatOption = OutputFormat.TEXT,
) -> None:
    """Set what SELECTOR matches, or with --locale the document's locale."""
    cellParts = (value, cellFormat, cellControl, cellStyle)
    if locale is not None:
        if selector is not None or any(
            part is not None for part in (*cellParts, border, tableStyle)
        ):
            raise typer.BadParameter(
                "--locale sets the whole document, so give it without a SELECTOR."
            )
        setLocale(context, documentPath, locale, output, preview, outputFormat)
        return
    if selector is None:
        raise typer.BadParameter("Give a SELECTOR, or a --locale.")
    if border is None and any(
        part is not None for part in (borderStyle, borderWidth, borderColor)
    ):
        raise typer.BadParameter(
            "--border-style, --border-width and --border-color describe a --border, "
            "so give its POSITION."
        )
    if all(part is None for part in (*cellParts, border, tableStyle)):
        raise typer.BadParameter(
            "Give a VALUE, a --cell-format, a --cell-control, a --cell-style, a "
            "--border or a --table-style."
        )
    if border is not None and border not in borderPositions:
        raise typer.BadParameter(
            pybers.composeChoiceRefusal(border, "a border position", borderPositions)
        )
    if borderStyle is not None and borderStyle not in ("none", *borderStyles):
        choices = ", ".join(borderStyles)
        raise typer.BadParameter(
            f"--border-style is one of {choices} or none, and is {borderStyle!r}."
        )
    target = findSaveTarget(documentPath, output, preview)
    with reportPybersErrors(context):
        document = (
            pybers.open(documentPath) if timeZone is None
            else pybers.open(documentPath, timeZone=timeZone)
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
    context: typer.Context, documentPath: Path, identifier: str, output: Path | None,
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
