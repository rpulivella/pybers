#!/usr/bin/env python3
"""\
A cell's printed form: its public fields, a private field shown under its public name.

UPDATES
2026-10-20  Written for PYB-225.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/20"

import re
from decimal import Decimal

import pybers
from conftest import findDocumentPath

privateField: re.Pattern[str] = re.compile(r"\b_\w+=")


def buildCell() -> pybers.Cell:
    """Return a cell holding a number, in a table of its own."""
    cell = pybers.Table(name="Q3", rowCount=3, colCount=3).cell("B2")
    cell.value = Decimal("42")
    return cell


def testAPrintedCellShowsItsValueByItsPublicName() -> None:
    assert re.search(r"\bvalue=Decimal\('42'\)", repr(buildCell()))


def testAPrintedCellShowsNoPrivateField() -> None:
    assert not privateField.search(repr(buildCell()))


def testAPrintedCellShowsItsAddressFormulaAndStyle() -> None:
    printed = repr(buildCell())
    assert "address=CellAddress(row=2, col=2)" in printed
    assert "formula=None" in printed
    assert "style=Style(" in printed


def testNoCellInADocumentPrintsAPrivateField() -> None:
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    printed = [repr(cell) for _, _, cell in document.cellsIterate()]
    assert any("formula=Formula(" in line for line in printed)
    assert not [line for line in printed if privateField.search(line)]
