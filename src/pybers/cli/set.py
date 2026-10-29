#!/usr/bin/env python3
"""\
`pybers set`: one cell's value, its kind inferred from the text or named with `--as`.

The command reads the text into a value, makes one `cellSet` call, and saves only
when the cell changed and the call was not a preview.

UPDATES
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

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Group
from rich.text import Text

import pybers
from pybers.cli._common import (
    OutputOption,
    PreviewOption,
    findSaveTarget,
    reportPybersErrors,
    reportWrite,
)
from pybers.cli._formats import FormatOption, OutputFormat, printResult
from pybers.cli._report import formatCount, formatLine


def formatValue(value: pybers.CellValue, kind: pybers.CellKind) -> Text:
    """Return a value and its kind as one report value, `none` for an empty cell."""
    shown = pybers.formatCellValue(value)
    return Text.assemble((shown, "value"), (f" ({kind.value})", "detail"))


def formatChange(change: pybers.CellChange) -> Group:
    """Return the report lines of one cell's change."""
    lines = [
        formatLine("Cell", (str(change.reference), "identifier")),
        formatLine("Before") + formatValue(change.valueBefore, change.kindBefore),
        formatLine("After") + formatValue(change.valueAfter, change.kindAfter),
    ]
    if change.rowsAdded or change.colsAdded:
        lines.append(formatLine(
            "Grown",
            f"{formatCount(change.rowsAdded, 'row')}, "
            f"{formatCount(change.colsAdded, 'column')}",
        ))
    return Group(*lines)


def runSet(
    context: typer.Context,
    documentPath: Annotated[
        Path,
        typer.Argument(
            metavar="FILE", help="The .numbers document.", show_default=False
        ),
    ],
    reference: Annotated[
        str,
        typer.Argument(
            metavar="CELL",
            help="The cell, its table named: `Q3::B4` or `Budget::Q3::B4`.",
            show_default=False,
        ),
    ],
    value: Annotated[
        str,
        typer.Argument(
            metavar="VALUE",
            help=(
                "The value as text: 42, 42 EUR, TRUE, 2026-10-20 09:00, 1h 30m, or any "
                "text."
            ),
            show_default=False,
        ),
    ],
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
    output: OutputOption = None,
    preview: PreviewOption = False,
    extend: Annotated[
        bool,
        typer.Option("--extend", help="Grow the table when CELL lies outside it."),
    ] = False,
    outputFormat: FormatOption = OutputFormat.TEXT,
) -> None:
    """Set one cell's value, its kind inferred from VALUE unless --as names one."""
    target = findSaveTarget(documentPath, output, preview)
    with reportPybersErrors(context):
        document = (
            pybers.open(documentPath) if timeZone is None
            else pybers.open(documentPath, timeZone=timeZone)
        )
        change = document.cellSet(
            reference,
            pybers.parseCellValue(value, kind),
            extend=extend,
            preview=preview,
        )
        if target is not None and change.changed:
            document.save(target)
    printResult(change, outputFormat, formatChange)
    reportWrite(change.changed, target, "the cell already holds that.")


__all__ = ["runSet"]
