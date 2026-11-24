#!/usr/bin/env python3
"""\
What every command shares: the root options, where a write goes, how a pybers
error reaches a person, and what a selector completes to.

The root callback stores `CommandSettings` on Click's context object, which is
how Click hands a group's options down to its commands.

UPDATES
2026-11-23  Click rather than Typer, and a selector completes to the sheets and
            tables of the document typed before it, for PYB-304.
2026-11-23  Every message composed by its shape's composer, for PYB-307.
            `composeUsageRefusal` builds a command line's own refusal.
2026-11-17  A report's value is a phrase, `previewing only`, for PYB-266.
2026-10-28  Where a write goes, its two options and its report, shared by `set`
            and `locale`, FILE itself unless `-o` names a new one, for PYB-272.
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

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import click
from click.shell_completion import CompletionItem

import pybers
from pybers.cli._console import statusConsole
from pybers.cli._report import formatDetail, formatLine, formatRefusal


@dataclass(frozen=True, slots=True)
class CommandSettings:
    """The root options, as every command reads them."""

    debug: bool = False


def findCommandSettings(context: click.Context) -> CommandSettings:
    """Return the root options, or the defaults for a command invoked alone."""
    settings = context.find_object(CommandSettings)
    return settings if settings is not None else CommandSettings()


@contextmanager
def reportPybersErrors(context: click.Context) -> Generator[None]:
    """Turn a pybers error into one line on stderr and status 1, unless debugging."""
    try:
        yield
    except pybers.PybersError as exc:
        if findCommandSettings(context).debug:
            raise
        command = str(context.info_name)
        statusConsole.print(formatRefusal(command, formatRefusalText(exc, command)))
        raise click.exceptions.Exit(1) from exc


def formatRefusalText(error: pybers.PybersError, command: str) -> str:
    """Return a refusal as a command shows it, saying where choices it omits are."""
    if not error.choices:
        return str(error)
    pointer = f"`pybers {command} --help` lists every one."
    if error.notDone is None:
        return f"{error} {pointer}"
    notDone = f" {error.notDone}."
    return f"{str(error).removesuffix(notDone)} {pointer}{notDone}"


def composeUsageRefusal(
    place: str, cause: str, fix: str | None = None, notDone: str | None = None
) -> click.BadParameter:
    """Return a command line's own refusal, the one place one is built.

    Shown only at a shell, so its words may specify options and arguments.
    """
    return click.BadParameter(pybers.composeRefusal(place, cause, fix, notDone))


def composeUsageChoiceRefusal(
    given: str, noun: str, choices: Sequence[str], command: str,
    notDone: str | None = None,
) -> click.BadParameter:
    """Return a command line's refusal of a choice, as a library one is shown."""
    refused = pybers.composeChoiceRefusal(
        pybers.PybersError, given, noun, choices, notDone
    )
    return click.BadParameter(formatRefusalText(refused, command))


outputOption = click.option(
    "-o", "output", metavar="NEW", type=click.Path(path_type=Path),
    help="Write the changed document to NEW, not to FILE.",
)
previewOption = click.option(
    "--preview", is_flag=True, help="Show the change and write nothing."
)


def listSelectorCompletions(
    context: click.Context, parameter: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Return the sheets and tables of the document typed as FILE, as selectors."""
    documentPath = context.params.get("file")
    if documentPath is None:
        return []
    try:
        document = pybers.open(documentPath)
    except pybers.PybersError:
        # A FILE that is not yet a document has nothing to offer.
        return []
    selectors = [
        selector
        for sheet in document.sheets
        for selector in (
            str(pybers.SheetReference(sheet.name)),
            *(str(table.reference) for table in sheet.tables),
        )
    ]
    return [CompletionItem(each) for each in selectors if each.startswith(incomplete)]


def findSaveTarget(
    documentPath: Path, output: Path | None, preview: bool
) -> Path | None:
    """Return where a writing verb writes, None for a preview, or refuse the flags.

    A writing verb changes FILE itself, since the verb is the act. `-o` specifies a
    new document instead, and never one that exists, whatever it is.
    """
    if preview and output is not None:
        raise composeUsageRefusal(
            "-o and --preview", "cannot be given together", "Give one of them",
            pybers.nothingWritten,
        )
    if output is not None and output.exists():
        raise composeUsageRefusal(
            f"-o {output}", "specifies a file that exists, and -o writes only a new "
            "one", f"Specify a new path, or leave out -o to change {documentPath} "
            "itself", pybers.nothingWritten,
        )
    if preview:
        return None
    return documentPath if output is None else output


def reportWrite(changed: bool, target: Path | None, unchanged: str) -> None:
    """Say on stderr whether a writing verb wrote, and where, or why it did not."""
    if not changed:
        statusConsole.print(formatDetail(f"Nothing written: {unchanged}"))
    elif target is None:
        statusConsole.print(formatDetail("Nothing written: previewing only"))
    else:
        statusConsole.print(formatLine("Written", str(target)))


__all__ = [
    "CommandSettings",
    "listSelectorCompletions",
    "composeUsageChoiceRefusal",
    "composeUsageRefusal",
    "findCommandSettings",
    "findSaveTarget",
    "formatRefusalText",
    "outputOption",
    "previewOption",
    "reportPybersErrors",
    "reportWrite",
]
