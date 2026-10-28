#!/usr/bin/env python3
"""\
What every command shares: the root options, where a write goes, and how a pybers
error reaches a person.

The root callback stores `CommandSettings` on Typer's context object, which is
how Typer hands a group's options down to its commands.

UPDATES
2026-10-28  Where a write goes, shared by `set` and `locale`, for PYB-272.
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


def findSaveTarget(
    documentPath: Path, inPlace: bool, output: Path | None, preview: bool
) -> Path | None:
    """Return where the document is written, None for a preview, or refuse the flags."""
    if inPlace and output is not None:
        raise typer.BadParameter("Give --in-place or -o, not both.")
    if output is not None and output.exists():
        raise typer.BadParameter(
            f"{output} already exists. Use --in-place to change a document where it "
            "is, or name a new file."
        )
    if inPlace:
        return documentPath
    if output is None and not preview:
        raise typer.BadParameter(
            "Name where the document is written, with --in-place or -o NEW, or show "
            "the change alone with --preview."
        )
    return output


__all__ = [
    "CommandSettings",
    "findCommandSettings",
    "findSaveTarget",
    "reportPybersErrors",
]
