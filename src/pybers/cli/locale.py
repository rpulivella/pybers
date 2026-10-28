#!/usr/bin/env python3
"""\
`pybers locale`: a document's language and region, and the regions pybers offers.

With no identifier the command reports the document's region and every region
offered, by language. With one it makes one `localeSet` call, and saves only when the
region changed and the call was not a preview.

UPDATES
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
from rich.console import Group
from rich.text import Text

import pybers
from pybers.cli._common import findSaveTarget, reportPybersErrors
from pybers.cli._console import TreeCompact, statusConsole
from pybers.cli._formats import FormatOption, OutputFormat, printResult
from pybers.cli._report import formatCount, formatLine


@dataclass(frozen=True, slots=True)
class LocaleListing:
    """A document's region beside every region pybers offers."""

    localeIdentifier: str | None
    locales: tuple[str, ...]


def formatListing(listing: LocaleListing) -> Group:
    """Return the document's region, then the regions offered, by language."""
    byLanguage: dict[str, list[str]] = {}
    for identifier in listing.locales:
        byLanguage.setdefault(identifier.partition("_")[0], []).append(identifier)
    tree = TreeCompact(
        Text.assemble(
            ("Regions offered: ", "label"),
            (formatCount(len(listing.locales), "region"), "value"),
        ),
        guide_style="label",
    )
    for language, identifiers in byLanguage.items():
        tree.add(Text.assemble(
            (language, "identifier"), (": ", "label"), (", ".join(identifiers), "value")
        ))
    current = listing.localeIdentifier
    return Group(
        formatLine("Locale", (current, "identifier") if current else "none"), tree
    )


def formatChange(change: pybers.LocaleChange) -> Group:
    """Return the report lines of a region change."""
    before = change.localeBefore
    return Group(
        formatLine("Before", (before, "identifier") if before else "none"),
        formatLine("After", (change.localeAfter, "identifier")),
    )


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
    inPlace: Annotated[
        bool, typer.Option("--in-place", help="Write the change into FILE itself.")
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("-o", metavar="NEW", help="Write the changed document to NEW."),
    ] = None,
    preview: Annotated[
        bool, typer.Option("--preview", help="Show the change and write nothing.")
    ] = False,
    outputFormat: FormatOption = OutputFormat.TEXT,
) -> None:
    """Show a document's language and region, or change it to LOCALE."""
    if identifier is None:
        with reportPybersErrors(context):
            document = pybers.open(documentPath)
        listing = LocaleListing(document.localeIdentifier, pybers.locales)
        printResult(listing, outputFormat, formatListing)
        return
    target = findSaveTarget(documentPath, inPlace, output, preview)
    with reportPybersErrors(context):
        document = pybers.open(documentPath)
        change = document.localeSet(identifier, preview=preview)
        if target is not None and not preview and change.changed:
            document.save(target)
    printResult(change, outputFormat, formatChange)
    if preview:
        statusConsole.print(Text("Nothing written: a preview.", "detail"))
    elif not change.changed:
        statusConsole.print(
            Text("Nothing written: the document already uses that region.", "detail")
        )
    elif target is not None:
        statusConsole.print(
            Text.assemble(("Written: ", "label"), (str(target), "value"))
        )


__all__ = ["runLocale"]
