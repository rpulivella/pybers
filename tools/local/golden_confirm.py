#!/usr/bin/env python3
"""\
pybers golden confirmation tool

Opens a temporary copy of a golden in running Numbers, checks every cell of every
table against what pybers reads from the golden, and writes a report a developer reads
in place of a manual session in Numbers. Backs the /golden-confirm skill (PYB-94).

Everything that needs Accessibility, Screen Recording or control of Numbers happens in
pybersdev-golden-confirm.app, built from tools/local/lib/golden-confirm-helper/ by the
`helper-build` command, so that Terminal holds none of those permissions.

Shells out to `security`, `swiftc`, `codesign` and `open`, the external toolchain the
house rules allow: no Python library signs an app or starts one under its own grants.

Usage:
    .venv/bin/python3 -m tools.local.golden_confirm run 20-sheets-added.numbers
    .venv/bin/python3 -m tools.local.golden_confirm run 20-sheets-added.numbers \
        --preview
    .venv/bin/python3 -m tools.local.golden_confirm damage-check
    .venv/bin/python3 -m tools.local.golden_confirm helper-build
    .venv/bin/python3 -m tools.local.golden_confirm helper-build --identity <hash> \
        --preview
    .venv/bin/python3 -m tools.local.golden_confirm permissions
    .venv/bin/python3 -m tools.local.golden_confirm measure 63b-fill-dragged-down

A run holds `caffeinate` while it drives Numbers, because the screen lock that follows
display sleep stops it.

Each run's helper log is `helper.log` beside its report rather than in workarea/logs/,
so the log is purged with the ticket's folder that holds the run it explains.

Runs on the repository's venv, which holds rich and pybers, and needs the Xcode
command line tools for `helper-build`.

UPDATES
2026-10-23  `--preview` names what was `--dry-run`, as the command-line design does,
            for PYB-156.
2026-10-22  A golden's expected values are generated from it on every run, for
            PYB-255.
2026-10-21  A measurement's deadline grows with its steps, for PYB-219.
2026-10-14  Moved here from `scripts/golden-confirm.py`, and run as a module,
            for PYB-204.
2026-10-13  The repository root, a branch's ticket number and the help formatter
            come from `lib/shared.py`, for PYB-204.
2026-10-13  Quotes each reported value as a code span, and spaces the operators of
            a reported formula, both from `golden_confirm_lib`, for PYB-201.
2026-10-13  Imports pybers before any command runs, for PYB-201.
2026-10-13  Every command it shows runs on the repository's venv, for PYB-201.
2026-10-13  A recipe step can type a value or formula into a cell, and a
            measurement may start from a golden, so Numbers can save what pybers
            wrote, for PYB-139.
2026-09-29  `measure` makes a measurement in Numbers from the recipe beside it, for
            PYB-118.
2026-09-22  Checks a table's size and merges and an empty cell, for PYB-111.
2026-09-21  A check a person makes is QA's rather than a human's, for PYB-17.
2026-09-17  Written for PYB-94.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/17"
__usage__ = ".venv/bin/python3 -m tools.local.golden_confirm <command> [options]"

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from tools.local.lib.golden_confirm import (
    GoldenConfirmError,
    GoldenRun,
    HelperProblem,
    buildHelper,
    checkDamagedCopies,
    checkHelperCanRun,
    checkPermissions,
    confirmGolden,
    findDocument,
    findGolden,
    findSigningIdentity,
    holdDisplayAwake,
    listInspectedCells,
    maxCaptures,
    measurementDirectory,
    readMeasurementRecipe,
    readProblems,
    readTicketKey,
    reportRoot,
    requestHelper,
)

# Internal on purpose: pybers exposes no archives, and round-trip tests share this.
from tools.local.lib.golden_expected import buildExpectedValues
from tools.workflow.lib.shared import (
    RichHelpFormatter,
    repositoryRoot,
)

console: Console = Console()

damageCheckGolden: str = "11-text-written-and-retyped.numbers"
editDeadlineSeconds: float = 300.0
# A custom format step drags and opens menus, and takes up to five seconds.
editStepSeconds: float = 5.0


def runGoldenConfirm(golden: Path, preview: bool) -> GoldenRun:
    """Confirm one golden in running Numbers and return every check it made."""
    ticket = readTicketKey()
    expected = buildExpectedValues(golden)
    sheets = list(dict.fromkeys(table.sheet for table in expected.tables))
    captureCount = len(sheets) + len(listInspectedCells(expected))
    if captureCount > maxCaptures:
        raise GoldenConfirmError(
            f"checking these cells takes {captureCount} screenshots, over the limit of "
            f"{maxCaptures}, since each currency or control is read in the inspector"
        )
    outputDirectory = reportRoot / ticket / golden.stem
    run = GoldenRun(golden, ticket, outputDirectory, captureCount, [])
    if preview:
        return run

    with holdDisplayAwake():
        return confirmGolden(golden, run)


def reportProblems(problems: list[HelperProblem]) -> None:
    """Print each problem with the place a developer fixes it."""
    for problem in problems:
        console.print(f"[red]{escape(problem.kind)}[/]: {escape(problem.detail)}")
        console.print(f"  [dim]{escape(problem.remedy)}[/]")


def runHelperBuild(arguments: argparse.Namespace) -> int:
    """Build, sign and install the helper, or preview that under --preview."""
    identity = findSigningIdentity(arguments.identity)
    build = buildHelper(identity, arguments.preview)
    verb = "installed" if build.installed else "would install"
    console.print(f"[green]{verb}[/] {escape(str(build.bundle))}")
    console.print(f"  signed by {escape(build.identity)}")
    console.print(f"  source hash {escape(build.sourceHash)}")
    return 0


def runPermissions(arguments: argparse.Namespace) -> int:
    """Report whether the helper can run, and what to grant when it cannot."""
    problems = checkPermissions()
    if not problems:
        console.print("[green]the helper holds every permission it needs[/]")
        return 0
    reportProblems(problems)
    return 1


def runMeasure(arguments: argparse.Namespace) -> int:
    """Make one measurement in Numbers from its recipe, refusing to replace one."""
    recipe = readMeasurementRecipe(arguments.name)
    target = measurementDirectory / f"{arguments.name}.numbers"
    if target.exists():
        raise GoldenConfirmError(f"{target.relative_to(repositoryRoot)} already exists")
    sources = [findDocument(stem) for stem in [recipe.base, *recipe.documents]]
    if arguments.preview:
        console.print(f"would make {escape(str(target.relative_to(repositoryRoot)))}")
        for position, source in enumerate(sources):
            console.print(f"  document {position}: {escape(source.name)}")
        console.print(f"  {len(recipe.steps)} steps")
        return 0
    checkHelperCanRun()
    with (
        holdDisplayAwake(),
        tempfile.TemporaryDirectory(prefix="pybers-measure-") as work,
    ):
        copies = []
        for position, source in enumerate(sources):
            copy = Path(work) / f"{position}-{source.name}"
            shutil.copyfile(source, copy)
            copies.append(str(copy))
        saved = Path(work) / target.name
        result = requestHelper({
            "operation": "documentEdit",
            "documentPaths": copies,
            "savedCopyPath": str(saved),
            "steps": recipe.steps,
        }, deadlineSeconds=editDeadlineSeconds + editStepSeconds * len(recipe.steps),
            logPath=Path(work) / "helper.log")
        problems = readProblems(result)
        if problems or not saved.is_file():
            console.print(
                f"[red]stopped after {result.get('stepsDone', 0)} of "
                f"{len(recipe.steps)} steps[/]"
            )
            reportProblems(problems)
            return 1
        shutil.copyfile(saved, target)
    console.print(f"[green]made[/] {escape(str(target.relative_to(repositoryRoot)))} "
                  f"in Numbers {escape(str(result.get('numbersVersion')))}")
    return 0


def runDamageCheck(arguments: argparse.Namespace) -> int:
    """Show that a damaged golden fails the run and names what Numbers did."""
    checks = checkDamagedCopies(findGolden(arguments.golden))
    for check in checks:
        color = "green" if check.status == "passed" else "red"
        subject, detail = escape(check.subject), escape(check.detail)
        console.print(f"[{color}]{check.status}[/] {subject}: {detail}")
    return 0 if all(check.status == "passed" for check in checks) else 1


def runRun(arguments: argparse.Namespace) -> int:
    """Confirm a golden in running Numbers and summarize the report it wrote."""
    golden = findGolden(arguments.golden)
    run = runGoldenConfirm(golden, arguments.preview)
    if arguments.preview:
        console.print(f"[green]would confirm[/] {escape(golden.name)} for {run.ticket}")
        console.print(f"  {run.captureCount} screenshots into "
                      f"{escape(str(run.outputDirectory))}")
        return 0
    reportProblems(run.problems)
    counts = {status: sum(1 for c in run.checks if c.status == status)
              for status in ("passed", "failed", "qa")}
    for check in run.checks:
        if check.status == "failed":
            console.print(
                f"[red]failed[/] {escape(check.subject)}: {escape(check.detail)}"
            )
    console.print(
        f"[green]{counts['passed']} passed[/], [red]{counts['failed']} failed[/], "
        f"[yellow]{counts['qa']} left for QA[/]"
    )
    console.print(f"report: {escape(str(run.outputDirectory / 'report.md'))}")
    return 1 if counts["failed"] or run.problems else 0


def buildParser() -> argparse.ArgumentParser:
    """Describe the command line, one subcommand per handler."""
    parser = argparse.ArgumentParser(
        description="Confirm a golden in running Numbers.",
        formatter_class=RichHelpFormatter,
    )
    commands = parser.add_subparsers(required=True)

    build = commands.add_parser(
        "helper-build", help="build, sign and install pybersdev-golden-confirm.app",
        formatter_class=RichHelpFormatter,
    )
    build.add_argument("--identity", help="signing identity fingerprint or name")
    build.add_argument("--preview", action="store_true", help="resolve and report only")
    build.set_defaults(handler=runHelperBuild)

    permissions = commands.add_parser(
        "permissions", help="report what the helper still needs granted",
        formatter_class=RichHelpFormatter,
    )
    permissions.set_defaults(handler=runPermissions)

    confirm = commands.add_parser(
        "run", help="confirm one golden in running Numbers and write its report",
        formatter_class=RichHelpFormatter,
    )
    confirm.add_argument("golden", help="a .numbers file in tests/golden/")
    confirm.add_argument("--preview", action="store_true",
                         help="check the golden and its expected values, open nothing")
    confirm.set_defaults(handler=runRun)

    measure = commands.add_parser(
        "measure", help="make a measurement in Numbers from the recipe beside it",
        formatter_class=RichHelpFormatter,
    )
    measure.add_argument("name", help="a measurement's name, without an extension")
    measure.add_argument("--preview", action="store_true",
                         help="read the recipe and its documents, open nothing")
    measure.set_defaults(handler=runMeasure)

    damaged = commands.add_parser(
        "damage-check",
        help="open damaged copies of a golden and check that each run fails loudly",
        formatter_class=RichHelpFormatter,
    )
    damaged.add_argument("golden", nargs="?", default=damageCheckGolden,
                         help="a .numbers file in tests/golden/ to damage copies of")
    damaged.set_defaults(handler=runDamageCheck)
    return parser


def main() -> int:
    """Parse the command line and dispatch, reporting failures without a traceback."""
    arguments = buildParser().parse_args()
    try:
        return int(arguments.handler(arguments))
    except GoldenConfirmError as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return 2


if __name__ == "__main__":
    sys.exit(main())
