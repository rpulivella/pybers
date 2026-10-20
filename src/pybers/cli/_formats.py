#!/usr/bin/env python3
"""\
The formats every command offers, the option that chooses one, and how each is written.

A command passes its result and its own text renderer to `printResult`, and never
builds JSON itself, so `--format` means the same in every command. JSON keys are
the library's own field names, `None` is `null`, and a sentinel is its name, so the
reasons a value is missing survive. Objects stay as the library returned them until
the encoder reaches each one. See `docs/cli-design.md`.

UPDATES
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

import dataclasses
import json
from collections.abc import Callable
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

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


def encodeJsonValue(value: object) -> Any:
    """Return what the JSON encoder writes for a value it cannot write itself."""
    if isinstance(value, sentinel):
        return repr(value)
    # A number as its exact digits, so no float ever stands between the cell and JSON.
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, pybers.CellAddress | pybers.CellReference):
        return str(value)
    if isinstance(value, frozendict):
        return dict(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: getattr(value, field.name)
            for field in dataclasses.fields(value) if field.repr
        }
    raise TypeError(f"pybers has no JSON form for {type(value).__name__}.")


def printResult[T](
    result: T, outputFormat: OutputFormat, renderText: Callable[[T], RenderableType]
) -> None:
    """Print a command's result on stdout in the format asked for."""
    if outputFormat is OutputFormat.JSON:
        text = json.dumps(
            result, default=encodeJsonValue, ensure_ascii=False, indent=2
        )
        console.out(text, highlight=False)
    else:
        console.print(renderText(result))


__all__ = ["FormatOption", "OutputFormat", "encodeJsonValue", "printResult"]
