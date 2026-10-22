#!/usr/bin/env python3
"""\
Any value kind written into any cell, whatever the cell held, and read back as written.

Most tests write into a copy of `11-value-types-noformats`, whose row 1 holds a number,
a date, a duration, a checkbox, a star rating, a slider, a stepper and a pop-up menu,
and whose `J1` has no record at all.

UPDATES
2026-10-22  A number written into a currency cell keeps its currency, for
            PYB-220.
2026-10-20  Written for PYB-144.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/20"

import datetime
import zoneinfo
from decimal import Decimal
from pathlib import Path

import pytest
from test_cell_kinds import findFirstEmptyRecord, forgeRecordType, unmeasuredTypeByte
from test_format_refcounts import readDisplayedKind, readFormatLedger, readTableModels
from test_writer import listArchiveDifferences, readRecordAt

import pybers
from conftest import copyDocument, findDocumentPath
from pybers import CellKind
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import readPackage
from pybers._persistence.cells import countedFormatSlots, findSlotValue
from pybers.currency import CurrencyAmount
from pybers.table._records import controlSlot

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"
baseStem: str = "11-value-types-noformats"

# A cell of every kind a record stores, as the first table of its document holds it.
sourceCells: tuple[tuple[str, str, CellKind], ...] = (
    (baseStem, "A1", CellKind.NUMBER),
    (baseStem, "C1", CellKind.DATE_TIME),
    (baseStem, "D1", CellKind.DURATION),
    (baseStem, "E1", CellKind.BOOLEAN),
    (baseStem, "I1", CellKind.TEXT),
    (baseStem, "J1", CellKind.EMPTY),
    ("12-number-currency", "B1", CellKind.CURRENCY),
    ("67-series-rich-base", "A2", CellKind.RICH_TEXT),
    ("67-series-rich-base", "B3", CellKind.EMPTY),
)

# What a script writes; an `int` and a `date` are accepted beside `CellValue`.
Writable = pybers.CellValue | int | datetime.date

writtenValues: tuple[tuple[Writable, CellKind], ...] = (
    (Decimal("12.5"), CellKind.NUMBER),
    ("written", CellKind.TEXT),
    (datetime.datetime(2026, 10, 20, 9, 30), CellKind.DATE_TIME),
    (datetime.timedelta(minutes=90), CellKind.DURATION),
    (True, CellKind.BOOLEAN),
    (False, CellKind.BOOLEAN),
)


def openFirstTable(path: Path) -> tuple[pybers.Document, pybers.Table]:
    """Return a document and its first table."""
    document = pybers.open(path)
    return document, document.sheets[0].tables[0]


def writeAndReopen(path: Path, address: str, value: Writable) -> pybers.Cell:
    """Write one value, save, and return the cell as a fresh read finds it."""
    document, table = openFirstTable(path)
    table.cell(address).value = value
    document.save()
    return openFirstTable(path)[1].cell(address)


def readOtherRecords(path: Path, address: str) -> dict[str, bytes]:
    """Return every record of the first table but one, by address."""
    _, table = openFirstTable(path)
    return {
        str(cell.address): readRecordAt(path, str(cell.address)).raw
        for cell in table.cells.values()
        if str(cell.address) != address and cell.description.kind is not CellKind.EMPTY
    }


def readFormatEntry(path: Path, address: str) -> tst.TableDataList.ListEntry:
    """Return the format list entry a cell displays with."""
    record = readRecordAt(path, address)
    kind, _ = readDisplayedKind(record)
    assert kind is not None
    key = findSlotValue(record, countedFormatSlots[kind - 1])
    index, model = readTableModels(path)[0]
    formats = index.resolve(model.base_data_store.format_table, tst.TableDataList)
    return next(entry for entry in formats.entries if entry.key == key)


# ── AC 1 and 2: any kind into any cell ──────────────────────────────────────


@pytest.mark.parametrize(("value", "kind"), writtenValues, ids=repr)
@pytest.mark.parametrize(
    ("stem", "address", "held"), sourceCells, ids=lambda each: str(each)
)
def testAnyValueIsWrittenIntoACellOfAnyKind(
    stem: str, address: str, held: CellKind, value: Writable, kind: CellKind,
    tmp_path: Path,
) -> None:
    working = copyDocument(stem, tmp_path)
    before = openFirstTable(working)[1].cell(address)
    assert before.description.kind is held
    wanted = value
    if isinstance(before.value, CurrencyAmount) and isinstance(value, Decimal):
        wanted = CurrencyAmount(value, before.value.currency)

    cell = writeAndReopen(working, address, value)

    assert type(cell.value) is type(wanted)
    assert cell.value == wanted
    expected = (
        CellKind.CURRENCY if held is CellKind.CURRENCY and kind is CellKind.NUMBER
        else kind
    )
    assert cell.description.kind is expected


def testTheCellReportsItsNewKindOnceSaved(tmp_path: Path) -> None:
    document, table = openFirstTable(copyDocument(baseStem, tmp_path))
    cell = table.cell("A1")
    cell.value = True
    assert cell.description.format is pybers.UNDETERMINED
    document.save()
    assert cell.description.kind is CellKind.BOOLEAN
    assert cell.description.format is pybers.CellFormat.BOOLEAN


# ── AC 3: exact read back ───────────────────────────────────────────────────


def testNinetyMinutesReadsBackAsExactly5400Seconds(tmp_path: Path) -> None:
    cell = writeAndReopen(
        copyDocument(baseStem, tmp_path), "A1", datetime.timedelta(minutes=90)
    )
    assert isinstance(cell.value, datetime.timedelta)
    assert cell.value.total_seconds() == 5400


def testADateReadsBackAsTheSameWallClockTime(tmp_path: Path) -> None:
    written = datetime.datetime(2026, 10, 20, 9, 30, 15, 250000)
    cell = writeAndReopen(copyDocument(baseStem, tmp_path), "A1", written)
    assert cell.value == written


# ── AC 4: everything else carried through ──────────────────────────────────


@pytest.mark.parametrize(("value", "_"), writtenValues, ids=repr)
def testWritingACellLeavesEveryOtherCellUnchanged(
    value: Writable, _: CellKind, tmp_path: Path
) -> None:
    working = copyDocument(baseStem, tmp_path)
    before = readOtherRecords(working, "A1")
    writeAndReopen(working, "A1", value)
    assert readOtherRecords(working, "A1") == before


def testAWriteChangesOnlyTheArchivesHoldingTheCell(tmp_path: Path) -> None:
    working = copyDocument(baseStem, tmp_path)
    original = readPackage(working)
    writeAndReopen(working, "A1", datetime.timedelta(minutes=90))

    changed = listArchiveDifferences(original, readPackage(working))
    assert changed
    assert all("Tile-" in line or "DataList-" in line or "Metadata" in line
               or "CalculationEngine" in line for line in changed), changed


def testAnUnrecognizedRecordElsewhereSurvivesAWrite(tmp_path: Path) -> None:
    working = copyDocument("65-series-base", tmp_path)
    row, column = findFirstEmptyRecord(working)
    forgeRecordType(working, row, column, unmeasuredTypeByte)
    address = f"{pybers.toColumnLetter(column)}{row}"
    before = readRecordAt(working, address).raw
    writeAndReopen(working, "A2", True)
    assert readRecordAt(working, address).raw == before


# ── AC 5: what cannot be stored ─────────────────────────────────────────────


@pytest.mark.parametrize(("value", "reason"), [
    (1.5, "Write Decimal"),
    (Decimal("NaN"), "not a finite number"),
    (Decimal("1." + "1" * 40), "decimal128 holds 34"),
    (datetime.time(9, 30), "A cell holds a Decimal"),
])
def testAValueThatCannotBeStoredIsRefusedAndTheTableKept(
    value: object, reason: str, tmp_path: Path
) -> None:
    _, table = openFirstTable(copyDocument(baseStem, tmp_path))
    cell = table.cell("A1")
    with pytest.raises(pybers.WriteError, match=reason) as refused:
        cell.value = value  # type: ignore[assignment]
    assert "A1" in str(refused.value)
    assert cell.value == Decimal("1234.5")
    assert cell.description.kind is CellKind.NUMBER


def testAFloatIsRefusedNamingDecimal(tmp_path: Path) -> None:
    _, table = openFirstTable(copyDocument(baseStem, tmp_path))
    with pytest.raises(pybers.WriteError, match=r"A1 .*Decimal\('0.1'\)"):
        table.cell("A1").value = 0.1  # type: ignore[assignment]


def testAValueOverAnUnrecognizedRecordIsRefusedAndTheFileKept(tmp_path: Path) -> None:
    working = copyDocument("65-series-base", tmp_path)
    row, column = findFirstEmptyRecord(working)
    forgeRecordType(working, row, column, unmeasuredTypeByte)
    unchanged = working.read_bytes()
    document, table = openFirstTable(working)
    table.cell(row=row, col=column).value = True

    with pytest.raises(pybers.WriteError) as refused:
        document.save()
    assert str(refused.value) == (
        f"The cell in column {column} holds a value of a type pybers does not "
        f"recognize, {unmeasuredTypeByte}, so pybers cannot tell where its value ends."
    )
    assert working.read_bytes() == unchanged


# ── AC 7: int and date ──────────────────────────────────────────────────────


def testAnIntIsWrittenAsThatExactNumber(tmp_path: Path) -> None:
    big = 10**33 + 1
    cell = writeAndReopen(copyDocument(baseStem, tmp_path), "A1", big)
    assert cell.value == Decimal(big)
    assert isinstance(cell.value, Decimal)


def testADateWithNoTimeIsWrittenAsMidnight(tmp_path: Path) -> None:
    cell = writeAndReopen(
        copyDocument(baseStem, tmp_path), "A1", datetime.date(2026, 10, 20)
    )
    assert cell.value == datetime.datetime(2026, 10, 20)


# ── AC 8: Automatic for a kind that changed ─────────────────────────────────


@pytest.mark.parametrize(("value", "formatType", "displayed"), [
    (True, 1, 6),
    (Decimal("7"), 256, 1),
    ("seven", 260, 5),
    (datetime.timedelta(minutes=7), 268, 4),
    (datetime.datetime(2026, 10, 20), 261, 3),
])
def testACellWhoseKindChangesShowsTheAutomaticFormat(
    value: Writable, formatType: int, displayed: int, tmp_path: Path
) -> None:
    working = copyDocument(baseStem, tmp_path)
    address = "A2" if isinstance(value, Decimal) else "A1"
    writeAndReopen(working, address, value)

    kind, held = readDisplayedKind(readRecordAt(working, address))
    assert (kind, displayed in held) == (displayed, True)
    assert readFormatEntry(working, address).format.format_type == formatType
    assert not readRecordAt(working, address).raw[6]


@pytest.mark.parametrize(("value", "pattern"), [
    (datetime.datetime(2026, 10, 20), "yyyy-MM-dd"),
    (datetime.datetime(2026, 10, 20, 9, 30), "yyyy-MM-dd HH:mm"),
])
def testADateTakesISOOrderWithOrWithoutItsTime(
    value: Writable, pattern: str, tmp_path: Path
) -> None:
    working = copyDocument(baseStem, tmp_path)
    writeAndReopen(working, "A1", value)
    assert readFormatEntry(working, "A1").format.date_time_format == pattern


def testABooleanTakesTheFormatAFormulaResultTakes(tmp_path: Path) -> None:
    working = copyDocument(baseStem, tmp_path)
    writeAndReopen(working, "A1", True)
    entry = readFormatEntry(working, "A1")
    assert str(entry.format).split() == ["format_type:", "1"]


def testAChosenTextFormatGoesWithTheTextItWasChosenFor(tmp_path: Path) -> None:
    working = copyDocument(baseStem, tmp_path)
    document, table = openFirstTable(working)
    table.cell("A1").textLiteralSet("=1+1")
    document.save()
    cell = writeAndReopen(working, "A1", Decimal("2"))
    assert not cell.description.formatChosen


def testTheFormatCountsMatchTheCellsAfterEveryKindIsWritten(tmp_path: Path) -> None:
    working = copyDocument(baseStem, tmp_path)
    document, table = openFirstTable(working)
    for address, (value, _) in zip(
        ("A1", "B1", "C1", "D1", "J1", "A2"), writtenValues, strict=False
    ):
        table.cell(address).value = value
    document.save()
    declared, claims = readFormatLedger(working, "Table 1")
    assert declared == {key: claims[key] for key in declared}


# ── AC 11 and 12: dates and the document's zone ─────────────────────────────


def testADateIsReadAsANaiveDatetime() -> None:
    value = openFirstTable(findDocumentPath(baseStem))[1].cell("C1").value
    assert isinstance(value, datetime.datetime)
    assert (value, value.tzinfo) == (datetime.datetime(2027, 6, 15), None)


def testANaiveDatetimeIsWrittenAsItIs(tmp_path: Path) -> None:
    written = datetime.datetime(2026, 3, 8, 2, 30)
    working = copyDocument(baseStem, tmp_path)
    document = pybers.open(working, timeZone="America/New_York")
    document.sheets[0].tables[0].cell("C1").value = written
    document.save()
    assert openFirstTable(working)[1].cell("C1").value == written


@pytest.mark.parametrize("zone", ["America/Los_Angeles", zoneinfo.ZoneInfo(
    "America/Los_Angeles"
)], ids=["name", "tzinfo"])
def testAnAwareDatetimeIsWrittenInTheDocumentsZone(
    zone: pybers.TimeZoneLike, tmp_path: Path
) -> None:
    working = copyDocument(baseStem, tmp_path)
    document = pybers.open(working, timeZone=zone)
    document.sheets[0].tables[0].cell("C1").value = datetime.datetime(
        2026, 10, 20, 16, tzinfo=datetime.UTC
    )
    document.save()
    assert openFirstTable(working)[1].cell("C1").value == datetime.datetime(
        2026, 10, 20, 9
    )


def testTheZoneDefaultsToThisMachines(tmp_path: Path) -> None:
    moment = datetime.datetime(2026, 1, 15, 12, tzinfo=datetime.UTC)
    document, table = openFirstTable(copyDocument(baseStem, tmp_path))
    assert isinstance(document.timeZone, pybers.MachineTimeZone)
    table.cell("C1").value = moment
    assert table.cell("C1").value == moment.astimezone().replace(tzinfo=None)


def testTheZoneIsSetAfterOpeningByName(tmp_path: Path) -> None:
    document, table = openFirstTable(copyDocument(baseStem, tmp_path))
    document.timeZone = "Asia/Tokyo"
    table.cell("C1").value = datetime.datetime(2026, 10, 20, tzinfo=datetime.UTC)
    assert table.cell("C1").value == datetime.datetime(2026, 10, 20, 9)


def testAZoneNoOneKnowsIsRefusedBeforeTheFileIsRead(tmp_path: Path) -> None:
    with pytest.raises(pybers.TimeZoneError, match="'Mars/Olympus'"):
        pybers.open(tmp_path / "absent.numbers", timeZone="Mars/Olympus")


def testTheZoneIsNeverSavedInTheFile(tmp_path: Path) -> None:
    saved = []
    for zone in ("Asia/Tokyo", "America/Chicago"):
        into = tmp_path / zone.replace("/", "-")
        into.mkdir()
        working = copyDocument(baseStem, into)
        document = pybers.open(working, timeZone=zone)
        document.sheets[0].tables[0].cell("C1").value = datetime.datetime(2026, 1, 1)
        document.save()
        saved.append(readPackage(working))
    assert listArchiveDifferences(*saved) == []


# ── AC 14: a format never blocks a write ────────────────────────────────────


@pytest.mark.parametrize(("address", "value"), [
    ("E1", False), ("F1", Decimal("2")), ("G1", Decimal("70")),
    ("H1", Decimal("3")), ("I1", "Item 1"),
])
def testAValueOfTheControlsKindKeepsTheControl(
    address: str, value: Writable, tmp_path: Path
) -> None:
    working = copyDocument(baseStem, tmp_path)
    control = findSlotValue(readRecordAt(working, address), controlSlot)
    cell = writeAndReopen(working, address, value)
    assert cell.value == value
    assert findSlotValue(readRecordAt(working, address), controlSlot) == control


@pytest.mark.parametrize(("address", "value"), [
    ("F1", Decimal("7")), ("F1", Decimal("-1")), ("G1", Decimal("150")),
    ("H1", Decimal("500")), ("I1", "Banana"),
])
def testAValueTheControlCannotShowDropsTheControlAndKeepsTheValue(
    address: str, value: Writable, tmp_path: Path
) -> None:
    working = copyDocument(baseStem, tmp_path)
    cell = writeAndReopen(working, address, value)
    assert cell.value == value
    assert findSlotValue(readRecordAt(working, address), controlSlot) is None
    assert cell.description.format in (pybers.CellFormat.NUMBER, pybers.CellFormat.TEXT)


@pytest.mark.parametrize(("address", "value"), [
    ("F1", Decimal("0")), ("F1", Decimal("5")), ("G1", Decimal("100")),
    ("H1", Decimal("1")), ("I1", "Item 3"),
])
def testAValueAtTheControlsEdgeKeepsIt(
    address: str, value: Writable, tmp_path: Path
) -> None:
    working = copyDocument(baseStem, tmp_path)
    control = findSlotValue(readRecordAt(working, address), controlSlot)
    writeAndReopen(working, address, value)
    assert findSlotValue(readRecordAt(working, address), controlSlot) == control


def testADroppedControlIsReleasedAndItsEntryRemoved(tmp_path: Path) -> None:
    working = copyDocument(baseStem, tmp_path)
    key = findSlotValue(readRecordAt(working, "I1"), controlSlot)
    writeAndReopen(working, "I1", "Banana")
    index, model = readTableModels(working)[0]
    controls = index.resolve(
        model.base_data_store.control_cell_spec_table, tst.TableDataList
    )
    assert key not in {entry.key for entry in controls.entries}


def testAValueOfAnotherKindDropsTheControlAndReleasesIt(tmp_path: Path) -> None:
    working = copyDocument(baseStem, tmp_path)
    index, model = readTableModels(working)[0]
    controls = index.resolve(
        model.base_data_store.control_cell_spec_table, tst.TableDataList
    )
    key = findSlotValue(readRecordAt(working, "F1"), controlSlot)
    assert key in {entry.key for entry in controls.entries}

    writeAndReopen(working, "F1", True)

    assert findSlotValue(readRecordAt(working, "F1"), controlSlot) is None
    index, model = readTableModels(working)[0]
    controls = index.resolve(
        model.base_data_store.control_cell_spec_table, tst.TableDataList
    )
    assert key not in {entry.key for entry in controls.entries}


# ── AC 6: the goldens ───────────────────────────────────────────────────────

# Each golden's mutation, in the order it is written.
goldenWrites: dict[str, tuple[tuple[str, Writable], ...]] = {
    "11-dates-written-by-pybers": (
        ("A1", datetime.datetime(2027, 1, 31)),
        ("B1", datetime.datetime(2026, 10, 20, 9, 30)),
        ("C1", datetime.datetime(2027, 6, 16)),
        ("J1", datetime.datetime(2026, 12, 25, 18, 45)),
    ),
    "11-durations-written-by-pybers": (
        ("A1", datetime.timedelta(minutes=90)),
        ("D1", datetime.timedelta(hours=2)),
        ("J1", datetime.timedelta(days=1, hours=2)),
    ),
    "11-controls-written-by-pybers": (
        ("E1", False),
        ("F1", Decimal("7")),
        ("G1", Decimal("100")),
        ("H1", Decimal("500")),
        ("I1", "Banana"),
    ),
    "11-booleans-written-by-pybers": (
        ("A1", True),
        ("B1", False),
        ("E1", False),
        ("F1", True),
        ("J1", True),
    ),
}


def writeKindGolden(name: str, into: Path) -> Path:
    """Write one golden's mutation into a fresh copy of its fixture, and return it."""
    working = copyDocument(baseStem, into)
    document, table = openFirstTable(working)
    for address, value in goldenWrites[name]:
        table.cell(address).value = value
    document.save()
    return working


@pytest.mark.parametrize("name", goldenWrites)
def testTheKindGoldensMatchWhatThisLibraryProduces(name: str, tmp_path: Path) -> None:
    golden = goldenDirectory / f"{name}.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"
    differences = listArchiveDifferences(
        readPackage(golden), readPackage(writeKindGolden(name, tmp_path))
    )
    assert not differences, (
        "the writer no longer produces the confirmed output:\n  "
        + "\n  ".join(differences)
    )


@pytest.mark.parametrize("name", goldenWrites)
def testTheKindGoldensHoldWhatTheyClaimTo(name: str) -> None:
    golden = goldenDirectory / f"{name}.numbers"
    _, table = openFirstTable(golden)
    for address, value in goldenWrites[name]:
        assert table.cell(address).value == value




# ── The two consumers ───────────────────────────────────────────────────────


def testAScriptRecordsWhenEachTaskStartedAndHowLongItRan(tmp_path: Path) -> None:
    working = copyDocument(baseStem, tmp_path)
    document = pybers.open(working, timeZone="Europe/Rome")
    table = document.sheets[0].tables[0]
    table.cell("A1").value = datetime.datetime(2026, 10, 20, 7, tzinfo=datetime.UTC)
    table.cell("B1").value = datetime.timedelta(minutes=90)
    table.cell("C1").value = True
    document.save()

    reopened = pybers.open(working).sheets[0].tables[0]
    assert [reopened.cell(address).value for address in ("A1", "B1", "C1")] == [
        datetime.datetime(2026, 10, 20, 9), datetime.timedelta(seconds=5400), True,
    ]
