#!/usr/bin/env python3
"""\
Keep the session dashboard, `workarea/dashboard.md`, in step with the repository.

`sync` rewrites the status line for the ticket in focus and rebuilds the queue's
`› blocked by` notes from GitHub. `focus` names the ticket in focus off its branch, and
`merged` records a ticket that merged. `ticket start`, `pr create`, `pr ready` and `pr
merge` do the same as they change a ticket's stage, and `/dashboard-update` describes
everything a person edits by hand.

Usage:
    .venv/bin/python3 -m tools.workflow.dashboard sync
    .venv/bin/python3 -m tools.workflow.dashboard focus PYB-156
    .venv/bin/python3 -m tools.workflow.dashboard focus none
    .venv/bin/python3 -m tools.workflow.dashboard merged PYB-193 210

UPDATES
2026-10-14  Written for PYB-211.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/14"
__usage__ = ".venv/bin/python3 -m tools.workflow.dashboard <command> [options]"

import argparse
import sys

from rich.console import Console
from rich.markup import escape

from tools.workflow.lib import github
from tools.workflow.lib.dashboard import (
    Dashboard,
    DashboardError,
    readDashboard,
    recordMerge,
    renderBoard,
    updateDashboard,
    writeDashboard,
)
from tools.workflow.lib.shared import RichHelpFormatter, errorExitCode

console = Console()


def saveDashboard(board: Dashboard, dryRun: bool) -> None:
    """Write the dashboard, or print it under `--dry-run`."""
    if dryRun:
        console.print(renderBoard(board), markup=False, highlight=False)
        return
    writeDashboard(board)
    console.print(f"[green]wrote[/] {escape(board.status)}")


def parseTicketKey(value: str) -> str:
    """Return a ticket's key in its one spelling, from any form `ticket` accepts."""
    return github.formatTicketRef(github.parseTicketNumber(value))


def parseFocusKey(value: str) -> str:
    """Return a ticket's key, or '' for `none`, which clears the focus."""
    return "" if value.lower() == "none" else parseTicketKey(value)


def runSync(arguments: argparse.Namespace) -> int:
    """Rewrite the status line for the ticket in focus, and the queue's notes."""
    board = readDashboard()
    updateDashboard(github.resolveToken(), board)
    saveDashboard(board, arguments.dryRun)
    return 0


def runFocus(arguments: argparse.Namespace) -> int:
    """Put a ticket in focus off its branch, or `none` to clear it."""
    board = readDashboard()
    updateDashboard(github.resolveToken(), board, arguments.key)
    saveDashboard(board, arguments.dryRun)
    return 0


def runMerged(arguments: argparse.Namespace) -> int:
    """Record a merged ticket at the top of the recent list."""
    board = readDashboard()
    recordMerge(board, arguments.key, arguments.pullRequest)
    saveDashboard(board, arguments.dryRun)
    return 0


def buildParser() -> argparse.ArgumentParser:
    """Return the command line, one subcommand per handler."""
    parser = argparse.ArgumentParser(
        description="Keep the session dashboard in step with the repository.",
        formatter_class=RichHelpFormatter,
    )
    subparsers = parser.add_subparsers(required=True)
    sync = subparsers.add_parser("sync", help="rewrite the status line and notes")
    sync.set_defaults(handler=runSync)
    focus = subparsers.add_parser("focus", help="name the ticket in focus")
    focus.add_argument(
        "key", type=parseFocusKey, help="the ticket, such as PYB-156, or none"
    )
    focus.set_defaults(handler=runFocus)
    merged = subparsers.add_parser("merged", help="record a ticket that merged")
    merged.add_argument("key", type=parseTicketKey, help="the ticket, such as PYB-193")
    merged.add_argument("pullRequest", type=int, help="its pull request's number")
    merged.set_defaults(handler=runMerged)
    for command in (sync, focus, merged):
        command.add_argument("--dry-run", dest="dryRun", action="store_true")
    return parser


def main() -> int:
    """Parse the command line and dispatch, reporting failures without a traceback."""
    arguments = buildParser().parse_args()
    try:
        return int(arguments.handler(arguments))
    except (DashboardError, RuntimeError) as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return errorExitCode


if __name__ == "__main__":
    sys.exit(main())
