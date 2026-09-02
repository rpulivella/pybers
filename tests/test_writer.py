#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
Writing a document back out, asserted archive by archive against what was read.

The comparison here is deliberately not a byte compare of the two files. The zip
envelope is known to differ by the local extra fields `zipfile` cannot emit, which
`test_numbersfile_container` pins exactly, and a byte compare at this level would fail
for that reason on every fixture while saying nothing about the document inside.
So this module compares the decoded archive stream: same members in the same
order, same archives in the same order, same messages, same contents.

Where two message bodies differ byte for byte the comparison does not stop there.
Protobuf serialization is not canonical, so a body re-encoded from a parsed
message can differ from the bytes it came from while carrying identical fields.
Those are parsed and compared as messages. A type absent from the registry cannot
be parsed at all, so a byte difference on one is reported as a difference rather
than assumed to be a harmless re-encoding.

UPDATES
2026-09-01  Written for #2, AC 1: the unchanged round trip.
2026-09-01  Numeric edits, for #2 AC 2, 3, 4 and 6.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/01"

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from pybers.numbersfile import CellRecord, NumbersPackage, decodeRow, readPackage
from pybers.numbersfile.types import archiveTypes
from pybers.model import Document, toCellReference
from pybers.writer import WriteError, writeDocument

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"

allFixtures: list[Path] = sorted(fixtureDirectory.glob("*.numbers"))


def numericRecords(path: Path) -> list[CellRecord]:
    """Every numeric cell record in a file, in tile order, for archive-level checks."""
    from pybers._generated import TSTArchives_pb2 as tst

    records: list[CellRecord] = []
    for iwaFile in readPackage(path).iwaFiles:
        for archive in iwaFile.archives:
            for message in archive.messages:
                if message.typeId != 6002:
                    continue
                tile = tst.Tile()
                tile.ParseFromString(message.data)
                for info in tile.rowInfos:
                    wide = info.has_wide_offsets or tile.should_use_wide_rows
                    records += [
                        record
                        for record in decodeRow(
                            info.cell_offsets, info.cell_storage_buffer, wide
                        )
                        if record.typeByte in (2, 10)
                    ]
    return records


def messagesAreEquivalent(typeId: int, before: bytes, after: bytes) -> bool:
    """Report whether two message bodies of the same type carry the same fields.

    Identical bytes settle it without parsing anything, which is the case for every
    archive of an untouched document. Differing bytes are only equivalent if the
    type is one this library can parse and both sides decode to the same message.
    """
    if before == after:
        return True
    messageClass = archiveTypes.get(typeId)
    if messageClass is None:
        return False
    first, second = messageClass(), messageClass()
    try:
        first.ParseFromString(before)
        second.ParseFromString(after)
    except Exception:
        return False
    return first == second


def archiveDifferences(before: NumbersPackage, after: NumbersPackage) -> list[str]:
    """Return every way two packages differ at the archive level, as readable lines.

    A list rather than a bare boolean, because a round trip that breaks needs to say
    which archive of which member went wrong. This format answers a wrong offset with
    a plausible wrong value rather than an error, and a failure reporting only "not
    equal" leaves the whole package to search by hand.
    """
    differences: list[str] = []

    beforeNames = [iwaFile.name for iwaFile in before.iwaFiles]
    afterNames = [iwaFile.name for iwaFile in after.iwaFiles]
    if beforeNames != afterNames:
        differences.append(
            f"IWA members differ: {beforeNames} became {afterNames}."
        )
        return differences

    for beforeFile, afterFile in zip(before.iwaFiles, after.iwaFiles):
        beforeIds = [archive.identifier for archive in beforeFile.archives]
        afterIds = [archive.identifier for archive in afterFile.archives]
        if beforeIds != afterIds:
            differences.append(
                f"{beforeFile.name}: {len(beforeIds)} archives became "
                f"{len(afterIds)}, or their order changed."
            )
            continue

        for beforeArchive, afterArchive in zip(beforeFile.archives, afterFile.archives):
            beforeShape = [(m.typeId, m.version) for m in beforeArchive.messages]
            afterShape = [(m.typeId, m.version) for m in afterArchive.messages]
            if beforeShape != afterShape:
                differences.append(
                    f"{beforeFile.name} archive {beforeArchive.identifier}: "
                    f"messages {beforeShape} became {afterShape}."
                )
                continue
            for index, (beforeMessage, afterMessage) in enumerate(
                zip(beforeArchive.messages, afterArchive.messages)
            ):
                if not messagesAreEquivalent(
                    beforeMessage.typeId, beforeMessage.data, afterMessage.data
                ):
                    differences.append(
                        f"{beforeFile.name} archive {beforeArchive.identifier} "
                        f"message {index} (type {beforeMessage.typeId}) changed: "
                        f"{len(beforeMessage.data)} bytes became "
                        f"{len(afterMessage.data)}."
                    )
    return differences


# ── AC 1: an unchanged document writes back unchanged ────────────────────────

def test_thereIsACorpusToWriteAtAll() -> None:
    """Guard the parametrization: an empty glob would make every case vacuous."""
    assert len(allFixtures) >= 40


@pytest.mark.parametrize("path", allFixtures, ids=lambda path: path.stem)
def test_everyFixtureWritesBackWithEveryArchiveUnchanged(
    path: Path, tmp_path: Path
) -> None:
    """AC 1 and AC 1.b: open, save with no edit, and every archive is equivalent.

    Numbers opening the result cleanly is the other half of AC 1 and is not
    assertable from pytest. It rests on the container round trip, confirmed by hand
    in Numbers 15.3.1 on 2026-08-16 and pinned by `test_numbersfile_container`, which
    this path writes through unchanged.
    """
    destination = tmp_path / f"{path.stem}-saved.numbers"
    pybers.open(path).save(destination)

    differences = archiveDifferences(readPackage(path), readPackage(destination))
    assert not differences, (
        f"{path.name} did not survive an unchanged save:\n  "
        + "\n  ".join(differences)
    )


@pytest.mark.parametrize("path", allFixtures, ids=lambda path: path.stem)
def test_aSavedFixtureReadsBackAsTheSameDocument(path: Path, tmp_path: Path) -> None:
    """The model is equal across the round trip, which the archive check cannot see.

    Both fields holding archive state are excluded from equality, so this compares
    the sheets, tables and cells a caller actually works with.
    """
    destination = tmp_path / f"{path.stem}-saved.numbers"
    original = pybers.open(path)
    original.save(destination)

    assert original == pybers.open(destination)


def test_savingWithNoPathWritesBackWhereTheDocumentCameFrom(tmp_path: Path) -> None:
    """`doc.save()` is in place, which is what makes the common edit a two-liner."""
    working = tmp_path / "in-place.numbers"
    shutil.copy(fixtureDirectory / "00-baseline.numbers", working)

    document = pybers.open(working)
    document.save()

    assert not archiveDifferences(
        readPackage(fixtureDirectory / "00-baseline.numbers"), readPackage(working)
    )


def test_savingIsRepeatableAndLeavesTheDocumentUsable(tmp_path: Path) -> None:
    """There is no close and no invalidation, so a second save is an ordinary call."""
    document = pybers.open(fixtureDirectory / "00-baseline.numbers")
    first = tmp_path / "first.numbers"
    second = tmp_path / "second.numbers"

    document.save(first)
    document.save(second)

    assert document.sheets, "the document stopped being usable after saving"
    assert not archiveDifferences(readPackage(first), readPackage(second))


# ── Refusals: a save that cannot be correct raises rather than guessing ──────

def test_savingADocumentThatWasNeverReadIsRefused() -> None:
    """A hand-built Document has no archives, so there is nothing to write back."""
    with pytest.raises(WriteError, match="carries no archives"):
        Document().save()


def test_savingInPlaceWithNoSourcePathIsRefused() -> None:
    """The package is present but the origin is not, so in place has no meaning."""
    document = pybers.open(fixtureDirectory / "00-baseline.numbers")
    document._sourcePath = None

    with pytest.raises(WriteError, match="nowhere to save"):
        document.save()


def test_savingIntoAMissingDirectoryIsRefused(tmp_path: Path) -> None:
    """Named rather than left to an OSError from deep inside `zipfile`."""
    document = pybers.open(fixtureDirectory / "00-baseline.numbers")

    with pytest.raises(WriteError, match="is not a directory"):
        document.save(tmp_path / "no-such-folder" / "out.numbers")


def test_aFailedSaveLeavesTheExistingFileIntact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason the write goes to a temporary name and then replaces the target.

    Saving over the document you are editing is the ordinary case, so a write that
    dies part way through must not be able to leave a truncated zip where the file
    used to be.
    """
    working = tmp_path / "precious.numbers"
    shutil.copy(fixtureDirectory / "00-baseline.numbers", working)
    before = working.read_bytes()

    document = pybers.open(working)

    def explode(package: NumbersPackage, path: Path) -> None:
        path.write_bytes(b"half a zip")
        raise OSError("the disk filled up half way through")

    monkeypatch.setattr("pybers.writer.writePackage", explode)

    with pytest.raises(OSError, match="disk filled up"):
        document.save()

    assert working.read_bytes() == before, "a failed save damaged the original"
    leftovers = [item.name for item in tmp_path.iterdir() if item.name != "precious.numbers"]
    assert not leftovers, f"a failed save left {leftovers} behind"


def test_writeDocumentIsTheSameCallAsSave(tmp_path: Path) -> None:
    """The function and the method are one path, so neither can drift from the other."""
    document = pybers.open(fixtureDirectory / "00-baseline.numbers")
    viaFunction = tmp_path / "function.numbers"
    viaMethod = tmp_path / "method.numbers"

    writeDocument(document, viaFunction)
    document.save(viaMethod)

    assert viaFunction.read_bytes() == viaMethod.read_bytes()


# ── AC 2, 3 and 4: a numeric edit reaches its cell and touches nothing else ──

def workingCopy(name: str, tmp_path: Path) -> Path:
    """Copy a fixture somewhere writable, since a save lands in place by default."""
    working = tmp_path / f"{name}-edited.numbers"
    shutil.copy(fixtureDirectory / f"{name}.numbers", working)
    return working


def test_aDecimalWrittenToACellIsThereWhenTheFileIsReopened(tmp_path: Path) -> None:
    """AC 2 and AC 3 together, which is the pair a caller actually experiences."""
    working = workingCopy("11-value-types-noformats", tmp_path)

    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = Decimal("98765.4321")
    document.save()

    assert pybers.open(working).sheets[0].tables[0].cell("A1").value == Decimal(
        "98765.4321"
    )


@pytest.mark.parametrize(
    "text",
    [
        "0", "-1", "1.50", "0.001", "-98765.4321", "1E+20",
        "9999999999999999999999999999999999",
        "3.141592653589793238462643383279502",
    ],
)
def test_noDigitsAreGainedOrLostAcrossTheRoundTrip(text: str, tmp_path: Path) -> None:
    """AC 3 exactly: the scale survives too, so 1.50 does not come back as 1.5.

    A cell's trailing zeros are how Numbers shows its precision, so a value that
    round trips numerically but changes scale has still lost something visible.
    """
    working = workingCopy("11-value-types-noformats", tmp_path)

    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = Decimal(text)
    document.save()

    written = pybers.open(working).sheets[0].tables[0].cell("A1").value
    assert written == Decimal(text)
    assert str(written) == str(Decimal(text)), "the scale moved"


def test_oneEditChangesOneArchiveAndLeavesEveryOtherAlone(tmp_path: Path) -> None:
    """AC 4, by the same comparison AC 1 uses.

    The record is patched in its sixteen value bytes rather than rebuilt, so the
    tile does not even change length. Everything the model does not represent
    survives because nothing touched it.
    """
    working = workingCopy("11-value-types-noformats", tmp_path)
    source = fixtureDirectory / "11-value-types-noformats.numbers"

    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = Decimal("4242.42")
    document.save()

    differences = archiveDifferences(readPackage(source), readPackage(working))
    assert len(differences) == 1, (
        f"expected one changed archive, got {len(differences)}:\n  "
        + "\n  ".join(differences)
    )
    assert "type 6002" in differences[0], "the change was not in a tile"


def test_theNeighborsOfAnEditedCellAreUntouched(tmp_path: Path) -> None:
    """A wrong offset here writes into the wrong cell and raises nothing."""
    working = workingCopy("11-value-types-noformats", tmp_path)
    before = pybers.open(working).sheets[0].tables[0]
    expected = {
        reference: cell.value
        for reference, cell in before.cells.items()
        if reference != toCellReference("A1")
    }

    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = Decimal("4242.42")
    document.save()

    after = pybers.open(working).sheets[0].tables[0]
    for reference, value in expected.items():
        assert after.cells[reference].value == value, f"{reference} changed"


def test_aCellsNumberFormatSurvivesAnEdit(tmp_path: Path) -> None:
    """The trailing references carry the format, so a rebuilt record would drop it.

    Asserted through the archive rather than the model, because pybers does not read
    number formats yet and so cannot see the loss from the model side.
    """
    source = fixtureDirectory / "12-number-currency.numbers"
    working = workingCopy("12-number-currency", tmp_path)

    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    target = next(
        reference for reference, cell in sorted(table.cells.items(), key=lambda kv: (kv[0].row, kv[0].col))
        if isinstance(cell.value, Decimal)
    )
    table.cells[target].value = Decimal("77.77")
    document.save()

    beforeRecords = numericRecords(source)
    afterRecords = numericRecords(working)
    assert len(beforeRecords) == len(afterRecords)
    for before, after in zip(beforeRecords, afterRecords):
        assert before.references == after.references, (
            "a cell's format references changed, so its formatting was dropped"
        )


# ── AC 6 and its siblings: a write that cannot be correct raises ─────────────

def test_writingOverAFormulaIsRefused(tmp_path: Path) -> None:
    """AC 6. The formula and its cached result are separate storage.

    Writing only the result leaves a document whose formula and displayed value
    disagree until Numbers recalculates, so this refuses instead.
    """
    working = workingCopy("18-formula-literals", tmp_path)

    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = Decimal("999")

    with pytest.raises(WriteError, match="backed by a formula"):
        document.save()


def test_aRefusedSaveLeavesTheFileExactlyAsItWas(tmp_path: Path) -> None:
    """The refusal is worth nothing if half the package has already been written."""
    working = workingCopy("18-formula-literals", tmp_path)
    before = working.read_bytes()

    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = Decimal("999")
    with pytest.raises(WriteError):
        document.save()

    assert working.read_bytes() == before


def test_writingTextIsRefusedRatherThanDropped(tmp_path: Path) -> None:
    """Text needs the table's pooled string list, which this version does not write."""
    working = workingCopy("11-value-types-noformats", tmp_path)

    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = "not a number"

    with pytest.raises(WriteError, match="only a Decimal"):
        document.save()


def test_changingACellsTypeIsRefused(tmp_path: Path) -> None:
    """A number written over a date needs a new record, not a patched one."""
    working = workingCopy("11-value-types-noformats", tmp_path)

    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    dateCell = next(
        cell for cell in table.cells.values()
        if cell.value is not None and not isinstance(cell.value, (Decimal, str, bool))
    )
    dateCell.value = Decimal("1")

    with pytest.raises(WriteError, match="Changing a cell's type"):
        document.save()


# ── AC 5: the golden file ────────────────────────────────────────────────────

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"


def test_aNumericEditMatchesTheGoldenFile(tmp_path: Path) -> None:
    """AC 5. One mutation against a fixture, compared to a file Numbers accepted.

    Every other test here checks pybers against pybers, which can agree with itself
    while both halves are wrong. This one compares against output that a human opened
    in Numbers and confirmed, which is the only check that reaches outside this
    library. This one was confirmed on 2026-09-01 in Numbers 15.3.1: it opened with no
    warning and no repair prompt, and every interactive control in the row survived
    the edit. See `tests/golden/README.md`.

    Compared with `archiveDifferences` rather than byte for byte, because the zip
    envelope is known to differ by the local extra fields `zipfile` cannot emit.
    """
    golden = goldenDirectory / "11-value-types-noformats-A1-edited.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    working = workingCopy("11-value-types-noformats", tmp_path)
    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = Decimal("98765.4321")
    document.save()

    differences = archiveDifferences(readPackage(golden), readPackage(working))
    assert not differences, (
        "the writer no longer produces the confirmed output:\n  "
        + "\n  ".join(differences)
    )


def test_theGoldenFileHoldsWhatItClaimsTo() -> None:
    """Guard the guard: a golden that stopped holding the edit would pass silently.

    The test above compares two files this library produced. If the golden were
    replaced by an unedited copy, that comparison would still pass on the day the
    writer broke in the same direction, so the golden's own contents are asserted
    here against the values confirmed on screen on 2026-09-01.
    """
    table = pybers.open(
        goldenDirectory / "11-value-types-noformats-A1-edited.numbers"
    ).sheets[0].tables[0]

    assert table.cell("A1").value == Decimal("98765.4321")
    # The label row is deliberately stale, which is how the edit is visible by eye.
    assert table.cell("A2").value == "plain number 1234.5"
    assert table.cell("B1").value == Decimal("42")
    assert table.cell("E1").value is True
    assert table.cell("I1").value == "Item 1"


def test_aMultiSheetEditMatchesTheGoldenFile(tmp_path: Path) -> None:
    """The same check one sheet wider, driven by `Document.cellsIterate`.

    Every other edit test here changes one table on one sheet, so nothing covered
    `documentEditsApplied` walking sheets and filtering tables out of each drawable
    list. That code decides which table an edit lands in, and its failure mode is the
    format's usual one, a plausible file with the right number in the wrong table.

    Confirmed on 2026-09-02 in Numbers 15.3.1: the file opened with no warning and no
    repair prompt, and all twelve edits landed in the table they were addressed to. The
    same confirmation found that Numbers does NOT recalculate the formulas depending on
    those cells, which is why the guard below asserts the stale cached results rather
    than the arithmetic. See `tests/golden/README.md`.
    """
    golden = goldenDirectory / "20-formula-shapes-multisheet-edited.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    working = workingCopy("20-formula-shapes", tmp_path)
    document = pybers.open(working)
    for _, _, cell in document.cellsIterate():
        # Rows 11 and 12 are the formula row and its labels. A formula-backed cell is
        # refused rather than overwritten, and a label is not a number.
        if isinstance(cell.value, Decimal) and cell.reference.row <= 10:
            cell.value = cell.value + Decimal(1000)
    document.save()

    differences = archiveDifferences(readPackage(golden), readPackage(working))
    assert not differences, (
        "the writer no longer produces the confirmed output:\n  "
        + "\n  ".join(differences)
    )


def test_theMultiSheetGoldenHoldsWhatItClaimsTo() -> None:
    """Guard the guard, the same way the single-table golden is guarded.

    Asserted per table rather than in one sweep, because the whole point of this
    golden is which table each edit landed in.
    """
    document = pybers.open(
        goldenDirectory / "20-formula-shapes-multisheet-edited.numbers"
    )

    first = document.sheet("Sheet 1").table("Table 1")
    assert [first.cell(f"A{row}").value for row in range(1, 11)] == [
        Decimal(1000 + row) for row in range(1, 11)
    ]
    # Deliberately stale, and confirmed stale on screen: `A11` is `SUM(A1:A10)`, whose
    # operands now sum to 10055, and Numbers displays the cached 55 after an open.
    assert first.cell("A12").value == "Typed directly: SUM(A1:A10)"
    assert first.cell("A11").value == Decimal(55)
    assert sum(first.cell(f"A{row}").value for row in range(1, 11)) == Decimal(10055)

    assert document.sheet("Sheet 1").table("Table 2").cell("A1").value == Decimal(1042)
    assert document.sheet("Sheet 2").table("Table 1").cell("A1").value == Decimal(1053)


def test_editingAndSavingRepeatedlyKeepsWorking(tmp_path: Path) -> None:
    """A save rewrites the archives it read, so a second one has to see the first.

    The package travels with the `Document` and `messageReplace` swaps the archive in
    place, so a second save indexes the already-edited archives. Nothing else asserts
    that, and a stale index would write the second edit on top of the original bytes.
    """
    working = workingCopy("11-value-types-noformats", tmp_path)

    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = Decimal("111.11")
    document.save()
    assert pybers.open(working).sheets[0].tables[0].cell("A1").value == Decimal("111.11")

    # Same handle, edited again.
    document.sheets[0].tables[0].cell("A1").value = Decimal("222.22")
    document.save()
    assert pybers.open(working).sheets[0].tables[0].cell("A1").value == Decimal("222.22")

    # A fresh handle editing a different cell leaves the first edit alone.
    second = pybers.open(working)
    second.sheets[0].tables[0].cell("B1").value = Decimal("777")
    second.save()

    table = pybers.open(working).sheets[0].tables[0]
    assert table.cell("A1").value == Decimal("222.22")
    assert table.cell("B1").value == Decimal("777")
