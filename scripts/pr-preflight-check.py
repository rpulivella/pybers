#!/usr/bin/env python3
"""\
Pull Request Preflight Check

Run every gate this repository has, in one pass, and report all of them. A pull
request should fail on mechanical problems before a human or an agent reads it,
and one run should list everything to fix rather than the first thing.

**Run this with the project venv, not the system interpreter.** That is the
opposite of the other scripts here and it is deliberate: pytest, ruff and mypy
live only in `.venv`, and `pip install -e ".[dev]"` puts rich there too, so one
environment carries all four gates and this script's own output.

Three of the four gates are driven through real interfaces rather than a shell.
`pytest.main()`, `mypy.api.run()` and the standards checker's own functions all
return results. Ruff is the exception: its Python package is a shim exporting
`find_ruff_bin()` and no linting API at all, so the binary is located through
that function and run as a subprocess. Locating it through the package rather
than trusting PATH is what keeps the exception narrow.

**Scope is what the branch changed, not what the working tree changed.** The
standards checker defaults to uncommitted files, which is right for a habit run
before committing and wrong here: a preflight runs after committing, when the
tree is clean, so that default would examine nothing and pass. A green signal
with no evidence behind it is worse than no gate.

UPDATES
2026-09-02  Written for #3.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/02"
__usage__ = "python3 scripts/pr-preflight-check.py [--base BRANCH] [--gate NAME ...]"

import argparse
import contextlib
import importlib
import io
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from rich.console import Console
from rich.markup import escape

try:
    from rich_argparse import RichHelpFormatter
except ImportError:  # rich_argparse is optional, per scripts/README.md
    RichHelpFormatter = argparse.HelpFormatter  # type: ignore[assignment,misc]

console: Console = Console()

# The branch every pull request targets. A repository whose deploy tracks another
# branch passes --base rather than editing this.
defaultBase: str = "develop"

# git is the one sanctioned subprocess in this repository's tooling, because there
# is no Python equivalent worth the dependency. Ruff is the second, for the reason
# the module docstring gives.
gitTimeoutSeconds: int = 30


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


def repositoryRoot() -> Path:
    """Return the repository root, so the script runs from any directory."""
    return Path(__file__).resolve().parent.parent


def changedFiles(base: str) -> list[Path]:
    """Return the files this branch changed relative to `base`, prose ones only.

    `git diff base...HEAD` is the branch's own contribution rather than every
    difference between the two, so a `base` that moved ahead does not drag
    unrelated files in.

    Three questions rather than one, because a branch contributes work that is
    committed and work that is not. Asking only the first leaves the gate vacuous
    before the first commit, which is the same hole the checker's own default has
    after the last one.

    Filtered here rather than left to the standards checker, whose `collectFiles`
    applies its extension filter to a directory and not to explicit paths.
    """
    standards = standardsModule()
    resolved = resolveBase(base)
    found: set[Path] = set()
    for command in (
        ["git", "diff", "--name-only", f"{resolved}...HEAD"],   # committed here
        ["git", "diff", "--name-only", "HEAD"],             # not yet committed
        ["git", "ls-files", "--others", "--exclude-standard"],  # not yet tracked
    ):
        for line in gitLines(command, base).split("\n"):
            candidate = repositoryRoot() / line.strip()
            if line.strip() and candidate.suffix in standards.checkExtensions \
                    and candidate.is_file():
                found.add(candidate)
    return sorted(found)


def resolveBase(base: str) -> str:
    """Return a ref for `base` that this checkout actually has.

    A clone of one branch carries no local `develop`, which is the shape CI checks
    out and the shape a contributor gets from `git clone --branch`. Trying the
    remote-tracking name second costs one command and turns an obscure git error
    into a working gate.

    Refusing when neither resolves is deliberate. Falling back to "check only what
    is uncommitted" would leave the gate quietly examining less than it claims to,
    which is the failure this whole script exists to avoid.
    """
    for candidate in (base, f"origin/{base}"):
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", candidate],
            capture_output=True,
            text=True,
            check=False,
            cwd=repositoryRoot(),
            timeout=gitTimeoutSeconds,
        )
        if completed.returncode == 0:
            return candidate
    raise PreflightError(
        f"neither {base!r} nor 'origin/{base}' is a ref in this checkout, so the "
        "files this branch changed cannot be determined. Fetch it first: a "
        "single-branch or shallow clone does not carry it."
    )


def gitLines(command: list[str], base: str) -> str:
    """Return one git command's output, or raise naming what could not be asked."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            cwd=repositoryRoot(),
            timeout=gitTimeoutSeconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PreflightError(
            f"could not ask git what this branch changed: {exc}"
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise PreflightError(
            f"{' '.join(command)} failed against {base!r}: {detail or 'no message'}"
        )
    return completed.stdout


def standardsModule() -> ModuleType:
    """Return the standards checker as a module.

    `scripts/` carries no `__init__.py` and is an implicit namespace package, and
    the file name has a hyphen, so `import_module` with a string is the only
    spelling that works. It needs no importlib machinery beyond that.
    """
    if str(repositoryRoot()) not in sys.path:
        sys.path.insert(0, str(repositoryRoot()))
    return importlib.import_module("scripts.standards-check")


def runTests() -> GateResult:
    """Run the whole pytest suite in this process and report what it found."""
    import pytest

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = pytest.main(["-q", str(repositoryRoot() / "tests")])
    output = buffer.getvalue().strip()
    lastLine = output.splitlines()[-1] if output else "pytest printed nothing"
    return GateResult("pytest", int(code) == 0, lastLine, output)


def runStandards(base: str) -> GateResult:
    """Check this branch's prose, failing on a FAILURE and never on a WARNING."""
    standards = standardsModule()
    files = changedFiles(base)
    # The checker records a finding as (level, path, line, message).
    warnings: list[str] = []
    findings: list[tuple[str, Path, int, str]] = []
    for path in files:
        standards.checkFile(path, findings)

    # Captured rather than swapping the checker's own console: rich resolves
    # `sys.stdout` on every write, so redirecting is enough and nothing reaches
    # into another module's globals.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = standards.report(findings, files, warnings)

    failures = sum(1 for finding in findings if finding[0] == "FAIL")
    return GateResult(
        "standards",
        code == 0,
        f"{len(files)} file(s) changed on this branch, {failures} failure(s)",
        buffer.getvalue().strip(),
    )


def runRuff() -> GateResult:
    """Run ruff over the whole repository, the one gate that needs a binary."""
    from ruff.__main__ import find_ruff_bin

    binary = find_ruff_bin()
    try:
        completed = subprocess.run(
            [binary, "check", "."],
            capture_output=True,
            text=True,
            check=False,
            cwd=repositoryRoot(),
        )
    except OSError as exc:
        raise PreflightError(f"could not run ruff at {binary}: {exc}") from exc
    output = (completed.stdout or completed.stderr or "").strip()
    lastLine = output.splitlines()[-1] if output else "ruff printed nothing"
    return GateResult("ruff", completed.returncode == 0, lastLine, output)


def runTypes() -> GateResult:
    """Run mypy through its own API over the paths pyproject.toml declares."""
    import mypy.api

    output, errors, status = mypy.api.run([])
    combined = (output + errors).strip()
    lastLine = combined.splitlines()[-1] if combined else "mypy printed nothing"
    return GateResult("mypy", status == 0, lastLine, combined)


# Every gate, in the order a reader most wants them. Named so that --gate can
# select one during development without the others' runtime.
gates: dict[str, Callable[[str], GateResult]] = {
    "pytest": lambda base: runTests(),
    "standards": runStandards,
    "ruff": lambda base: runRuff(),
    "mypy": lambda base: runTypes(),
}


def runGates(names: list[str], base: str) -> list[GateResult]:
    """Run each named gate to completion and return every result.

    No gate may abort the run, which is the whole point: one pass has to list
    everything to fix rather than the first thing. A gate that cannot run at all
    becomes a failing result carrying its own reason.
    """
    results: list[GateResult] = []
    for name in names:
        try:
            results.append(gates[name](base))
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
        prog="pr-preflight-check.py",
        description="Run every pybers gate in one pass and report all of them.",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "--base",
        default=defaultBase,
        help=f"branch this one targets (default: {defaultBase})",
    )
    parser.add_argument(
        "--gate",
        action="append",
        choices=sorted(gates),
        help="run only this gate, repeatable (default: all of them)",
    )
    arguments = parser.parse_args()
    chosen = arguments.gate or ["pytest", "standards", "ruff", "mypy"]
    return report(runGates(chosen, arguments.base))


if __name__ == "__main__":
    raise SystemExit(main())
