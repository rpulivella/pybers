#!/usr/bin/env python3
"""\
Setting a cell's style: its whole box replaced, a default dropped, a match shared.

UPDATES
2026-11-12  Written for PYB-265.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/12"

from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from test_cli_set import runSetCommand
from test_cli_show import runShowCommand
from test_writer import listArchiveDifferences, readRecordAt, tableInfoTypeId

import pybers
from conftest import copyDocument, findDocumentPath
from pybers import (
    CellStyle,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
    Color,
    FillGradient,
    FillImage,
    FillNone,
)
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSDArchives_pb2 as tsd
from pybers._generated import TSTArchives_pb2 as tst
from pybers._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from pybers._persistence import readPackage
from pybers._persistence.cells import cellStyleSlot, findSlotValue
from pybers._persistence.index import ArchiveIndex, findRoot
from pybers.formula.relocation import FormulaReferenceRelocation
from pybers.style._write import composeCellProperties
from pybers.table._read import iterateCellRecords
from pybers.table._refcounts import listStyleClaims
from pybers.table.fill import CellValueFill

yellow = Color.parse("#ffd60aff")
red = Color.parse("#ff0000ff")
boxed = CellStyle(
    background=yellow, padding=Decimal(6),
    verticalAlign=CellStyleVerticalAlign.MIDDLE, textWrap=CellStyleTextWrap.WRAP,
)


def createTable(tmp_path: Path) -> tuple[pybers.Document, Path]:
    """Return a created document holding one 4 by 4 table, and where it saves."""
    document = pybers.create("en_US")
    document.sheets[0].tableAdd("T", rows=4, cols=4)
    return document, tmp_path / "styled.numbers"


def saveAndReopen(document: pybers.Document, path: Path) -> pybers.Table:
    """Save a document and return its table `T` as read back."""
    document.save(path)
    return pybers.open(path).sheet("Sheet 1").table("T")


def testEachPropertySetOnARangeReadsBackAfterASave(tmp_path: Path) -> None:
    document, path = createTable(tmp_path)
    document.cellSet("Sheet 1::T::A1:B2", cellStyle=boxed)
    table = saveAndReopen(document, path)
    assert {table.cell(each).cellStyle for each in ("A1", "B1", "A2", "B2")} == {boxed}


def testAStyleSetReplacesTheWholeBox(tmp_path: Path) -> None:
    document, path = createTable(tmp_path)
    document.cellSet("Sheet 1::T::A1", cellStyle=boxed)
    document.cellSet("Sheet 1::T::A1", cellStyle=CellStyle(padding=Decimal(2)))
    assert saveAndReopen(document, path).cell("A1").cellStyle == CellStyle(
        padding=Decimal(2)
    )


def testAClearedStyleLeavesTheCellNamingNone(tmp_path: Path) -> None:
    document, path = createTable(tmp_path)
    document.cellSet("Sheet 1::T::A1", 5, cellStyle=boxed)
    document.save(path)
    reopened = pybers.open(path)
    changes = reopened.cellSet("Sheet 1::T::A1", cellStyle=None)
    assert changes.changed
    reopened.save()
    assert pybers.open(path).sheet("Sheet 1").table("T").cell("A1").cellStyle is None
    assert findSlotValue(readRecordAt(path, "A1", "T"), cellStyleSlot) is None


def testAMergedBlockTakesTheStyleOnce(tmp_path: Path) -> None:
    document, path = createTable(tmp_path)
    document.sheets[0].table("T").mergeAdd("A1:B2")
    changes = document.cellSet("Sheet 1::T::A1:B2", cellStyle=boxed)
    assert [str(each.reference.address) for each in changes.changes] == ["A1"]
    assert saveAndReopen(document, path).cell("A1").cellStyle == boxed


@pytest.mark.parametrize("fill", [FillGradient(), FillImage()])
def testAFillPybersOnlyCarriesIsRefusedNamingItsType(
    tmp_path: Path, fill: FillGradient | FillImage
) -> None:
    document, _ = createTable(tmp_path)
    with pytest.raises(pybers.WriteError, match=f"A {fill.fillType} fill"):
        document.cellSet("Sheet 1::T::A1", cellStyle=CellStyle(background=fill))
    assert document.sheets[0].table("T").cells.get(pybers.CellAddress(1, 1)) is None


def testUnevenPaddingIsRefused(tmp_path: Path) -> None:
    document, _ = createTable(tmp_path)
    sides = (Decimal(0), Decimal(2), Decimal(2), Decimal(2))
    with pytest.raises(pybers.WriteError, match="one length for every side"):
        document.cellSet("Sheet 1::T::A1", cellStyle=CellStyle(padding=sides))


@pytest.mark.parametrize("padding", [Decimal("-1"), 1.5, True])
def testAPaddingThatIsNoLengthOfPointsIsRefused(
    tmp_path: Path, padding: object
) -> None:
    document, _ = createTable(tmp_path)
    with pytest.raises(pybers.WriteError, match="padding"):
        document.cellSet(
            "Sheet 1::T::A1", cellStyle=CellStyle(padding=padding)  # type: ignore[arg-type]
        )


def testAValueTheCellInheritsWritesNoOverride(tmp_path: Path) -> None:
    document, path = createTable(tmp_path)
    inherited = CellStyle(
        background=FillNone(), padding=Decimal(4),
        verticalAlign=CellStyleVerticalAlign.TOP, textWrap=CellStyleTextWrap.NOWRAP,
    )
    changes = document.cellSet("Sheet 1::T::A1", 1, cellStyle=inherited)
    assert changes.changes[0].cellStyleAfter is None
    assert saveAndReopen(document, path).cell("A1").cellStyle is None


def testWrapOnOverridesACreatedTableThatDoesNotWrap(tmp_path: Path) -> None:
    document, path = createTable(tmp_path)
    wrapping = CellStyle(textWrap=CellStyleTextWrap.WRAP)
    document.cellSet("Sheet 1::T::A1", 1, cellStyle=wrapping)
    assert saveAndReopen(document, path).cell("A1").cellStyle == wrapping


def testNoFillOverridesAHeaderCellAndNotABodyCell(tmp_path: Path) -> None:
    working = copyDocument("40-table-bands", tmp_path)
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    body = next(
        address for address, cell in table.cells.items()
        if cell.cellStyle is None
        and table.headers.regionFind(address, table.rowCount).value == "body"
    )
    cleared = CellStyle(background=FillNone())
    header = document.cellSet(f"::{table.name}::B1", cellStyle=cleared)
    unchanged = document.cellSet(f"::{table.name}::{body}", cellStyle=cleared)
    assert header.changes[0].cellStyleAfter == cleared
    assert not unchanged.changed


def testCellsStyledAlikeShareOneStoredStyle(tmp_path: Path) -> None:
    document, path = createTable(tmp_path)
    document.cellSet("Sheet 1::T::A1:B2", cellStyle=boxed)
    document.cellSet("Sheet 1::T::D4", 9, cellStyle=boxed)
    document.save(path)
    keys = {
        findSlotValue(readRecordAt(path, each, "T"), cellStyleSlot)
        for each in ("A1", "B1", "A2", "B2", "D4")
    }
    assert len(keys) == 1


def testAStyleTheCellShowsAlreadyChangesAndWritesNothing(
    tmp_path: Path,
) -> None:
    working = copyDocument("98b-cell-box-styles", tmp_path)
    before = readPackage(working)
    document = pybers.open(working)
    changes = document.cellSet("::Table 1::B1", cellStyle=CellStyle(background=yellow))
    assert not changes.changed
    document.save()
    assert listArchiveDifferences(before, readPackage(working)) == []


def testAStyleLeavesTheValueFormatAndParagraphStyleAsTheyWere(
    tmp_path: Path,
) -> None:
    working = copyDocument("98b-cell-box-styles", tmp_path)
    before = readRecordAt(working, "G1")
    document = pybers.open(working)
    document.cellSet("::Table 1::G1", cellStyle=CellStyle(background=yellow))
    document.save()
    after = readRecordAt(working, "G1")
    cell = pybers.open(working).sheets[0].tables[0].cell("G1")
    assert cell.value == Decimal(1)
    assert cell.cellStyle == CellStyle(background=yellow)
    assert findSlotValue(after, (8, 0x40)) == findSlotValue(before, (8, 0x40))
    assert after.references[-2:] == before.references[-2:]


def testANewValueTakesNoStyleFromTheRecordItBorrows(tmp_path: Path) -> None:
    document, path = createTable(tmp_path)
    document.cellSet("Sheet 1::T::A1:B2", cellStyle=boxed)
    document.cellSet("Sheet 1::T::C3", 7)
    table = saveAndReopen(document, path)
    assert table.cell("C3").cellStyle is None
    assert table.cell("A1").cellStyle == boxed


def testReplacingTheBoxCarriesABorderTheStyleHolds() -> None:
    carried = tstStyles.CellStylePropertiesArchive(
        top_stroke=tsd.StrokeArchive(width=2), text_wrap=False
    )
    composed = composeCellProperties(CellStyle(padding=Decimal(6)), carried)
    assert composed.top_stroke.width == 2
    assert not composed.HasField("text_wrap")
    assert composed.padding.top == 6


def testACommandSetsACellsBoxAndShowPrintsIt(tmp_path: Path) -> None:
    working = copyDocument("98b-cell-box-styles", tmp_path)
    declared = "background: #ffd60aff; padding: 6pt; vertical-align: middle"
    result = runSetCommand(str(working), "::Table 1::A1:A2", "--cell-style", declared)
    assert result.exit_code == 0
    assert f"Written: {working}" in result.stderr
    shown = runShowCommand(working, "Sheet 1::Table 1::A1").stdout
    assert f"  Cell style: {declared}" in shown.splitlines()


def testACommandClearsACellsBoxWithNone(tmp_path: Path) -> None:
    working = copyDocument("98b-cell-box-styles", tmp_path)
    result = runSetCommand(str(working), "::Table 1::B1", "--cell-style", "none")
    assert result.exit_code == 0
    assert pybers.open(working).sheets[0].tables[0].cell("B1").cellStyle is None


@pytest.mark.parametrize(("declared", "reason"), [
    ("padding: 6", "padding is a length in points such as 6pt"),
    ("background: gradient", "A gradient fill is read and carried"),
    ("padding: 0pt 2pt 2pt 2pt", "one length for every side"),
    ("vertical-align: center", "vertical-align is one of top, middle, bottom"),
])
def testACommandRefusesAStyleItCannotWriteAndWritesNothing(
    tmp_path: Path, declared: str, reason: str
) -> None:
    working = copyDocument("98b-cell-box-styles", tmp_path)
    before = readPackage(working)
    result = runSetCommand(str(working), "::Table 1::A1", "--cell-style", declared)
    assert result.exit_code == 1
    assert reason in result.stderr
    assert listArchiveDifferences(before, readPackage(working)) == []


@pytest.mark.parametrize("stem", ["98b-cell-box-styles", "98c-cell-box-regions"])
def testEveryCellStyleReadsBackFromItsTextForm(stem: str) -> None:
    for _, _, cell in pybers.open(findDocumentPath(stem)).cellsIterate():
        if cell.cellStyle is not None:
            text = pybers.formatCellStyle(cell.cellStyle)
            assert pybers.parseCellStyle(text) == cell.cellStyle


def listStyleCountMismatches(path: Path) -> list[tuple[int, int, int]]:
    """Return each style entry whose refcount differs from the records naming it."""
    index = ArchiveIndex(readPackage(path))
    mismatched = []
    for sheet in findRoot(index).sheets:
        for drawable in index.resolve(sheet, tn.SheetArchive).drawable_infos:
            if index.typeOf(drawable) != tableInfoTypeId:
                continue
            info = index.resolve(drawable, tst.TableInfoArchive)
            model = index.resolve(info.tableModel, tst.TableModelArchive)
            named = Counter(
                key for _, record in iterateCellRecords(index, model, path)
                for key in listStyleClaims(record)
            )
            styles = index.resolve(model.base_data_store.styleTable, tst.TableDataList)
            mismatched.extend(
                (int(entry.key), int(entry.refcount), named[entry.key])
                for entry in styles.entries if named[entry.key] != entry.refcount
            )
    return mismatched


def addCopyRows(table: pybers.Table) -> None:
    """Give a table three more rows beneath its first, room for a copy to land."""
    table.rowAdd(3, 3)


keep = FormulaReferenceRelocation.PRESERVE_RELATIVE_POSITION
padded = CellStyle(padding=Decimal(8))


@pytest.mark.parametrize(("edit", "expected"), [
    (lambda table: (
        addCopyRows(table), table.cellsCopy("B1:C1", "B4", references=keep)
    ),
     {"B4": CellStyle(background=yellow), "C4": CellStyle(background=red)}),
    (lambda table: (addCopyRows(table), table.cellsMove("B1", "B4", references=keep)),
     {"B1": None, "B4": CellStyle(background=yellow)}),
    (lambda table: (addCopyRows(table), table.cellsFill(
        "F1", "F3:F5", references=keep, values=CellValueFill.REPEAT_SOURCE_VALUE)),
     {each: CellStyle(padding=Decimal(6)) for each in ("F3", "F4", "F5")}),
    (lambda table: table.rowAdd(1, 1), {"B2": CellStyle(background=yellow)}),
    (lambda table: table.columnAdd(1, 1), {"G1": CellStyle(padding=Decimal(6))}),
    (lambda table: table.columnRemove(1, 1), {"E1": CellStyle(padding=Decimal(6))}),
], ids=["copy", "move", "fill", "row-added", "column-added", "column-removed"])
def testAStoredStyleSurvivesEachEditAndItsSave(
    tmp_path: Path, edit: object, expected: dict[str, CellStyle | None]
) -> None:
    working = copyDocument("98b-cell-box-styles", tmp_path)
    document = pybers.open(working)
    edit(document.sheets[0].tables[0])  # type: ignore[operator]
    document.save()
    table = pybers.open(working).sheets[0].tables[0]
    assert {address: table.cell(address).cellStyle for address in expected} == expected
    assert listStyleCountMismatches(working) == []


@pytest.mark.parametrize(("edit", "addresses"), [
    (lambda table: table.cellsCopy("A1", "A4", references=keep), ("A1", "A4")),
    (lambda table: table.cellsMove("A1", "A4", references=keep), ("A4",)),
    (lambda table: table.cellsFill(
        "A1", "A3:A5", references=keep, values=CellValueFill.REPEAT_SOURCE_VALUE),
     ("A1", "A3", "A4", "A5")),
], ids=["copy", "move", "fill"])
def testAStyleSetBeforeAnEditReachesEveryCellItLands(
    tmp_path: Path, edit: object, addresses: tuple[str, ...]
) -> None:
    working = copyDocument("98b-cell-box-styles", tmp_path)
    document = pybers.open(working)
    addCopyRows(document.sheets[0].tables[0])
    document.cellSet("::Table 1::A1", cellStyle=padded)
    edit(document.sheets[0].tables[0])  # type: ignore[operator]
    document.save()
    table = pybers.open(working).sheets[0].tables[0]
    assert {table.cell(address).cellStyle for address in addresses} == {padded}
    assert listStyleCountMismatches(working) == []
