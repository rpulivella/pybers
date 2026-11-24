#!/usr/bin/env python3
"""\
pybers font catalog

Read every face macOS installs, as pybers reads any font file, and report how the faces
differ from the catalog committed at src/pybers/_generated/fonts.py.

**Why macOS is the source.** A document opened on a Mac draws its text with a face that
Mac has, so the catalog lists every face macOS installs, and a script on a server with
none of them still names faces every Mac carries. The catalog is read once on a Mac and
committed, because `pip install pybers` has no macOS to read. See docs/decisions.md.

**When to run it.** When a new major version of macOS ships, which the suite reports
on a Mac by failing `tests/test_font_catalog.py`. Nothing is written unless --write is
passed.

Usage:
    .venv/bin/python3 -m tools.local.fonts_extract
    .venv/bin/python3 -m tools.local.fonts_extract --write
    .venv/bin/python3 -m tools.local.fonts_extract --write --preview

macOS only.

UPDATES
2026-11-24  Written for PYB-315.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"
__usage__ = ".venv/bin/python3 -m tools.local.fonts_extract [options]"

import argparse
import platform
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from tools.local.lib.fonttable import formatModule, readCommitted, readSystemRows
from tools.workflow.lib.shared import RichHelpFormatter, repositoryRoot

console: Console = Console()

# Committed, so that naming a face never needs a local macOS.
generatedPath: Path = repositoryRoot / "src" / "pybers" / "_generated" / "fonts.py"


def main() -> int:
    """Parse arguments, read the faces, report the difference, and write when asked."""
    parser = argparse.ArgumentParser(
        description=(
            "Read every face macOS installs, and report how they differ from the "
            "committed catalog."
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
        console.print("[red]The font catalog is read from macOS, and this is not.[/]")
        return 1
    rows = readSystemRows()
    console.print(f"macOS {macOS}: {len(rows)} faces")
    committed = readCommitted(generatedPath)
    if committed is None:
        console.print(
            f"No catalog is committed at {generatedPath.relative_to(repositoryRoot)}."
        )
    else:
        added = sorted(set(rows) - set(committed))
        removed = sorted(set(committed) - set(rows))
        console.print(f"Added: {len(added)}, removed: {len(removed)}")
        for label, changed in (("+", added), ("-", removed)):
            for row in changed:
                console.print(f"  {label} {escape(repr(row))}")

    if not arguments.write:
        console.print(
            "\nRead-only run. Pass --write to update "
            f"{generatedPath.relative_to(repositoryRoot)}."
        )
        return 0

    source = formatModule(rows, macOS)
    if arguments.preview:
        console.print("\n[bold]Would write[/]")
        console.print(source, markup=False, highlight=False)
        return 0

    generatedPath.write_text(source)
    console.print(
        f"\n[green]Wrote[/] {escape(str(generatedPath.relative_to(repositoryRoot)))}, "
        f"{len(rows)} faces."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
