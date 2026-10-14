#!/usr/bin/env python3
"""\
Pull Request Preflight Check

Run every gate this repository has, in one pass, and report all of them. A pull
request should fail on mechanical problems before a human or an agent reads it,
and one run should list everything to fix rather than the first thing.

**Run this with the project venv, as every script here is run.** pytest, ruff and
mypy live only in `.venv`, and all three are imported before any gate starts, so
the wrong interpreter stops the run at once rather than inside a gate.

Three of the four gates are driven through real interfaces rather than a shell.
`pytest.main()`, `mypy.api.run()` and the standards checker's own functions all
return results. Ruff is the exception: its Python package is a shim exporting
`find_ruff_bin()` and no linting API at all, so the binary is located through
that function and run as a subprocess. Locating it through the package rather
than trusting PATH is what keeps the exception narrow.

**Every gate is repository-wide, so this script asks git nothing.** Ruff checks
the tree, mypy checks the paths pyproject.toml declares, pytest runs the whole
suite, and the standards checker is given its own `--all` scope rather than its
default of whatever git reports as changed. That default serves the habit run
before a commit and fails here twice over: a preflight runs when the tree is
clean, so it would examine nothing and pass, and a clone of a single branch has
no base to diff against. Needing neither is why this runs unchanged in CI on a
default shallow checkout.

UPDATES
2026-10-14  Moved here from `scripts/pr-preflight-check.py`, and run as a module,
            for PYB-204.
2026-10-13  Imports every gate's tool and the standards checks at the top, and
            takes the repository root from `lib/shared.py`, for PYB-204.
2026-09-02  Written for #3. Repository-wide from the start; an early
            branch-scoped draft needed a git base that a shallow CI
            checkout does not carry.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/02"
__usage__ = ".venv/bin/python3 -m tools.workflow.preflight [--gate NAME ...]"

import argparse
import contextlib
import io
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import mypy.api
import pytest
from rich.console import Console
from rich.markup import escape
from ruff.__main__ import find_ruff_bin

from tools.workflow.lib import standards
from tools.workflow.lib.shared import RichHelpFormatter, repositoryRoot

console: Console = Console()


@dataclass(frozen=True)
class GateResult:
    """One gate's verdict, its one-line summary, and everything it printed.

    Frozen because a result is a record of what happened. The output is carried
    rather than printed, so that a gate stays logic and the reporting stays in
    one place, and so that every gate runs before anything is shown.
    """

    name: str
    passed: bool
    summary: str
    output: str


class PreflightError(RuntimeError):
    """A gate that could not be run at all, as distinct from one that failed."""


def runTests() -> GateResult:
    """Run the whole pytest suite in this process and report what it found."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = pytest.main(["-q", "tests"])
    output = buffer.getvalue().strip()
    lastLine = output.splitlines()[-1] if output else "pytest printed nothing"
    return GateResult("pytest", int(code) == 0, lastLine, output)


def runStandards() -> GateResult:
    """Check every prose file in the repository, failing only on a FAILURE.

    A warning here is a heuristic worth reading and not a defect, so it is
    reported and never gates.
    """
    warnings: list[str] = []
    # The checker records a finding as (level, path, line, message).
    findings: list[tuple[str, Path, int, str]] = []
    buffer = io.StringIO()

    # Its own --all scope, so this script inherits the checker's skip rules
    # rather than reimplementing them.
    scope = argparse.Namespace(paths=[], all=True)
    files = standards.collectFiles(scope, warnings)
    for path in files:
        standards.checkFile(path, findings)

    # Captured rather than swapping the checker's own console: rich resolves
    # `sys.stdout` on every write, so redirecting is enough and nothing reaches
    # into another module's globals.
    with contextlib.redirect_stdout(buffer):
        code = standards.report(findings, files, warnings)

    failures = sum(1 for finding in findings if finding[0] == "FAIL")
    return GateResult(
        "standards",
        code == 0,
        f"{len(files)} file(s) checked, {failures} failure(s)",
        buffer.getvalue().strip(),
    )


def runRuff() -> GateResult:
    """Run ruff over the whole repository, the one gate that needs a binary."""
    binary = find_ruff_bin()
    try:
        completed = subprocess.run(
            [binary, "check", "."],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise PreflightError(f"could not run ruff at {binary}: {exc}") from exc
    output = (completed.stdout or completed.stderr or "").strip()
    lastLine = output.splitlines()[-1] if output else "ruff printed nothing"
    return GateResult("ruff", completed.returncode == 0, lastLine, output)


def runTypes() -> GateResult:
    """Run mypy through its own API over the paths pyproject.toml declares."""
    output, errors, status = mypy.api.run([])
    combined = (output + errors).strip()
    lastLine = combined.splitlines()[-1] if combined else "mypy printed nothing"
    return GateResult("mypy", status == 0, lastLine, combined)


# Every gate, in the order a reader most wants them. Named so that --gate can
# select one during development without the others' runtime.
gates: dict[str, Callable[[], GateResult]] = {
    "pytest": runTests,
    "standards": runStandards,
    "ruff": runRuff,
    "mypy": runTypes,
}


def runGates(names: list[str]) -> list[GateResult]:
    """Run each named gate to completion and return every result.

    No gate may abort the run, which is the whole point: one pass has to list
    everything to fix rather than the first thing. A gate that cannot run at all
    becomes a failing result carrying its own reason.
    """
    results: list[GateResult] = []
    for name in names:
        try:
            results.append(gates[name]())
        except PreflightError as exc:
            results.append(GateResult(name, False, "could not run", str(exc)))
    return results


def report(results: list[GateResult]) -> int:
    """Print every gate's verdict and return the exit code.

    Failing gates print their output in full, because the reason to run this
    locally is to fix things without opening a log.
    """
    for result in results:
        mark = "[green]PASS[/]" if result.passed else "[red]FAIL[/]"
        console.print(
            f"{mark} [bold]{escape(result.name)}[/]  {escape(result.summary)}"
        )

    failed = [result for result in results if not result.passed]
    if not failed:
        console.print(f"\n[green]All {len(results)} gate(s) passed.[/]")
        return 0

    for result in failed:
        console.print(f"\n[bold red]{escape(result.name)}[/]")
        console.print(result.output or "(no output)", markup=False, highlight=False)
    console.print(
        f"\n[red]{len(failed)} of {len(results)} gate(s) failed:[/] "
        f"{escape(', '.join(result.name for result in failed))}"
    )
    return 1


def main() -> int:
    """Parse arguments, run the gates, and report."""
    parser = argparse.ArgumentParser(
        description="Run every pybers gate in one pass and report all of them.",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "--gate",
        action="append",
        choices=sorted(gates),
        help="run only this gate, repeatable (default: all of them)",
    )
    arguments = parser.parse_args()
    chosen = arguments.gate or list(gates)

    # Every gate reads configuration relative to the root: mypy and ruff find
    # pyproject.toml there, and the standards checker resolves its own roots.
    # Done once here so that running this from anywhere is one guarantee rather
    # than four separate habits, one of which was already missing.
    with contextlib.chdir(repositoryRoot):
        return report(runGates(chosen))


if __name__ == "__main__":
    raise SystemExit(main())
