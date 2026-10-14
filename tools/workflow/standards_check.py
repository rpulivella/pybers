#!/usr/bin/env python3
"""\
Standards Check, the command line over `lib/standards.py`.

The checks, their scope and their history live in `tools/workflow/lib/standards.py`,
which the preflight and the tests import.

Usage:
    .venv/bin/python3 -m tools.workflow.standards_check
    .venv/bin/python3 -m tools.workflow.standards_check --all
    .venv/bin/python3 -m tools.workflow.standards_check docs/decisions.md
    .venv/bin/python3 -m tools.workflow.standards_check --text 'draft copy'

UPDATES
2026-10-14  Moved here from `scripts/standards-check.py`, and run as a module,
            for PYB-204.
2026-10-13  Split from its checks, which moved to `lib/standards.py`, for
            PYB-204.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/27"
__usage__ = (
    ".venv/bin/python3 -m tools.workflow.standards_check "
    "[--all | PATH ... | --text STRING]"
)

import argparse
import sys
from pathlib import Path

from tools.workflow.lib.standards import (
    Finding,
    checkExtensions,
    checkFile,
    collectFiles,
    console,
    report,
)


def main() -> int:
    """Parse the scope, run the checks, print the report."""
    parser = argparse.ArgumentParser(
        description="Lint prose and Python house style.",
        epilog="With no arguments, checks git-changed files.")
    parser.add_argument("paths", nargs="*", help="files or directories to check")
    parser.add_argument("--all", action="store_true", help="check the whole tree")
    parser.add_argument("--text", help="lint a raw string instead of files")
    parser.add_argument("--ext", choices=checkExtensions, default=".md",
                        help="which check set --text gets (default: .md)")
    arguments = parser.parse_args()

    findings: list[Finding] = []
    warnings: list[str] = []

    if arguments.text is not None:
        pseudo = Path(f"<text>{arguments.ext}")
        checkFile(pseudo, findings, text=arguments.text)
        return report(findings, [pseudo], warnings)

    files = collectFiles(arguments, warnings)
    if not files:
        console.print("[green]PASS[/], nothing in scope to check.")
        return 0
    for path in files:
        checkFile(path, findings)
    return report(findings, files, warnings)


if __name__ == "__main__":
    sys.exit(main())
