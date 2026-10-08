#!/usr/bin/env python3
"""\
The line between the library and its front ends, checked over the source itself.

`pybers.cli` and `pybers.tui` are the front ends, and `pybers/__main__.py` is the
command's second door. No other module prints or imports one, and a front end
reaches the library through `import pybers` alone.

UPDATES
2026-10-07  Written for PYB-169, enforcing the PYB-168 constraint.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/07"

import ast
from pathlib import Path

import pytest

import pybers

pybersDirectory: Path = Path(pybers.__file__).resolve().parent
frontEndPackages: tuple[str, ...] = ("cli", "tui")
machineWritten: tuple[str, ...] = ("_generated", "protos")
frontEndLibraries: tuple[str, ...] = ("typer", "click", "rich", "textual")


def findModulePaths() -> list[Path]:
    """Return every authored module of the package."""
    return [
        path for path in sorted(pybersDirectory.rglob("*.py"))
        if path.relative_to(pybersDirectory).parts[0] not in machineWritten
    ]


def isFrontEnd(path: Path) -> bool:
    """Report whether a module belongs to a front end."""
    parts = path.relative_to(pybersDirectory).parts
    return parts[0] in frontEndPackages or parts == ("__main__.py",)


def listImportedModules(tree: ast.Module) -> list[str]:
    """Return every module a tree imports, a relative one with its leading dots."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
        elif isinstance(node, ast.ImportFrom):
            names.append("." * node.level + (node.module or ""))
    return names


def readTree(path: Path) -> ast.Module:
    """Parse one module."""
    return ast.parse(path.read_text(), filename=str(path))


libraryPaths: list[Path] = [
    path for path in findModulePaths() if not isFrontEnd(path)
]
frontEndPaths: list[Path] = [path for path in findModulePaths() if isFrontEnd(path)]


@pytest.mark.parametrize(
    "path", libraryPaths, ids=lambda path: path.relative_to(pybersDirectory).as_posix()
)
def testALibraryModuleNeverPrints(path: Path) -> None:
    calls = [
        node.lineno for node in ast.walk(readTree(path))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "print"
    ]
    assert calls == []


@pytest.mark.parametrize(
    "path", libraryPaths, ids=lambda path: path.relative_to(pybersDirectory).as_posix()
)
def testALibraryModuleNeverImportsAFrontEnd(path: Path) -> None:
    forbidden = [
        name for name in listImportedModules(readTree(path))
        if name.split(".")[0] in frontEndLibraries
        or any(name.startswith(f"pybers.{package}") for package in frontEndPackages)
    ]
    assert forbidden == []


@pytest.mark.parametrize(
    "path", frontEndPaths, ids=lambda path: path.relative_to(pybersDirectory).as_posix()
)
def testAFrontEndReachesTheLibraryThroughImportPybers(path: Path) -> None:
    reached = [
        name for name in listImportedModules(readTree(path))
        if name.startswith(".")
        or (name.startswith("pybers.")
            and not any(
                name.startswith(f"pybers.{package}") for package in frontEndPackages
            ))
    ]
    assert reached == []


def testTheCommandLineIsAFrontEnd() -> None:
    assert frontEndPaths
