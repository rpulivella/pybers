#!/usr/bin/env python3
"""\
pybers locale table

Read each region's formatting symbols from macOS's own ICU, as Numbers reads them, and
report how they differ from the table committed at src/pybers/_generated/locales.py.

**Why macOS is the source.** Numbers writes a document's `TSK.FormattingSymbolsArchive`
from the ICU in `libicucore`, CLDR with Apple's tailoring, so a table read from
anywhere else, Babel's CLDR included, disagrees with Numbers in places. The table is
read once on a Mac and committed, because `pip install pybers` has no macOS to read.
See findings-12-language-and-region.md.

**When to run it.** When macOS's ICU moves to a new CLDR release, and when a new major
version of Numbers ships. Each run is followed by the sweep in Numbers that
findings-12-language-and-region.md records. Nothing is written unless --write is
passed.

Usage:
    .venv/bin/python3 -m tools.local.locales_extract
    .venv/bin/python3 -m tools.local.locales_extract --write
    .venv/bin/python3 -m tools.local.locales_extract --write --preview

Reads the libraries through `ctypes` and runs nothing else. macOS only.

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
__usage__ = ".venv/bin/python3 -m tools.local.locales_extract [options]"

import argparse
import platform
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from tools.local.lib.icudata import Icu, IcuError
from tools.local.lib.localetable import compareTables, readCommitted, renderModule
from tools.workflow.lib.shared import RichHelpFormatter, repositoryRoot

console: Console = Console()

# Committed, so that changing a document's region never needs a local macOS.
generatedPath: Path = repositoryRoot / "src" / "pybers" / "_generated" / "locales.py"


def main() -> int:
    """Parse arguments, read the table, report it, and write it when asked."""
    parser = argparse.ArgumentParser(
        description=(
            "Read each region's formatting symbols from macOS's ICU, and report how "
            "they differ from the committed table."
        ),
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=f"write {generatedPath.relative_to(repositoryRoot)}",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="with --write, print what would be written and write nothing",
    )
    arguments = parser.parse_args()

    macOS = platform.mac_ver()[0]
    if not macOS:
        console.print("[red]The locale table is read from macOS, and this is not.[/]")
        return 1
    try:
        icu = Icu()
        versions = icu.versionsRead()
        table = {each: icu.symbolsCompose(each) for each in icu.localesList()}
    except IcuError as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return 1

    console.print(
        f"macOS {macOS}, ICU {versions.icu}, CLDR {versions.cldr}, CoreFoundation "
        f"{versions.coreFoundation}: {len(table)} regions"
    )
    committed = readCommitted(generatedPath)
    if committed is None:
        console.print(
            f"No table is committed at {generatedPath.relative_to(repositoryRoot)}."
        )
    else:
        comparison = compareTables(table, committed)
        console.print(
            f"Added: {len(comparison.added)}, removed: {len(comparison.removed)}, "
            f"fields changed: {len(comparison.changed)}"
        )
        for identifier, name in comparison.changed:
            console.print(f"  {escape(identifier)} {escape(name)}")

    if not arguments.write:
        console.print(
            "\nRead-only run. Pass --write to update "
            f"{generatedPath.relative_to(repositoryRoot)}."
        )
        return 0

    source = renderModule(table, versions, macOS)
    if arguments.preview:
        console.print("\n[bold]Would write[/]")
        console.print(source, markup=False, highlight=False)
        return 0

    generatedPath.write_text(source)
    console.print(
        f"\n[green]Wrote[/] {escape(str(generatedPath.relative_to(repositoryRoot)))}, "
        f"{len(table)} regions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
