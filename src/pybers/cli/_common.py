#!/usr/bin/env python3
"""\
What every command shares: the root options, and how a pybers error reaches a person.

The root callback stores `CommandSettings` on Typer's context object, which is
how Typer hands a group's options down to its commands.

UPDATES
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


__all__ = ["CommandSettings", "findCommandSettings", "reportPybersErrors"]
