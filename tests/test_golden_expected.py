#!/usr/bin/env python3
"""\
What a golden should show, generated from the golden, and its comparison with Numbers.

A reading here is a dictionary of the shape the helper returns, so nothing drives
Numbers.

UPDATES
2026-10-22  Written for PYB-255.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/22"

import tomllib
from decimal import Decimal
from pathlib import Path
from typing import Any

import pybers
from conftest import findDocumentPath
from pybers import CellControlSlider, CellFormat, CellKind
from tools.local.lib import golden_confirm as report
from tools.local.lib.golden_expected import (
    ExpectedCell,
    ExpectedTable,
    ExpectedValues,
    buildExpectedValues,
    writeExpectations,
    writeExpectationsToml,
)

goldenDirectory: Path = report.goldenDirectory


def buildGolden(name: str) -> ExpectedValues:
    """Return what one committed golden should show."""
    return buildExpectedValues(goldenDirectory / f"{name}.numbers")


def findCell(expected: ExpectedValues, name: str) -> ExpectedCell:
    """Return one cell of a golden's first table."""
    return next(cell for cell in expected.tables[0].cells if cell.cell == name)


def buildCell(**fields: Any) -> ExpectedCell:
    """Return an expected cell, an automatic number unless a field says otherwise."""
    defaults: dict[str, Any] = {
        "cell": "A1", "kind": CellKind.NUMBER, "value": Decimal(1), "formula": None,
        "format": CellFormat.NUMBER, "formatChosen": False, "control": None,
        "currencyMenu": None, "label": None,
    }
    return ExpectedCell(**(defaults | fields))


def buildReading(grid: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Return a table reading of the helper's shape, every name its own cell's."""
    names = [[pybers.CellReference(row, column).asReference()
              for column in range(1, len(facts) + 1)]
             for row, facts in enumerate(grid, start=1)]
    return {"rowCount": len(grid), "columnCount": len(grid[0]), "cellNames": names,
            "cellFacts": grid}


def buildFact(kind: str = "empty", text: str = "", formula: str | None = None,
              formatKind: str = "automatic") -> dict[str, Any]:
    """Return what AppleScript answers for one cell."""
    return {"value": {"kind": kind, "text": text}, "formula": formula,
            "formatKind": formatKind}


def testEveryFilledCellOfEveryTableIsExpected() -> None:
    expected = buildGolden("12-currency-written-by-pybers")
    document = pybers.open(goldenDirectory / "12-currency-written-by-pybers.numbers")
    filled = sum(1 for sheet in document.sheets for table in sheet.tables
                 for cell in table.cells.values() if cell.value is not None)
    assert sum(len(table.cells) for table in expected.tables) == filled == 8


def testACurrencyAmountNamesTheCurrencyAsTheMenuTitlesIt() -> None:
    cell = findCell(buildGolden("12-currency-written-by-pybers"), "A1")
    assert (cell.kind, cell.currencyMenu) == (CellKind.CURRENCY, "Swiss Franc (CHF)")


def testAMeasuredCellIsLabeledByTheTextBeneathIt() -> None:
    assert findCell(buildGolden("12-currency-written-by-pybers"), "A1").label == "A2"


def testALabelBeneathAnEmptyCellIsLeftItsOwnEntry() -> None:
    expected = buildExpectedValues(findDocumentPath("90-values-for-booleans"))
    assert findCell(expected, "E2").label is None
    assert all(cell.label != "E2" for cell in expected.tables[0].cells)


def testATableNotLaidOutAsAMeasurementHasNoLabels() -> None:
    expected = buildGolden("20-formula-shapes-multisheet-edited")
    assert all(cell.label is None for table in expected.tables for cell in table.cells)


def testASliderIsExpectedWithItsRange() -> None:
    cell = findCell(buildGolden("11-controls-written-by-pybers"), "C1")
    assert cell.control == CellControlSlider(Decimal(1), Decimal(100), Decimal(1))


def testTheMachineFormParsesAsTomlWithEveryCell(tmp_path: Path) -> None:
    expected = buildGolden("11-controls-written-by-pybers")
    written = tomllib.loads(writeExpectationsToml(expected, tmp_path).read_text())
    cells = written["table"][0]["cell"]
    assert len(cells) == len(expected.tables[0].cells)
    slider = next(cell for cell in cells if cell["cell"] == "C1")
    assert slider["control"] == {
        "kind": "slider", "minimum": "1", "maximum": "100", "increment": "1"
    }


def testTheExpectationsFlattenACellAndFoldItsLabel(tmp_path: Path) -> None:
    expected = buildGolden("12-currency-written-by-pybers")
    written = writeExpectations(expected, tmp_path).read_text()
    assert "### A1 · measured\n- value: `99.5`\n- kind: currency\n" in written
    assert "- currency: Swiss Franc (CHF)\n\n### A2 · describes A1\n" in written
    assert "8 filled, every other cell empty" in written
    assert "|" not in written


def testAControlDecidesTheFormatNumbersNames() -> None:
    slider = buildCell(control=CellControlSlider(Decimal(0), Decimal(9), Decimal(1)))
    assert report.findNumbersFormat(slider) == ("slider", "Slider")


def testAFormatNobodyChoseIsAutomatic() -> None:
    assert report.findNumbersFormat(buildCell()) == ("automatic", "Automatic")
    chosen = buildCell(format=CellFormat.PERCENT, formatChosen=True)
    assert report.findNumbersFormat(chosen) == ("percent", "Percentage")


def testOnlyACurrencyOrAControlNeedsTheInspector() -> None:
    assert not report.checkNeedsInspector(buildCell())
    assert report.checkNeedsInspector(buildCell(currencyMenu="Euro (€)"))


def testASliderIsInspectedForItsRange() -> None:
    bounds = CellControlSlider(Decimal(0), Decimal(9), Decimal("0.5"))
    slider = buildCell(control=bounds)
    assert report.listInspectorSettings(slider) == {
        "Data Format": "Slider", "Minimum": "0", "Maximum": "9", "Increment": "0.5"
    }


def buildTable(*cells: ExpectedCell) -> ExpectedTable:
    """Return a one-row table of two columns holding these cells."""
    return ExpectedTable("Sheet 1", "Table 1", 1, 2, (), cells)


def testAGridMatchingWhatPybersReadPassesInOneCheck() -> None:
    table = buildTable(buildCell())
    reading = buildReading([[buildFact("number", "1.0"), buildFact()]])
    checks = report.checkTableGrid(table, reading)
    assert [check.status for check in checks] == ["passed"] * 3
    assert "1 of them filled" in checks[0].detail


def testAValueInACellPybersReadAsEmptyFails() -> None:
    reading = buildReading([[buildFact("number", "1.0"), buildFact("text", "stray")]])
    failed = [check for check in report.checkTableGrid(buildTable(buildCell()), reading)
              if check.status == "failed"]
    assert [(check.subject, check.detail) for check in failed] == [
        ("Sheet 1 / Table 1 / B1", "value text `stray`, expected empty")
    ]


def testAFormatOtherThanTheOneExpectedFails() -> None:
    reading = buildReading([[buildFact("number", "1.0", formatKind="percent"),
                             buildFact()]])
    failed = [check.detail for check in
              report.checkTableGrid(buildTable(buildCell()), reading)
              if check.status == "failed"]
    assert failed == ["format `percent`, expected `automatic`"]


def testAFormulaNumbersDoesNotHoldFails() -> None:
    cell = buildCell(formula="=1+1", value=Decimal(2))
    reading = buildReading([[buildFact("number", "2.0"), buildFact()]])
    failed = [check.detail for check in report.checkTableGrid(buildTable(cell), reading)
              if check.status == "failed"]
    assert failed == ["formula nothing, expected `=1+1`"]


def testARecalculatedFormulaValueIsLeftForAPersonShowingBothSides() -> None:
    cell = buildCell(formula="=SUM(B1:B10)", value=Decimal(56))
    reading = buildReading([[buildFact("number", "0.0", formula="=SUM(B1:B10)"),
                             buildFact()]])
    checks = report.checkTableGrid(buildTable(cell), reading)
    recalculated = "Numbers recalculated it to number `0.0`, where pybers stored `56`"
    assert ("qa", recalculated) in [(check.status, check.detail) for check in checks]
    assert "failed" not in [check.status for check in checks]


def testAnErrorCellIsCheckedByItsFormulaAlone() -> None:
    cell = buildCell(kind=CellKind.ERROR, value=None, formula="=1/0", format=None)
    reading = buildReading([[buildFact("text", "#DIV/0!", formula="=1/0"),
                             buildFact()]])
    checks = report.checkTableGrid(buildTable(cell), reading)
    statuses = [check.status for check in checks]
    assert "failed" not in statuses


def testEachLabeledCellIsLeftForAPersonToCompare() -> None:
    table = buildTable(buildCell(label="A2"),
                       buildCell(cell="A2", kind=CellKind.TEXT, value="one"))
    checks = report.listLabelChecks(table)
    assert [(check.status, check.detail) for check in checks] == [
        ("qa", "matches A2: one")
    ]


def testACellAMergeCoversIsLeftToTheMergeCheck() -> None:
    table = ExpectedTable("Sheet 1", "Table 1", 1, 2, ("A1:B1",), (buildCell(),))
    reading = buildReading([[buildFact("number", "1.0"),
                             buildFact("number", "1.0")]])
    reading["cellNames"] = [["A1", "A1"]]
    statuses = [check.status for check in report.checkTableGrid(table, reading)]
    assert "failed" not in statuses


def testATableOfTextIsNotTakenForALabeledMeasurement() -> None:
    expected = buildGolden("45-merged-by-pybers")
    assert all(cell.label is None for table in expected.tables for cell in table.cells)
