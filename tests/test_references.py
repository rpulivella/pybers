#!/usr/bin/env python3
"""\
Every reference a document makes, found, followed and moved.

`20-formula-shapes` is the measurement that matters here: it is the only one holding
a reference into another table and a reference into another sheet, side by side
with six table-local ones, so a walk that took the wrong table has somewhere to
show it.

The retarget assertions read the formula back as TEXT rather than as nodes. A
node array can be shifted correctly and still resolve against the wrong host, and
`=SUM(H2:H11)` is the sentence a person would check in Numbers.

UPDATES
2026-09-08  Written for #13.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

import dataclasses
import shutil
from pathlib import Path

import pytest

import pybers
from conftest import findDocumentPath, readDataListBytes
from pybers import Table
from pybers._persistence import readPackage
from pybers._persistence.difference import listPackageDifferences
from pybers.formula.nodes import FormulaRange, FormulaReference, Span

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"

# What `20-formula-shapes` reads as before anything moves, which is also what the
# retarget below has to leave the last two rows of.
originalText: dict[str, str] = {
    "A11": "=SUM(A1:A10)",
    "B11": "=SUM(A1:A10)+1",
    "C11": '=SUMIFS(A1:A10,A1:A10,">5")',
    "D11": '=IF(SUM(A1:A5)>10,"big","small")',
    "E11": "=A11*2",
    "F11": "=SUM(A)",
    "G11": "=Table 2::A1",
    "H11": "=Sheet 2::Table 1::A1",
}

# Row 10 of the golden, written before the retarget because row 11 carries no
# anchored reference at all. Every combination of locked and free axis, once for a
# single cell and once for a range, so which axis moved is readable in the result.
authoredRowTen: tuple[tuple[str, str], ...] = (
    ("A10", "=$A$1*10"),
    ("B10", "=$A$3*2"),
    ("C10", "=A$3*2"),
    ("D10", "=$A3*2"),
    ("E10", "=SUM($A$1:$A$5)"),
    ("F10", "=SUM(A$1:A$5)"),
    ("G10", "=SUM($A1:$A5)"),
    ("H10", "=$A$4"),
)

# Those eight after the retarget. Four could not move, and each of the four that
# could moved on one axis alone.
rowTenRetargeted: dict[str, str] = {
    "A10": "=$A$1*10",
    "B10": "=$A$3*2",
    "C10": "=H$3*2",
    "D10": "=$A4*2",
    "E10": "=SUM($A$1:$A$5)",
    "F10": "=SUM(H$1:H$5)",
    "G10": "=SUM($A2:$A6)",
    "H10": "=$A$4",
}

# The same eight after every reference into `Sheet 1 / Table 1` moves one row down
# and seven columns right. The last two point elsewhere and do not move.
retargetedText: dict[str, str] = {
    "A11": "=SUM(H2:H11)",
    "B11": "=SUM(H2:H11)+1",
    "C11": '=SUMIFS(H2:H11,H2:H11,">5")',
    "D11": '=IF(SUM(H2:H6)>10,"big","small")',
    "E11": "=H12*2",
    "F11": "=SUM(H)",
    "G11": "=Table 2::A1",
    "H11": "=Sheet 2::Table 1::A1",
}


def openShapes() -> pybers.Document:
    """Return `20-formula-shapes`, the three-table two-sheet measurement."""
    return pybers.open(findDocumentPath("20-formula-shapes"))


def copyDocument(name: str, into: Path) -> Path:
    """Return a writable copy of a document, so a save never touches the documents."""
    return Path(shutil.copy(findDocumentPath(name), into / f"{name}.numbers"))


def readFormulaTexts(table: Table) -> dict[str, str]:
    """Return every formula a table holds, as text, keyed by its cell."""
    return {
        str(reference): cell.formulaText
        for reference, cell in sorted(
            table.cells.items(), key=lambda pair: pair[0].asRowColumn()
        )
        if cell.formula is not None
    }


def findLocationAt(document: pybers.Document, name: str) -> pybers.ReferenceLocation:
    """Return the one reference location in a named cell, where there is one."""
    return next(
        location
        for location in document.referencesIterate()
        if str(location.cell.address) == name
    )


# ── AC 1: a reference names its target, and the target resolves ──────────────


def testACrossTableReferenceResolvesToTheTableObjectItNames() -> None:
    """AC 1. `G11` holds `=Table 2::A1`, and that is the Table 2 on Sheet 1."""
    document = openShapes()
    assert findLocationAt(document, "G11").target is (
        document.sheet("Sheet 1").table("Table 2")
    )


def testACrossSheetReferenceResolvesToTheTableOnTheOtherSheet() -> None:
    """AC 1.i. Two tables are named `Table 1`, and `H11` names the far one.

    The archive draws no distinction between another table and another sheet, so
    the only thing separating these two is the identity, which is the claim.
    """
    document = openShapes()
    far = findLocationAt(document, "H11").target
    assert far is document.sheet("Sheet 2").table("Table 1")
    assert far is not document.sheet(1).table("Table 1")


def testATableLocalReferenceTargetsTheTableHoldingIt() -> None:
    """AC 1. Every location has a table, so filtering by one tests no absence."""
    document = openShapes()
    assert findLocationAt(document, "A11").target is document.sheet(1).table("Table 1")


def testTableForFindsATableByTheIdentityAFormulaNamesItBy() -> None:
    """AC 1. The reverse of `tableIdentities`, and what a location resolves through."""
    document = openShapes()
    table = document.sheet("Sheet 1").table("Table 2")
    assert document.tableFor(table.identifier) is table


def testTableForRaisesNamingAnIdentityTheDocumentDoesNotHold() -> None:
    """AC 1. A miss says which identity failed rather than returning nothing."""
    with pytest.raises(pybers.SelectionError, match="ff" * 16):
        openShapes().tableFor("ff" * 16)


def testTheWalkRefusesAReferenceIntoATableTheDocumentDoesNotHold() -> None:
    """AC 1. Skipping it would report fewer references than the document makes.

    The refusal lives in the walk rather than in `tableFor`, and the two are
    separate branches, so a test of one says nothing about the other.
    """
    document = openShapes()
    document.sheet("Sheet 1").table("Table 2").identifier = "ff" * 16

    with pytest.raises(pybers.SelectionError, match="reaches into table"):
        list(document.referencesIterate())


def testACellAddressNeverNamesATable() -> None:
    """AC 1.ii. A position stays table-local: a row and a column, nothing more."""
    assert [field.name for field in dataclasses.fields(pybers.CellAddress)] == [
        "row", "col",
    ]
    with pytest.raises(pybers.ReferenceError, match="names a table"):
        pybers.CellAddress.parse("Table 2::A1")


# ── AC 2: every reference, in one call ───────────────────────────────────────


def testEveryReferenceInTheDocumentIsWalkedInOneCall() -> None:
    """AC 2. Nine locations across eight formulas, none of them named in advance."""
    locations = list(openShapes().referencesIterate())
    assert [str(location.cell.address) for location in locations] == [
        "A11", "B11", "C11", "C11", "D11", "E11", "F11", "G11", "H11",
    ]


def testTheWalkYieldsEachRangeOfAMultiRangeCallSeparately() -> None:
    """AC 2. `SUMIFS(A1:A10,A1:A10,">5")` is two ranges, and both can move."""
    locations = [
        location for location in openShapes().referencesIterate()
        if str(location.cell.address) == "C11"
    ]
    assert [location.index for location in locations] == [0, 1]
    assert all(isinstance(location.content, FormulaRange) for location in locations)


def testTheWalkFindsReferencesOnEverySheet() -> None:
    """AC 2. A walk stopping at the first sheet would still pass most of these.

    Both locations here point into Sheet 2's table: one from the sheet holding it and
    one from the sheet before it, so a walk finding either alone is short.
    """
    document = openShapes()
    far = document.sheet("Sheet 2").table("Table 1")
    far.cell("C1").formulaText = "=A1+1"

    found = [
        (location.sheet.name, str(location.cell.address))
        for location in document.referencesIterate()
        if location.target is far
    ]
    assert found == [("Sheet 1", "H11"), ("Sheet 2", "C1")]


def testACellHoldingNoFormulaContributesNoSite() -> None:
    """AC 2. `20-formula-shapes` stores 96 cells and 8 of them hold a formula."""
    document = openShapes()
    stored = sum(
        len(table.cells) for sheet in document.sheets for table in sheet.tables
    )
    assert stored > len(list(document.referencesIterate()))


def testASiteReportsWhetherItLeavesTheTableHoldingIt() -> None:
    """AC 2. What a CLI filters on, and the reason `target` alone is not enough."""
    document = openShapes()
    assert [
        str(location.cell.address) for location in document.referencesIterate()
        if location.crossTable
    ] == ["G11", "H11"]


def testASiteShowsItsReferenceAsNumbersSpellsIt() -> None:
    """AC 2. One reference on its own, without rendering the formula around it."""
    document = openShapes()
    assert findLocationAt(document, "G11").text == "Table 2::A1"
    assert findLocationAt(document, "H11").text == "Sheet 2::Table 1::A1"
    assert findLocationAt(document, "F11").text == "A"


def testASiteWhoseFormulaWasReplacedRefusesRatherThanReadingTheWrongNode() -> None:
    """AC 2. A location views a formula, so dropping that formula invalidates it."""
    document = openShapes()
    location = findLocationAt(document, "A11")
    location.cell.formula = None
    with pytest.raises(pybers.FormulaError, match="no longer the reference"):
        _ = location.content


# ── AC 3: a cross-table document round trips ─────────────────────────────────


def testCrossTableLinksSurviveASaveAndAReopen(tmp_path: Path) -> None:
    """AC 3. Identity is what a link is, so the check is that it resolves again."""
    working = copyDocument("20-formula-shapes", tmp_path)
    pybers.open(working).save()

    after = pybers.open(working)
    firstSheet, secondSheet = after.sheet("Sheet 1"), after.sheet("Sheet 2")
    assert findLocationAt(after, "G11").target is firstSheet.table("Table 2")
    assert findLocationAt(after, "H11").target is secondSheet.table("Table 1")
    assert readFormulaTexts(after.sheet(1).table("Table 1")) == originalText


# ── AC 4: a scripted retarget ────────────────────────────────────────────────


def testARetargetMovesEveryReferenceIntoOneTableAndNoOther() -> None:
    """AC 4. Seven locations point into Table 1, and the two pointing away stay put."""
    document = openShapes()
    target = document.sheet("Sheet 1").table("Table 1")

    moved = sum(
        location.shift(rows=1, cols=7)
        for location in document.referencesIterate()
        if location.target is target
    )

    assert moved == 7
    assert readFormulaTexts(target) == retargetedText


def testARetargetSurvivesASaveAndAReopen(tmp_path: Path) -> None:
    """AC 4. The edit reaches the file, not only the model that made it."""
    working = copyDocument("20-formula-shapes", tmp_path)
    document = pybers.open(working)
    target = document.sheet("Sheet 1").table("Table 1")
    for location in document.referencesIterate():
        if location.target is target:
            location.shift(rows=1, cols=7)
    document.save()

    after = pybers.open(working)
    assert readFormulaTexts(after.sheet(1).table("Table 1")) == retargetedText


def testALockedAxisDoesNotMove() -> None:
    """AC 4.i. `B$1` shifted down one row is still `B$1`, and its column is not."""
    document = openShapes()
    cell = document.sheet("Sheet 1").table("Table 2").cell("E9")
    cell.formulaText = "=B$1"
    location = findLocationAt(document, "E9")

    assert location.shift(rows=1) is False
    assert location.text == "B$1"
    assert location.shift(cols=1) is True
    assert location.text == "C$1"


def testABrokenReferenceStaysBroken() -> None:
    """AC 4.ii. Numbers records `#REF` as coordinates pointing nowhere on purpose."""
    document = pybers.open(findDocumentPath("21-formula-errors"))
    location = findLocationAt(document, "C1")

    assert location.broken
    assert location.shift(rows=1, cols=7) is False
    assert location.broken


def testARangeMovesBothEndsTogether() -> None:
    """AC 4.iii. `C3:C25` shifted down one is `C4:C26`, never `C3:C26`."""
    document = openShapes()
    cell = document.sheet("Sheet 1").table("Table 2").cell("E10")
    cell.formulaText = "=SUM(C3:C25)"
    location = findLocationAt(document, "E10")

    assert location.shift(rows=1) is True
    assert location.text == "C4:C26"


def testARangeLockedAtBothEndsDoesNotMove() -> None:
    """AC 4.i and 4.iii together: one `absolute` covers a whole axis of a span."""
    assert FormulaRange(rows=Span(3, 25, absolute=True)).shifted(rows=1) == (
        FormulaRange(rows=Span(3, 25, absolute=True))
    )


def testAnUnboundedAxisHasNothingToMove() -> None:
    """AC 4. `SUM(A)` is a whole column, so its rows are absent rather than zero."""
    document = openShapes()
    location = findLocationAt(document, "F11")

    assert location.shift(rows=1) is False
    assert location.shift(cols=7) is True
    assert location.text == "H"


def testAShiftOfNothingReportsNothingAndWritesNothing() -> None:
    """AC 4. A no-op must report accurately and must not touch the formula."""
    document = openShapes()
    before = {
        str(location.cell.address): location.cell.formula
        for location in document.referencesIterate()
    }

    assert not any(location.shift() for location in document.referencesIterate())
    assert all(
        location.cell.formula is before[str(location.cell.address)]
        for location in document.referencesIterate()
    )


def testAShiftOfNothingLeavesEveryArchiveUntouched(tmp_path: Path) -> None:
    """AC 4. The write path has to agree that nothing happened, not only the model."""
    working = copyDocument("20-formula-shapes", tmp_path)
    before = readPackage(working)
    document = pybers.open(working)
    for location in document.referencesIterate():
        location.shift()
    document.save()

    assert listPackageDifferences(before, readPackage(working)) == []


def testShiftingOneLocationLeavesTheOthersOnThatFormulaUsable() -> None:
    """AC 4. Two ranges in one formula, and moving one does not strand the other."""
    document = openShapes()
    first, second = (
        location for location in document.referencesIterate()
        if str(location.cell.address) == "C11"
    )

    assert first.shift(cols=7) is True
    assert second.shift(cols=7) is True
    assert second.cell.formulaText == '=SUMIFS(H1:H10,H1:H10,">5")'


def testAReferenceCarriesFieldsThisModelDoesNotInterpretThroughAShift() -> None:
    """AC 4. A shift patches the node it was read as, rather than building a new one."""
    document = openShapes()
    location = findLocationAt(document, "G11")
    raw = location.node.raw

    assert raw
    assert location.shift(cols=1) is True
    assert location.node.raw == raw


# ── AC 3 and AC 4: the golden, which is the only test Numbers confirmed ──────


def buildGolden(working: Path) -> int:
    """Write the golden's row 10, retarget the table, and return what moved.

    Row 10 exists so the golden covers anchoring, which row 11 does not carry a
    single example of. Four of its eight references cannot move and four can, and
    each of the four kinds is one axis different from another.
    """
    document = pybers.open(working)
    target = document.sheet("Sheet 1").table("Table 1")
    for address, text in authoredRowTen:
        target.cell(address).formulaText = text
    moved = sum(
        location.shift(rows=1, cols=7)
        for location in document.referencesIterate()
        if location.target is target
    )
    document.save()
    return moved


def testARetargetMatchesItsGoldenFile(tmp_path: Path) -> None:
    """A retarget against output confirmed in Numbers itself.

    Every other test here checks pybers against pybers. See
    `tests/golden/README.md` for the confirmation state of this file.
    """
    golden = goldenDirectory / "20-formula-retargeted.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    working = copyDocument("20-formula-shapes", tmp_path)
    assert buildGolden(working) == 11
    assert readDataListBytes(golden) == readDataListBytes(working), (
        "the writer no longer produces the confirmed formula lists"
    )


def testTheRetargetGoldenHoldsWhatItClaimsTo() -> None:
    """Guard the guard: a golden replaced by an unedited copy would pass silently.

    The two cross-table formulas are asserted structurally as well, because a
    retarget that dropped a table identity still reads back as a formula.
    """
    golden = goldenDirectory / "20-formula-retargeted.numbers"
    if not golden.is_file():
        pytest.skip(f"{golden.name} is not present yet")
    document = pybers.open(golden)

    assert readFormulaTexts(document.sheet(1).table("Table 1")) == (
        rowTenRetargeted | retargetedText
    )
    assert findLocationAt(document, "G11").target is document.sheet(1).table("Table 2")
    assert findLocationAt(document, "H11").target is document.sheet(2).table("Table 1")


def testTheGoldensAnchoredReferencesRecordWhichAxisMoved() -> None:
    """Guard the guard: all four anchoring cases, each differing by one axis.

    An implementation moving a locked axis, or failing to move a free one beside
    it, changes exactly one of these four and leaves the other three passing.
    """
    golden = goldenDirectory / "20-formula-retargeted.numbers"
    if not golden.is_file():
        pytest.skip(f"{golden.name} is not present yet")
    table = pybers.open(golden).sheet(1).table("Table 1")

    assert table.cell("B10").formulaText == "=$A$3*2"
    assert table.cell("C10").formulaText == "=H$3*2"
    assert table.cell("D10").formulaText == "=$A4*2"
    assert table.cell("E10").formulaText == "=SUM($A$1:$A$5)"


# ── AC 5: identity outlives a name ───────────────────────────────────────────


def testACrossTableReferenceSurvivesRenamingTheTableItPointsAt() -> None:
    """AC 5. The archive stores the identity, so a rename is a display change."""
    document = openShapes()
    location = findLocationAt(document, "G11")
    target = location.target

    target.name = "Receipts"

    assert location.target is target
    assert location.text == "Receipts::A1"
    assert location.cell.formulaText == "=Receipts::A1"


def testRenamingATableDoesNotDisturbAReferenceIntoADifferentOne() -> None:
    """AC 5. Guard the guard: a rename that renamed by name would pass the above."""
    document = openShapes()
    document.sheet("Sheet 1").table("Table 2").name = "Receipts"

    assert findLocationAt(document, "H11").text == "Sheet 2::Table 1::A1"


# ── The two consumers ────────────────────────────────────────────────────────


def testAScriptRetargetsOneTableInThreeLines() -> None:
    """The `import pybers` consumer, written as a script author would write it.

    The assertion is the shape as much as the count. A `target` that could be
    absent, or a shift needing the node index, would each add a branch here.
    """
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    sales = document.sheet("Sheet 1").table("Table 1")
    moved = sum(
        location.shift(rows=1, cols=7)
        for location in document.referencesIterate()
        if location.target is sales
    )

    assert moved == 7


def testACliListsEveryReferenceWithWhereItIsAndWhereItPoints() -> None:
    """The `pybers references list` consumer: one printable line per reference."""
    document = openShapes()
    report = [
        f"{location.sheet.name}/{location.table.name}/{location.cell.address}"
        f"  {location.text}  -> {location.target.name}"
        for location in document.referencesIterate()
    ]

    assert report[0] == "Sheet 1/Table 1/A11  A1:A10  -> Table 1"
    assert report[-1] == (
        "Sheet 1/Table 1/H11  Sheet 2::Table 1::A1  -> Table 1"
    )
    assert len(report) == 9


def testACliReportsBrokenReferencesAndTheirCount() -> None:
    """The `pybers references check` consumer, whose exit code is that count."""
    document = pybers.open(findDocumentPath("21-formula-errors"))
    broken = [location for location in document.referencesIterate() if location.broken]

    assert [str(location.cell.address) for location in broken] == ["C1"]


def testATuiFollowsAReferenceToTheCellItPointsAt() -> None:
    """The reveal-target action: from the reference under the cursor to its cell."""
    document = openShapes()
    location = findLocationAt(document, "G11")

    destination = location.target.cell(
        location.content.resolve(location.cell.address)
    )

    assert destination.value == 42


def testATuiShowsEveryReferenceOfTheCellUnderTheCursor() -> None:
    """The inspector panel: the references of one cell, without walking the rest."""
    document = openShapes()
    cursor = document.sheet(1).table("Table 1").cell("C11")
    shown = [
        location.text
        for location in document.referencesIterate()
        if location.cell is cursor
    ]

    assert shown == ["A1:A10", "A1:A10"]


def testEveryNameThisTicketAddsIsReachableFromPybersAlone() -> None:
    """Neither consumer imports anything deeper than `pybers`."""
    assert pybers.ReferenceLocation is not None
    assert hasattr(pybers.Document, "referencesIterate")
    assert hasattr(pybers.Document, "tableFor")
    assert hasattr(pybers.FormulaReference, "shifted")
    assert hasattr(pybers.FormulaRange, "shifted")


# ── The arithmetic, at the node the format stores ────────────────────────────


def testShiftingLeavesTheStoredOffsetOfALockedAxisAlone() -> None:
    """An absolute axis is a line counted from one, and a relative one a distance."""
    reference = FormulaReference(
        column=pybers.Coordinate(2, absolute=True), row=pybers.Coordinate(-3)
    )
    moved = reference.shifted(rows=1, cols=7)

    assert moved.column == pybers.Coordinate(2, absolute=True)
    assert moved.row == pybers.Coordinate(-2)


def testShiftingReturnsTheSameObjectWhenNothingCanMove() -> None:
    """What `shift` reports False from, and the reason it writes nothing."""
    reference = FormulaReference(
        column=pybers.Coordinate(2, absolute=True),
        row=pybers.Coordinate(1, absolute=True),
    )

    assert reference.shifted(rows=1, cols=7) is reference
    assert reference.shifted() is reference


def testShiftingKeepsTheTableAReferencePointsAt() -> None:
    """A retarget moves where inside a table, never which table."""
    identity = "ab" * 16
    moved = FormulaReference(
        column=pybers.Coordinate(0), row=pybers.Coordinate(0), tableId=identity
    ).shifted(rows=1)

    assert moved.tableId == identity
