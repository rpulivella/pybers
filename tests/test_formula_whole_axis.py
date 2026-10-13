#!/usr/bin/env python3
"""\
Ranges reaching every row or every column, and TRUE and FALSE typed bare.

Numbers stores an unbounded range axis as an absolute line past any table with no
end, and a bare TRUE as a boolean node rather than a call. Both were measured by
typing each formula into Numbers, in `71-whole-axis-ranges-and-booleans`.

UPDATES
2026-10-13  Each node compares with no field set aside, for PYB-200.
2026-10-13  Written for PYB-139.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/13"

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from conftest import findDocumentPath, readDataListBytes
from pybers._generated import TSCEArchives_pb2 as tsce
from pybers.addressing import CellReference
from pybers.formula._write import encodeFormulaNode
from pybers.formula.functions import findFunctionIndex
from pybers.formula.nodes import (
    FormulaFunctionCall,
    FormulaNode,
    FormulaRange,
    booleanNodeType,
    numberNodeType,
)
from pybers.formula.parse import parseFormula

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"
goldenName: str = "20-whole-axis-ranges-and-booleans-by-pybers.numbers"
measurementStem: str = "71-whole-axis-ranges-and-booleans"

# What was typed into `Sheet 1 / Table 2`, as pybers renders it back: `Table 1` is
# named with its sheet because `Sheet 2` holds a `Table 1` as well.
typedFormulas: tuple[tuple[str, str], ...] = (
    ("B1", "=SUM(C:D)"),
    ("B2", "=SUM(5:6)"),
    ("B3", "=SUM(Sheet 1::Table 1::B:C)"),
    ("B4", "=SUM(Sheet 1::Table 1::2:3)"),
    ("B5", "=TRUE"),
    ("B6", "=IF(FALSE,1,2)"),
    ("B7", "=SUM(Sheet 1::Table 1::$B:$C)"),
    ("B8", "=SUM(Sheet 1::Table 1::$2:$3)"),
)

# What Numbers 15.4 calculated for each when it saved the measurement.
calculatedByNumbers: dict[str, Decimal | bool] = {
    "B1": Decimal("0"), "B2": Decimal("2"), "B3": Decimal("96"),
    "B4": Decimal("5"), "B5": True, "B6": Decimal("2"),
    "B7": Decimal("96"), "B8": Decimal("5"),
}


def openMeasuredTable() -> tuple[pybers.Document, pybers.Table]:
    """Return the measurement and the table Numbers typed the formulas into."""
    document = pybers.open(findDocumentPath(measurementStem))
    return document, document.sheet("Sheet 1").table("Table 2")


def readStoredNode(node: FormulaNode) -> tsce.ASTNodeArrayArchive.ASTNodeArchive:
    """Return a node exactly as Numbers stored it."""
    stored = tsce.ASTNodeArrayArchive.ASTNodeArchive()
    stored.ParseFromString(node.raw)
    return stored


def authorTypedFormulas(working: Path) -> None:
    """Write the measured formulas into `Sheet 1 / Table 2` of a copy, by text."""
    document = pybers.open(working)
    table = document.sheet("Sheet 1").table("Table 2")
    for address, text in typedFormulas:
        table.cell(address).formulaText = text
    document.save()


def testNumbersOwnFormulasRenderAsTheyWereTyped() -> None:
    _, table = openMeasuredTable()
    assert {
        address: table.cell(address).formulaText for address, _ in typedFormulas
    } == dict(typedFormulas)


def testAnUnboundedAxisReadsAsNone() -> None:
    _, table = openMeasuredTable()
    columnFormula, rowFormula = table.cell("B1").formula, table.cell("B2").formula
    assert columnFormula is not None and rowFormula is not None
    column, row = next(iter(columnFormula)).content, next(iter(rowFormula)).content
    assert isinstance(column, FormulaRange) and isinstance(row, FormulaRange)
    assert (column.rows, row.columns) == (None, None)


@pytest.mark.parametrize(("address", "text"), typedFormulas)
def testEachFormulaEncodesAsNumbersStoredIt(address: str, text: str) -> None:
    document, table = openMeasuredTable()
    cell = table.cell(address)
    stored = cell.formula
    assert stored is not None
    parsed = parseFormula(text, cell.reference, tables=document.tableIdentities)
    assert [encodeFormulaNode(node) for node in parsed] == [
        readStoredNode(node) for node in stored
    ]


def testNumbersCalculatedEachFormula() -> None:
    _, table = openMeasuredTable()
    assert {
        address: table.cell(address).value for address, _ in typedFormulas
    } == calculatedByNumbers


def testATemplatesWholeColumnLookupRenders() -> None:
    document = pybers.open(findDocumentPath("70-retirement-template-15-4"))
    table = document.sheet("Retirement").table("Retirement Goals")
    assert table.cell("C1").formulaText == "=VLOOKUP(Life Plans::B1,Data::B:E,4,FALSE)"


def testTrueWithBracketsStaysACall() -> None:
    [node] = list(parseFormula("=TRUE()", CellReference.parse("A1")))
    assert node.content == FormulaFunctionCall(findFunctionIndex("TRUE"), 0)


@pytest.mark.parametrize(("text", "literal"), [("=true", True), ("=False", False)])
def testABooleanLiteralIgnoresCase(text: str, literal: bool) -> None:
    [node] = list(parseFormula(text, CellReference.parse("A1")))
    assert (node.nodeType, node.content) == (booleanNodeType, literal)


def testABareNumberStaysANumber() -> None:
    [node] = list(parseFormula("=5", CellReference.parse("A1")))
    assert (node.nodeType, node.content) == (numberNodeType, Decimal("5"))


def testTheTypedFormulasMatchTheirGoldenFile(tmp_path: Path) -> None:
    working = Path(
        shutil.copy(findDocumentPath("20-formula-shapes"), tmp_path / "20.numbers")
    )
    authorTypedFormulas(working)
    assert readDataListBytes(goldenDirectory / goldenName) == readDataListBytes(working)


def testTheGoldenHoldsEveryTypedFormula() -> None:
    document = pybers.open(goldenDirectory / goldenName)
    table = document.sheet("Sheet 1").table("Table 2")
    assert {
        address: table.cell(address).formulaText for address, _ in typedFormulas
    } == dict(typedFormulas)
