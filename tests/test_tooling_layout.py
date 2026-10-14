#!/usr/bin/env python3
"""\
The tooling's layout: commands in each folder, libraries in its `lib/`, and imports.

Read as source, so nothing here runs a command or reaches GitHub or Numbers.

UPDATES
2026-10-13  Written for PYB-204.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/13"

import ast
import re
from pathlib import Path

import pytest

repositoryRoot: Path = Path(__file__).resolve().parent.parent
toolingFiles: list[Path] = sorted(
    path
    for path in (repositoryRoot / "tools").rglob("*.py")
    if path.name != "__init__.py"
)
# A command, shown without the venv's interpreter, or by a path rather than a module.
shownCommand: re.Pattern[str] = re.compile(
    r"(?<![/\w.])python3? -m tools\.|python3? (?:scripts|tools)/"
)


def readTree(path: Path) -> ast.Module:
    """Return one file's syntax tree."""
    return ast.parse(path.read_text(encoding="utf-8"))


def isCommand(tree: ast.Module) -> bool:
    """Report whether a file runs as a command, which only a `__main__` guard says."""
    return any(
        isinstance(node, ast.If) and "__main__" in ast.unparse(node.test)
        for node in tree.body
    )


@pytest.mark.parametrize("path", toolingFiles, ids=lambda path: path.name)
def testACommandSitsInItsFolderAndALibraryInLib(path: Path) -> None:
    assert isCommand(readTree(path)) != (path.parent.name == "lib")


@pytest.mark.parametrize("path", toolingFiles, ids=lambda path: path.name)
def testNoFunctionImportsAModule(path: Path) -> None:
    late = [
        node.lineno
        for function in ast.walk(readTree(path))
        if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef)
        for node in ast.walk(function)
        if isinstance(node, ast.Import | ast.ImportFrom)
    ]
    assert late == []


@pytest.mark.parametrize("path", toolingFiles, ids=lambda path: path.name)
def testNoScriptDeclaresATypedDict(path: Path) -> None:
    assert "TypedDict" not in path.read_text(encoding="utf-8")


def testNoTestLoadsAHyphenatedCommand() -> None:
    loaders = [
        path.name
        for path in (repositoryRoot / "tests").glob("test_*.py")
        if path.name != Path(__file__).name
        and re.search(
            r"spec_from_file_location|import_module\(\"[^\"]*-",
            path.read_text(encoding="utf-8"),
        )
    ]
    assert loaders == []


def testEveryShownCommandRunsOnTheVenv() -> None:
    shown = [
        f"{path.relative_to(repositoryRoot)}:{number}"
        for path in [
            *toolingFiles,
            *(repositoryRoot / ".claude" / "commands").glob("*.md"),
            *(repositoryRoot / "tools").rglob("README.md"),
            repositoryRoot / "CONTRIBUTING.md",
            repositoryRoot / "CLAUDE.md",
        ]
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if shownCommand.search(line)
    ]
    assert shown == []


@pytest.mark.parametrize(
    "path",
    [path for path in toolingFiles if "workflow" in path.parts],
    ids=lambda path: path.name,
)
def testTheSharedWorkflowImportsNothingLocal(path: Path) -> None:
    imported = [
        node.module or ""
        for node in ast.walk(readTree(path))
        if isinstance(node, ast.ImportFrom)
    ]
    assert not [module for module in imported if module.startswith("tools.local")]
