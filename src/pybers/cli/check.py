#!/usr/bin/env python3
"""\
`pybers check FILE`: whether pybers can read a document, and what it runs on.

The output is meant to be pasted into a public bug report, so it holds nothing
from the document, not even its file name. `--names` adds the document's own
names for the person holding it. Exit status 0 means
pybers opened the document, and 1 means it could not, or that the file could not
be checked.

UPDATES
2026-10-12  `--format json` prints the same facts, and an uninstalled pybers reads
            unknown, for PYB-187.
2026-10-12  A part a check could not determine reads unknown, for PYB-190.
2026-10-11  Type counts arrive as frozendict, for PYB-189.
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

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Group, RenderableType
from rich.text import Text

import pybers
from pybers.cli._common import findCommandSettings, reportPybersErrors
from pybers.cli._console import TreeCompact, statusConsole
from pybers.cli._formats import FormatOption, OutputFormat, printResult


def formatLine(label: str, *value: str | tuple[str, str]) -> Text:
    """Return `label: value`, the label dimmed and a bare string as a bold value."""
    parts = [(part, "value") if isinstance(part, str) else part for part in value]
    return Text.assemble((f"{label}: ", "label"), *parts)


def formatPybersVersion(found: str | pybers.UNDETERMINED) -> str:
    """Return the pybers version, which an uninstalled pybers cannot determine."""
    return "unknown" if found is pybers.UNDETERMINED else found


def formatNumbersVersion(
    found: pybers.NumbersVersion | pybers.UNDETERMINED | None,
) -> str:
    """Return a Numbers version as `Numbers 15.3.1 (build 7050.1.1-2)`."""
    if found is None:
        return "none"
    if found is pybers.UNDETERMINED:
        return "unknown"
    return f"Numbers {found.version} (build {found.build})"


def formatTypeCounts(
    counts: frozendict[int, int] | pybers.UNDETERMINED,
) -> str | tuple[str, str]:
    """Return type identifiers with their counts, as a warning when there are any."""
    if counts is pybers.UNDETERMINED:
        return "unknown"
    if not counts:
        return "none"
    found = ", ".join(f"{typeId} (x{count})" for typeId, count in counts.items())
    return (found, "warning")


def formatReadable(failure: pybers.CheckFailure | None) -> list[Text]:
    """Return the lines saying whether pybers read the document, and if not, why."""
    if failure is None:
        return [formatLine("Readable", ("yes", "success"))]
    reason = failure.errorType
    if failure.message is not pybers.WITHHELD:
        reason = f"{reason}: {failure.message}"
    return [formatLine("Readable", (f"no, {reason}", "failure"))] + [
        Text(f"  at {frame}", "detail") for frame in failure.frames
    ]


def formatTable(table: pybers.CheckTable) -> Text:
    """Return a table as `name: 10 rows, 7 columns`."""
    return Text.assemble(
        (table.name, "value"),
        (": ", "label"),
        (f"{table.rowCount} rows, {table.colCount} columns", "value"),
    )


def formatSheets(
    sheets: tuple[pybers.CheckSheet, ...] | pybers.UNDETERMINED,
) -> list[RenderableType]:
    """Return the sheets heading, then one tree per sheet holding its tables."""
    if sheets is pybers.UNDETERMINED:
        return [formatLine("Sheets", "unknown")]
    shown: list[RenderableType] = [Text("Sheets:", "label")]
    for sheet in sheets:
        tree = TreeCompact(Text(sheet.name, "value"), guide_style="label")
        for table in sheet.tables:
            tree.add(formatTable(table))
        shown.append(tree)
    return shown


def formatUnrecognizedCells(
    cells: tuple[pybers.CheckCell, ...] | pybers.UNDETERMINED,
) -> list[RenderableType]:
    """Return the unrecognized cells heading, then a tree per sheet down to each."""
    if cells is pybers.UNDETERMINED:
        return [formatLine("Unrecognized cells", "unknown")]
    if not cells:
        return [formatLine("Unrecognized cells", "none")]
    grouped: dict[str, dict[str, list[pybers.CheckCell]]] = {}
    for cell in cells:
        byTable = grouped.setdefault(cell.sheetName, {})
        byTable.setdefault(cell.tableName, []).append(cell)
    shown: list[RenderableType] = [Text("Unrecognized cells:", "label")]
    for sheetName, tables in grouped.items():
        tree = TreeCompact(Text(sheetName, "value"), guide_style="label")
        for tableName, tableCells in tables.items():
            branch = tree.add(Text(tableName, "value"))
            for cell in tableCells:
                branch.add(Text.assemble(
                    (cell.address, "identifier"),
                    (": ", "label"),
                    (f"cell type {cell.typeCode}", "warning"),
                ))
        shown.append(tree)
    return shown


def formatCheck(check: pybers.Check) -> Group:
    """Return a check as the lines a bug report pastes."""
    environment = check.environment
    shown: list[RenderableType] = [
        formatLine("pybers", formatPybersVersion(environment.pybersVersion)),
        formatLine("Python", environment.pythonVersion),
        formatLine("protobuf", environment.protobufVersion),
        formatLine("OS", environment.operatingSystem),
        formatLine("Saved with", formatNumbersVersion(check.savedBy)),
        *formatReadable(check.failure),
        formatLine(
            "Untested archive types", formatTypeCounts(check.untestedArchiveTypes)
        ),
        formatLine(
            "Unrecognized cell types", formatTypeCounts(check.unrecognizedCellTypes)
        ),
    ]
    if check.names is not pybers.NOT_REQUESTED:
        shown += formatSheets(check.names.sheets)
        shown += formatUnrecognizedCells(check.names.unrecognizedCells)
    return Group(*shown)


def runCheck(
    context: typer.Context,
    documentPath: Annotated[
        Path,
        # Not `readable`, so pybers alone refuses a file, with one message and status.
        typer.Argument(
            metavar="FILE",
            help="The .numbers document to check.",
            readable=False,
            show_default=False,
        ),
    ],
    names: Annotated[
        bool,
        typer.Option(
            "--names",
            help="Add sheet and table names and where each unrecognized cell sits. "
            "Not for posting publicly.",
        ),
    ] = False,
    outputFormat: FormatOption = OutputFormat.TEXT,
) -> None:
    """Report whether pybers can read a document, and what it is running on."""
    with reportPybersErrors(context), statusConsole.status("") as status:
        check = pybers.checkDocument(
            documentPath, names=names, onProgress=status.update
        )
    printResult(check, outputFormat, formatCheck)
    if check.failure is not None:
        if findCommandSettings(context).debug and check.failure.error is not None:
            raise check.failure.error
        raise typer.Exit(1)


__all__ = ["formatCheck", "runCheck"]
