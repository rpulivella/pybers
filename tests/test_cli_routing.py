#!/usr/bin/env python3
"""\
`pybers FILE` runs `check --names`, and every command is still reached by its name.

UPDATES
2026-10-12  Written for PYB-187.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/12"

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import findDocumentPath
from pybers.cli._app import app

baselinePath: Path = findDocumentPath("00-baseline")
runner: CliRunner = CliRunner()


def testAFileAloneRunsCheckWithNames() -> None:
    result = runner.invoke(app, [str(baselinePath)])
    assert result.exit_code == 0
    assert "Readable: yes" in result.stdout
    assert "└ Table 1: 1 rows, 1 columns" in result.stdout


def testNoArgumentsPrintsTheHelp() -> None:
    result = runner.invoke(app, [])
    assert result.output.rstrip() == runner.invoke(app, ["--help"]).output.rstrip()


def testCheckByNameReachesCheckWithoutNames() -> None:
    result = runner.invoke(app, ["check", str(baselinePath)])
    assert result.exit_code == 0
    assert "Sheets:" not in result.stdout


def testARootOptionBeforeTheFileStillApplies() -> None:
    result = runner.invoke(app, ["--debug", str(baselinePath)])
    assert result.exit_code == 0
    assert "Sheets:" in result.stdout


def testAFileNamedLikeACommandIsReachedThroughItsPath(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copy(baselinePath, tmp_path / "check")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["./check"])
    assert result.exit_code == 0
    assert "Sheets:" in result.stdout


def testAMisspelledCommandIsCheckedAsAFileAndRefused() -> None:
    result = runner.invoke(app, ["chek"])
    assert result.exit_code == 1
    assert "pybers check: chek does not exist." in result.stderr
