#!/usr/bin/env python3
"""\
A block of cells filled across a range, under the two rules its caller names.

What a fill writes into the model, the records a save duplicates and the entries
they claim, the refusals that leave a table as it was, and the few lines a script
or a command line writes to fill a block.

UPDATES
2026-09-30  Series continued by `CONTINUE_SERIES`, checked against the drag Numbers
            made in `65b-series-dragged`, for PYB-137.
2026-09-29  Written for PYB-118, taking over the fill tests of `formulaFill`, and
            checked against the fills Numbers made in `63*-fill-*`.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/29"

from collections import Counter
from collections.abc import Callable, Iterable
from decimal import Decimal
from pathlib import Path

import pytest
from structurefacts import readTableFacts

import pybers
from conftest import findDocumentPath
from pybers import CellValueFill, FormulaReferenceRelocation
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSPMessages_pb2 as tsp
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import chooseOffsetUnit, decodeRow, readPackage
from pybers._persistence.cells import (
    CellRecord,
    carriesFormula,
    findFormulaKeySlot,
)
from pybers._persistence.difference import listPackageDifferences
from pybers._persistence.index import ArchiveIndex, findRoot
from pybers.addressing.reference import ReferenceError as CellReferenceError
from pybers.table._refcounts import (
    countFormatClaims,
    listStringClaims,
    listStyleClaims,
)

relative = FormulaReferenceRelocation.PRESERVE_RELATIVE_POSITION
named = FormulaReferenceRelocation.PRESERVE_NAMED_CELL
repeat = CellValueFill.REPEAT_SOURCE_VALUE
series = CellValueFill.CONTINUE_SERIES

type Ledger = dict[str, tuple[dict[int, int], Counter[int]]]


def openTable(name: str) -> tuple[pybers.Document, pybers.Table]:
    """Return a fresh copy of a document and the first table of its first sheet."""
    document = pybers.open(findDocumentPath(name))
    return document, document.sheets[0].tables[0]


def readTableState(table: pybers.Table) -> tuple[object, ...]:
    """Return what a refused fill must leave alone: every cell and every merge."""
    return (
        {
            reference: (cell.formulaText or cell.value, cell._copiedFrom)
            for reference, cell in table.cells.items()
        },
        list(table.mergeRanges),
    )


def resolveTableStore(path: Path, tableName: str) -> tuple[ArchiveIndex, tst.DataStore]:
    """Return the index of a saved package and one table's data store in it."""
    index = ArchiveIndex(readPackage(path))
    for sheet in findRoot(index).sheets:
        for drawable in index.resolve(sheet, tn.SheetArchive).drawable_infos:
            info = index.resolve(drawable, tst.TableInfoArchive)
            model = index.resolve(info.tableModel, tst.TableModelArchive)
            if model.table_name == tableName:
                return index, model.base_data_store
    raise AssertionError(f"{tableName!r} is not in {path.name}")


def readRecords(path: Path, tableName: str) -> dict[tuple[int, int], CellRecord]:
    """Return every record of one table by its stored (row, column)."""
    index, store = resolveTableStore(path, tableName)
    records: dict[tuple[int, int], CellRecord] = {}
    for entry in store.tiles.tiles:
        tile = index.resolve(entry.tile, tst.Tile)
        for rowInfo in tile.rowInfos:
            row = entry.tileid * store.tiles.tile_size + rowInfo.tile_row_index
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                records[(row, record.column)] = record
    return records


def listFormulaClaims(record: CellRecord) -> list[int]:
    """Return the formula key a record names, if it carries one."""
    if not carriesFormula(record):
        return []
    return [record.references[findFormulaKeySlot(record)]]


def readLedger(path: Path, tableName: str) -> Ledger:
    """Return, per list, each entry's declared refcount and how often cells name it."""
    index, store = resolveTableStore(path, tableName)
    records = list(readRecords(path, tableName).values())
    lists: dict[str, tuple[tsp.Reference, Callable[[CellRecord], Iterable[int]]]] = {
        "strings": (store.stringTable, listStringClaims),
        "styles": (store.styleTable, listStyleClaims),
        "formats": (
            store.format_table, lambda record: countFormatClaims(record.raw).elements()
        ),
        "formulas": (store.formula_table, listFormulaClaims),
    }
    ledger: Ledger = {}
    for name, (reference, claims) in lists.items():
        declared: dict[int, int] = {}
        if reference.identifier:
            entries = index.resolve(reference, tst.TableDataList).entries
            declared = {int(entry.key): int(entry.refcount) for entry in entries}
        named: Counter[int] = Counter()
        for record in records:
            named.update(claims(record))
        ledger[name] = (declared, named)
    return ledger


def assertClaimsCounted(before: Ledger, after: Ledger) -> None:
    """Assert every refcount moved by exactly as much as the cells naming it moved."""
    for name, (declaredAfter, namedAfter) in after.items():
        declaredBefore, namedBefore = before[name]
        for key in set(declaredAfter) | set(declaredBefore):
            declaredChange = declaredAfter.get(key, 0) - declaredBefore.get(key, 0)
            namedChange = namedAfter[key] - namedBefore[key]
            assert declaredChange == namedChange, (name, key)


def fillAndSave(
    name: str, source: str, through: str, rule: FormulaReferenceRelocation,
    target: Path,
) -> None:
    """Fill a block of a document's first table and save it to `target`."""
    document, table = openTable(name)
    table.cellsFill(source, through, references=rule, values=repeat)
    document.save(target)


def testAFillNamingNoReferenceRuleIsATypeError() -> None:
    """PYB-118 AC 1: the reference rule has no default, so leaving it out cannot run."""
    _, table = openTable("20-formula-shapes")
    with pytest.raises(TypeError, match="references"):
        table.cellsFill("A11", "A11:D11", values=repeat)  # type: ignore[call-arg]


def testAFillNamingNoValueRuleIsATypeError() -> None:
    """PYB-118 AC 1: the value rule has no default either."""
    _, table = openTable("20-formula-shapes")
    with pytest.raises(TypeError, match="values"):
        table.cellsFill("A11", "A11:D11", references=relative)  # type: ignore[call-arg]


def testARelativeFillSharesOneStoredFormula(tmp_path: Path) -> None:
    """PYB-118 AC 2: four cells, one entry, each resolving against its own column."""
    target = tmp_path / "relative.numbers"
    fillAndSave("20-formula-shapes", "A11", "A11:D11", relative, target)
    table = pybers.open(target).sheets[0].tables[0]
    for reference, expected in (("A11", "A1:A10"), ("B11", "B1:B10"),
                                ("C11", "C1:C10"), ("D11", "D1:D10")):
        cell = table.cell(reference)
        assert cell.formula is not None
        assert str(cell.formula.ranges[0].resolve(cell.reference)) == expected
    records = readRecords(target, "Table 1")
    keys = {listFormulaClaims(records[(10, column)])[0] for column in range(4)}
    assert len(keys) == 1


def testARelativeFillKeepsEachLockedAxis() -> None:
    """PYB-118 AC 2: `$B2` keeps column B and follows the row it lands in."""
    _, table = openTable("60-move-base")
    table.cellsFill("D3", "D3:F4", references=relative, values=repeat)
    assert table.cell("D4").formulaText == "=$B3"
    assert table.cell("F3").formulaText == "=$B2"
    assert table.cell("F4").formulaText == "=$B3"


def testANamedCellFillNamesTheSourceCellsFromEveryCell() -> None:
    """PYB-118 AC 3: every filled cell reads exactly what the source reads."""
    _, table = openTable("60-move-base")
    table.cellsFill("D2", "D2:F4", references=named, values=repeat)
    for name in ("D3", "D4", "E2", "F4"):
        assert table.cell(name).formulaText == "=B2+C2", name


def testANamedCellFillGivesEachCellAFormulaOfItsOwn(tmp_path: Path) -> None:
    """PYB-118 AC 3: the stored formulas differ per cell, and read back unchanged."""
    target = tmp_path / "named.numbers"
    fillAndSave("60-move-base", "D2", "D2:D4", named, target)
    table = pybers.open(target).sheet(1).table("Table 1")
    assert [table.cell(name).formulaText for name in ("D2", "D3", "D4")] == [
        "=B2+C2", "=B2+C2", "=B2+C2"
    ]
    records = readRecords(target, "Table 1")
    keys = [listFormulaClaims(records[(row, 3)])[0] for row in (1, 2, 3)]
    assert len(set(keys)) == 3


def testAFillSkipsWhatAMergeCoversAndCountsWhatItFilled() -> None:
    """PYB-118 AC 4: `C5` is covered by `B5:C5`, so three of four positions fill."""
    _, table = openTable("60-move-base")
    assert table.cellsFill("E1", "A5:D5", references=relative, values=repeat) == 4 - 1
    assert table.cell("B5").value == Decimal(7)
    assert pybers.CellReference.parse("C5") not in table.cells


@pytest.mark.parametrize(
    ("fill", "message"),
    [
        (lambda table: table.cellsFill(
            "D3", "D3:D13", references=relative, values=repeat), "reaches outside"),
        (lambda table: table.cellsFill(
            "B5:C5", "B6:C7", references=relative, values=repeat), "a fill copies no"),
        (lambda table: table.cellsFill(
            "A:A", "B1:B3", references=relative, values=repeat), "unbounded"),
        (lambda table: table.cellsFill(
            "D3", "D4", references="sideways", values=repeat), "not a reference rule"),
        (lambda table: table.cellsFill(
            "D3", "D4", references=relative, values="upward"), "not a value rule"),
        (lambda table: table.cellsFill(
            "A2:A3", "A4:B4", references=relative, values=series), "asks for both"),
    ],
)
def testARefusedFillLeavesTheTableAsItWas(
    fill: Callable[[pybers.Table], object], message: str
) -> None:
    """PYB-118 AC 5 and 9: outside the grid, a merge, unbounded, and each bad rule."""
    _, table = openTable("60-move-base")
    before = readTableState(table)
    with pytest.raises(CellReferenceError, match=message):
        fill(table)
    assert readTableState(table) == before


def testABlockRepeatsFromItsOwnCorner() -> None:
    """PYB-118 AC 7: each filled cell takes the block cell at the matching position."""
    _, table = openTable("61-move-styles-base")
    assert table.cellsFill("B2:D3", "A1:H7", references=relative, values=repeat) == (
        7 * 8 - 6
    )
    assert [str(table.cell(name).value) for name in ("F6", "H7", "A1", "B4")] == [
        "22", "31", "33", "21"
    ]


def testAFilledRecordIsTheRecordItCopied(tmp_path: Path) -> None:
    """PYB-118 AC 7: a fill, a bold face and highlighting fill with their values."""
    target = tmp_path / "styles.numbers"
    fillAndSave("61-move-styles-base", "B2:D3", "B2:H7", relative, target)
    base = readRecords(findDocumentPath("61-move-styles-base"), "Table 1")
    ours = readRecords(target, "Table 1")
    for row in range(1, 7):
        for column in range(1, 8):
            source = (1 + (row - 1) % 2, 1 + (column - 1) % 3)
            assert ours[(row, column)].raw == base[source].raw, (row, column)


@pytest.mark.parametrize(
    ("name", "source", "through", "rule"),
    [
        ("61-move-styles-base", "B2:D3", "B2:H7", relative),
        ("20-formula-shapes", "A11", "A11:H11", relative),
        ("20-formula-shapes", "A11", "A11:D11", named),
        ("20-formula-shapes", "A12", "A12:C12", relative),
        ("60-move-base", "D2:E4", "D2:H4", named),
    ],
)
def testEveryEntryAFillNamesIsCounted(
    name: str, source: str, through: str, rule: FormulaReferenceRelocation,
    tmp_path: Path,
) -> None:
    """PYB-118 AC 7: strings, styles, formats and formulas claimed and released."""
    target = tmp_path / "counted.numbers"
    fillAndSave(name, source, through, rule, target)
    assertClaimsCounted(
        readLedger(findDocumentPath(name), "Table 1"), readLedger(target, "Table 1")
    )


def testRepeatedValuesReadBackExactly(tmp_path: Path) -> None:
    """PYB-118 AC 8: a number and a text fill read back equal to their sources."""
    document, table = openTable("20-formula-shapes")
    table.cellsFill("A12", "A12:C12", references=relative, values=repeat)
    table.cellsFill("A10", "A10:C10", references=relative, values=repeat)
    target = tmp_path / "values.numbers"
    document.save(target)
    saved = pybers.open(target).sheets[0].tables[0]
    assert [saved.cell(name).value for name in ("B10", "C10")] == [Decimal("10")] * 2
    assert [saved.cell(name).value for name in ("B12", "C12")] == [
        "Typed directly: SUM(A1:A10)"
    ] * 2


def testFillingFromAnEmptyCellEmptiesTheRange(tmp_path: Path) -> None:
    """A source holding nothing leaves each filled position holding nothing."""
    target = tmp_path / "emptied.numbers"
    fillAndSave("61-move-styles-base", "F2", "B2:D2", relative, target)
    assert not {(1, 1), (1, 2), (1, 3)} & readRecords(target, "Table 1").keys()
    assertClaimsCounted(
        readLedger(findDocumentPath("61-move-styles-base"), "Table 1"),
        readLedger(target, "Table 1"),
    )


def testAFillFromAFilledCellCopiesWhatThatCellCopied(tmp_path: Path) -> None:
    """Two fills before a save write what one fill from the first source writes."""
    document, table = openTable("61-move-styles-base")
    table.cellsFill("C2", "F2", references=relative, values=repeat)
    table.cellsFill("F2", "G2:H2", references=relative, values=repeat)
    target = tmp_path / "chained.numbers"
    document.save(target)
    records = readRecords(target, "Table 1")
    assert records[(1, 6)].raw == records[(1, 7)].raw == records[(1, 2)].raw


def testASecondSaveAfterAFillChangesNothing(tmp_path: Path) -> None:
    """A filled cell forgets its source once saved, so saving again copies nothing."""
    document, table = openTable("61-move-styles-base")
    table.cellsFill("B2:D3", "B2:H7", references=relative, values=repeat)
    first, second = tmp_path / "first.numbers", tmp_path / "second.numbers"
    document.save(first)
    document.save(second)
    differences = listPackageDifferences(readPackage(first), readPackage(second))
    assert [
        difference for difference in differences if difference.identifier is not None
    ] == []


def testAFillAfterARowIsAddedCopiesTheShiftedRecord(tmp_path: Path) -> None:
    """A structural edit before the fill moves the source, and the copy follows it."""
    document, table = openTable("20-formula-shapes")
    table.rowAdd(1)
    table.cellsFill("A13", "B13", references=relative, values=repeat)
    target = tmp_path / "shifted.numbers"
    document.save(target)
    records = readRecords(target, "Table 1")
    assert records[(12, 1)].raw == records[(12, 0)].raw
    saved = pybers.open(target).sheets[0].tables[0]
    assert saved.cell("B13").value == "Typed directly: SUM(A1:A10)"


def testAFillWhoseSourceWasRemovedIsRefusedAtSave(tmp_path: Path) -> None:
    """Removing the source row before saving leaves no record to copy, so none is."""
    document, table = openTable("20-formula-shapes")
    table.cellsFill("A11", "A12", references=relative, values=repeat)
    table.rowRemove(11)
    target = tmp_path / "orphaned.numbers"
    with pytest.raises(pybers.WriteError, match="no longer in"):
        document.save(target)
    assert not target.exists()


def readListCounts(path: Path, listName: str) -> list[tuple[int, int]]:
    """Return one of a table's data lists as (key, refcount) pairs."""
    index, store = resolveTableStore(path, "Table 1")
    entries = index.resolve(getattr(store, listName), tst.TableDataList).entries
    return [(int(entry.key), int(entry.refcount)) for entry in entries]


def testAFillWritesTheRecordsNumbersDragWrote(tmp_path: Path) -> None:
    """Columns B and D, which Numbers repeated rather than continued, match `63e`."""
    target = tmp_path / "dragged.numbers"
    fillAndSave("63d-fill-border-base", "B2:D3", "B2:D7", relative, target)
    theirs = findDocumentPath("63e-fill-border-dragged-down")
    ours, measured = readRecords(target, "Table 1"), readRecords(theirs, "Table 1")
    for row in range(1, 7):
        for column in (1, 3):
            assert ours[(row, column)].raw == measured[(row, column)].raw, (row, column)
    assert readTableFacts(target)["Table 1"]["strokes"] == (
        readTableFacts(theirs)["Table 1"]["strokes"]
    )
    for listName in ("rich_text_table", "control_cell_spec_table", "styleTable"):
        assert readListCounts(target, listName) == readListCounts(theirs, listName)


def testATopRowFillWritesWhatNumbersMenuFillWrote(tmp_path: Path) -> None:
    """Numbers' Autofill Down repeats the top row over row 3, as `63b` measured."""
    target = tmp_path / "menu.numbers"
    fillAndSave("63-fill-base", "B2:D2", "B2:D7", relative, target)
    theirs = findDocumentPath("63b-fill-menu-down")
    assert {position: record.raw for position, record in readRecords(
        target, "Table 1").items()} == {
        position: record.raw for position, record in readRecords(
            theirs, "Table 1").items()
    }
    for listName in ("rich_text_table", "control_cell_spec_table", "styleTable"):
        assert readListCounts(target, listName) == readListCounts(theirs, listName)


def testAnOverwrittenRichTextCellTakesItsArchivesWithIt(tmp_path: Path) -> None:
    """The payload, storage and four character styles Numbers removed in `63b`."""
    target = tmp_path / "menu.numbers"
    fillAndSave("63-fill-base", "B2:D2", "B2:D7", relative, target)
    held = set(resolveTableStore(findDocumentPath("63-fill-base"), "Table 1")[0]
               .byIdentifier)
    kept = set(resolveTableStore(target, "Table 1")[0].byIdentifier)
    assert sorted(held - kept) == [909660, 909661, 909662, 909663, 909664, 909720]


def testACopiedRichTextCellHasAPayloadOfItsOwn(tmp_path: Path) -> None:
    """Each copy of `B3` names a payload and a storage no other cell names."""
    target = tmp_path / "rich.numbers"
    fillAndSave("63-fill-base", "B3", "B3:B5", relative, target)
    index, store = resolveTableStore(target, "Table 1")
    entries = index.resolve(store.rich_text_table, tst.TableDataList).entries
    payloads = [
        index.resolve(entry.rich_text_payload, tst.RichTextPayloadArchive)
        for entry in entries
    ]
    assert len({entry.rich_text_payload.identifier for entry in entries}) == 3
    assert len({payload.storage.identifier for payload in payloads}) == 3
    saved = pybers.open(target).sheets[0].tables[0]
    assert [saved.cell(name).value for name in ("B4", "B5")] == ["Hello", "Hello"]


def testAFillOverACheckboxReleasesItsControl(tmp_path: Path) -> None:
    """`D3` is the one cell naming its control, so Numbers removes it, as in `63b`."""
    target = tmp_path / "unchecked.numbers"
    fillAndSave("63-fill-base", "D2", "D2:D3", relative, target)
    assert readListCounts(target, "control_cell_spec_table") == []


def testCopyingARecordNamingAnUnidentifiedEntryIsRefused(tmp_path: Path) -> None:
    """`B10` names an entry through byte 9 bit 0x08, whose count nobody knows."""
    document, table = openTable("46-formula-rare-functions")
    table.cellsFill("B10", "C10", references=relative, values=repeat)
    target = tmp_path / "unidentified.numbers"
    with pytest.raises(pybers.WriteError, match="not identified"):
        document.save(target)
    assert not target.exists()


goldenDirectory: Path = Path(__file__).resolve().parent / "golden"


@pytest.mark.parametrize(
    ("name", "base", "source", "through", "rule"),
    [
        ("20-cells-filled-relative-by-pybers", "20-formula-shapes", "A11", "A11:D11",
         relative),
        ("20-cells-filled-named-by-pybers", "20-formula-shapes", "A11", "A11:D11",
         named),
        ("61-cells-filled-by-pybers", "61-move-styles-base", "B2:D3", "B2:H7",
         relative),
        ("63-cells-filled-by-pybers", "63d-fill-border-base", "B2:D3", "B2:D7",
         relative),
    ],
)
def testTheFillGoldensMatchWhatThisLibraryProduces(
    name: str, base: str, source: str, through: str,
    rule: FormulaReferenceRelocation, tmp_path: Path,
) -> None:
    """PYB-118 AC 6: each fill again, against the file Numbers confirmed."""
    target = tmp_path / f"{name}.numbers"
    fillAndSave(base, source, through, rule, target)
    differences = listPackageDifferences(
        readPackage(goldenDirectory / f"{name}.numbers"), readPackage(target)
    )
    assert [
        difference for difference in differences if difference.identifier is not None
    ] == []


def testTheFillGoldensHoldWhatTheyClaimTo() -> None:
    """Guard the guard: a golden replaced by an unedited copy would pass above."""
    relativeTable = pybers.open(
        goldenDirectory / "20-cells-filled-relative-by-pybers.numbers"
    ).sheets[0].tables[0]
    assert relativeTable.cell("D11").formulaText == "=SUM(D1:D10)"
    namedTable = pybers.open(
        goldenDirectory / "20-cells-filled-named-by-pybers.numbers"
    ).sheets[0].tables[0]
    assert namedTable.cell("D11").formulaText == "=SUM(A1:A10)"
    styled = pybers.open(
        goldenDirectory / "61-cells-filled-by-pybers.numbers"
    ).sheets[0].tables[0]
    assert styled.cell("H7").value == Decimal(31)
    dragged = pybers.open(
        goldenDirectory / "63-cells-filled-by-pybers.numbers"
    ).sheets[0].tables[0]
    assert [dragged.cell(name).value for name in ("B5", "D7")] == ["Hello", True]


def testFormulaFillNoLongerExists() -> None:
    """PYB-118 AC 10: one fill, for any content, and nothing kept beside it."""
    assert not hasattr(pybers.Table, "formulaFill")


def testAScriptAuthorFillsABlockAndSaves(tmp_path: Path) -> None:
    """The few lines a script writes: open, fill, save, and read it back."""
    document = pybers.open(findDocumentPath("61-move-styles-base"))
    document.sheet(1).table("Table 1").cellsFill(
        "B2:D2", "B2:D5",
        references=FormulaReferenceRelocation.PRESERVE_RELATIVE_POSITION,
        values=CellValueFill.REPEAT_SOURCE_VALUE,
    )
    document.save(tmp_path / "scripted.numbers")
    table = pybers.open(tmp_path / "scripted.numbers").sheet(1).table("Table 1")
    assert table.cell("C5").value == Decimal("22")


def testACommandLineFillsWithTheRulesAsTyped() -> None:
    """A CLI passes `--references named-cell --values source-value` as it read them."""
    arguments = ["Table 1", "D2", "D2:D4", "named-cell", "source-value"]
    document = pybers.open(findDocumentPath("60-move-base"))
    table = document.sheet(1).table(arguments[0])
    filled = table.cellsFill(
        arguments[1], arguments[2],
        references=arguments[3],  # type: ignore[arg-type]
        values=arguments[4],  # type: ignore[arg-type]
    )
    assert filled == 2
    assert table.cell("D4").formulaText == "=B2+C2"


seedRows: dict[str, int] = {"D": 4}
seededColumns: str = "ABCDEFGHIJKLMN"


def readColumnValues(table: pybers.Table, column: str, last: int) -> list[object]:
    """Return a column's values from row 2 down to `last`."""
    return [table.cell(f"{column}{row}").value for row in range(2, last + 1)]


def testADragOfEveryColumnIsWhatCellsFillProducesUnderSeries(tmp_path: Path) -> None:
    """PYB-137 AC 2: each column of `65b` equals its seeds filled, saved and read."""
    document, table = openTable("65-series-base")
    for column in seededColumns:
        seeds = seedRows.get(column, 3)
        table.cellsFill(
            f"{column}2:{column}{seeds}", f"{column}{seeds + 1}:{column}17",
            references=relative, values=series,
        )
    target = tmp_path / "series.numbers"
    document.save(target)
    saved = pybers.open(target).sheets[0].tables[0]
    dragged = pybers.open(findDocumentPath("65b-series-dragged")).sheets[0].tables[0]
    for column in seededColumns:
        assert readColumnValues(saved, column, 17) == readColumnValues(
            dragged, column, 17
        ), column


def testASeriesFillContinuesAColumnBesideOneThatRepeats() -> None:
    """A block continues the columns that begin a series and repeats the rest."""
    _, table = openTable("65-series-base")
    table.cellsFill("A2:B3", "A4:B5", references=relative, values=series)
    table.cellsFill("I2:J3", "I4:J5", references=relative, values=series)
    assert [table.cell(name).value for name in ("A5", "B5", "I5", "J5")] == [
        Decimal("4"), Decimal("40"), "April", "Item 4"
    ]


def testASeriesFillFromAColumnBeginningNoSeriesRepeatsTheBlock() -> None:
    """`1, 2, 4` and `alpha, beta` begin no series, which the drag repeated whole."""
    _, table = openTable("65-series-base")
    table.cellsFill("D2:D4", "D5:D7", references=relative, values=series)
    table.cellsFill("N2:N3", "N4:N7", references=relative, values=series)
    assert readColumnValues(table, "D", 7) == [Decimal(n) for n in (1, 2, 4, 1, 2, 4)]
    assert readColumnValues(table, "N", 7) == ["alpha", "beta"] * 3


def testAFormulaInASeriesSourceFillsAsItDoesWhenRepeated() -> None:
    """PYB-137 AC 3: a column holding a formula repeats, under either reference rule."""
    for rule in FormulaReferenceRelocation:
        _, repeated = openTable("60-move-base")
        _, continued = openTable("60-move-base")
        repeated.cellsFill("B2:D3", "B4:D4", references=rule, values=repeat)
        continued.cellsFill("B2:D3", "B4:D4", references=rule, values=series)
        for name in ("B4", "C4", "D4"):
            assert continued.cell(name).formulaText == repeated.cell(name).formulaText
            assert continued.cell(name).value == repeated.cell(name).value


def testAScriptContinuesRowNumbersDownAColumn() -> None:
    """A script numbering rows names the rule as a string, as a command line would."""
    document = pybers.open(findDocumentPath("65-series-base"))
    table = document.sheets[0].tables[0]
    filled = table.cellsFill(
        "A2:A3", "A4:A12",
        references="relative-position",  # type: ignore[arg-type]
        values="series",  # type: ignore[arg-type]
    )
    assert filled == 9
    assert table.cell("A12").value == Decimal("11")


directionDocuments: dict[str, str] = {
    "down": "66b-series-down", "up": "66c-series-up",
    "right": "66d-series-right", "left": "66e-series-left",
}


def findSeedCount(index: int) -> int:
    """Return how many seeds case `index` of the `66` bases holds."""
    return 3 if index == 2 else 1 if index >= 15 else 2


def fillCase(table: pybers.Table, direction: str, index: int) -> None:
    """Fill one case of a `66` base the way its drag was made."""
    count = findSeedCount(index)
    if direction in ("down", "up"):
        letter = chr(65 + index)
        source = f"{letter}10:{letter}{9 + count}"
        through = (
            f"{letter}{10 + count}:{letter}21" if direction == "down"
            else f"{letter}2:{letter}9"
        )
    else:
        row = index + 1
        source = f"J{row}:{chr(73 + count)}{row}"
        through = (
            f"{chr(74 + count)}{row}:U{row}" if direction == "right"
            else f"B{row}:I{row}"
        )
    table.cellsFill(source, through, references=relative, values=series)


@pytest.mark.parametrize("direction", ["down", "up", "right", "left"])
def testAFillInEachDirectionIsWhatNumbersDragged(
    direction: str, tmp_path: Path
) -> None:
    """PYB-137 AC 2: all twenty cases of `66b` to `66e` equal their seeds filled."""
    base = (
        "66-series-vertical-base" if direction in ("down", "up")
        else "66-series-horizontal-base"
    )
    document, table = openTable(base)
    for index in range(20):
        fillCase(table, direction, index)
    target = tmp_path / "series.numbers"
    document.save(target)
    saved = pybers.open(target).sheets[0].tables[0]
    dragged = pybers.open(findDocumentPath(directionDocuments[direction]))
    dragged = dragged.sheets[0].tables[0]
    for index in range(20):
        if direction in ("down", "up"):
            names = [f"{chr(65 + index)}{row}" for row in range(2, 22)]
        else:
            names = [f"{chr(65 + column)}{index + 1}" for column in range(1, 21)]
        assert [saved.cell(name).value for name in names] == [
            dragged.cell(name).value for name in names
        ], (direction, index)


def testAFillOfThreeSeedsAndOfRichTextIsWhatNumbersDragged(tmp_path: Path) -> None:
    """PYB-137 AC 2: `67b` repeats rich text and continues three seeds, types too."""
    document, table = openTable("67-series-rich-base")
    seedCounts = {
        "A": 2, "B": 1, "C": 2, "D": 3, "E": 3, "F": 3, "G": 3, "H": 3,
    }
    for letter, count in seedCounts.items():
        table.cellsFill(
            f"{letter}2:{letter}{1 + count}", f"{letter}{2 + count}:{letter}13",
            references=relative, values=series,
        )
    target = tmp_path / "rich.numbers"
    document.save(target)
    saved = pybers.open(target).sheets[0].tables[0]
    dragged_path = findDocumentPath("67b-series-rich-dragged")
    dragged = pybers.open(dragged_path).sheets[0].tables[0]
    savedRecords = readRecords(target, saved.name)
    draggedRecords = readRecords(dragged_path, dragged.name)
    for row in range(2, 14):
        for column, letter in enumerate("ABCDEFGH"):
            assert saved.cell(f"{letter}{row}").value == dragged.cell(
                f"{letter}{row}"
            ).value, (letter, row)
            assert (
                savedRecords[(row - 1, column)].typeByte
                == draggedRecords[(row - 1, column)].typeByte
            ), (letter, row)


seedCountsByColumn: dict[str, int] = {
    "A": 2, "B": 1, "C": 2, "D": 3, "E": 3, "F": 3, "G": 3, "H": 3,
}


def fillSeriesGolden(name: str, target: Path) -> None:
    """Fill a series golden's base the way the golden was made, and save it."""
    if name.startswith("67"):
        document, table = openTable("67-series-rich-base")
        for letter, count in seedCountsByColumn.items():
            table.cellsFill(
                f"{letter}2:{letter}{1 + count}", f"{letter}{2 + count}:{letter}13",
                references=relative, values=series,
            )
    else:
        direction = name.split("-")[3]
        document, table = openTable(
            "66-series-vertical-base" if direction in ("down", "up")
            else "66-series-horizontal-base"
        )
        for index in range(20):
            fillCase(table, direction, index)
    document.save(target)


@pytest.mark.parametrize(
    "name",
    [
        "66-series-filled-down-by-pybers",
        "66-series-filled-up-by-pybers",
        "66-series-filled-right-by-pybers",
        "66-series-filled-left-by-pybers",
        "67-series-filled-by-pybers",
    ],
)
def testTheSeriesGoldensMatchWhatThisLibraryProduces(
    name: str, tmp_path: Path
) -> None:
    """PYB-137 AC 4: each series fill again, against the file to be confirmed."""
    target = tmp_path / f"{name}.numbers"
    fillSeriesGolden(name, target)
    differences = listPackageDifferences(
        readPackage(goldenDirectory / f"{name}.numbers"), readPackage(target)
    )
    assert [
        difference for difference in differences if difference.identifier is not None
    ] == []


def testTheSeriesGoldensHoldWhatTheyClaimTo() -> None:
    """Guard the guard: an unfilled copy of a base would pass the match above."""
    down, up, right, left = (
        pybers.open(
            goldenDirectory / f"66-series-filled-{direction}-by-pybers.numbers"
        ).sheets[0].tables[0]
        for direction in ("down", "up", "right", "left")
    )
    assert [down.cell("A21").value, up.cell("A2").value] == [
        Decimal("12"), Decimal("-7")
    ]
    assert [right.cell("U1").value, left.cell("B1").value] == [
        Decimal("12"), Decimal("-7")
    ]
    assert down.cell("I21").value == "Friday"
    rich = pybers.open(
        goldenDirectory / "67-series-filled-by-pybers.numbers"
    ).sheets[0].tables[0]
    assert [rich.cell(name).value for name in ("A13", "D13", "G13")] == [
        "Item 2", Decimal("23"), "Item 23"
    ]


def testAFilledCopyOfRichTextStillRepeatsWhenFilledAsASeries() -> None:
    """PYB-137: a copy of rich text is rich text, so its series fill still repeats."""
    _, table = openTable("67-series-rich-base")
    table.cellsFill("A2:A3", "A4:A5", references=relative, values=repeat)
    table.cellsFill("A4:A5", "A6:A7", references=relative, values=series)
    assert readColumnValues(table, "A", 7)[2:] == ["Item 1", "Item 2"] * 2


def testRichTextOverwrittenWithPlainTextContinuesAsASeries() -> None:
    """PYB-137: a cell holds rich text only while its value is still that text."""
    _, table = openTable("67-series-rich-base")
    table.cell("A2").value = "Thing 1"
    table.cell("A3").value = "Thing 2"
    table.cellsFill("A2:A3", "A4:A5", references=relative, values=series)
    assert readColumnValues(table, "A", 5) == [
        "Thing 1", "Thing 2", "Thing 3", "Thing 4"
    ]
