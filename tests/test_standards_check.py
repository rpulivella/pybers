#!/usr/bin/env python3
"""\
The prose gate reads a Markdown line in full, whatever code span it holds.

A code span at the start of a line, blanked to spaces, once made the line read as an
indented code block, so the whole sentence escaped every check.

UPDATES
2026-10-13  Imports `lib/standards.py` rather than loading the command, for
            PYB-204.
2026-10-06  Written for PYB-178.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/06"

from pathlib import Path

import pytest

repositoryRoot: Path = Path(__file__).resolve().parent.parent
from tools.workflow.lib import standards  # noqa: E402


def findMessages(text: str) -> list[str]:
    """Return every finding the gate reports for one Markdown text."""
    findings: list = []
    standards.checkFile(Path("sample.md"), findings, text)
    return [finding[3] for finding in findings if finding[0] == "FAIL"]


@pytest.mark.parametrize(
    "line",
    ["`x` is load-bearing here.\n", "`foo/bar/` is load-bearing here.\n"],
    ids=["short span", "path span"],
)
def testALineOpeningWithACodeSpanIsChecked(line: str) -> None:
    assert findMessages(line) != []


def testALineHoldingACodeSpanMidwayIsChecked() -> None:
    assert findMessages("See `a.py`, load-bearing here.\n") != []


@pytest.mark.parametrize(
    "line",
    ["`load-bearing` opens the line.\n", "A span, `load-bearing`, sits midway.\n"],
    ids=["span first", "span midway"],
)
def testTextInsideACodeSpanStaysExempt(line: str) -> None:
    assert findMessages(line) == []


def testAnIndentedCodeBlockStaysExempt() -> None:
    assert findMessages("A paragraph.\n\n    load-bearing in code\n") == []
