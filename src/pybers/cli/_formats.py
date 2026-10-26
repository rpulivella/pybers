#!/usr/bin/env python3
"""\
The formats every command offers, the option that chooses one, and how each is written.

A command passes its result and its own text renderer to `printResult`, and never
builds JSON itself: `--format json` is `pybers.formatJsonForm`, the library's one
serializer, so a command's JSON and a script's are the same text. See
`docs/cli-design.md`.

UPDATES
2026-10-24  JSON written by `pybers.formatJsonForm`, keeping only the choice of
            format here, for PYB-259.
2026-10-20  A date and a duration as the text `pybers set` reads, for PYB-144.
2026-10-20  A Decimal as its exact digits, and a cell's address or reference as
            its text, for PYB-217.
2026-10-12  Written for PYB-187.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/12"

from collections.abc import Callable
from enum import StrEnum
from typing import Annotated

import typer
from rich.console import RenderableType

import pybers
from pybers.cli._console import console


class OutputFormat(StrEnum):
    """A format every command can print its result in."""

    TEXT = "text"
    JSON = "json"


FormatOption = Annotated[
    OutputFormat,
    typer.Option("--format", help="How to print the result.", show_default=True),
]


def printResult[T](
    result: T, outputFormat: OutputFormat, renderText: Callable[[T], RenderableType]
) -> None:
    """Print a command's result on stdout in the format asked for."""
    if outputFormat is OutputFormat.JSON:
        console.out(pybers.formatJsonForm(result), highlight=False)
    else:
        console.print(renderText(result))


__all__ = ["FormatOption", "OutputFormat", "printResult"]
