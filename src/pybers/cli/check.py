#!/usr/bin/env python3
"""\
`pybers check FILE`: whether pybers can read a document, what it runs on, and its tree.

The output is meant to be pasted into a public bug report, so it holds nothing from
the document, not even its file name: its sheets and tables show as their kind and
size. `--names` adds the document's own names for the person holding it. Exit status 0
means pybers opened the document, and 1 means it could not, or that the file could not
be checked.

UPDATES
2026-11-23  Declared for Click, for PYB-304.
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-03  Every check shows the sheets and tables as one tree, each unrecognized
            cell badged under its table, `--names` naming them, for PYB-223.
2026-10-27  Report lines and the sheet outline shared with `show`, a size of one
            row reading `1 row`, for PYB-260.
2026-10-12  `--output-format json` prints the same facts, and an uninstalled pybers
            reads unknown, for PYB-187.
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

import click
from rich.console import Group, RenderableType
from rich.text import Text

import pybers
from pybers.cli._common import findCommandSettings, reportPybersErrors
from pybers.cli._console import TreeCompact, statusConsole
from pybers.cli._formats import OutputFormat, outputFormatOption, printResult
from pybers.cli._help import PybersArgument, PybersCommand
from pybers.cli._report import (
    BadgeLevel,
    childIndent,
    formatBadge,
    formatBadgedNode,
    formatCount,
    formatDetail,
    formatHeading,
    formatLine,
    formatTree,
    formatTreeNode,
)


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
) -> tuple[str, BadgeLevel | None]:
    """Return type identifiers with their counts, as a warning when there are any."""
    if counts is pybers.UNDETERMINED:
        return "unknown", None
    if not counts:
        return "none", None
    found = ", ".join(f"{typeId} (x{count})" for typeId, count in counts.items())
    return found, BadgeLevel.WARNING


def formatReadable(failure: pybers.CheckFailure | None) -> list[Text]:
    """Return the lines saying whether pybers read the document, and if not, why."""
    if failure is None:
        return [formatLine("Readable", "yes", BadgeLevel.SUCCESS)]
    reason = failure.errorType
    if failure.message is not pybers.WITHHELD:
        reason = f"{reason}: {failure.message}"
    return [formatLine("Readable", f"no, {reason}", BadgeLevel.FAILURE)] + [
        formatDetail(f"at {frame}", childIndent) for frame in failure.frames
    ]


def chooseName(name: str | pybers.WITHHELD, kind: str) -> str:
    """Return a name, or the kind of thing it names when it is withheld."""
    return name if isinstance(name, str) else kind


def formatSheetTree(sheet: pybers.CheckSheet) -> TreeCompact:
    """Return a sheet as a tree of its tables and sizes, unrecognized cells badged."""
    tree = formatTree(formatTreeNode(chooseName(sheet.name, "Sheet")))
    for table in sheet.tables:
        size = (
            f"{formatCount(table.rowCount, 'row')} × "
            f"{formatCount(table.colCount, 'column')}"
        )
        branch = tree.add(formatTreeNode(chooseName(table.name, "Table"), size))
        for cell in table.unrecognizedCells:
            branch.add(formatBadgedNode(
                cell.address, formatBadge("unrecognized", BadgeLevel.WARNING),
                f"cell type {cell.typeCode}",
            ))
    return tree


def formatSheets(
    sheets: tuple[pybers.CheckSheet, ...] | pybers.UNDETERMINED,
) -> list[RenderableType]:
    """Return the sheets heading, then one tree per sheet holding its tables."""
    if sheets is pybers.UNDETERMINED:
        return [formatLine("Sheets", "unknown")]
    return [formatHeading("Sheets"), *(formatSheetTree(sheet) for sheet in sheets)]


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
            "Untested archive types", *formatTypeCounts(check.untestedArchiveTypes)
        ),
        formatLine(
            "Unrecognized cell types", *formatTypeCounts(check.unrecognizedCellTypes)
        ),
    ]
    shown += formatSheets(check.sheets)
    return Group(*shown)


@click.command("check", cls=PybersCommand)
# Not `readable`, so pybers alone refuses a file, with one message and status.
@click.argument(
    "file", cls=PybersArgument, type=click.Path(path_type=Path, readable=False),
    help="The .numbers document to check.",
)
@click.option(
    "--names", is_flag=True,
    help="Show each sheet's and table's name, and where each unrecognized cell sits, "
    "in output not meant for posting publicly.",
)
@outputFormatOption
@click.pass_context
def runCheck(
    context: click.Context, file: Path, names: bool, outputFormat: OutputFormat
) -> None:
    """Report whether pybers can read a document, and what it is running on."""
    with reportPybersErrors(context), statusConsole.status("") as status:
        check = pybers.checkDocument(file, names=names, onProgress=status.update)
    printResult(check, outputFormat, formatCheck)
    if check.failure is not None:
        if findCommandSettings(context).debug and check.failure.error is not None:
            raise check.failure.error
        raise click.exceptions.Exit(1)


__all__ = ["formatCheck", "runCheck"]
