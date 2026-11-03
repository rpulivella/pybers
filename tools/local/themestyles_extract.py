#!/usr/bin/env python3
"""\
pybers theme style table

Read the properties Numbers states on every root style of each type a created theme
holds, valued as the Blank theme of `00-baseline` states them, and report whether the
table committed at src/pybers/_generated/themestyles.py still matches.

**Why the documents are the source.** A root style missing a property Numbers always
states fails the first action that reaches it, so the census reads every fixture and
measurement Numbers made. Nothing is copied: each value is read as plain data, and
pybers composes each style field by field from it. See findings-10-creation.md.

**When to run it.** When a new version of Numbers ships and `00-baseline` is measured
again. `tests/test_theme_styles.py` fails when the committed table and the documents
disagree. Nothing is written unless --write is passed.

Usage:
    .venv/bin/python3 -m tools.local.themestyles_extract
    .venv/bin/python3 -m tools.local.themestyles_extract --write

UPDATES
2026-11-03  Written for PYB-261.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/03"
__usage__ = ".venv/bin/python3 -m tools.local.themestyles_extract [options]"

import argparse

from rich.console import Console

from tools.local.lib.themestyles import buildThemeStyles, modulePath, renderModule
from tools.workflow.lib.shared import RichHelpFormatter, repositoryRoot

console: Console = Console()


def main() -> int:
    """Read the table, report whether the committed one matches, and write if asked."""
    parser = argparse.ArgumentParser(
        description=(
            "Read the properties a created theme's root styles state, and report "
            "whether the committed table matches."
        ),
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=f"write {modulePath.relative_to(repositoryRoot)}",
    )
    arguments = parser.parse_args()
    rendered = renderModule(buildThemeStyles())
    current = modulePath.read_text() if modulePath.is_file() else ""
    if rendered == current:
        console.print("[green]The committed theme style table matches.[/]")
        return 0
    if not arguments.write:
        console.print(
            "[yellow]The committed theme style table differs from the documents.[/] "
            "Run with --write to regenerate it."
        )
        return 1
    modulePath.write_text(rendered)
    console.print(f"[green]wrote[/] {modulePath.relative_to(repositoryRoot)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
