#!/usr/bin/env python3
"""\
Status messages through the command line: a spinner for a step, a bar for a known
total, each gone once the call finishes, and every outcome and skipped part.

UPDATES
2026-11-24  Written for PYB-319.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"

import io
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rich.console import Console

import pybers
from conftest import copyDocument, renderPlain
from pybers.cli import _console
from pybers.cli._app import app
from pybers.cli._report import composeOutcome, formatSkip

runner: CliRunner = CliRunner()
# What Rich writes to erase the line a transient display drew.
lineErased: str = "\x1b[2K"


@pytest.fixture
def terminal(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Return what a terminal on stderr receives, a spinner and a bar included."""
    received = io.StringIO()
    monkeypatch.setattr(_console, "statusConsole", Console(
        file=received, force_terminal=True, force_interactive=True, width=100,
        theme=_console.theme,
    ))
    return received


@pytest.fixture
def working(tmp_path: Path) -> Path:
    """Return a copy of the document, so a write never touches the fixture."""
    return copyDocument("20-formula-shapes", tmp_path)


def runCommand(*arguments: str | Path) -> Result:
    """Return what `pybers` does with these arguments."""
    return runner.invoke(app, [str(each) for each in arguments])


def testAStepShowsASpinnerAndLeavesNothing(terminal: io.StringIO) -> None:
    with _console.showProgress() as onProgress:
        onProgress(pybers.ProgressStep("reading the catalog…"))
    shown = terminal.getvalue()
    assert "⠋" in shown and "reading the catalog…" in shown
    assert shown.endswith(lineErased)


def testAKnownTotalShowsABarAndLeavesNothing(terminal: io.StringIO) -> None:
    with _console.showProgress() as onProgress:
        onProgress(pybers.ProgressStep("reading the tables…", 2, 5))
    shown = terminal.getvalue()
    assert "━" in shown and "2/5" in shown
    assert shown.endswith(lineErased)


def testShowShowsItsReadAndLeavesOnlyTheResult(
    terminal: io.StringIO, working: Path
) -> None:
    result = runCommand("show", working, "::Table 2::B2")
    assert result.exit_code == 0
    shown = terminal.getvalue()
    assert "unpacking the document…" in shown and "reading the tables…" in shown
    assert shown.endswith(lineErased)
    assert "reading" not in result.stdout


def testSetShowsItsSaveOnATerminal(terminal: io.StringIO, working: Path) -> None:
    result = runCommand("set", working, "::Table 2::B2", "42")
    assert result.exit_code == 0
    assert "saving the document…" in terminal.getvalue()


def testOffATerminalProgressWritesNothing(working: Path) -> None:
    result = runCommand("set", working, "::Table 2::B2", "42")
    assert result.stderr.splitlines() == [f"Written: {working}"]


@pytest.mark.parametrize(("changed", "target", "shown"), [
    (True, Path("budget.numbers"), "Written: budget.numbers"),
    (True, None, "Nothing written: previewing only"),
    (False, Path("budget.numbers"), "Nothing written: already set"),
])
def testAnOutcomeSaysWhetherAWriteWrote(
    changed: bool, target: Path | None, shown: str
) -> None:
    assert renderPlain(composeOutcome(changed, target, "already set")) == f"{shown}\n"


def testASkippedPartPrintsItsPlaceThenItsReason() -> None:
    skip = pybers.PartSkip("Sheet 1::Table 1::A11", "holds a formula")
    assert renderPlain(formatSkip(skip)) == (
        "Skipped: Sheet 1::Table 1::A11  holds a formula\n"
    )


def testSetPrintsACellItSkipped(working: Path) -> None:
    result = runCommand("set", working, "Sheet 1::Table 1::A11", "1")
    assert result.stderr.splitlines() == [
        "Skipped: Sheet 1::Table 1::A11  holds a formula",
        "Nothing written: already set",
    ]


def testShowPrintsAFontFileItSkipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "broken.otf"
    broken.write_text("not a font")
    monkeypatch.setattr(
        "pybers.typeface.typefaces.findMachineFontFiles", lambda: (broken,)
    )
    result = runCommand("show", "typefaces", "Helvetica::Bold")
    assert result.exit_code == 0
    assert result.stderr.splitlines() == [
        f"Skipped: {broken}  is not a font file pybers can read",
    ]
