#!/usr/bin/env python3
"""\
Every command prints through the shared components, never styling text itself.

A command module that builds Rich text or names a style would print a part its own
way, so the layout, the spacing and the color of everything shown would drift apart.

UPDATES
2026-11-24  Written for PYB-315.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"

import ast
from pathlib import Path

import pytest

cliPath: Path = Path(__file__).parent.parent / "src" / "pybers" / "cli"
# The modules that are the components, and the theme and logo they draw with.
componentModules: frozenset[str] = frozenset({
    "_report.py", "_help.py", "_console.py", "_logo.py",
})
commandModules: list[Path] = sorted(
    path for path in cliPath.glob("*.py") if path.name not in componentModules
)


def listStyling(path: Path) -> list[str]:
    """Return each place a module builds Rich text or passes a style, by line."""
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call):
            called = node.func
            name = called.id if isinstance(called, ast.Name) else (
                called.attr if isinstance(called, ast.Attribute) else ""
            )
            if name in {"Text", "assemble"}:
                found.append(f"{path.name}:{node.lineno} builds {name}")
            # A theme style is passed as its name, where a border style is a value.
            found += [
                f"{path.name}:{node.lineno} passes {each.arg}"
                for each in node.keywords
                if each.arg and "style" in each.arg
                and isinstance(each.value, ast.Constant)
                and isinstance(each.value.value, str)
            ]
    return found


@pytest.mark.parametrize("path", commandModules, ids=lambda path: path.name)
def testCommandPrintsOnlyThroughComponents(path: Path) -> None:
    assert listStyling(path) == []
