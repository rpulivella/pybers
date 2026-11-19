#!/usr/bin/env python3
"""\
Changing part of a cell's style: properties updated or one cleared, the rest kept.

UPDATES
2026-11-19  Written for PYB-290.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/19"

import dataclasses
from decimal import Decimal
from pathlib import Path

import pytest
from test_cli_set import runSetCommand
from test_cli_show import runShowCommand

import pybers
from pybers import (
    CellStyle,
    CellStyleProperty,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
    Color,
    FillGradient,
)

yellow: Color = Color.parse("#ffd60aff")
blue: Color = Color.parse("#0a84ffff")
boxed: CellStyle = CellStyle(
    background=yellow, padding=Decimal(6),
    verticalAlign=CellStyleVerticalAlign.MIDDLE, textWrap=CellStyleTextWrap.WRAP,
)
cells: str = "Sheet 1::T::A1:B2"


def createStyled(tmp_path: Path) -> tuple[pybers.Document, Path]:
    """Return a created document whose table `T` has A1:B2 boxed, and where it saves."""
    document = pybers.create("en_US")
    document.sheets[0].tableAdd("T", rows=4, cols=4)
    document.cellSet(cells, cellStyle=boxed)
    return document, tmp_path / "styled.numbers"


def readStyles(path: Path, addresses: str = "A1 B1 A2 B2") -> set[CellStyle | None]:
    """Return every distinct style the cells named hold, as a fresh read finds them."""
    table = pybers.open(path).sheet("Sheet 1").table("T")
    return {table.cell(each).cellStyle for each in addresses.split()}


def testAnUpdateChangesEachStatedPropertyAndKeepsTheRest(tmp_path: Path) -> None:
    document, path = createStyled(tmp_path)
    changes = document.cellStyleUpdate(cells, CellStyle(background=blue))
    assert changes.changed
    document.save(path)
    assert readStyles(path) == {dataclasses.replace(boxed, background=blue)}


def testAnUpdateGivesACellWithNoStyleTheStyleGiven(tmp_path: Path) -> None:
    document, path = createStyled(tmp_path)
    document.cellStyleUpdate("Sheet 1::T::C3", CellStyle(padding=Decimal(12)))
    document.save(path)
    assert readStyles(path, "C3") == {CellStyle(padding=Decimal(12))}


def testAnUpdateReachesACellHoldingAFormula(tmp_path: Path) -> None:
    document, path = createStyled(tmp_path)
    document.sheet().table("T").cell("C1").formulaSet("=1+1")
    changes = document.cellStyleUpdate("Sheet 1::T::C1", CellStyle(background=blue))
    assert changes.changed
    assert changes.skipped == ()


def testAnUpdateACellAlreadyStatesChangesNothing(tmp_path: Path) -> None:
    document, _ = createStyled(tmp_path)
    changes = document.cellStyleUpdate(cells, CellStyle(background=yellow))
    assert not changes.changed


def testAnUpdateStatingNoPropertyIsRefused(tmp_path: Path) -> None:
    document, _ = createStyled(tmp_path)
    with pytest.raises(pybers.WriteError, match="stating no property"):
        document.cellStyleUpdate(cells, CellStyle())


@pytest.mark.parametrize(("given", "reason"), [
    (CellStyle(background=FillGradient()), "gradient fill is read and carried"),
    ("background: #0a84ffff", "takes a CellStyle, and was given str"),
])
def testAnUpdatePybersCannotWriteIsRefusedChangingNothing(
    tmp_path: Path, given: object, reason: str
) -> None:
    document, _ = createStyled(tmp_path)
    with pytest.raises(pybers.WriteError, match=reason):
        document.cellStyleUpdate(cells, given)  # type: ignore[arg-type]
    assert document.sheet().table("T").cell("A1").cellStyle == boxed


@pytest.mark.parametrize("cleared", list(CellStyleProperty))
def testRemovingAPropertyClearsItAndKeepsTheRest(
    tmp_path: Path, cleared: CellStyleProperty
) -> None:
    document, path = createStyled(tmp_path)
    assert document.cellStylePropertyRemove(cells, cleared).changed
    document.save(path)
    assert readStyles(path) == {dataclasses.replace(boxed, **{cleared.fieldName: None})}


def testRemovingAPropertyACellDoesNotStateChangesNothing(tmp_path: Path) -> None:
    document, _ = createStyled(tmp_path)
    changes = document.cellStylePropertyRemove(
        "Sheet 1::T::C3", CellStyleProperty.PADDING
    )
    assert not changes.changed


def testRemovingTheLastPropertyLeavesTheCellNoStyle(tmp_path: Path) -> None:
    document, path = createStyled(tmp_path)
    document.cellSet("Sheet 1::T::C3", cellStyle=CellStyle(padding=Decimal(12)))
    document.cellStylePropertyRemove("Sheet 1::T::C3", CellStyleProperty.PADDING)
    document.save(path)
    assert readStyles(path, "C3") == {None}


def testRemovingAPropertyByAnUnknownNameIsRefusedNamingTheClosest(
    tmp_path: Path,
) -> None:
    document, _ = createStyled(tmp_path)
    with pytest.raises(pybers.WriteError, match="The closest is padding"):
        document.cellStylePropertyRemove(cells, "paddng")  # type: ignore[arg-type]


def testEveryPropertyNamesOneCellStyleField() -> None:
    fields = [field.name for field in dataclasses.fields(CellStyle)]
    assert [each.fieldName for each in CellStyleProperty] == fields


def testAScriptUpdatesARangeAndClearsOneCell(tmp_path: Path) -> None:
    document, path = createStyled(tmp_path)
    document.cellStyleUpdate(cells, CellStyle(padding=Decimal(12)))
    document.cellStylePropertyRemove("Sheet 1::T::A1", CellStyleProperty.BACKGROUND)
    document.save(path)
    padded = dataclasses.replace(boxed, padding=Decimal(12))
    assert readStyles(path, "B1 A2 B2") == {padded}
    assert readStyles(path, "A1") == {dataclasses.replace(padded, background=None)}


def saveStyled(tmp_path: Path) -> Path:
    """Return the path of a saved created document whose A1:B2 is boxed."""
    document, path = createStyled(tmp_path)
    document.save(path)
    return path


def testACommandUpdatesPartOfACellsBoxAndShowPrintsIt(tmp_path: Path) -> None:
    path = saveStyled(tmp_path)
    result = runSetCommand(str(path), cells, "--cell-style-update", "padding: 12pt")
    assert result.exit_code == 0
    assert f"Written: {path}" in result.stderr
    shown = runShowCommand(path, "Sheet 1::T::A1").stdout
    assert (
        "  Cell style: background: #ffd60aff; padding: 12pt; vertical-align: middle; "
        "text-wrap: wrap"
    ) in shown.splitlines()


def testACommandRemovesOnePropertyOfACellsBox(tmp_path: Path) -> None:
    path = saveStyled(tmp_path)
    result = runSetCommand(str(path), cells, "--cell-style-remove", "vertical-align")
    assert result.exit_code == 0
    assert readStyles(path) == {dataclasses.replace(boxed, verticalAlign=None)}


@pytest.mark.parametrize("option", [
    ("--cell-style-update", "padding: 6pt"), ("--cell-style-remove", "padding"),
])
def testACommandChangingNothingWritesNothing(
    tmp_path: Path, option: tuple[str, str]
) -> None:
    path = saveStyled(tmp_path)
    target = cells if option[0] == "--cell-style-update" else "Sheet 1::T::C3"
    before = path.read_bytes()
    result = runSetCommand(str(path), target, *option)
    assert result.exit_code == 0
    assert "Nothing written: already set" in result.stderr
    assert path.read_bytes() == before


@pytest.mark.parametrize(("arguments", "reason"), [
    (("--cell-style", "none", "--cell-style-remove", "padding"), "give one of them"),
    (("--cell-style-remove", "bakground"), "The closest is background"),
])
def testACommandRefusesAStyleRequestBeforeReadingTheFile(
    tmp_path: Path, arguments: tuple[str, ...], reason: str
) -> None:
    path = saveStyled(tmp_path)
    before = path.read_bytes()
    result = runSetCommand(str(path), cells, *arguments)
    assert result.exit_code == 2
    assert reason in " ".join(result.stderr.split())
    assert path.read_bytes() == before


def testACommandRefusesNoneAsAnUpdateWritingNothing(tmp_path: Path) -> None:
    path = saveStyled(tmp_path)
    before = path.read_bytes()
    result = runSetCommand(str(path), cells, "--cell-style-update", "none")
    assert result.exit_code == 1
    assert "Give --cell-style none to remove the whole box" in result.stderr
    assert path.read_bytes() == before
