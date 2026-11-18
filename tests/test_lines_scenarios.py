#!/usr/bin/env python3
"""\
A table's lines through every edit and a save, and the few lines each consumer writes.

The edits compare the model with itself across a save, since `57-*`, `61-*`, `63e`
and `64-*` already compare each one with what Numbers made of it.

UPDATES
2026-11-18  The table bands its rows too, so every edit keeps its banding, for
            PYB-267.
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

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

import pybers
from conftest import copyDocument
from pybers.cli._app import app

relative = pybers.FormulaReferenceRelocation.PRESERVE_NAMED_CELL


def buildLinedDocument() -> pybers.Document:
    """Return a created document whose table draws borders, its lines and a band."""
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Lines", rows=6, cols=6)
    table.cell("B2").value = Decimal(1)
    document.cellBordersSet(
        "::Lines::B2:C3", pybers.CellBorderPosition.ALL,
        style=pybers.CellBorderStyle.DASHED, width=2,
    )
    table.tableStyleSet(
        tableOutlineTitle=True,
        bandedRows=pybers.TableBand(True, pybers.Color.parse("#ffd60aff")),
    )
    return document


@pytest.mark.parametrize("edit", [
    lambda table: table.rowAdd(2),
    lambda table: table.rowRemove(4),
    lambda table: table.columnAdd(3),
    lambda table: table.columnRemove(5),
    lambda table: table.cellsMove("B2:C3", "D4", references=relative),
    lambda table: table.cellsCopy("B2:C3", "D4", references=relative),
    lambda table: table.cellsFill(
        "B2", "B2:B5", references=relative,
        values=pybers.CellValueFill.REPEAT_SOURCE_VALUE,
    ),
    lambda table: table.mergeAdd("E5:F6"),
], ids=["row added", "row removed", "column added", "column removed", "moved",
        "copied", "filled", "merged"])
def test_every_edit_keeps_a_tables_lines_through_a_save(
    edit: Callable[[pybers.Table], object], tmp_path: Path
) -> None:
    document = buildLinedDocument()
    table = document.table("Lines")
    edit(table)
    expected = {cell.address: cell.borders for cell in table.gridIterate()}
    lines = table.tableStyle
    target = tmp_path / "edited.numbers"
    document.save(target)
    reread = pybers.open(target).table("Lines")
    assert {cell.address: cell.borders for cell in reread.gridIterate()} == expected
    assert reread.tableStyle == lines


def test_a_script_author_draws_a_budgets_lines(tmp_path: Path) -> None:
    document = pybers.open(copyDocument("100-lines-base", tmp_path))
    document.cellBordersSet(
        "::Untouched::B2:C3", pybers.CellBorderPosition.OUTER,
        style=pybers.CellBorderStyle.DASHED, width=1,
    )
    table = document.table("Untouched")
    table.tableStyleSet(pybers.parseTableStyle(
        "body-vertical-gridlines: none; table-outline: 1pt solid black",
        table.tableStyle,
    ))
    document.save()

    reread = pybers.open(tmp_path / "100-lines-base.numbers").table("Untouched")
    assert pybers.formatCellBorders(reread.cell("B2")).startswith(
        "border-top: 1pt dashed"
    )
    assert not reread.tableStyle.bodyVerticalGridlines.visible


def test_a_command_draws_and_reads_a_tables_lines(tmp_path: Path) -> None:
    path = str(copyDocument("100-lines-base", tmp_path))
    runner = CliRunner()

    runner.invoke(app, ["set", path, "::Untouched::B2:C3", "--border", "outer"])
    runner.invoke(app, ["set", path, "*::Untouched",
                        "--table-style", "table-outline: 1pt dashed black"])
    shown = runner.invoke(app, ["show", path, "*::Untouched"]).stdout

    assert "table-outline: 1pt dashed #000000ff" in shown
    assert "border-top: 0.35pt solid #000000ff" in shown
