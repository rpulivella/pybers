#!/usr/bin/env python3
"""\
A pooled entry's refcount against the cells that name it, before and after a save.

Counts are read from the format list and from the cell records separately, so a test
compares what the file declares with what its cells actually reference rather than
asking the model, which would agree with itself while both halves were wrong.

UPDATES
2026-09-15  Written for PYB-89, with the kind a cell displays with for its AC 7,
            spent formats and merges for its AC 9 and 10. Strings and styles
            a merge removes, and spent strings, for PYB-92, with formulas and
            rich text for its AC 5.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/15"

from collections import Counter
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest
from test_formula_nodes import formulaCellRegister
from test_writer import archiveDifferences, recordAt, retypedCells, workingCopy

import pybers
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import CellRecord, decodeRecord, readPackage, writePackage
from pybers._persistence.cells import (
    carriesFormula,
    decodeRow,
    formulaKeySlot,
    offsetUnitFor,
)
from pybers._persistence.index import ArchiveIndex, findRoot, tableInfoTypeId
from pybers.errors import WriteError
from pybers.table._write import (
    borrowedShape,
    countedFormatSlots,
    countedStyleSlots,
    displayedKindSlot,
    formatClaims,
    referenceSlots,
    richTextClaims,
    stringClaims,
    textFormatSlot,
)

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"
goldenDirectory: Path = Path(__file__).resolve().parent / "golden"

numberFormatType: int = 256
textFormatType: int = 260
dateFormatType: int = 261
starRatingFormatType: int = 267


def tableModels(path: Path) -> list[tuple[ArchiveIndex, tst.TableModelArchive]]:
    """Return every table model in a package, with the index that resolves it."""
    index = ArchiveIndex(readPackage(path))
    return [
        (index, index.resolve(
            index.resolve(drawable, tst.TableInfoArchive).tableModel,
            tst.TableModelArchive,
        ))
        for sheet in findRoot(index).sheets
        for drawable in index.resolve(sheet, tn.SheetArchive).drawable_infos
        if index.typeOf(drawable) == tableInfoTypeId
    ]


def tableRecords(
    index: ArchiveIndex, model: tst.TableModelArchive
) -> list[CellRecord]:
    """Return every cell record one table stores, read from its tiles."""
    store = model.base_data_store
    records: list[CellRecord] = []
    for entry in store.tiles.tiles:
        tile = index.resolve(entry.tile, tst.Tile)
        for rowInfo in tile.rowInfos:
            unit = offsetUnitFor(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            records.extend(decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ))
    return records


def cellClaims(index: ArchiveIndex, model: tst.TableModelArchive) -> Counter[int]:
    """Return how often this table's cells name each format."""
    counted: Counter[int] = Counter()
    for record in tableRecords(index, model):
        counted.update(formatClaims(record.raw))
    return counted


def displayedKind(record: CellRecord) -> tuple[int | None, set[int]]:
    """Return the kind a record displays with, and the kinds of the slots it holds."""
    named = dict(zip(referenceSlots(record.raw), record.references, strict=True))
    held = {
        position + 1 for position, slot in enumerate(countedFormatSlots)
        if slot in named
    }
    return named.get(displayedKindSlot), held


def formatLedger(path: Path, tableName: str) -> tuple[dict[int, int], Counter[int]]:
    """Return one table's declared format refcounts and what its cells name."""
    for index, model in tableModels(path):
        if model.table_name != tableName:
            continue
        formats = index.resolve(model.base_data_store.format_table, tst.TableDataList)
        declared = {int(entry.key): int(entry.refcount) for entry in formats.entries}
        return declared, cellClaims(index, model)
    raise AssertionError(f"{tableName!r} is not in {path.name}")


def formatKeyOfType(path: Path, tableName: str, formatType: int) -> int:
    """Return the key of the first format entry of this kind in one table."""
    for index, model in tableModels(path):
        if model.table_name != tableName:
            continue
        formats = index.resolve(model.base_data_store.format_table, tst.TableDataList)
        for entry in formats.entries:
            if entry.HasField("format") and entry.format.format_type == formatType:
                return int(entry.key)
    raise AssertionError(f"{tableName!r} in {path.name} holds no {formatType} format")


def dataListForge(
    path: Path,
    tableName: str,
    change: Callable[[tst.TableDataList], None],
    listName: str = "format_table",
) -> None:
    """Rewrite one of a table's data lists in a working copy, as a disagreeing file."""
    package = readPackage(path)
    index = ArchiveIndex(package)
    for _, model in tableModels(path):
        if model.table_name != tableName:
            continue
        reference = getattr(model.base_data_store, listName)
        formats = index.resolve(reference, tst.TableDataList)
        change(formats)
        owner = next(
            iwaFile for iwaFile in package.iwaFiles
            if any(archive.identifier == reference.identifier
                   for archive in iwaFile.archives)
        )
        owner.messageReplace(reference.identifier, 0, formats.SerializeToString())
        writePackage(package, path)
        return
    raise AssertionError(f"{tableName!r} is not in {path.name}")


def test_theCountedSlotsReproduceEveryFormatRefcountNumbersWrote() -> None:
    """The measurement the counting rests on, run over every table in the fixtures."""
    checked = 0
    for path in sorted(fixtureDirectory.glob("*.numbers")):
        for index, model in tableModels(path):
            if not model.base_data_store.format_table.identifier:
                continue
            formats = index.resolve(
                model.base_data_store.format_table, tst.TableDataList
            )
            declared = {
                int(entry.key): int(entry.refcount) for entry in formats.entries
            }
            counted = cellClaims(index, model)
            assert {key: counted[key] for key in declared} == declared, (
                f"{path.name} / {model.table_name}"
            )
            checked += 1
    assert checked >= 89


def test_everyRecordNumbersWroteDisplaysAKindItHolds() -> None:
    """AC 7's measurement: byte 9 `0x10` is a position among the slots a record holds.

    `11-value-types-noformats` keys its number and text formats 1 and 5, the same
    numbers as their kinds, so only a file keyed otherwise tells a kind from a key.
    """
    checked = 0
    for path in sorted(fixtureDirectory.glob("*.numbers")):
        for index, model in tableModels(path):
            for record in tableRecords(index, model):
                kind, held = displayedKind(record)
                if kind is None:
                    continue
                assert kind in held, f"{path.name} / {model.table_name} {record.column}"
                checked += 1
    assert checked >= 11581


def test_textWrittenIntoSeveralCellsCountsEachOne(tmp_path: Path) -> None:
    """AC 1. Two numbers retyped and one empty cell, three references in one save."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    textKey = formatKeyOfType(working, "Table 1", textFormatType)
    before, _ = formatLedger(working, "Table 1")
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    table.cell("A1").value = "first"
    table.cell("B1").value = "second"
    table.cell("J1").value = "third"
    document.save()

    after, claims = formatLedger(working, "Table 1")
    assert after[textKey] == before[textKey] + 3
    assert after[textKey] == claims[textKey]


def test_theFirstTextInATableCountsEveryCellItReaches(tmp_path: Path) -> None:
    """AC 1, where the text format entry is created by the same save."""
    working = workingCopy("20-formula-shapes", tmp_path)
    document = pybers.open(working)
    table = document.sheet("Sheet 1").table("Table 2")
    for address in ("B1", "C1", "A3"):
        table.cell(address).value = f"text at {address}"
    document.save()

    textKey = formatKeyOfType(working, "Table 2", textFormatType)
    declared, claims = formatLedger(working, "Table 2")
    assert declared[textKey] == 3
    assert declared == {key: claims[key] for key in declared}


def test_numbersWrittenIntoACreatedTableCountEachOne(tmp_path: Path) -> None:
    """AC 2. A created table has no record to borrow, so every cell is built fresh."""
    working = workingCopy("20-formula-shapes", tmp_path)
    document = pybers.open(working)
    table = document.sheetAdd("Fresh").tableAdd("Output", rows=4, cols=3)
    table.cell("A1").value = Decimal("1")
    table.cell("B2").value = Decimal("2.5")
    table.cell("C3").value = Decimal("-3")
    document.save()

    numberKey = formatKeyOfType(working, "Output", numberFormatType)
    declared, claims = formatLedger(working, "Output")
    assert declared[numberKey] == 3
    assert declared == {key: claims[key] for key in declared}


def test_aNumberBecomingTextReleasesItsNumberFormat(tmp_path: Path) -> None:
    """AC 3.i. `A1` shows a plain number and `F1` a star rating, each its only user."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    numberKey = formatKeyOfType(working, "Table 1", numberFormatType)
    starKey = formatKeyOfType(working, "Table 1", starRatingFormatType)
    before, _ = formatLedger(working, "Table 1")
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    table.cell("A1").value = "was a number"
    table.cell("F1").value = "was a star rating"
    document.save()

    after, _ = formatLedger(working, "Table 1")
    assert after[numberKey] == before[numberKey] - 1
    assert before[starKey] == 1
    assert starKey not in after, "released to 0, so removed as Numbers removes it"


def test_textBecomingANumberReleasesTheTextFormat(tmp_path: Path) -> None:
    """AC 3.ii. `A2` is a label, and the number format gains what the text loses."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    numberKey = formatKeyOfType(working, "Table 1", numberFormatType)
    textKey = formatKeyOfType(working, "Table 1", textFormatType)
    before, _ = formatLedger(working, "Table 1")
    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A2").value = Decimal("12")
    document.save()

    after, _ = formatLedger(working, "Table 1")
    assert after[textKey] == before[textKey] - 1
    assert after[numberKey] == before[numberKey] + 1


def test_aFormatNoWrittenCellNamesKeepsTheCountItHad(tmp_path: Path) -> None:
    """AC 4. A date count forged to disagree with its one cell is left disagreeing."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    dateKey = formatKeyOfType(working, "Table 1", dateFormatType)

    def dateCountForge(formats: tst.TableDataList) -> None:
        for entry in formats.entries:
            if entry.key == dateKey:
                entry.refcount = 9

    dataListForge(working, "Table 1", dateCountForge)
    before, _ = formatLedger(working, "Table 1")
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    table.cell("A1").value = "now text"
    table.cell("A2").value = Decimal("5")
    document.save()

    after, _ = formatLedger(working, "Table 1")
    moved = {
        formatKeyOfType(working, "Table 1", numberFormatType),
        formatKeyOfType(working, "Table 1", textFormatType),
    }
    assert after[dateKey] == 9
    assert {key: count for key, count in after.items() if key not in moved} == {
        key: count for key, count in before.items() if key not in moved
    }


def test_aCellNamingAFormatItsTableDoesNotHoldIsRefused(tmp_path: Path) -> None:
    """A borrowed text shape names the text format, so its absence stops the save."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    textKey = formatKeyOfType(working, "Table 1", textFormatType)

    def textFormatRemove(formats: tst.TableDataList) -> None:
        kept = [entry for entry in formats.entries if entry.key != textKey]
        del formats.entries[:]
        formats.entries.extend(kept)

    dataListForge(working, "Table 1", textFormatRemove)
    unchanged = working.read_bytes()
    document = pybers.open(working)
    document.sheets[0].tables[0].cell("J1").value = "into an empty cell"

    with pytest.raises(WriteError, match=f"J1 would name format {textKey}"):
        document.save()
    assert working.read_bytes() == unchanged


def test_aBorrowedShapeKeepsOnlyTheFormatSlotOfItsOwnKind() -> None:
    """`N2` is text remembering a number, a date and a duration format as well.

    Those three belong to the cell they were chosen for, and a new cell naming them
    would claim counts in slots this library does not maintain.
    """
    record = recordAt(fixtureDirectory / "15-number-duration-formats.numbers", "N2")
    shaped = decodeRecord(record.column, borrowedShape(record))

    kept = set(referenceSlots(shaped.raw))
    assert len(referenceSlots(record.raw)) == 5, "the fixture cell remembers formats"
    assert kept == {textFormatSlot, displayedKindSlot}
    assert not shaped.raw[6] & 0x80, "a chosen format is not borrowed either"
    assert shaped.value == record.value


def test_theRetypedGoldenCountsEveryFormatByItsCells(tmp_path: Path) -> None:
    """AC 5. The golden is reproduced, and every count it stores matches its cells."""
    golden = goldenDirectory / "11-text-written-and-retyped.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    working = workingCopy("11-value-types-noformats", tmp_path)
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    for address, value in retypedCells:
        table.cell(address).value = value
    document.save()

    differences = archiveDifferences(readPackage(golden), readPackage(working))
    assert not differences, (
        "the writer no longer produces the confirmed output:\n  "
        + "\n  ".join(differences)
    )
    declared, claims = formatLedger(golden, "Table 1")
    assert declared == {key: claims[key] for key in declared}


@pytest.mark.parametrize(
    ("address", "value", "kind"),
    [("A1", "now text", 5), ("J1", "into an empty cell", 5), ("A2", Decimal("5"), 1)],
)
def test_aWrittenCellDisplaysTheKindItsValueIs(
    address: str, value: str | Decimal, kind: int, tmp_path: Path
) -> None:
    """AC 7. A retype, a borrowed shape, and text becoming a number."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    document = pybers.open(working)
    document.sheets[0].tables[0].cell(address).value = value
    document.save()

    assert displayedKind(recordAt(working, address)) == (kind, {kind})


def test_theFirstTextInATableDisplaysAsTextWhateverItsFormatKey(tmp_path: Path) -> None:
    """AC 7. `Table 2` keys its created text format 2, which is the currency kind."""
    working = workingCopy("20-formula-shapes", tmp_path)
    document = pybers.open(working)
    document.sheet("Sheet 1").table("Table 2").cell("B1").value = "first text"
    document.save()

    assert formatKeyOfType(working, "Table 2", textFormatType) == 2
    kind, held = displayedKind(recordAt(working, "B1", table="Table 2"))
    assert (kind, held) == (5, {5})


def test_aNumberInACreatedTableDisplaysAsANumberWhateverItsFormatKey(
    tmp_path: Path,
) -> None:
    """AC 7. `Output` keys its number format 2 once text claimed key 1 first."""
    working = workingCopy("20-formula-shapes", tmp_path)
    document = pybers.open(working)
    table = document.sheetAdd("Fresh").tableAdd("Output", rows=2, cols=2)
    table.cell("A1").value = "label"
    table.cell("B2").value = Decimal("12.5")
    document.save()

    numberKey = formatKeyOfType(working, "Output", numberFormatType)
    kind, held = displayedKind(recordAt(working, "B2", table="Output"))
    assert numberKey != 1, "the key differs from the kind, or this proves nothing"
    assert (kind, held) == (1, {1})


@pytest.mark.parametrize(
    "name",
    [
        "11-text-written-and-retyped",
        "20-first-text-in-a-table",
        "20-tables-added",
        "45-merged-by-pybers",
        "22c-merged-by-pybers",
    ],
)
def test_aGoldenThatWroteCellsDisplaysKindsAndCountsCells(name: str) -> None:
    """PYB-89 and PYB-92, read from the goldens themselves rather than regenerated."""
    golden = goldenDirectory / f"{name}.numbers"
    for index, model in tableModels(golden):
        for record in tableRecords(index, model):
            kind, held = displayedKind(record)
            assert kind is None or kind in held, f"{model.table_name} {record.column}"
        formats = index.resolve(model.base_data_store.format_table, tst.TableDataList)
        declared = {int(entry.key): int(entry.refcount) for entry in formats.entries}
        claims = cellClaims(index, model)
        assert declared == {key: claims[key] for key in declared}, model.table_name
        assert listsAgreeWithCells(index, model) == [], model.table_name


def formatListNext(path: Path, tableName: str) -> int:
    """Return the key one table's format list would give its next entry."""
    for index, model in tableModels(path):
        if model.table_name == tableName:
            formats = index.resolve(
                model.base_data_store.format_table, tst.TableDataList
            )
            return int(formats.nextListID)
    raise AssertionError(f"{tableName!r} is not in {path.name}")


def test_aSpentFormatKeepsItsKeyRetired(tmp_path: Path) -> None:
    """AC 9. `54c` shows Numbers removing the entry and leaving `nextListID` alone."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    before = formatListNext(working, "Table 1")
    document = pybers.open(working)
    document.sheets[0].tables[0].cell("F1").value = "was a star rating"
    document.save()

    assert formatListNext(working, "Table 1") == before


def test_aFormatACellStillNamesIsKeptWhenItsCountSaysOtherwise(
    tmp_path: Path,
) -> None:
    """AC 9 against AC 4. An undercounted format released to 0 still has cells."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    textKey = formatKeyOfType(working, "Table 1", textFormatType)

    def textCountForge(formats: tst.TableDataList) -> None:
        for entry in formats.entries:
            if entry.key == textKey:
                entry.refcount = 1

    dataListForge(working, "Table 1", textCountForge)
    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A2").value = Decimal("5")
    document.save()

    after, claims = formatLedger(working, "Table 1")
    assert claims[textKey] > 0, "other labels still name the text format"
    assert after[textKey] == 0, "kept, because removing it would orphan them"


def test_aMergeReleasesTheFormatsOfTheRecordsItRemoves(tmp_path: Path) -> None:
    """AC 10. `KJ7` holds text, and merging `KI7:KJ7` removes its record."""
    working = workingCopy("45-columns-over-255", tmp_path)
    document = pybers.open(working)
    document.sheets[0].tables[0].mergeAdd("KI7:KJ7")
    document.save()

    for index, model in tableModels(working):
        formats = index.resolve(model.base_data_store.format_table, tst.TableDataList)
        declared = {int(entry.key): int(entry.refcount) for entry in formats.entries}
        claims = cellClaims(index, model)
        assert declared == {key: claims[key] for key in declared}, model.table_name


def pooledCounts(
    index: ArchiveIndex, model: tst.TableModelArchive
) -> tuple[Counter[int], Counter[int]]:
    """Return how often this table's cells name each string and each style."""
    strings: Counter[int] = Counter()
    styles: Counter[int] = Counter()
    for record in tableRecords(index, model):
        strings.update(stringClaims(record))
        styles.update(
            key
            for slot, key in zip(
                referenceSlots(record.raw), record.references, strict=True
            )
            if slot in countedStyleSlots
        )
    return strings, styles


def listsAgreeWithCells(index: ArchiveIndex, model: tst.TableModelArchive) -> list[str]:
    """Return each string or style list whose refcounts differ from its cells."""
    strings, styles = pooledCounts(index, model)
    store = model.base_data_store
    disagreeing = []
    for name, reference, counted in (
        ("string", store.stringTable, strings),
        ("style", store.styleTable, styles),
    ):
        if not reference.identifier:
            continue
        entries = index.resolve(reference, tst.TableDataList).entries
        if any(entry.refcount != counted[entry.key] for entry in entries):
            disagreeing.append(name)
    return disagreeing


def listNext(path: Path, tableName: str, listName: str) -> int:
    """Return the key one of a table's data lists would give its next entry."""
    for index, model in tableModels(path):
        if model.table_name == tableName:
            reference = getattr(model.base_data_store, listName)
            return int(index.resolve(reference, tst.TableDataList).nextListID)
    raise AssertionError(f"{tableName!r} is not in {path.name}")


def stringEntries(path: Path, tableName: str) -> dict[int, tuple[str, int]]:
    """Return one table's pooled strings as key to text and refcount."""
    for index, model in tableModels(path):
        if model.table_name == tableName:
            entries = index.resolve(
                model.base_data_store.stringTable, tst.TableDataList
            ).entries
            return {
                int(entry.key): (entry.string, int(entry.refcount))
                for entry in entries
            }
    raise AssertionError(f"{tableName!r} is not in {path.name}")


def test_theCountedStringsAndStylesReproduceEveryListNumbersWrote() -> None:
    """PYB-92's measurement: strings by text record, styles by byte 8 slots."""
    checked = 0
    for path in sorted(fixtureDirectory.glob("*.numbers")):
        for index, model in tableModels(path):
            assert listsAgreeWithCells(index, model) == [], (
                f"{path.name} / {model.table_name}"
            )
            checked += 1
    assert checked >= 92


def test_aMergeReleasesTheStringOfTheTextRecordItRemoves(tmp_path: Path) -> None:
    """PYB-92 AC 1. `KJ7` holds the only `r6c296`, so its entry goes with it."""
    working = workingCopy("45-columns-over-255", tmp_path)
    before = stringEntries(working, "45-row-offsets-32bit")
    document = pybers.open(working)
    document.sheets[0].tables[0].mergeAdd("KI7:KJ7")
    document.save()

    after = stringEntries(working, "45-row-offsets-32bit")
    assert ("r6c296", 1) in before.values()
    assert "r6c296" not in {text for text, _ in after.values()}
    for index, model in tableModels(working):
        assert listsAgreeWithCells(index, model) == []


def test_aMergeReleasesTheStylesOfTheRecordItRemoves(tmp_path: Path) -> None:
    """PYB-92 AC 2. `M3` is a style-only record an imported merge left behind."""
    working = workingCopy("22c-merge-overpaints", tmp_path)
    before = recordAt(working, "M3")
    document = pybers.open(working)
    document.sheets[0].tables[0].mergeAdd("L3:M3")
    document.save()

    assert {slot for slot in referenceSlots(before.raw)} >= set(countedStyleSlots)
    for index, model in tableModels(working):
        assert listsAgreeWithCells(index, model) == []


def test_aStringNothingNamesIsRemovedWithItsKeyRetired(tmp_path: Path) -> None:
    """PYB-92 AC 3. `A2` is the only cell labeled `plain number 1234.5`."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    before = listNext(working, "Table 1", "stringTable")
    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A2").value = Decimal("5")
    document.save()

    texts = {text for text, _ in stringEntries(working, "Table 1").values()}
    assert "plain number 1234.5" not in texts
    assert listNext(working, "Table 1", "stringTable") == before


def test_aStringACellStillNamesIsKeptWhenItsCountSaysOtherwise(
    tmp_path: Path,
) -> None:
    """PYB-92 AC 3 against a count Numbers wrote too low: the entry stays."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    table.cell("A1").value = "shared"
    table.cell("B1").value = "shared"
    document.save()
    key = next(
        key for key, (text, _) in stringEntries(working, "Table 1").items()
        if text == "shared"
    )

    def sharedCountForge(strings: tst.TableDataList) -> None:
        for entry in strings.entries:
            if entry.key == key:
                entry.refcount = 1

    dataListForge(working, "Table 1", sharedCountForge, "stringTable")
    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = Decimal("5")
    document.save()

    assert stringEntries(working, "Table 1")[key] == ("shared", 0)


def test_textWrittenLaterInTheSaveSharesAStringReleasedEarlier(tmp_path: Path) -> None:
    """PYB-92 AC 3. A release is final only when the save ends, not when it happens."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    table.cell("A2").value = Decimal("5")
    table.cell("J1").value = "plain number 1234.5"
    document.save()

    matching = [
        count for text, count in stringEntries(working, "Table 1").values()
        if text == "plain number 1234.5"
    ]
    assert matching == [1]


def poolsAgreeWithCells(path: Path) -> list[str]:
    """Return each formula or rich-text list whose refcounts differ from its cells."""
    disagreeing = []
    for index, model in tableModels(path):
        store = model.base_data_store
        records = tableRecords(index, model)
        formulas = Counter(
            record.references[formulaKeySlot(record)]
            for record in records if carriesFormula(record)
        )
        richText = Counter(key for record in records for key in richTextClaims(record))
        for name, present, reference, counted in (
            ("formula", store.formula_table.identifier, store.formula_table, formulas),
            ("rich text", store.HasField("rich_text_table"), store.rich_text_table,
             richText),
        ):
            if not present:
                continue
            entries = index.resolve(reference, tst.TableDataList).entries
            if any(entry.refcount != counted[entry.key] for entry in entries):
                disagreeing.append(f"{model.table_name} {name}")
    return disagreeing


def test_aMergeReleasesTheFormulaOfACellItCoversAndDeregistersIt(
    tmp_path: Path,
) -> None:
    """PYB-92 AC 5.i. `B1` holds `=2*3`, and merging `A1:B1` removes its record."""
    working = workingCopy("18-formula-literals", tmp_path)
    assert (0, 1) in formulaCellRegister(working)[0], "B1 holds a formula"
    document = pybers.open(working)
    document.sheets[0].tables[0].mergeAdd("A1:B1")
    document.save()

    expanded, tiled = formulaCellRegister(working)
    assert (0, 1) not in expanded, "a covered cell is no longer a formula cell"
    assert expanded == tiled
    assert poolsAgreeWithCells(working) == []


def test_aMergeReleasesTheRichTextOfACellItCovers(tmp_path: Path) -> None:
    """PYB-92 AC 5.ii. `C2` and `D2` are both rich text, and `D2` is covered."""
    working = workingCopy("30-style-align", tmp_path)
    document = pybers.open(working)
    document.sheets[0].tables[0].mergeAdd("C2:D2")
    document.save()

    assert poolsAgreeWithCells(working) == []


def test_theMergedOverFormulaGoldenIsWhatTheWriterProduces(tmp_path: Path) -> None:
    """PYB-92 AC 5.i, against the file Numbers opened, and its counts read directly."""
    golden = goldenDirectory / "18-merged-over-a-formula.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    working = workingCopy("18-formula-literals", tmp_path)
    document = pybers.open(working)
    document.sheets[0].tables[0].mergeAdd("A1:B1")
    document.save()

    differences = archiveDifferences(readPackage(golden), readPackage(working))
    assert not differences, "\n  ".join(differences)
    assert poolsAgreeWithCells(golden) == []
    assert (0, 1) not in formulaCellRegister(golden)[0]
