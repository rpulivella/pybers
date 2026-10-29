#!/usr/bin/env python3
"""\
The JSON form of a document and its parts: what it holds, and that it reads back.

UPDATES
2026-10-28  A document's `localeIdentifier` is in its form, for PYB-272.
2026-10-27  A table's `reference` is where it sits, not what it holds, for PYB-260.
2026-10-24  Written for PYB-259.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/24"

import dataclasses
import inspect
import json
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import pytest

import pybers
from conftest import allDocuments, findDocumentPath
from pybers.document._form import DocumentForm, SheetForm
from pybers.interchange._tree import listFormFields
from pybers.table._form import CellForm, TableForm

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"


@cache
def writeForm(path: Path) -> str:
    """Return a document's JSON form, written once per document for every test."""
    return pybers.formatJsonForm(pybers.open(path))


def readTree(text: str) -> Any:
    """Return JSON text as a tree of Decimal numbers, as the user docs read it."""
    return json.loads(text, parse_float=Decimal, parse_int=Decimal)


def findTable(stem: str, sheet: str, table: str) -> pybers.Table:
    """Return one table of a document in the tests."""
    return pybers.open(findDocumentPath(stem)).sheet(sheet).table(table)


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def testEveryDocumentReadsBackEqualFromItsJsonForm(path: Path) -> None:
    assert pybers.parseJsonForm(writeForm(path)) == pybers.open(path)


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def testADocumentWritesTheSameBytesOnEveryRun(path: Path) -> None:
    assert pybers.formatJsonForm(pybers.open(path)) == writeForm(path)


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def testWhatReadsBackWritesTheSameJsonForm(path: Path) -> None:
    written = writeForm(path)
    assert pybers.formatJsonForm(pybers.parseJsonForm(written)) == written


def testTheFormOpensWithItsVersion() -> None:
    text = writeForm(findDocumentPath("20-formula-shapes"))
    assert text.startswith(f'{{\n  "jsonFormVersion": {pybers.jsonFormVersion},\n')


def testASheetReadsBackAsThatSheet() -> None:
    sheet = pybers.open(findDocumentPath("20-formula-shapes")).sheet("Sheet 1")
    text = pybers.formatJsonForm(sheet)
    assert list(readTree(text)) == ["jsonFormVersion", "sheet", "documentTables"]
    assert pybers.parseJsonForm(text) == sheet


def testATableReadsBackAsThatTableAndNamesItsSheet() -> None:
    table = findTable("20-formula-shapes", "Sheet 1", "Table 2")
    text = pybers.formatJsonForm(table)
    assert readTree(text)["sheetName"] == "Sheet 1"
    assert pybers.parseJsonForm(text) == table


def testARangeHoldsOnlyItsCellsAndReadsBackAsThem() -> None:
    table = findTable("20-formula-shapes", "Sheet 1", "Table 2")
    text = pybers.formatJsonForm(table, "B2:C3")
    cells = readTree(text)["table"]["cells"]
    assert {cell["address"] for cell in cells} <= {"B2", "B3", "C2", "C3"}
    readBack = pybers.parseJsonForm(text)
    assert isinstance(readBack, tuple)
    assert readBack == tuple(table.cells[cell.address] for cell in readBack)


def testACellReadsBackAsThatCell() -> None:
    cell = findTable("20-formula-shapes", "Sheet 1", "Table 2").cell("B2")
    text = pybers.formatJsonForm(cell)
    assert readTree(text)["cell"] == "B2"
    assert pybers.parseJsonForm(text) == cell


def testATableOnNoSheetNamesNone() -> None:
    table = pybers.Table(name="Loose", rowCount=1, colCount=1)
    table.cell("A1").value = Decimal("3")
    text = pybers.formatJsonForm(table)
    assert readTree(text)["sheetName"] is None
    assert pybers.formatJsonForm(pybers.parseJsonForm(text)) == text


@pytest.mark.parametrize(("model", "form", "excluded"), [
    # Where a cell sits, or what its owners derive, rather than what it holds.
    (pybers.Cell, CellForm, {"table", "reference", "tableNames", "timeZone",
                             "mergeAnchored"}),
    # Back-pointers and views derived from the declared size and the cells.
    (pybers.Table, TableForm, {"document", "sheet", "extent", "rows", "reference"}),
    (pybers.Sheet, SheetForm, {"document", "tableIdentities"}),
    # A session's time zone, which the file has nowhere to keep, and the currency
    # placement the document's `localeIdentifier` decides.
    (pybers.Document, DocumentForm, {"timeZone", "currencyPattern"}),
])
def testEveryPublicNameOfAnOwnerIsInItsForm(
    model: type, form: type, excluded: set[str]
) -> None:
    public = {each.name for each in dataclasses.fields(model)
              if not each.name.startswith("_")}
    public |= {name for name, member in inspect.getmembers(model)
               if isinstance(member, property) and not name.startswith("_")}
    written = {each.name for each in listFormFields(form)}
    assert excluded <= public
    assert public - excluded <= written


def testACellsKeysRunInTheOrderShowPrintsThem() -> None:
    cell = findTable("20-formula-shapes", "Sheet 1", "Table 2").cell("B2")
    keys = list(readTree(pybers.formatJsonForm(cell))["table"]["cells"][0])
    assert keys[:6] == ["address", "value", "kind", "formulaText", "valueCached",
                        "presentation"]


def testACellCarriesItsFormatWhetherChosenAndItsControlWithEverySetting() -> None:
    document = pybers.open(goldenDirectory / "11-controls-written-by-pybers.numbers")
    cell = document.sheets[0].tables[0].cell("C1")
    tree = readTree(pybers.formatJsonForm(cell))["table"]["cells"][0]
    assert tree["presentation"] == {
        "format": cell.presentation.format, "formatChosen": True,
        "control": {"controlType": "slider", "minimum": Decimal(1),
                    "maximum": Decimal(100), "increment": Decimal(1)},
    }


def testAnUnknownControlIsCarriedByItsInteractionType() -> None:
    control = pybers.CellControlUnknown(9)
    assert readTree(pybers.formatJsonForm(control)) == {
        "controlType": "unknown", "interactionType": Decimal(9)
    }


def testACellOfAnUnknownTypeCarriesItsTypeCode() -> None:
    table = pybers.Table(name="T", rowCount=1, colCount=1)
    table.cell("A1")._stored = dataclasses.replace(
        table.cell("A1")._stored, kind=pybers.CellKind.UNKNOWN, unrecognizedTypeCode=4
    )
    text = pybers.formatJsonForm(table)
    assert readTree(text)["table"]["cells"][0]["unrecognizedTypeCode"] == 4
    assert pybers.parseJsonForm(text) == table


def testAFormulaWhoseTextLosesItsWhitespaceCarriesItsNodes() -> None:
    document = pybers.open(findDocumentPath("70-retirement-template-15-4"))
    cell = next(cell for _, _, cell in document.cellsIterate()
                if cell.formula is not None
                and {32, 33} & {node.nodeType for node in cell.formula.nodes})
    nodes = readTree(pybers.formatJsonForm(cell))["table"]["cells"][0]["formula"]
    assert {32, 33} & {int(node["nodeType"]) for node in nodes["nodes"]}
    readBack = pybers.parseJsonForm(pybers.formatJsonForm(cell))
    assert isinstance(readBack, pybers.Cell) and readBack.formula is not None
    assert [node.raw for node in readBack.formula.nodes] == [
        node.raw for node in cell.formula.nodes
    ]


def testAFormulaItsTextReproducesIsWithheld() -> None:
    cell = findTable("20-formula-shapes", "Sheet 1", "Table 1").cell("A11")
    assert cell.formula is not None
    formula = readTree(pybers.formatJsonForm(cell))["table"]["cells"][0]["formula"]
    assert formula == "WITHHELD"


def testAFormulaNamingAnotherSheetsTableReadsBackFromItsTableAlone() -> None:
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    cell = next(cell for _, _, cell in document.cellsIterate()
                if cell.formulaText is not None and "::" in cell.formulaText
                and not {32, 33} & {node.nodeType for node in cell.formula.nodes})
    text = pybers.formatJsonForm(cell.table)
    readBack = pybers.parseJsonForm(text)
    assert readBack == cell.table
    assert isinstance(readBack, pybers.Table)
    assert readBack.cells[cell.address].formulaText == cell.formulaText


def testEveryPartCarriesTheDocumentsTableDirectory() -> None:
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    tree = readTree(pybers.formatJsonForm(document.sheet("Sheet 1").tables[0]))
    assert [(entry["sheetName"], entry["name"]) for entry in tree["documentTables"]] \
        == [(sheet.name, table.name) for sheet in document.sheets
            for table in sheet.tables]


def testAFormulasValueSaysItIsCached() -> None:
    cell = findTable("20-formula-shapes", "Sheet 1", "Table 1").cell("A11")
    tree = readTree(pybers.formatJsonForm(cell))["table"]["cells"][0]
    assert (tree["valueCached"], tree["formulaText"]) == (True, cell.formulaText)


def testASheetSharingItsNameWithAnotherReadsBackAsItself() -> None:
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    first, second = document.sheets[0], document.sheets[1]
    second.name = first.name
    assert pybers.parseJsonForm(pybers.formatJsonForm(first)) == first
    assert pybers.parseJsonForm(pybers.formatJsonForm(second)) == second
