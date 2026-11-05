#!/usr/bin/env python3
"""\
`pybers locale`: a document's language and region, or a change to it.

With no identifier the command prints the document's region as `pybers show` prints
it. With one it makes one `localeSet` call, prints the region the same way, and saves
only when the region changed and the call was not a preview.

UPDATES
2026-11-03  The region prints as `show` prints it, before and after a change
            alike, and the regions offered are left to the library, for PYB-223.
2026-10-28  Written for PYB-272.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/28"

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
from pybers.cli._formats import FormatOption, OutputFormat, printResult
from pybers.cli._report import formatLine


@dataclass(frozen=True, slots=True)
class DocumentLocale:
    """A document's language and region, under the key its JSON form gives it."""

    localeIdentifier: str | None


def formatLocale(locale: DocumentLocale) -> Text:
    """Return a document's region as `pybers show` prints it."""
    current = locale.localeIdentifier
    return formatLine("Locale", (current, "identifier") if current else "none")


def runLocale(
    context: typer.Context,
    documentPath: Annotated[
        Path,
        typer.Argument(
            metavar="FILE", help="The .numbers document.", show_default=False
        ),
    ],
    identifier: Annotated[
        str | None,
        typer.Argument(
            metavar="LOCALE",
            help="The language and region to change to, such as de_DE or en_GB.",
            show_default=False,
        ),
    ] = None,
    output: OutputOption = None,
    preview: PreviewOption = False,
    outputFormat: FormatOption = OutputFormat.TEXT,
) -> None:
    """Show a document's language and region, or change it to LOCALE."""
    target = None if identifier is None else findSaveTarget(
        documentPath, output, preview
    )
    with reportPybersErrors(context):
        document = pybers.open(documentPath)
        changed = identifier is not None and document.localeSet(identifier).changed
        if target is not None and changed:
            document.save(target)
    printResult(DocumentLocale(document.localeIdentifier), outputFormat, formatLocale)
    if identifier is not None:
        reportWrite(changed, target, "the document already uses that region.")


__all__ = ["runLocale"]
