#!/usr/bin/env python3
"""\
A block of cells moved within its table, against the moves Numbers made by hand.

The archives a save writes for a move, the refusals that leave a table as it was,
and the few lines a script or a command line writes to move a block.

UPDATES
2026-09-23  Written for PYB-18.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/23"

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest
from structurefacts import readConditionalRules, readTableFacts

import pybers
from conftest import findDocumentPath
from pybers import FormulaReferenceRelocation
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import readPackage
from pybers._persistence.difference import listPackageDifferences
from pybers.addressing.reference import ReferenceError as CellReferenceError

relative = FormulaReferenceRelocation.PRESERVE_RELATIVE_POSITION
named = FormulaReferenceRelocation.PRESERVE_NAMED_CELL

# Where pybers deliberately differs from Numbers' cut and paste, named so a further
# difference fails: Numbers leaves the empty source merge behind, and stores the
# two formulas whose offsets leave their tables as errors it recomputes on open.
cutPasteDifferences: dict[str, dict[str, object]] = {
    "60b-move-cut-pasted": {"merges": None, "records": {(9, 7), (10, 7)}},
    "61b-move-styles-cut-pasted": {},
}

# Numbers' drags, as the base, the anchor, and the cached results Numbers
# recomputes on open: `E7` reads `B6`, where the drag in `60d` put the merge.
dragged: dict[str, tuple[str, str, set[tuple[int, int]]]] = {
    "60c-move-dragged": ("60-move-base", "F8", set()),
    "60d-move-overlapping": ("60-move-base", "B3", {(6, 4)}),
    "61c-move-styles-dragged": ("61-move-styles-base", "F8", set()),
    "62b-move-rules-dragged": ("62-move-rules-base", "F8", set()),
}


def openTable(name: str) -> tuple[pybers.Document, pybers.Table]:
    """Return a fresh copy of a measurement and its first table."""
    document = pybers.open(findDocumentPath(name))
    return document, document.sheet(1).table("Table 1")


def readTableState(table: pybers.Table) -> tuple[object, ...]:
    """Return what a refused move must leave alone: every cell and every merge."""
    return (
        {
            reference: (cell.formulaText or cell.value, cell.reference)
            for reference, cell in table.cells.items()
        },
        list(table.mergeRanges),
    )


def moveAndSave(base: str, target: Path) -> None:
    """Move `B2:D5` of a base to `F8` as cut and paste does, and save it."""
    document, table = openTable(base)
    table.cellsMove("B2:D5", "F8", references=relative)
    document.save(target)


@pytest.mark.parametrize(
    ("base", "name"),
    [
        ("60-move-base", "60b-move-cut-pasted"),
        ("61-move-styles-base", "61b-move-styles-cut-pasted"),
    ],
)
def testACutAndPasteMoveWritesTheArchivesNumbersWrote(
    base: str, name: str, tmp_path: Path
) -> None:
    """PYB-18 AC 1 and 2.ii: records, headers, borders, tiles and the engine."""
    target = tmp_path / f"{name}.numbers"
    moveAndSave(base, target)
    ours = readTableFacts(target)
    theirs = readTableFacts(findDocumentPath(name))
    allowed = cutPasteDifferences[name]
    for tableName, facts in theirs.items():
        for key, value in facts.items():
            if key in allowed and allowed[key] is None:
                continue
            if key == "records":
                assert isinstance(value, dict)
                skipped = allowed.get("records", set())
                assert isinstance(skipped, set)
                value = {k: v for k, v in value.items() if k not in skipped}
                mine = ours[tableName][key]
                assert isinstance(mine, dict)
                assert {k: v for k, v in mine.items() if k not in skipped} == value
                continue
            assert ours[tableName][key] == value, (tableName, key)


@pytest.mark.parametrize("name", sorted(dragged))
def testADragWritesTheArchivesNumbersWrote(name: str, tmp_path: Path) -> None:
    """PYB-18 AC 2.i and 3: a named-cell move saved as Numbers saved the drag."""
    base, anchor, recomputed = dragged[name]
    document, table = openTable(base)
    table.cellsMove("B2:D5", anchor, references=named)
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    ours = readTableFacts(target)
    theirs = readTableFacts(findDocumentPath(name))
    for tableName, facts in theirs.items():
        for key, value in facts.items():
            mine = ours[tableName][key]
            if key == "records":
                assert isinstance(value, dict) and isinstance(mine, dict)
                assert {k: v for k, v in mine.items() if k not in recomputed} == {
                    k: v for k, v in value.items() if k not in recomputed
                }
                continue
            assert mine == value, (tableName, key)


@pytest.mark.parametrize("name", ["60c-move-dragged", "60d-move-overlapping"])
def testANamedCellMoveRewritesFormulasAsADragDoes(name: str) -> None:
    """PYB-18 AC 2.i and 3: inside the block, out of it, and from another table."""
    base, anchor, _ = dragged[name]
    document, table = openTable(base)
    table.cellsMove("B2:D5", anchor, references=named)
    theirs = pybers.open(findDocumentPath(name))
    for tableName in ("Table 1", "Table 2"):
        mine = document.sheet(1).table(tableName)
        for reference, cell in theirs.sheet(1).table(tableName).cells.items():
            if cell.formula is not None:
                assert mine.cell(reference).formulaText == cell.formulaText, reference


def testAConditionFollowsARowAddedAboveIt() -> None:
    """A structural edit moves a highlighting condition as it moves a formula."""
    _, table = openTable("62-move-rules-base")
    table.rowAdd(1)
    (condition,) = table.cell("C3")._conditions
    (reference,) = condition.references
    assert reference.resolve(table.cell("C3").reference) == pybers.CellReference(2, 1)


def readRuleConditions(path: Path) -> dict[tuple[int, int], object]:
    """Return each highlighted cell's kind, rule references and cached match.

    A rule is read as the references its conditions hold, since Numbers rebuilds a
    moved rule with fresh style archives and numbers its keys as it likes.
    """
    cells, _ = readConditionalRules(path, "Table 1")
    assert isinstance(cells, dict)
    found: dict[tuple[int, int], object] = {}
    for position, (kind, rules, match) in cells.items():
        if not isinstance(rules, bytes):
            continue
        archive = tst.ConditionalStyleSetArchive()
        archive.ParseFromString(rules)
        found[position] = (
            kind,
            [
                (node.AST_column.column, node.AST_row.row)
                for rule in archive.rules.rule
                for node in rule.predicate.formula.AST_node_array.AST_node
                if node.HasField("AST_column")
            ],
            match,
        )
    return found


def testADragRewritesHighlightingAsNumbersDid(tmp_path: Path) -> None:
    """PYB-18 AC 2.i and 3: a moved rule keeps reading `A1`, and `E2`'s follows `C2`."""
    document, table = openTable("62-move-rules-base")
    table.cellsMove("B2:D5", "F8", references=named)
    target = tmp_path / "ruled.numbers"
    document.save(target)
    assert readRuleConditions(target) == readRuleConditions(
        findDocumentPath("62b-move-rules-dragged")
    )


def testMovedHighlightingKeepsItsRuleAndItsMatch(tmp_path: Path) -> None:
    """PYB-18 AC 1: the rule on `C2` travels unchanged, landing where Numbers put it.

    Numbers rebuilds the rule with fresh style archives, so the rule is compared
    with the one the base holds, and its position and match with Numbers'.
    """
    target = tmp_path / "moved.numbers"
    moveAndSave("61-move-styles-base", target)
    ourCells, ourRules = readConditionalRules(target, "Table 1")
    _, baseRules = readConditionalRules(
        findDocumentPath("61-move-styles-base"), "Table 1"
    )
    theirCells, _ = readConditionalRules(
        findDocumentPath("61b-move-styles-cut-pasted"), "Table 1"
    )
    assert ourRules == baseRules
    assert isinstance(ourCells, dict) and isinstance(theirCells, dict)
    assert {
        position: (kind, match) for position, (kind, _, match) in ourCells.items()
    } == {
        position: (kind, match) for position, (kind, _, match) in theirCells.items()
    }


def testMovedFormulasKeepTheirOffsetsAsCutAndPasteDoes() -> None:
    """PYB-18 AC 2.ii and 3: nothing rewritten, inside the block or outside it."""
    _, table = openTable("60-move-base")
    table.cellsMove("B2:D5", "F8", references=relative)
    _, theirs = openTable("60b-move-cut-pasted")
    for reference, cell in theirs.cells.items():
        if cell.formula is not None:
            assert table.cell(reference).formulaText == cell.formulaText, reference


def testVacatedCellsReadEmptyAfterASave(tmp_path: Path) -> None:
    """PYB-18 AC 1: values arrive and nothing is left where they were."""
    target = tmp_path / "moved.numbers"
    moveAndSave("61-move-styles-base", target)
    table = pybers.open(target).sheet(1).table("Table 1")
    assert [cell.value for cell in table.range("B2:D5")] == [None] * 12
    assert table.cell("F8").value == Decimal("21")
    assert table.cell("H11").value == Decimal("53")


def testAMoveOverlappingItselfLandsEveryCell(tmp_path: Path) -> None:
    """A block moved one row down lifts every record before setting any down."""
    document, table = openTable("61-move-styles-base")
    table.cellsMove("B2:D5", "B3", references=relative)
    target = tmp_path / "overlap.numbers"
    document.save(target)
    reopened = pybers.open(target).sheet(1).table("Table 1")
    assert [cell.value for cell in reopened.range("B2:D2")] == [None] * 3
    assert [cell.value for cell in reopened.range("B3:D3")] == [
        Decimal("21"), Decimal("22"), Decimal("23"),
    ]
    assert reopened.cell("D6").value == Decimal("53")


def testABlockMovedAcrossTilesBesideAnInsertionKeepsItsValues(
    tmp_path: Path,
) -> None:
    """`27-big-table` spans eight tiles and fills four columns, so two are added.

    One save carries both edits: the new columns, then a block from row 1 into
    them at row 600, which changes tile.
    """
    document = pybers.open(findDocumentPath("27-big-table"))
    table = document.sheets[0].tables[0]
    before = [cell.value for cell in table.range("A1:B2")]
    table.columnAdd("E", 2)
    table.cellsMove("A1:B2", "E600", references=relative)
    target = tmp_path / "tiles.numbers"
    document.save(target)
    reopened = pybers.open(target).sheets[0].tables[0]
    assert [cell.value for cell in reopened.range("E600:F601")] == before
    assert [cell.value for cell in reopened.range("A1:B2")] == [None] * 4


@pytest.mark.parametrize("rule", list(FormulaReferenceRelocation))
def testTwoMovesBeforeASaveWriteWhatOneMoveWrites(
    rule: FormulaReferenceRelocation, tmp_path: Path
) -> None:
    """Each cell's origin is where the file holds it, however often it moved since."""
    chained, table = openTable("61-move-styles-base")
    table.cellsMove("B2:D5", "E2", references=rule)
    table.cellsMove("E2:G5", "F8", references=rule)
    chained.save(tmp_path / "chained.numbers")
    direct, table = openTable("61-move-styles-base")
    table.cellsMove("B2:D5", "F8", references=rule)
    direct.save(tmp_path / "direct.numbers")
    assert readTableFacts(tmp_path / "chained.numbers") == readTableFacts(
        tmp_path / "direct.numbers"
    )


def testASecondSaveAfterAMoveChangesNothing(tmp_path: Path) -> None:
    """Each cell records where the first save put it, so the next finds no move."""
    document, table = openTable("61-move-styles-base")
    table.cellsMove("B2:D5", "F8", references=relative)
    first = tmp_path / "first.numbers"
    second = tmp_path / "second.numbers"
    document.save(first)
    document.save(second)
    differences = listPackageDifferences(readPackage(first), readPackage(second))
    assert [
        difference for difference in differences if difference.identifier is not None
    ] == []


def testAMoveOntoItselfWritesNothing(tmp_path: Path) -> None:
    """A block landing where it is moves nothing, and the save changes nothing."""
    document, table = openTable("61-move-styles-base")
    assert table.cellsMove("B2:D5", "B2", references=relative) == []
    target = tmp_path / "unchanged.numbers"
    document.save(target)
    differences = listPackageDifferences(
        readPackage(findDocumentPath("61-move-styles-base")), readPackage(target)
    )
    assert [
        difference for difference in differences if difference.identifier is not None
    ] == []


@pytest.mark.parametrize(
    ("move", "message"),
    [
        (lambda table: table.cellsMove("B2:D5", "C2", references=relative),
         "E2 is occupied"),
        (lambda table: table.cellsMove("B2:D5", "F10", references=relative),
         "reaches outside"),
        (lambda table: table.cellsMove("B2:B5", "F8", references=relative),
         "cuts the merge B5:C5"),
        (lambda table: table.cellsMove("F7:G8", "B4", references=relative),
         "lands on the merge B5:C5"),
        (lambda table: table.cellsMove("B2:D5", "F8", references="sideways"),
         "not a reference rule"),
    ],
)
def testARefusedMoveLeavesTheTableAsItWas(
    move: Callable[[pybers.Table], object], message: str
) -> None:
    """PYB-18 AC 4, 5 and 6: occupied, outside the grid, a cut merge, a bad rule."""
    _, table = openTable("60-move-base")
    before = readTableState(table)
    with pytest.raises(CellReferenceError, match=message):
        move(table)
    assert readTableState(table) == before


def testAMoveNamingNoRuleIsATypeError() -> None:
    """PYB-18 AC 2: the rule has no default, so leaving it out cannot run."""
    _, table = openTable("60-move-base")
    with pytest.raises(TypeError, match="references"):
        table.cellsMove("B2:D5", "F8")  # type: ignore[call-arg]


def testAMergedBlockCarriesItsMerge() -> None:
    """PYB-18 AC 5: the merge inside the block moves and none is left behind."""
    _, table = openTable("60-move-base")
    table.cellsMove("B2:D5", "F8", references=relative)
    assert [str(merge.extent) for merge in table.mergeRanges] == ["F11:G11"]
    assert table.cell("F11").value == "merge B5:C5"


def testASavedMoveLeavesNoMergeBehind(tmp_path: Path) -> None:
    """PYB-18 AC 5: unlike Numbers' cut and paste, the source merge goes with it."""
    target = tmp_path / "merged.numbers"
    moveAndSave("60-move-base", target)
    table = pybers.open(target).sheet(1).table("Table 1")
    assert [str(merge.extent) for merge in table.mergeRanges] == ["F11:G11"]
    assert table.cell("C5").value is None


@pytest.mark.parametrize(
    ("rule", "anchor", "expected"),
    [
        (named, "F8", ["E4", "E8"]),
        (named, "B3", ["E4", "E8"]),
        (relative, "F8", ["E2", "E3", "E4", "E5", "E8", "E9", "A2", "A3"]),
    ],
)
def testAMoveReturnsEveryFormulaReadingAVacatedCell(
    rule: FormulaReferenceRelocation, anchor: str, expected: list[str]
) -> None:
    """PYB-18 AC 8: a partial range under either rule, the old address under one."""
    _, table = openTable("60-move-base")
    stranded = table.cellsMove("B2:D5", anchor, references=rule)
    assert [str(cell.reference) for cell in stranded] == expected


def testAMovedImportedMergeCarriesTheRecordsItCovers(tmp_path: Path) -> None:
    """An imported merge keeps a record under `B1`, and it goes with the merge."""
    document = pybers.open(findDocumentPath("22e-merge-imported"))
    table = document.sheets[0].tables[0]
    table.cellsMove("A1:B1", "A5", references=relative)
    target = tmp_path / "imported.numbers"
    document.save(target)
    records = readTableFacts(target)[table.name]["records"]
    assert isinstance(records, dict)
    assert {(4, 0), (4, 1)} <= records.keys()
    assert not {(0, 0), (0, 1)} & records.keys()


goldenDirectory: Path = Path(__file__).resolve().parent / "golden"


@pytest.mark.parametrize(
    ("name", "rule"),
    [("60-move-cut-pasted-by-pybers", relative), ("60-move-dragged-by-pybers", named)],
)
def testTheMoveGoldensMatchWhatThisLibraryProduces(
    name: str, rule: FormulaReferenceRelocation, tmp_path: Path
) -> None:
    """PYB-18 AC 7: each move again, against the file Numbers confirmed."""
    document, table = openTable("60-move-base")
    table.cellsMove("B2:D5", "F8", references=rule)
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    differences = listPackageDifferences(
        readPackage(goldenDirectory / f"{name}.numbers"), readPackage(target)
    )
    assert [
        difference for difference in differences if difference.identifier is not None
    ] == []


def testAScriptAuthorMovesABlockAndSaves(tmp_path: Path) -> None:
    """The few lines a script writes: open, move, save, and read it back."""
    document = pybers.open(findDocumentPath("61-move-styles-base"))
    document.sheet(1).table("Table 1").cellsMove(
        "B2:D5", "F8", references=FormulaReferenceRelocation.PRESERVE_RELATIVE_POSITION
    )
    document.save(tmp_path / "scripted.numbers")
    table = pybers.open(tmp_path / "scripted.numbers").sheet(1).table("Table 1")
    assert table.cell("G9").value == Decimal("32")


def testACommandLineDragsABlockWithTheRuleAsTyped() -> None:
    """A CLI passes `--references named-cell`, and a formula elsewhere follows."""
    arguments = ["Table 1", "B2:D5", "F8", "named-cell"]
    document = pybers.open(findDocumentPath("60-move-base"))
    table = document.sheet(1).table(arguments[0])
    table.cellsMove(arguments[1], arguments[2], references=arguments[3])  # type: ignore[arg-type]
    assert table.cell("E9").formulaText == "=SUM(F8:H11)"


def testACommandLineMovesABlockWithTheRuleAsTyped() -> None:
    """A CLI passes `--references relative-position` through as the text it read."""
    arguments = ["Table 1", "B2:D5", "F8", "relative-position"]
    document = pybers.open(findDocumentPath("60-move-base"))
    table = document.sheet(1).table(arguments[0])
    stranded = table.cellsMove(arguments[1], arguments[2], references=arguments[3])  # type: ignore[arg-type]
    assert table.cell("H8").formulaText == "=F8+G8"
    assert [
        f"{cell.table.name}::{cell.reference}" for cell in stranded if cell.table
    ] == [
        "Table 1::E2", "Table 1::E3", "Table 1::E4", "Table 1::E5", "Table 1::E8",
        "Table 1::E9", "Table 2::A2", "Table 2::A3",
    ]
