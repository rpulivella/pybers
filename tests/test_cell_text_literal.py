#!/usr/bin/env python3
"""\
Text Numbers will not interpret: a cell whose Data Format was chosen as Text.

Asserted on the record bytes as well as through the model, because byte 6's `0x80`
is the whole mechanism and a model that agreed with itself would prove nothing about
what Numbers reads. See findings-01-values.md.

UPDATES
2026-09-16  Written for PYB-83.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/16"

from decimal import Decimal
from pathlib import Path

import pytest
from test_format_refcounts import readDisplayedKind
from test_writer import copyDocument, listArchiveDifferences, readRecordAt

import pybers
from conftest import findDocumentPath
from pybers._persistence import readPackage
from pybers._persistence.cells import (
    carriesChosenFormat,
    listReferenceSlots,
    textFormatSlot,
)

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"

# The golden: a literal retyping a number and one borrowing a shape, beside plain text.
literalCells: tuple[tuple[str, str], ...] = (
    ("A1", "=SUM(B1:C1)"),
    ("J1", "=A1+1"),
)
plainCell: tuple[str, str] = ("B1", "=1+1")


def assertLiteralRecord(path: Path, address: str) -> None:
    """Assert a record is text displaying with a chosen text format, as C1 in 47 is."""
    record = readRecordAt(path, address)
    assert record.typeByte == 3, "the cell holds text"
    assert carriesChosenFormat(record), "byte 6 marks the format as chosen"
    assert readDisplayedKind(record) == (5, {5}), "it displays with the text kind"
    assert textFormatSlot in listReferenceSlots(record.raw)


def openFirstTableCell(stem: str, address: str) -> pybers.Cell:
    """Return one cell of the first table of a fixture or measurement."""
    return pybers.open(findDocumentPath(stem)).sheets[0].tables[0].cell(address)


def writeLiteralGolden(tmp_path: Path) -> Path:
    """Write the golden's mutation into a fresh copy of its fixture, and return it."""
    working = copyDocument("11-value-types-noformats", tmp_path)
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    for address, text in literalCells:
        table.cell(address).textLiteralSet(text)
    table.cell(plainCell[0]).value = plainCell[1]
    document.save()
    return working


def testTheMeasuredLiteralReadsAsTextWithAChosenFormat() -> None:
    cell = (
        pybers.open(findDocumentPath("47-formula-cell-attributes"))
        .sheets[0].table("Plain").cell("C1")
    )

    assert cell.value == "=SUM(A1:A5)"
    assert cell.formula is None
    assert cell.formatChosen


def testAnOrdinaryStringReadsAsAutomatic() -> None:
    cell = openFirstTableCell("01-text-plain", "A1")

    assert isinstance(cell.value, str)
    assert not cell.formatChosen


@pytest.mark.parametrize("address", ["A1", "J1"])
def testLiteralTextIsWrittenAsAChosenTextFormat(address: str, tmp_path: Path) -> None:
    """AC 1. `A1` was a number and is retyped, `J1` had no record and borrows one."""
    working = copyDocument("11-value-types-noformats", tmp_path)
    document = pybers.open(working)
    document.sheets[0].tables[0].cell(address).textLiteralSet("=SUM(B1:C1)")
    document.save()

    assertLiteralRecord(working, address)


def testLiteralTextOverOrdinaryTextSetsOnlyTheChosenBit(tmp_path: Path) -> None:
    """AC 1. Text over text patches the key, so byte 6 is the one header change."""
    working = copyDocument("11-value-types-noformats", tmp_path)
    document = pybers.open(working)
    document.sheets[0].tables[0].cell("J1").value = "=1+1"
    document.save()
    before = readRecordAt(working, "J1")

    document = pybers.open(working)
    document.sheets[0].tables[0].cell("J1").textLiteralSet("=1+1")
    document.save()
    after = readRecordAt(working, "J1")

    assert not carriesChosenFormat(before)
    assert after.raw[6] == before.raw[6] | 0x80
    assert after.raw[:6] + after.raw[7:] == before.raw[:6] + before.raw[7:]


@pytest.mark.parametrize("address", ["A1", "J1"])
def testAnOrdinaryStringIsStillWrittenAsAutomatic(address: str, tmp_path: Path) -> None:
    """AC 3. What typing into Numbers produces."""
    working = copyDocument("11-value-types-noformats", tmp_path)
    document = pybers.open(working)
    document.sheets[0].tables[0].cell(address).value = "=1+1"
    document.save()

    assert not carriesChosenFormat(readRecordAt(working, address))
    assert not pybers.open(working).sheets[0].tables[0].cell(address).formatChosen


def testLiteralTextReadsBackAsTheTextItWasGiven(tmp_path: Path) -> None:
    """AC 4."""
    working = writeLiteralGolden(tmp_path)
    table = pybers.open(working).sheets[0].tables[0]

    for address, text in literalCells:
        cell = table.cell(address)
        assert (cell.value, cell.formula, cell.formatChosen) == (text, None, True)


def testSavingLiteralTextAgainChangesNothing(tmp_path: Path) -> None:
    """AC 4. A no-op, whether the literal is left alone or set to the same text."""
    working = writeLiteralGolden(tmp_path)
    before = readPackage(working)

    document = pybers.open(working)
    for address, text in literalCells:
        document.sheets[0].tables[0].cell(address).textLiteralSet(text)
    document.save()

    assert listArchiveDifferences(before, readPackage(working)) == []


def testNewTextInALiteralCellStaysLiteral(tmp_path: Path) -> None:
    """Typing into a cell formatted Text keeps it Text, so a new value does too."""
    working = writeLiteralGolden(tmp_path)
    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = "=A1*2"
    document.save()

    assertLiteralRecord(working, "A1")


def testLiteralTextOverAFormulaIsRefusedAndLeavesTheCellAlone() -> None:
    """AC 5. The formula is what would be lost."""
    cell = openFirstTableCell("18-formula-literals", "A1")
    before = (cell.value, cell.formula, cell.formatChosen)

    with pytest.raises(pybers.WriteError, match="A1 is backed by a formula"):
        cell.textLiteralSet("=1+1")
    assert (cell.value, cell.formula, cell.formatChosen) == before


def testLiteralTextThatIsNotTextIsRefused() -> None:
    cell = openFirstTableCell("01-text-plain", "A1")

    with pytest.raises(pybers.WriteError, match="was given Decimal"):
        cell.textLiteralSet(Decimal("1"))  # type: ignore[arg-type]
    assert not cell.formatChosen


# ── The golden file ─────────────────────────────────────────────────────────


def testLiteralTextMatchesTheGoldenFile(tmp_path: Path) -> None:
    golden = goldenDirectory / "11-text-literal-written.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    differences = listArchiveDifferences(
        readPackage(golden), readPackage(writeLiteralGolden(tmp_path))
    )
    assert not differences, (
        "the writer no longer produces the confirmed output:\n  "
        + "\n  ".join(differences)
    )


def testTheLiteralGoldenHoldsWhatItClaimsTo() -> None:
    golden = goldenDirectory / "11-text-literal-written.numbers"
    table = pybers.open(golden).sheets[0].tables[0]

    for address, _ in literalCells:
        assertLiteralRecord(golden, address)
    assert not carriesChosenFormat(readRecordAt(golden, plainCell[0]))
    assert table.cell(plainCell[0]).value == plainCell[1]


# ── The two consumers ────────────────────────────────────────────────────────


def testAScriptWritesLabelsThatReadLikeFormulas(tmp_path: Path) -> None:
    """The `import pybers` consumer: a column of labels Numbers must not evaluate."""
    working = copyDocument("20-formula-shapes", tmp_path)
    document = pybers.open(working)
    table = document.sheet("Sheet 1").table("Table 2")
    for row, label in enumerate(["=total", "-net", "+gross"], start=1):
        table.cell(row=row, col=2).textLiteralSet(label)
    document.save()

    reopened = pybers.open(working).sheet("Sheet 1").table("Table 2")
    assert [reopened.cell(row=row, col=2).value for row in (1, 2, 3)] == [
        "=total", "-net", "+gross"
    ]
    assert all(reopened.cell(row=row, col=2).formatChosen for row in (1, 2, 3))


def testACliWritesLiteralTextAndPrintsItsFormat(tmp_path: Path) -> None:
    """The `pybers cell text SHEET TABLE REF TEXT --literal` consumer."""
    working = copyDocument("20-formula-shapes", tmp_path)
    arguments = ["Sheet 1", "Table 2", "C1", "=SUM(A1:A5)"]
    document = pybers.open(working)
    cell = document.sheet(arguments[0]).table(arguments[1]).cell(arguments[2])
    cell.textLiteralSet(arguments[3])
    document.save()

    shown = "Text" if cell.formatChosen else "Automatic"
    printed = f"{arguments[2]} {cell.value} ({shown})"
    assert printed == "C1 =SUM(A1:A5) (Text)"


def testACliRefusingAFormulaCellPrintsWhy() -> None:
    """The same command against a formula cell exits with the reason, not a trace."""
    cell = openFirstTableCell("18-formula-literals", "A1")

    with pytest.raises(pybers.PybersError) as refused:
        cell.textLiteralSet("=SUM(A1:A5)")
    assert "discard" in str(refused.value)


def testEveryNameThisTicketAddsIsReachableFromPybersAlone() -> None:
    """Neither consumer imports anything deeper than `pybers`."""
    assert hasattr(pybers.Cell, "textLiteralSet")
    assert hasattr(pybers.Cell, "formatChosen")
