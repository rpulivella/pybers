#!/usr/bin/env python3
"""\
Each cell's stored kind and format, read through one frozen description.

The kind every record in the documents stores, the format families the labeled
fixtures name, a kind following an edit, an unknown type carried through, and the
few lines a script or a command line writes to ask a cell what it holds.

UPDATES
2026-10-01  Written for PYB-141.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/01"

import dataclasses
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from test_format_refcounts import forgeDataList, readTableModels
from test_writer import copyDocument, readRecordAt

import pybers
from conftest import allDocuments, findDocumentPath
from pybers import CellFormat, CellKind, FormulaReferenceRelocation
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import chooseOffsetUnit, decodeRow, readPackage, writePackage
from pybers._persistence.index import ArchiveIndex

relative = FormulaReferenceRelocation.PRESERVE_RELATIVE_POSITION

# The answer key, from findings-01-values.md rather than from the reader.
recordKinds: dict[int, CellKind] = {
    0: CellKind.EMPTY,
    2: CellKind.NUMBER,
    3: CellKind.TEXT,
    5: CellKind.DATE_TIME,
    6: CellKind.BOOLEAN,
    7: CellKind.DURATION,
    8: CellKind.ERROR,
    9: CellKind.RICH_TEXT,
    10: CellKind.CURRENCY,
}

# A type byte neither `TST.CellType` nor any document uses.
unmeasuredTypeByte: int = 11


def openFirstTable(name: str) -> pybers.Table:
    """Return the first table of a document."""
    return pybers.open(findDocumentPath(name)).sheets[0].tables[0]


def readStoredTypes(path: Path) -> list[dict[tuple[int, int], int]]:
    """Return each table's record type bytes by row and column, counted from 1."""
    tables = []
    for index, model in readTableModels(path):
        store = model.base_data_store
        types: dict[tuple[int, int], int] = {}
        for entry in store.tiles.tiles:
            tile = index.resolve(entry.tile, tst.Tile)
            for rowInfo in tile.rowInfos:
                row = entry.tileid * store.tiles.tile_size + rowInfo.tile_row_index
                unit = chooseOffsetUnit(
                    rowInfo.has_wide_offsets, tile.should_use_wide_rows
                )
                for record in decodeRow(
                    rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
                ):
                    types[(row + 1, record.column + 1)] = record.typeByte
        tables.append(types)
    return tables


def forgeRecordType(path: Path, row: int, column: int, typeByte: int) -> None:
    """Rewrite one record's type byte in a working copy, as a file pybers never saw."""
    package = readPackage(path)
    index = ArchiveIndex(package)
    _, model = readTableModels(path)[0]
    store = model.base_data_store
    for entry in store.tiles.tiles:
        tile = index.resolve(entry.tile, tst.Tile)
        for rowInfo in tile.rowInfos:
            if entry.tileid * store.tiles.tile_size + rowInfo.tile_row_index != row - 1:
                continue
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            at = int.from_bytes(
                rowInfo.cell_offsets[(column - 1) * 2:][:2], "little"
            ) * unit
            buffer = bytearray(rowInfo.cell_storage_buffer)
            buffer[at + 1] = typeByte
            rowInfo.cell_storage_buffer = bytes(buffer)
            owner = next(
                iwaFile for iwaFile in package.iwaFiles
                if any(archive.identifier == entry.tile.identifier
                       for archive in iwaFile.archives)
            )
            owner.messageReplace(entry.tile.identifier, 0, tile.SerializeToString())
            writePackage(package, path)
            return
    raise AssertionError(f"Row {row} of {path.name} stores nothing.")


def findFirstEmptyRecord(path: Path) -> tuple[int, int]:
    """Return the first position of the first table whose record holds no value."""
    types = readStoredTypes(path)[0]
    return min(position for position, typeByte in types.items() if typeByte == 0)


def testTheKindsAreTheClosedSetTheTicketNames() -> None:
    """AC 1."""
    assert {kind.value for kind in CellKind} == {
        "empty", "number", "currency", "text", "rich-text", "date-time",
        "duration", "boolean", "error", "unknown",
    }


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def testEveryCellReportsTheKindItsRecordStores(path: Path) -> None:
    """AC 1 and AC 3, every cell of every document, a cell with no record included."""
    document = pybers.open(path)
    tables = [table for sheet in document.sheets for table in sheet.tables]
    for table, types in zip(tables, readStoredTypes(path), strict=True):
        assert set(types.values()) <= set(recordKinds)
        for cell in table.gridIterate():
            stored = types.get((cell.reference.row, cell.reference.col))
            expected = CellKind.EMPTY if stored is None else recordKinds[stored]
            assert cell.description.kind is expected, f"{table.name}!{cell.reference}"


@pytest.mark.parametrize(
    ("document", "address", "kind", "shown"),
    [
        ("11-value-types-noformats", "A1", CellKind.NUMBER, CellFormat.NUMBER),
        ("11-value-types-noformats", "C1", CellKind.DATE_TIME, CellFormat.DATE_TIME),
        ("11-value-types-noformats", "D1", CellKind.DURATION, CellFormat.DURATION),
        ("11-value-types-noformats", "E1", CellKind.BOOLEAN, CellFormat.CHECKBOX),
        ("11-value-types-noformats", "F1", CellKind.NUMBER, CellFormat.STAR_RATING),
        ("11-value-types-noformats", "I1", CellKind.TEXT, CellFormat.TEXT),
        ("11-value-types-noformats", "J1", CellKind.EMPTY, None),
        ("12-number-currency", "B1", CellKind.CURRENCY, CellFormat.CURRENCY),
        ("13-number-percent", "A1", CellKind.NUMBER, CellFormat.NUMBER),
        ("13-number-percent", "B1", CellKind.NUMBER, CellFormat.PERCENT),
        ("14-number-date", "B1", CellKind.DATE_TIME, CellFormat.DATE_TIME),
        ("16-number-scientific-numeralsystems", "B1", CellKind.NUMBER,
         CellFormat.SCIENTIFIC),
        ("16-number-scientific-numeralsystems", "E1", CellKind.NUMBER,
         CellFormat.NUMERAL_SYSTEM),
        ("17-number-custom", "B1", CellKind.NUMBER, CellFormat.CUSTOM_NUMBER),
        ("68-series-kinds-base", "D2", CellKind.NUMBER, CellFormat.FRACTION),
        ("02-text-rich", "A1", CellKind.RICH_TEXT, CellFormat.TEXT),
        ("21-formula-errors", "B1", CellKind.ERROR, None),
    ],
)
def testALabeledCellReportsTheKindAndFormatItsLabelNames(
    document: str, address: str, kind: CellKind, shown: CellFormat | None
) -> None:
    """AC 1 and AC 5: the format is the label's, and the kind is the stored type's."""
    description = openFirstTable(document).cell(address).description
    assert (description.kind, description.format) == (kind, shown)


def testAPercentageAndAPlainNumberAreBothNumbers() -> None:
    """AC 5."""
    table = openFirstTable("13-number-percent")
    plain, percent = table.cell("A1").description, table.cell("B1").description
    assert plain.kind is percent.kind is CellKind.NUMBER
    assert (plain.format, percent.format) == (CellFormat.NUMBER, CellFormat.PERCENT)


def testEveryDateIsADateWhateverFormatShowsIt() -> None:
    """The constraint: a date is type 5 whatever format is applied."""
    row = list(openFirstTable("14-number-date").rows)[0]
    assert {cell.description.kind for cell in row if cell.value is not None} == {
        CellKind.DATE_TIME
    }


def testAnUnmeasuredTypeReportsUnknown(tmp_path: Path) -> None:
    """AC 2."""
    working = copyDocument("65-series-base", tmp_path)
    row, column = findFirstEmptyRecord(working)
    forgeRecordType(working, row, column, unmeasuredTypeByte)

    cell = pybers.open(working).sheets[0].tables[0].cell(row=row, col=column)
    assert (cell.description.kind, cell.value) == (CellKind.UNKNOWN, None)


def testAnUnmeasuredTypeSurvivesASaveUnchanged(tmp_path: Path) -> None:
    """AC 2, the round trip, with another cell of the same table edited."""
    working = copyDocument("65-series-base", tmp_path)
    row, column = findFirstEmptyRecord(working)
    forgeRecordType(working, row, column, unmeasuredTypeByte)
    address = f"{pybers.toColumnLetter(column)}{row}"
    before = readRecordAt(working, address).raw

    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    edited = next(
        cell for cell in table.gridIterate()
        if cell.description.kind is CellKind.NUMBER and cell.formula is None
    )
    edited.value = Decimal("99")
    document.save()

    assert readRecordAt(working, address).raw == before
    reopened = pybers.open(working).sheets[0].tables[0].cell(address)
    assert reopened.description.kind is CellKind.UNKNOWN


def testAnUnmeasuredFormatTypeReportsAnUnknownFormat(tmp_path: Path) -> None:
    """AC 2 for the format: a family not measured is reported unknown, never guessed."""
    working = copyDocument("13-number-percent", tmp_path)

    def forgePercent(formats: tst.TableDataList) -> None:
        for entry in formats.entries:
            if entry.format.format_type == 258:
                entry.format.format_type = 999

    forgeDataList(working, "Table 1", forgePercent)
    description = pybers.open(working).sheets[0].tables[0].cell("B1").description
    assert (description.kind, description.format) == (
        CellKind.NUMBER, CellFormat.UNKNOWN
    )


def testRichTextOverwrittenWithPlainTextReportsText() -> None:
    """AC 4."""
    cell = openFirstTable("02-text-rich").cell("A1")
    cell.value = "Goodbye"
    assert cell.description.kind is CellKind.TEXT


def testRichTextGivenBackItsOwnTextIsRichAgain() -> None:
    """AC 4: the kind follows the value, so the stored value restores its kind."""
    cell = openFirstTable("02-text-rich").cell("A1")
    cell.value = "Goodbye"
    cell.value = "Hello"
    assert cell.description.kind is CellKind.RICH_TEXT


@pytest.mark.parametrize(
    ("address", "value", "kind"),
    [
        ("A1", "words", CellKind.TEXT),
        ("A1", None, CellKind.EMPTY),
        ("I1", Decimal("7"), CellKind.NUMBER),
        ("J1", "words", CellKind.TEXT),
        ("J1", True, CellKind.BOOLEAN),
    ],
)
def testAChangedValueReportsTheKindOfTheNewValue(
    address: str, value: pybers.CellValue, kind: CellKind
) -> None:
    """AC 4."""
    cell = openFirstTable("11-value-types-noformats").cell(address)
    cell.value = value
    assert cell.description.kind is kind


def testACurrencyAmountChangedStaysCurrency() -> None:
    """AC 4: the writer keeps a currency record's type, so the kind says so."""
    cell = openFirstTable("12-number-currency").cell("B1")
    cell.value = Decimal("1")
    assert cell.description.kind is CellKind.CURRENCY


def testAChangedKindHasNoFormatUntilTheSaveChoosesOne() -> None:
    """The format the record names belongs to the old kind, so none is reported."""
    cell = openFirstTable("11-value-types-noformats").cell("A1")
    cell.value = "words"
    assert cell.description.format is None


def testASavedCellIsDescribedByTheRecordTheSaveLeft(tmp_path: Path) -> None:
    """AC 7: a save describes each cell as a reopen would, without reopening."""
    working = copyDocument("11-value-types-noformats", tmp_path)
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    table.cell("A1").value = "words"
    table.cell("I1").value = Decimal("7")
    table.cell("J1").value = "fresh"
    document.save()

    reopened = pybers.open(working).sheets[0].tables[0]
    for address in ("A1", "I1", "J1", "B1"):
        assert table.cell(address).description == reopened.cell(address).description
    assert table.cell("A1").description.format is CellFormat.TEXT


def testARowInsertedIsDescribedAsAReopenDescribesIt(tmp_path: Path) -> None:
    """AC 7: every cell a structural edit moved is described where it now sits."""
    working = copyDocument("11-value-types-noformats", tmp_path)
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    table.rowAdd(1)
    document.save()

    reopened = pybers.open(working).sheets[0].tables[0]
    assert {
        str(cell.reference): cell.description for cell in table.gridIterate()
    } == {str(cell.reference): cell.description for cell in reopened.gridIterate()}


def testAFormulaGivenACellWithNoRecordIsAnErrorBeforeTheSave(tmp_path: Path) -> None:
    """The save stores type 8, uncalculated, so the line before it says so too."""
    working = copyDocument("18-formula-literals", tmp_path)
    document = pybers.open(working)
    cell = document.sheets[0].tables[0].cell("H1")
    cell.formulaSet("=1+1")
    before = cell.description
    document.save()

    reopened = pybers.open(working).sheets[0].tables[0].cell("H1").description
    assert before.kind is cell.description.kind is reopened.kind is CellKind.ERROR


def testAFormulaGivenAStyledEmptyRecordStaysEmpty(tmp_path: Path) -> None:
    """Attaching a formula keeps the record's type, so only a missing record errs."""
    working = copyDocument("65-series-base", tmp_path)
    row, column = findFirstEmptyRecord(working)
    document = pybers.open(working)
    cell = document.sheets[0].tables[0].cell(row=row, col=column)
    cell.formulaSet("=1+1")
    before = cell.description
    document.save()

    reopened = pybers.open(working).sheets[0].tables[0].cell(row=row, col=column)
    assert before.kind is reopened.description.kind is CellKind.EMPTY


def testTheDescriptionIsOneFrozenObject() -> None:
    """AC 6."""
    description = openFirstTable("21-formula-errors").cell("B1").description
    with pytest.raises(dataclasses.FrozenInstanceError):
        description.kind = CellKind.TEXT  # type: ignore[misc]
    assert {field.name for field in dataclasses.fields(description)} == {
        "kind", "format", "formatChosen"
    }


def testTheFlagsTheDescriptionReplacesAreGone() -> None:
    """The constraint: no second copy of what the description says."""
    cell = openFirstTable("02-text-rich").cell("A1")
    for name in ("errored", "formatChosen", "_formatChosen", "_richText"):
        assert not hasattr(cell, name), name


def testLiteralTextReportsAChosenFormat() -> None:
    """AC 6: the chosen format is read where the kind is."""
    cell = openFirstTable("11-value-types-noformats").cell("A1")
    cell.textLiteralSet("=1+1")
    assert (cell.description.kind, cell.description.formatChosen) == (
        CellKind.TEXT, True
    )


def testAFilledCopyReportsItsSourcesKind() -> None:
    """AC 7: a fill copies the record, so the copy stores what its source stores."""
    table = openFirstTable("67-series-rich-base")
    table.cellsFill(
        "A2", "A2:A4", references=relative,
        values=pybers.CellValueFill.REPEAT_SOURCE_VALUE,
    )
    assert table.cell("A4").description == table.cell("A2").description
    assert table.cell("A4").description.kind is CellKind.RICH_TEXT


def testAScriptCountsTheCurrencyAmountsInATable() -> None:
    """The few lines a script author writes."""
    table = openFirstTable("12-number-currency")
    kinds = Counter(cell.description.kind for cell in table.gridIterate())
    assert kinds[CellKind.CURRENCY] == 8


def testACommandLineListsEachCellsKindAsText() -> None:
    """The few lines a command line writes, printing kinds a person can read."""
    table = openFirstTable("21-formula-errors")
    shown = {
        str(cell.reference): {
            "kind": cell.description.kind.value,
            "format": cell.description.format and cell.description.format.value,
        }
        for cell in list(table.rows)[0]
    }
    assert json.loads(json.dumps(shown))["B1"] == {"kind": "error", "format": None}
