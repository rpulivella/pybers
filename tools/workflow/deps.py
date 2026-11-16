#!/usr/bin/env python3
"""\
Report what to bump: open Dependabot alerts, and declared packages with a newer release.

The report informs and never blocks, so a finding still exits 0. It exits 2 only
when a question could not be asked, and still answers the other.

Usage:
    .venv/bin/python3 -m tools.workflow.deps report

UPDATES
2026-11-16  Written for PYB-295.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/16"
__usage__ = ".venv/bin/python3 -m tools.workflow.deps <command> [options]"

import argparse
import sys

from rich.console import Console
from rich.markup import escape

from tools.workflow.lib import github
from tools.workflow.lib.dependencies import (
    alertsPageSize,
    readOpenAlerts,
    readOutdatedPackages,
)
from tools.workflow.lib.shared import RichHelpFormatter, errorExitCode

console = Console()


def reportAlerts() -> bool:
    """Print every open Dependabot alert, and return whether they could be read."""
    try:
        alerts = readOpenAlerts(github.resolveToken())
    except RuntimeError as exc:
        console.print(f"[red]Dependabot alerts unread[/]: {escape(str(exc))}")
        return False
    if not alerts:
        console.print("[green]No open Dependabot alerts[/]")
        return True
    # The endpoint pages by a cursor in its headers, which the shared client drops.
    atLeast = "at least " if len(alerts) == alertsPageSize else ""
    console.print(f"[yellow]{atLeast}{len(alerts)} open Dependabot alert(s)[/]")
    for alert in alerts:
        fixedIn = alert.fixedIn or "no fixed release yet"
        console.print(
            f"  {escape(alert.package)} {escape(alert.severity)}, fixed in "
            f"{escape(fixedIn)}, {escape(alert.manifest)}  {escape(alert.url)}"
        )
    return True


def reportOutdated() -> bool:
    """Print each declared package with a newer release, and whether pip answered."""
    try:
        outdated = readOutdatedPackages()
    except RuntimeError as exc:
        console.print(f"[red]Newer releases unread[/]: {escape(str(exc))}")
        return False
    if not outdated:
        console.print("[green]Every declared package is at its newest release[/]")
        return True
    count = len(outdated)
    console.print(f"[yellow]{count} declared package(s) with a newer release[/]")
    for package in outdated:
        console.print(
            f"  {escape(package.name)} {escape(package.installed)} → "
            f"{escape(package.newest)}"
        )
    return True


def runReport(arguments: argparse.Namespace) -> int:
    """Print both reports, each answered even when the other could not be."""
    alertsRead = reportAlerts()
    outdatedRead = reportOutdated()
    return 0 if alertsRead and outdatedRead else errorExitCode


def buildParser() -> argparse.ArgumentParser:
    """Return the command line, one subcommand per handler."""
    parser = argparse.ArgumentParser(
        description="Report what to bump, without blocking anything.",
        formatter_class=RichHelpFormatter,
    )
    subparsers = parser.add_subparsers(required=True)
    report = subparsers.add_parser(
        "report", help="list open Dependabot alerts and declared packages to bump"
    )
    report.set_defaults(handler=runReport)
    return parser


def main() -> int:
    """Parse the command line and dispatch."""
    arguments = buildParser().parse_args()
    return int(arguments.handler(arguments))


if __name__ == "__main__":
    sys.exit(main())
