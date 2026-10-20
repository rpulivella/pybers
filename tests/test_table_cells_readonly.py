#!/usr/bin/env python3
"""\
A table's cells read as a mapping and change only through the table.

UPDATES
2026-10-14  Written for PYB-193.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/14"

from pathlib import Path

import mypy.api
import pytest

import pybers
from conftest import findDocumentPath
from pybers.addressing import CellAddress, CellReference

sourceRoot: Path = Path(__file__).resolve().parent.parent / "src"
mutatingMethods: tuple[str, ...] = ("clear", "pop", "popitem", "setdefault", "update")


def openTable() -> pybers.Table:
    """Return a table read from a document, holding cells at known references."""
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    return document.sheet("Sheet 1").table("Table 1")


def testTheCellsReadAsAMapping() -> None:
    table = openTable()
    first = CellAddress.parse("A1")
    assert table.cells[first] is table.cell("A1")
    assert first in table.cells
    assert len(table.cells) == len(list(table.cells)) > 0


def testAssigningACellThroughCellsIsRefused() -> None:
    table = openTable()
    with pytest.raises(TypeError):
        table.cells[CellReference.parse("A1")] = table.cell("A2")  # type: ignore[index]


def testDeletingACellThroughCellsIsRefused() -> None:
    table = openTable()
    with pytest.raises(TypeError):
        del table.cells[CellReference.parse("A1")]  # type: ignore[attr-defined]


@pytest.mark.parametrize("method", mutatingMethods)
def testCellsOffersNoMethodThatChangesIt(method: str) -> None:
    assert not hasattr(openTable().cells, method)


def testTheTableStillChangesItsOwnCells() -> None:
    table = openTable()
    empty = next(
        reference
        for row in range(1, table.rowCount + 1)
        for col in range(1, table.colCount + 1)
        if (reference := CellAddress(row, col)) not in table.cells
    )
    table.cell(empty)
    assert empty in table.cells


def testMypyRefusesAWriteThroughCells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "write.py"
    script.write_text(
        "import pybers\n"
        "from pybers.addressing import CellReference\n\n\n"
        "def change(table: pybers.Table, cell: pybers.Cell) -> None:\n"
        '    table.cells[CellReference.parse("A1")] = cell\n'
    )
    monkeypatch.setenv("MYPYPATH", str(sourceRoot))
    report, _, status = mypy.api.run([
        str(script), "--follow-imports=silent", "--no-incremental",
        f"--cache-dir={tmp_path / 'cache'}",
    ])
    assert status == 1
    assert "Unsupported target for indexed assignment" in report
