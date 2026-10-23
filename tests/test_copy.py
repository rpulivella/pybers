#!/usr/bin/env python3
"""\
A block of cells copied to a new anchor, under the rule its caller names.

What a copy writes against Numbers' own paste in `64*-copy-*`, the refusals that
leave a table as it was, and the few lines a script or a command line writes to
copy a block.

UPDATES
2026-10-22  The golden's comparison moved to the golden builders, for PYB-255.
2026-09-29  Written for PYB-136.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/29"

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest
from structurefacts import readTableFacts

import pybers
from conftest import findDocumentPath
from pybers import CellValueFill, FormulaReferenceRelocation
from pybers._persistence import readPackage
from pybers._persistence.difference import listPackageDifferences
from pybers.addressing.reference import ReferenceError as CellReferenceError

relative = FormulaReferenceRelocation.PRESERVE_RELATIVE_POSITION
named = FormulaReferenceRelocation.PRESERVE_NAMED_CELL

# The error cells Numbers recalculates on open: `=I7` and `Table 2::E7` read nothing.
recalculated: set[tuple[int, int]] = {(9, 7), (10, 7)}

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"


def openTable(name: str) -> tuple[pybers.Document, pybers.Table]:
    """Return a fresh copy of a measurement and its first table."""
    document = pybers.open(findDocumentPath(name))
    return document, document.sheet(1).table("Table 1")


def readTableState(table: pybers.Table) -> tuple[object, ...]:
    """Return what a refused copy must leave alone: every cell and every merge."""
    return (
        {
            reference: (cell.formulaText or cell.value, cell._copiedFrom)
            for reference, cell in table.cells.items()
        },
        list(table.mergeRanges),
    )


def readFormulaTexts(document: pybers.Document) -> dict[str, str | None]:
    """Return every cell of every table by its qualified address and what it holds."""
    return {
        f"{table.name}::{reference}": cell.formulaText or str(cell.value)
        for sheet in document.sheets
        for table in sheet.tables
        for reference, cell in table.cells.items()
    }


def listLeftEdges(path: Path) -> set[tuple[int, int]]:
    """Return each (column, row) of Table 1 drawing a left border, counted from zero."""
    layers = readTableFacts(path)["Table 1"]["strokes"]
    assert isinstance(layers, dict)
    return {
        (column, row)
        for column, runs in layers["left"]
        for origin, length, _ in runs
        for row in range(origin, origin + length)
    }


def copyAndSave(
    base: str, rule: FormulaReferenceRelocation, target: Path, anchor: str = "F8",
    source: str = "B2:D5",
) -> None:
    """Copy a block of a base, `B2:D5` unless named, to an anchor, and save it."""
    document, table = openTable(base)
    table.cellsCopy(source, anchor, references=rule)
    document.save(target)


@pytest.mark.parametrize(
    ("base", "name", "source", "anchor"),
    [
        ("60-move-base", "64-copy-pasted", "B2:D5", "F8"),
        ("61-move-styles-base", "64b-copy-styles-pasted", "B2:D5", "F8"),
        ("64e-copy-border-emptied", "64f-copy-onto-empty-border", "B2:D5", "E8"),
        ("22e-merge-imported", "64g-copy-imported-merge", "A1:G2", "A5"),
    ],
)
def testACopyWritesTheArchivesNumbersWrote(
    base: str, name: str, source: str, anchor: str, tmp_path: Path
) -> None:
    """PYB-136 AC 1, 2.ii, 3 and 9: records, borders, merges, tiles and the engine."""
    target = tmp_path / f"{name}.numbers"
    copyAndSave(base, relative, target, anchor, source)
    ours = readTableFacts(target)
    for tableName, facts in readTableFacts(findDocumentPath(name)).items():
        for key, value in facts.items():
            mine = ours[tableName][key]
            if key == "records":
                assert isinstance(value, dict) and isinstance(mine, dict)
                assert {k: v for k, v in mine.items() if k not in recalculated} == {
                    k: v for k, v in value.items() if k not in recalculated
                }
                continue
            assert mine == value, (tableName, key)


def testARelativeCopyKeepsEachOffsetAsAPasteDoes() -> None:
    """PYB-136 AC 2.ii: offsets kept, `$` axes kept, and a range ending at the edge."""
    _, table = openTable("60-move-base")
    table.cellsCopy("B2:D5", "F8", references=relative)
    assert [
        table.cell(name).formulaText for name in ("H8", "F9", "G9", "H9", "G10")
    ] == ["=F8+G8", "=E9", "=$A$4", "=$B8", "=SUM(E7:E12)"]


def testANamedCellCopyNamesTheCellsItsSourceNamed() -> None:
    """PYB-136 AC 2.i: every copied formula reads what its source formula reads."""
    _, table = openTable("60-move-base")
    table.cellsCopy("B2:D5", "F8", references=named)
    assert [
        table.cell(name).formulaText
        for name in ("H8", "F9", "G9", "H9", "F10", "G10", "H10", "H11")
    ] == [
        "=B2+C2", "=A3", "=$A$4", "=$B2", "=SUM(B2:C2)", "=SUM(A1:A12)", "=E1",
        "=Table 2::A1",
    ]


@pytest.mark.parametrize("rule", [relative, named])
def testNoFormulaOutsideTheCopyChanges(rule: FormulaReferenceRelocation) -> None:
    """PYB-136 AC 1 and 3: the source and every other table read as before."""
    document, table = openTable("60-move-base")
    before = readFormulaTexts(document)
    destination = table.cellsCopy("B2:D5", "F8", references=rule)
    after = readFormulaTexts(document)
    assert {
        address: text for address, text in after.items()
        if not (
            address.startswith("Table 1::")
            and destination.covers(address.removeprefix("Table 1::"))
        )
    } == before


def testASavedCopyLeavesTheSourceAsItWas(tmp_path: Path) -> None:
    """PYB-136 AC 1: the source block reads the same after the file is reopened."""
    target = tmp_path / "copied.numbers"
    copyAndSave("61-move-styles-base", relative, target)
    source = pybers.open(findDocumentPath("61-move-styles-base")).sheet(1).table(
        "Table 1"
    )
    copied = pybers.open(target).sheet(1).table("Table 1")
    assert [cell.value for cell in copied.range("B2:D5")] == [
        cell.value for cell in source.range("B2:D5")
    ]
    assert [cell.value for cell in copied.range("F8:H11")] == [
        cell.value for cell in source.range("B2:D5")
    ]


def testACopiedBlockCarriesItsMergeAndKeepsTheSource(tmp_path: Path) -> None:
    """PYB-136 AC 1: the merge is copied and the source merge stays, as `64` shows."""
    target = tmp_path / "merged.numbers"
    copyAndSave("60-move-base", relative, target)
    table = pybers.open(target).sheet(1).table("Table 1")
    assert [str(merge.extent) for merge in table.mergeRanges] == ["B5:C5", "F11:G11"]
    assert table.cell("F11").value == "merge B5:C5"


def listMergedTables(name: str) -> list[tuple[str, str]]:
    """Return each (sheet, table) of a document holding a merge."""
    document = pybers.open(findDocumentPath(name))
    return [
        (sheet.name, table.name)
        for sheet in document.sheets for table in sheet.tables if table.mergeRanges
    ]


mergedDocuments: list[str] = [
    "22c-merge-overpaints", "22d-merge-multi-row", "22e-merge-imported",
    "57-structure-refusals-base", "60-move-base",
]


@pytest.mark.parametrize(
    ("name", "sheetName", "tableName"),
    [
        (name, sheetName, tableName)
        for name in mergedDocuments
        for sheetName, tableName in listMergedTables(name)
    ],
)
@pytest.mark.parametrize("operation", ["cellsCopy", "cellsMove"])
def testABlockCarriesEveryStoredPositionOfItsMerges(
    name: str, sheetName: str, tableName: str, operation: str, tmp_path: Path
) -> None:
    """PYB-136 AC 9: whatever sits under a merge goes with it, whatever wrote it."""
    document = pybers.open(findDocumentPath(name))
    table = document.sheet(sheetName).table(tableName)
    top = min(merge.bounds[0] for merge in table.mergeRanges)
    bottom = max(merge.bounds[2] for merge in table.mergeRanges)
    height, landing = bottom - top + 1, table.rowCount + 1
    table.rowAdd(landing, height)
    block = pybers.CellRange(top, 1, bottom, table.colCount)
    anchor = pybers.CellReference(landing, 1)
    getattr(table, operation)(block, anchor, references=relative)
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    before = readTableFacts(findDocumentPath(name))[tableName]["records"]
    after = readTableFacts(target)[tableName]["records"]
    assert isinstance(before, dict) and isinstance(after, dict)
    carried = {
        (row, column): kind for (row, column), kind in before.items()
        if top - 1 <= row <= bottom - 1
    }
    assert {
        (row - landing + top, column): kind for (row, column), kind in after.items()
        if row >= landing - 1
    } == carried


def testTwoCopiesOfOneBlockEachDrawItsBorders(tmp_path: Path) -> None:
    """One source copied twice before a save draws its border at both copies."""
    document, table = openTable("61-move-styles-base")
    table.cellsCopy("B2:D5", "F8", references=relative)
    table.cellsCopy("C3", "A12", references=relative)
    target = tmp_path / "twice.numbers"
    document.save(target)
    assert listLeftEdges(target) == {(2, 2), (6, 8), (0, 11)}


def testACopyTakesOffABorderItsSourceLacks(tmp_path: Path) -> None:
    """PYB-136 AC 10: `D3` has no border, so `G9` loses the one it had, as in `64f`."""
    target = tmp_path / "cleared.numbers"
    copyAndSave("64e-copy-border-emptied", relative, target, "E8")
    assert listLeftEdges(target) == {(2, 2), (5, 8)}


def testACellHoldingOnlyABorderCopiesIt(tmp_path: Path) -> None:
    """PYB-136 AC 10: `G9` holds a border and no record, and its copy draws it."""
    document, table = openTable("64e-copy-border-emptied")
    table.cellsCopy("G9", "A12", references=relative)
    target = tmp_path / "bordered.numbers"
    document.save(target)
    assert listLeftEdges(target) == {(2, 2), (6, 8), (0, 11)}


def testACopyOfAFilledCellDrawsNoBorderTheFillDidNot(tmp_path: Path) -> None:
    """A copy of a pending fill draws only the borders that fill will draw."""
    document, table = openTable("61-move-styles-base")
    table.cellsFill(
        "C3", "C3:C4", references=relative, values=CellValueFill.REPEAT_SOURCE_VALUE
    )
    table.cellsCopy("C4", "A12", references=relative)
    target = tmp_path / "chained.numbers"
    document.save(target)
    assert listLeftEdges(target) == {(2, 2)}
    assert pybers.open(target).sheet(1).table("Table 1").cell("A12").value == Decimal(
        32
    )


def testASecondSaveAfterACopyChangesNothing(tmp_path: Path) -> None:
    """A saved copy is settled, so saving the same document again writes the same."""
    document, table = openTable("61-move-styles-base")
    table.cellsCopy("B2:D5", "F8", references=relative)
    first, second = tmp_path / "first.numbers", tmp_path / "second.numbers"
    document.save(first)
    document.save(second)
    differences = listPackageDifferences(readPackage(first), readPackage(second))
    assert [
        difference for difference in differences if difference.identifier is not None
    ] == []


@pytest.mark.parametrize(
    ("copy", "message"),
    [
        (lambda table: table.cellsCopy("B2:D5", "E1", references=relative),
         "E1 is occupied"),
        (lambda table: table.cellsCopy("B2:D5", "C3", references=relative),
         "overlaps B2:D5"),
        (lambda table: table.cellsCopy("B2:D5", "B2", references=relative),
         "overlaps B2:D5"),
        (lambda table: table.cellsCopy("B2:D5", "F10", references=relative),
         "reaches outside"),
        (lambda table: table.cellsCopy("B2:B5", "F8", references=relative),
         "cuts the merge B5:C5"),
        (lambda table: table.cellsCopy("F7:G8", "B4", references=relative),
         "lands on the merge B5:C5"),
        (lambda table: table.cellsCopy("B2:D5", "F8", references="sideways"),
         "not a reference rule"),
    ],
)
def testARefusedCopyLeavesTheTableAsItWas(
    copy: Callable[[pybers.Table], object], message: str
) -> None:
    """PYB-136 AC 4 to 7: occupied, overlapping, outside, a cut merge, a bad rule."""
    _, table = openTable("60-move-base")
    before = readTableState(table)
    with pytest.raises(CellReferenceError, match=message):
        copy(table)
    assert readTableState(table) == before


def testACopyNamingNoRuleIsATypeError() -> None:
    """PYB-136 AC 2: the rule has no default, so leaving it out cannot run."""
    _, table = openTable("60-move-base")
    with pytest.raises(TypeError, match="references"):
        table.cellsCopy("B2:D5", "F8")  # type: ignore[call-arg]


def testCopyTakesTheArgumentsMoveTakes() -> None:
    """PYB-136 constraint: the same arguments, in the same order and spelling."""
    import inspect

    def listParameters(method: Callable[..., object]) -> list[tuple[str, object]]:
        return [
            (parameter.name, parameter.kind)
            for parameter in inspect.signature(method).parameters.values()
        ]

    assert listParameters(pybers.Table.cellsCopy) == listParameters(
        pybers.Table.cellsMove
    )


def testTheCopyGoldensHoldWhatTheyClaimTo() -> None:
    """Guard the guard: a golden replaced by an unedited copy would pass above."""
    relativeTable = pybers.open(
        goldenDirectory / "64-cells-copied-relative-by-pybers.numbers"
    ).sheet(1).table("Table 1")
    assert relativeTable.cell("H8").formulaText == "=F8+G8"
    namedTable = pybers.open(
        goldenDirectory / "64-cells-copied-named-by-pybers.numbers"
    ).sheet(1).table("Table 1")
    assert namedTable.cell("H8").formulaText == "=B2+C2"


def testAScriptAuthorCopiesABlockAndSaves(tmp_path: Path) -> None:
    """The few lines a script writes: open, copy, save, and read it back."""
    document = pybers.open(findDocumentPath("61-move-styles-base"))
    document.sheet(1).table("Table 1").cellsCopy(
        "B2:D5", "F8", references=FormulaReferenceRelocation.PRESERVE_RELATIVE_POSITION
    )
    document.save(tmp_path / "scripted.numbers")
    table = pybers.open(tmp_path / "scripted.numbers").sheet(1).table("Table 1")
    assert [table.cell(name).value for name in ("C3", "G9")] == [
        Decimal("32"), Decimal("32")
    ]


def testACommandLineCopiesABlockWithTheRuleAsTyped() -> None:
    """A CLI passes `--references named-cell` and reports where the copy landed."""
    arguments = ["Table 1", "B2:D5", "F8", "named-cell"]
    document = pybers.open(findDocumentPath("60-move-base"))
    table = document.sheet(1).table(arguments[0])
    landed = table.cellsCopy(arguments[1], arguments[2], references=arguments[3])  # type: ignore[arg-type]
    assert str(landed) == "F8:H11"
    assert table.cell("H8").formulaText == "=B2+C2"
