#!/usr/bin/env python3
"""\
Hold a skill to the steps it declares.

`hook` is what Claude Code's hooks run: it records what a session ran, keeps a turn
going while a declared step is owed, and reminds the next prompt of a step a turn left
owed. `skip` and `abandon` put a decision on the record, and `status` prints what a
session owes.

Usage:
    .venv/bin/python3 -m tools.workflow.steps hook < payload.json
    .venv/bin/python3 -m tools.workflow.steps skip "<step>" [more] --reason "<why>"
    .venv/bin/python3 -m tools.workflow.steps abandon <skill> --reason "<why>"
    .venv/bin/python3 -m tools.workflow.steps status <session>

UPDATES
2026-11-14  Written for PYB-294.
"""

from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/14"
__usage__ = ".venv/bin/python3 -m tools.workflow.steps <command> [options]"

import argparse
import json
import sys
from typing import Any

from rich.console import Console
from rich.markup import escape

from tools.workflow.lib.shared import RichHelpFormatter
from tools.workflow.lib.steps import (
    findBlockReason,
    findOwedSteps,
    readEvents,
    readHookEvents,
    recordEvent,
    replayObligations,
)

console = Console()
# Claude Code reads exit status 2 as a block at Stop, and shows its error elsewhere.
blockingExitCode: int = 2


def runHook(arguments: argparse.Namespace) -> int:
    """Record one hook payload, and block a Stop while a step is owed.

    A failure blocks a Stop with its cause rather than letting the turn end unchecked.
    """
    try:
        payload = json.load(sys.stdin)
    except ValueError as exc:
        sys.stderr.write(f"step ledger: the hook input is not JSON: {exc}\n")
        return blockingExitCode
    try:
        return handleHook(payload)
    except Exception as exc:
        if payload.get("hook_event_name") == "Stop":
            reason = (
                "The step ledger failed, so no step can be confirmed: "
                f"{type(exc).__name__}: {exc}"
            )
            sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
            return 0
        sys.stderr.write(f"step ledger: {type(exc).__name__}: {exc}\n")
        return 1


def handleHook(payload: dict[str, Any]) -> int:
    """Record the payload's events, then answer a Stop or a prompt."""
    sessionId = str(payload.get("session_id", ""))
    if not sessionId:
        return 0
    for item in readHookEvents(payload):
        recordEvent(sessionId, item)
    event = str(payload.get("hook_event_name", ""))
    if event == "Stop":
        reason = findBlockReason(readEvents(sessionId))
        if reason:
            sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    elif event == "UserPromptSubmit":
        owed = findOwedSteps(readEvents(sessionId))
        if owed:
            context = "Steps owed from an earlier turn:\n" + "\n".join(owed)
            sys.stdout.write(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "UserPromptSubmit",
                            "additionalContext": context,
                        }
                    }
                )
            )
    return 0


def runRecord(arguments: argparse.Namespace) -> int:
    """Acknowledge a skip or an abandon, which the hook records from its command."""
    for target in arguments.targets:
        console.print(
            f"[yellow]{arguments.verb}[/] {escape(target)}: {escape(arguments.reason)}"
        )
    return 0


def runStatus(arguments: argparse.Namespace) -> int:
    """Print each skill this session invoked, and what it owes or skipped."""
    for item in replayObligations(readEvents(arguments.session)):
        owed = (
            "abandoned" if item.abandoned else ", ".join(item.owed()) or "nothing owed"
        )
        console.print(f"/{item.skill}: {owed}", markup=False)
        for step, reason in item.skipped.items():
            console.print(f"  skipped {step}: {reason}", markup=False)
    return 0


def buildParser() -> argparse.ArgumentParser:
    """Return the command line, one subcommand per handler."""
    parser = argparse.ArgumentParser(
        description="Hold a skill to the steps it declares.",
        formatter_class=RichHelpFormatter,
    )
    subparsers = parser.add_subparsers(required=True)
    hook = subparsers.add_parser("hook", help="record a hook payload read from stdin")
    hook.set_defaults(handler=runHook)
    for verb, target in (("skip", "the declared step"), ("abandon", "the skill")):
        record = subparsers.add_parser(verb, help=f"record that {target} will not run")
        record.add_argument("targets", nargs="+", help=target)
        record.add_argument(
            "--reason", required=True, help="why, recorded beside the skip"
        )
        record.set_defaults(handler=runRecord, verb=verb)
    status = subparsers.add_parser("status", help="print what a session owes")
    status.add_argument("session", help="the session id")
    status.set_defaults(handler=runStatus)
    return parser


def main() -> int:
    """Parse the command line and dispatch."""
    arguments = buildParser().parse_args()
    return int(arguments.handler(arguments))


if __name__ == "__main__":
    sys.exit(main())
