#!/usr/bin/env python3
"""\
`pybers set --border`, the few lines a person or an agent writes to draw borders.

Each test edits a copy of `100-lines-base`, whose `Table 1` is two rows by seven
columns of labeled cells awaiting a border.

UPDATES
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-17  Written for PYB-266.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/17"

from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

import pybers
from conftest import copyDocument, findDocumentPath, listShownFields, readPlainText
from pybers.cli._app import app
from pybers.cli.set import borderPositions, borderStyles

runner: CliRunner = CliRunner()


@pytest.fixture
def working(tmp_path: Path) -> Path:
    """Return a copy of the document, so a write never touches the measurement."""
    return copyDocument("100-lines-base", tmp_path)


def runSetCommand(*arguments: str) -> Result:
    """Return what `pybers set` does with these arguments."""
    return runner.invoke(app, ["set", *arguments])


def readBorders(path: Path, address: str) -> pybers.CellBorders:
    """Return a cell of `Table 1`'s borders, as a fresh read finds them."""
    return pybers.open(path).table("Table 1").cell(address).borders


def testABorderIsDrawnAndEachCellItChangedPrinted(working: Path) -> None:
    result = runSetCommand(
        str(working), "::Table 1::B1", "--border", "outer", "--border-style",
        "dashed", "--border-width", "1pt", "--border-color", "#ff0000ff",
    )
    assert result.exit_code == 0
    fields = listShownFields(result.stdout)
    shown = dict(zip(
        [value for label, value in fields if label == "Cell"],
        [value for label, value in fields if label == "Borders"],
        strict=True,
    ))
    assert shown["Sheet 1::Table 1::B1"] == "border: 1pt dashed #ff0000ff"
    assert shown["Sheet 1::Table 1::A1"] == "border-right: 1pt dashed #ff0000ff"
    assert f"Written: {working}" in result.stderr


def testAStyleGivenAloneDrawsWhatNumbersDraws(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 1::A1", "--border", "outer")
    assert result.exit_code == 0
    measured = pybers.open(findDocumentPath("100b-lines")).table("Table 1")
    assert readBorders(working, "A1").top == measured.cell("A1").borders.top


def testNoneRemovesWhatHiddenStates(working: Path) -> None:
    runSetCommand(str(working), "::Table 1::A1:B1", "--border", "all",
                  "--border-style", "hidden")
    assert "border: hidden" in pybers.formatCellBorders(
        pybers.open(working).table("Table 1").cell("B1")
    )
    runSetCommand(str(working), "::Table 1::A1:B1", "--border", "all",
                  "--border-style", "none")
    assert readBorders(working, "B1") == pybers.CellBorders()


def testAPreviewWritesNothing(working: Path) -> None:
    before = working.read_bytes()
    result = runSetCommand(str(working), "::Table 1::A1", "--border", "all",
                           "--preview")
    assert result.exit_code == 0
    assert working.read_bytes() == before


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--border-style", "dashed"], "describe a --border"),
        (["--border", "outer", "--border-style", "brush"],
         "'brush' is not a border style"),
        (["--border", "outline"], "outline"),
        (["--border", "outer", "--border-width", "thick"], "a length in points"),
        (["--border", "outer", "--border-style", "hidden", "--border-width", "1pt"],
         "takes no width"),
    ],
)
def testABorderPybersCannotDrawIsRefused(
    working: Path, arguments: list[str], message: str
) -> None:
    before = working.read_bytes()
    result = runSetCommand(str(working), "::Table 1::A1", *arguments)
    assert result.exit_code != 0
    assert message in readPlainText(result.output)
    assert working.read_bytes() == before


def testTheCommandsBorderNamesAreTheLibrarys() -> None:
    assert borderPositions == tuple(pybers.CellBorderPosition)
    assert borderStyles == tuple(pybers.CellBorderStyle)
