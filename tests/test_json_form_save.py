#!/usr/bin/env python3
"""\
A document read from its JSON form saves as a created document holding what the form
describes, or is refused, naming what pybers cannot yet create.

UPDATES
2026-11-03  Written for PYB-261.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/03"

from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from conftest import findDocumentPath
from pybers.absence import UNDETERMINED
from pybers.interchange import formatJsonForm, parseJsonForm
from pybers.table._form import CellForm, buildCellForm
from pybers.table._records import refuseUncreatableCell

testsRoot: Path = Path(__file__).resolve().parent
numbersDocuments: list[Path] = sorted(
    [*(testsRoot / folder).glob("*.numbers") for folder in ("fixtures", "measurements")]
)


def saveCreated(tmp_path: Path) -> Path:
    """Return a created document holding values and a formula across two sheets."""
    document = pybers.create("en_US")
    document.sheet(1).tableAdd("Inputs", 2, 2).cell("A1").value = Decimal("5")
    calc = document.sheetAdd("Second").tableAdd("Calc", 2, 2)
    calc.cell("A1").formulaText = "=Inputs::A1*2"
    calc.cell("B1").value = "text"
    path = tmp_path / "created.numbers"
    document.save(path)
    return path


def testADocumentFromItsJsonFormSavesAsTheFormDescribes(tmp_path: Path) -> None:
    text = formatJsonForm(pybers.open(saveCreated(tmp_path)))
    path = tmp_path / "from-json.numbers"

    document = parseJsonForm(text)
    assert isinstance(document, pybers.Document)
    document.save(path)

    assert formatJsonForm(pybers.open(path)) == text


def testAMeasurementSavedThroughItsJsonFormKeepsEveryCell(tmp_path: Path) -> None:
    source = pybers.open(findDocumentPath("20-formula-shapes"))
    path = tmp_path / "from-json.numbers"

    document = parseJsonForm(formatJsonForm(source))
    assert isinstance(document, pybers.Document)
    document.save(path)

    reopened = pybers.open(path)
    assert [sheet.name for sheet in reopened.sheets] == [
        sheet.name for sheet in source.sheets
    ]
    for sheet, original in zip(reopened.sheets, source.sheets, strict=True):
        for table, before in zip(sheet.tables, original.tables, strict=True):
            assert table.identifier == before.identifier
            written = {at: cell.formulaText for at, cell in table.cells.items()}
            assert written == {
                address: cell.formulaText for address, cell in before.cells.items()
                if cell.value is not None or cell.formula is not None
            }


def findCellLoss(held: CellForm, written: CellForm | None) -> str | None:
    """Return what a cell lost on the way through its JSON form and a save, or None.

    A formula's result and its format are Numbers' to calculate, and a format the
    model had yet to determine is not lost.
    """
    holds = (held.formulaText, held.value, held.presentation.format,
             held.presentation.control)
    if written is None:
        return None if holds == (None, None, None, None) else "the cell"
    if held.formulaText != written.formulaText:
        return "its formula"
    if held.formulaText is None and (
        (held.kind, held.value) != (written.kind, written.value)
    ):
        return "its value"
    if held.presentation.control != written.presentation.control:
        return "its control"
    asked = held.presentation.format
    if held.formulaText is None and asked is not UNDETERMINED and (
        asked != written.presentation.format
    ):
        return "its format"
    return None


@pytest.mark.parametrize("path", numbersDocuments, ids=lambda path: path.stem)
def testEveryDocumentSavedThroughItsJsonFormKeepsEveryCellOrIsRefused(
    path: Path, tmp_path: Path
) -> None:
    source = pybers.open(path)
    document = parseJsonForm(formatJsonForm(source))
    assert isinstance(document, pybers.Document)
    saved = tmp_path / path.name
    try:
        document.save(saved)
    except pybers.WriteError as exc:
        assert "Nothing was written" in str(exc)
        assert not saved.exists()
        return
    written = pybers.open(saved)
    lost = [
        f"{sheet.name} / {table.name} / {address}: {loss}"
        for sheet, writtenSheet in zip(source.sheets, written.sheets, strict=True)
        for table, writtenTable in zip(sheet.tables, writtenSheet.tables, strict=True)
        for address, cell in table.cells.items()
        if (loss := findCellLoss(
            buildCellForm(cell),
            None if (other := writtenTable.cells.get(address)) is None
            else buildCellForm(other),
        )) is not None
    ]
    assert lost == []


def testADocumentHoldingAControlIsRefusedNamingTheCell(tmp_path: Path) -> None:
    source = pybers.open(findDocumentPath("81-control-formats"))
    document = parseJsonForm(formatJsonForm(source))
    assert isinstance(document, pybers.Document)
    path = tmp_path / "refused.numbers"

    refusal = r"control, which pybers cannot yet create\. Nothing was written"
    with pytest.raises(pybers.WriteError, match=refusal):
        document.save(path)

    assert not path.exists()
    assert document._package is None
    assert all(sheet._identifier is None for sheet in document.sheets)


def findFixtureCell(stem: str, sheet: str, table: str, address: str) -> pybers.Cell:
    """Return one cell of a fixture or measurement."""
    return pybers.open(findDocumentPath(stem)).sheet(sheet).table(table).cell(address)


def testACellHoldingRichTextIsRefused() -> None:
    cell = findFixtureCell("22c-merge-overpaints", "Sheet 1", "Table 1", "A3")

    with pytest.raises(pybers.WriteError, match="'T' A3 holds rich text"):
        refuseUncreatableCell(cell, "T")


def testACellHoldingAFormatAndNoValueIsRefused() -> None:
    cell = findFixtureCell("22c-merge-overpaints", "Sheet 1", "Table 1", "I5")

    with pytest.raises(pybers.WriteError, match="holds a number format and no value"):
        refuseUncreatableCell(cell, "T")


def testACellHoldingAFormatTheBuilderDoesNotWriteIsRefused() -> None:
    cell = findFixtureCell("68-series-kinds-base", "Sheet1", "Table 1", "A2")

    with pytest.raises(pybers.WriteError, match="holds a percent format"):
        refuseUncreatableCell(cell, "T")


def testACellHoldingTheFormatTheBuilderWritesIsAccepted(tmp_path: Path) -> None:
    document = pybers.open(saveCreated(tmp_path))
    cell = document.sheet(1).table(1).cell("A1")

    refuseUncreatableCell(cell, "T")


def testADocumentNamingNoRegionIsRefused(tmp_path: Path) -> None:
    document = pybers.Document(sheets=[pybers.Sheet(name="Only")])

    with pytest.raises(pybers.WriteError, match="names no language and region"):
        document.save(tmp_path / "refused.numbers")


def testADocumentHoldingNoSheetIsRefused(tmp_path: Path) -> None:
    document = pybers.Document()
    document._localeAssign("en_US")

    with pytest.raises(pybers.WriteError, match="holds no sheet"):
        document.save(tmp_path / "refused.numbers")
