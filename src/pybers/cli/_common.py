#!/usr/bin/env python3
"""\
What every command shares: the root options, where a write goes, and how a pybers
error reaches a person.

The root callback stores `CommandSettings` on Typer's context object, which is
how Typer hands a group's options down to its commands.

UPDATES
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

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from rich.text import Text

import pybers
from pybers.cli._console import statusConsole


@dataclass(frozen=True, slots=True)
class CommandSettings:
    """The root options, as every command reads them."""

    debug: bool = False


def findCommandSettings(context: typer.Context) -> CommandSettings:
    """Return the root options, or the defaults for a command invoked alone."""
    settings = context.find_object(CommandSettings)
    return settings if settings is not None else CommandSettings()


@contextmanager
def reportPybersErrors(context: typer.Context) -> Generator[None]:
    """Turn a pybers error into one line on stderr and status 1, unless debugging."""
    try:
        yield
    except pybers.PybersError as exc:
        if findCommandSettings(context).debug:
            raise
        statusConsole.print(
            Text.assemble((f"pybers {context.info_name}: ", "failure"), str(exc))
        )
        raise typer.Exit(1) from exc


OutputOption = Annotated[
    Path | None,
    typer.Option(
        "-o", metavar="NEW", help="Write the changed document to NEW, not to FILE."
    ),
]
PreviewOption = Annotated[
    bool, typer.Option("--preview", help="Show the change and write nothing.")
]


def findSaveTarget(
    documentPath: Path, output: Path | None, preview: bool
) -> Path | None:
    """Return where a writing verb writes, None for a preview, or refuse the flags.

    A writing verb changes FILE itself, since the verb is the act. `-o` names a new
    document instead, and never one that exists, whatever it is.
    """
    if preview and output is not None:
        raise typer.BadParameter("Give -o or --preview, not both.")
    if output is not None and output.exists():
        raise typer.BadParameter(
            f"{output} already exists. Name a new file, or leave out -o to change "
            f"{documentPath} itself."
        )
    if preview:
        return None
    return documentPath if output is None else output


def reportWrite(changed: bool, target: Path | None, unchanged: str) -> None:
    """Say on stderr whether a writing verb wrote, and where, or why it did not."""
    if not changed:
        statusConsole.print(Text(f"Nothing written: {unchanged}", "detail"))
    elif target is None:
        statusConsole.print(Text("Nothing written: a preview.", "detail"))
    else:
        statusConsole.print(
            Text.assemble(("Written: ", "label"), (str(target), "value"))
        )


__all__ = [
    "CommandSettings",
    "OutputOption",
    "PreviewOption",
    "findCommandSettings",
    "findSaveTarget",
    "reportPybersErrors",
    "reportWrite",
]
