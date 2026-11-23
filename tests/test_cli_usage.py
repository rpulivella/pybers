#!/usr/bin/env python3
"""\
Every command's usage line in POSIX notation, its help drawn by the one renderer, and
SELECTOR completing to the sheets and tables of the document typed before it.

UPDATES
2026-11-23  Written for PYB-304.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/23"

import ast
import re
import shlex
import tomllib
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

import pybers
from pybers.cli._app import PybersGroup, app
from pybers.cli._help import PybersArgument, PybersCommand

repositoryRoot: Path = Path(__file__).resolve().parent.parent
runner: CliRunner = CliRunner()

# A required piece bare and in capitals, an optional one in single brackets.
usagePiece: re.Pattern[str] = re.compile(r"(\[[A-Z][A-Z_-]*\]|[A-Z][A-Z_-]*)(\.\.\.)?")


def listCommands(
    command: click.Command = app, path: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], click.Command]]:
    """Return every command the app registers, the root included, by its path."""
    found = [(path, command)]
    if isinstance(command, click.Group):
        for name, child in sorted(command.commands.items()):
            found += listCommands(child, (*path, name))
    return found


everyCommand: list[tuple[tuple[str, ...], click.Command]] = listCommands()
commandIds: list[str] = [" ".join(("pybers", *path)) for path, _ in everyCommand]


def composeExpectedPiece(argument: click.Argument) -> str:
    """Return an argument as POSIX writes it, `FILE` or `[SELECTOR]`."""
    name = (argument.name or "").upper()
    shown = name if argument.required else f"[{name}]"
    return shown if argument.nargs == 1 else f"{shown}..."


@pytest.mark.parametrize(("path", "command"), everyCommand, ids=commandIds)
def testEveryArgumentIsBareWhenRequiredAndBracketedWhenOptional(
    path: tuple[str, ...], command: click.Command
) -> None:
    context = click.Context(command, info_name="pybers")
    for parameter in command.params:
        if isinstance(parameter, click.Argument):
            assert parameter.get_usage_pieces(context) == [
                composeExpectedPiece(parameter)
            ]


@pytest.mark.parametrize(("path", "command"), everyCommand, ids=commandIds)
def testEveryUsagePieceIsWrittenInPosixNotation(
    path: tuple[str, ...], command: click.Command
) -> None:
    context = click.Context(command, info_name="pybers")
    words = " ".join(command.collect_usage_pieces(context)).split()
    assert [word for word in words if not usagePiece.fullmatch(word)] == []


@pytest.mark.parametrize(("path", "command"), everyCommand, ids=commandIds)
def testNoHelpOrUsageErrorDoublesABracketOrUsesABrace(
    path: tuple[str, ...], command: click.Command
) -> None:
    printed = [
        runner.invoke(app, [*path, "--help"], prog_name="pybers").output,
        runner.invoke(app, list(path), prog_name="pybers").output,
    ]
    assert [each for each in printed if "[[" in each or "{" in each] == []


def testSetPrintsItsUsageInPosixNotation() -> None:
    result = runner.invoke(app, ["set", "--help"], prog_name="pybers")
    assert result.stdout.splitlines()[0] == (
        "Usage: pybers set [OPTIONS] FILE [SELECTOR] [VALUE]"
    )


@pytest.mark.parametrize(("path", "command"), everyCommand, ids=commandIds)
def testEveryCommandDrawsItsHelpThroughTheOneRenderer(
    path: tuple[str, ...], command: click.Command
) -> None:
    assert isinstance(command, PybersCommand | PybersGroup)
    assert all(
        isinstance(each, PybersArgument) and each.help
        for each in command.params if isinstance(each, click.Argument)
    )


@pytest.mark.parametrize(("path", "command"), everyCommand, ids=commandIds)
def testEveryHelpTitlesItsSectionsAlikeWithNoTrailingSpace(
    path: tuple[str, ...], command: click.Command
) -> None:
    result = runner.invoke(app, [*path, "--help"], prog_name="pybers")
    lines = result.stdout.splitlines()
    titles = [line for line in lines if line and not line.startswith((" ", "Usage:"))]
    assert set(titles) <= {"Arguments", "Options", "Commands"}
    assert "Options" in titles
    assert [line for line in lines if line != line.rstrip()] == []


def testNoPartOfPybersDependsOnOrImportsTyper() -> None:
    project = tomllib.loads((repositoryRoot / "pyproject.toml").read_text())["project"]
    declared = [*project["dependencies"]] + [
        each for extra in project["optional-dependencies"].values() for each in extra
    ]
    imported = [
        alias.name
        for path in (repositoryRoot / "src" / "pybers").rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text()))
        for alias in (node.names if isinstance(node, ast.Import) else [])
    ] + [
        node.module or ""
        for path in (repositoryRoot / "src" / "pybers").rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.ImportFrom)
    ]
    assert [each for each in declared if each.startswith("typer")] == []
    assert [each for each in imported if each.split(".")[0] == "typer"] == []


@pytest.fixture
def budgetPath(tmp_path: Path) -> Path:
    """Return a document pybers created, two sheets each holding one table."""
    document = pybers.create("en_US")
    document.sheet().tableAdd("Q3", rows=2, cols=2)
    document.sheetAdd("Budget").tableAdd("Totals", rows=2, cols=2)
    path = tmp_path / "budget.numbers"
    document.save(path)
    return path


def listCompletions(*words: str) -> list[str]:
    """Return what a bash completion offers for the last of the words typed."""
    result = runner.invoke(app, [], prog_name="pybers", env={
        "_PYBERS_COMPLETE": "bash_complete",
        "COMP_WORDS": " ".join(shlex.quote(word) for word in ("pybers", *words)),
        "COMP_CWORD": str(len(words)),
    })
    return [line.split(",", 1)[1] for line in result.stdout.splitlines() if line]


@pytest.mark.parametrize("command", ["show", "set"])
def testASelectorCompletesToTheSheetsAndTablesOfItsFile(
    budgetPath: Path, command: str
) -> None:
    assert listCompletions(command, str(budgetPath), "") == [
        "Sheet 1", "Sheet 1::Q3", "Budget", "Budget::Totals"
    ]


def testASelectorCompletesOnlyWhatStartsWithTheWordTyped(budgetPath: Path) -> None:
    assert listCompletions("show", str(budgetPath), "Bud") == [
        "Budget", "Budget::Totals"
    ]


def testASelectorAfterAFileThatIsNoDocumentCompletesToNothing(tmp_path: Path) -> None:
    assert listCompletions("show", str(tmp_path / "absent.numbers"), "") == []
