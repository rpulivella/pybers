#!/usr/bin/env python3
"""A1-style addressing: one cell, a rectangle, a list of rectangles.

The round trips here are the point. This format's characteristic failure is a
plausible wrong answer rather than an exception, and an off-by-one in the base-26
conversion or a dropped locking marker both produce a real address that names the
wrong cell. Parsing what each type emits and comparing is what catches that.

UPDATES
2026-09-01  Written for #9.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/01"

import inspect
from pathlib import Path

import pytest

import pybers
from pybers.model import (
    CellRange,
    CellRangeList,
    CellReference,
    MergeRange,
    ReferenceError,
    Table,
    columnLetter,
    columnNumber,
)
from pybers.model import reference as referenceModule
from pybers.model import table as tableModule

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"

allFixtures: list[Path] = sorted(fixtureDirectory.glob("*.numbers"))

# Either side of every base-26 boundary this library can reach, plus the two the
# conversion is most likely to get wrong: Z to AA, and ZZ to AAA.
boundaryColumns: list[int] = [1, 25, 26, 27, 28, 51, 52, 53, 701, 702, 703, 704]


def sampleTable() -> Table:
    """Return a three-by-three table, built through the public addressing only.

    The size is declared rather than grown into, because a Numbers table has a
    fixed row and column count and touching a far cell does not extend it.
    """
    table = Table(name="Table 1", rowCount=3, colCount=3)
    for reference in CellRange.parse("A1:C3"):
        table.cell(reference).value = reference.asReference()
    return table


# ── AC 1: one cell, addressed either way and reported both ways ──────────────

def test_aReferenceIsBuiltFromAStringOrFromARowAndColumn() -> None:
    assert CellReference.parse("B2") == CellReference(2, 2)
    assert CellReference(2, 2).asReference() == "B2"
    assert CellReference(2, 2).asRowColumn() == (2, 2)


# AC 1.a
@pytest.mark.parametrize("col", boundaryColumns)
def test_aColumnSurvivesTheBase26Boundary(col: int) -> None:
    """Z is 26 and AA is 27, so a plain base conversion is off by one here."""
    assert columnNumber(columnLetter(col)) == col


def test_theBase26BoundaryIsWhereItIsClaimedToBe() -> None:
    """Pin the boundary itself, since the round trip above would survive a
    conversion that was self-consistently wrong in both directions."""
    assert columnLetter(1) == "A"
    assert columnLetter(26) == "Z"
    assert columnLetter(27) == "AA"
    assert columnLetter(702) == "ZZ"
    assert columnLetter(703) == "AAA"
    assert columnNumber("AA") == 27


@pytest.mark.parametrize("path", allFixtures, ids=lambda path: path.stem)
def test_everyReferenceInTheCorpusSurvivesTheRoundTrip(path: Path) -> None:
    """Every cell in every fixture re-parses to the reference it came from."""
    document = pybers.open(path)
    for sheet in document.sheets:
        for table in sheet.tables:
            for cell in table.cells.values():
                assert (
                    CellReference.parse(cell.reference.asReference())
                    == cell.reference
                )


# AC 1.b
@pytest.mark.parametrize("row,col", [(0, 1), (1, 0), (0, 0), (-1, 5)])
def test_aCoordinateBelowOneIsRejectedAtConstruction(row: int, col: int) -> None:
    """The zero-based instinct fails here rather than in every method downstream."""
    with pytest.raises(ReferenceError):
        CellReference(row, col)


# ── AC 2: locking is two independent facts, and it survives ──────────────────

@pytest.mark.parametrize(
    "written,colAbsolute,rowAbsolute",
    [("A1", False, False), ("$A1", True, False), ("A$1", False, True),
     ("$A$1", True, True)],
)
def test_eachLockingMarkerParsesToItsOwnAxis(
    written: str, colAbsolute: bool, rowAbsolute: bool
) -> None:
    parsed = CellReference.parse(written)
    assert parsed.colAbsolute is colAbsolute
    assert parsed.rowAbsolute is rowAbsolute
    assert parsed.asReference() == written


def test_theFourLockingsOfOneCellAreFourDifferentReferences() -> None:
    """One flag per reference cannot represent `$A1`, and a formula holds an
    absolute column beside a relative row, so the four are genuinely distinct."""
    written = ["A1", "$A1", "A$1", "$A$1"]
    assert len({CellReference.parse(text) for text in written}) == len(written)
    assert all(
        CellReference.parse(text).asRowColumn() == (1, 1) for text in written
    )


# ── AC 3: a rectangle ────────────────────────────────────────────────────────

def test_aRangeIsBuiltFromAStringOrFromTwoReferences() -> None:
    assert CellRange.parse("A1:C3") == CellRange(1, 1, 3, 3)
    assert CellRange.fromReferences(
        CellReference(1, 1), CellReference(3, 3)
    ) == CellRange(1, 1, 3, 3)


def test_twoOppositeCornersBoundTheSameRectangleEitherWayRound() -> None:
    """The corners a caller holds are as often bottom-left and top-right."""
    assert CellRange.fromReferences(
        CellReference(3, 1), CellReference(1, 3)
    ) == CellRange(1, 1, 3, 3)


# AC 3.a
def test_aRangeReportsItsSpansAndWhatItCovers() -> None:
    block = CellRange.parse("B2:D5")
    assert block.rowSpan == 4
    assert block.colSpan == 3
    assert block.covers("B2") is True
    assert block.covers("D5") is True
    assert block.covers("A2") is False
    assert block.covers("B6") is False


# AC 3.b
def test_arangeYieldsEveryCellItCoversInRowMajorOrder() -> None:
    walked = [reference.asReference() for reference in CellRange.parse("A1:B2")]
    assert walked == ["A1", "B1", "A2", "B2"]


def test_aRangeRoundTripsThroughItsWrittenForm() -> None:
    for written in ("A1", "A1:C3", "$A$1:$C$3", "B2:D5"):
        assert CellRange.parse(written).asReference() == written


# ── AC 4: unbounded on one axis, and distinguishable ─────────────────────────

def test_aWholeColumnAndAWholeRowAreUnboundedOnTheOtherAxis() -> None:
    column = CellRange.parse("A")
    assert column.rowsUnbounded is True
    assert column.colsUnbounded is False
    assert column.rowSpan is None
    assert column.colSpan == 1

    row = CellRange.parse("1")
    assert row.colsUnbounded is True
    assert row.rowsUnbounded is False
    assert row.colSpan is None
    assert row.rowSpan == 1


def test_anUnboundedRangeIsNotABoundedOneOverTheSameCells() -> None:
    """`A` follows the table as it grows and `A1:A3` does not, so a sentinel
    standing in for the missing bound would make two different things compare
    equal."""
    assert CellRange.parse("A") != CellRange.parse("A1:A3")
    assert CellRange.parse("A").start is None


def test_anUnboundedRangeCannotBeWalkedUntilItIsBounded() -> None:
    with pytest.raises(ReferenceError):
        list(CellRange.parse("A"))
    bounded = CellRange.parse("A").boundedBy(CellRange(1, 1, 3, 3))
    assert [reference.asReference() for reference in bounded] == ["A1", "A2", "A3"]


def test_aSpanOfWholeColumnsOrWholeRowsParsesAndReEmits() -> None:
    for written in ("A", "1", "A:C", "1:3", "$A:$C"):
        assert CellRange.parse(written).asReference() == written


def test_aRangeUnboundedOnBothAxesIsRefused() -> None:
    with pytest.raises(ReferenceError):
        CellRange(None, None, None, None)


# ── AC 5: several rectangles at once ─────────────────────────────────────────

def test_aCommaSeparatedListParsesInTheOrderWritten() -> None:
    written = "A1:B2,D4:E5"
    parsed = CellRangeList.parse(written)
    assert len(parsed) == 2
    assert [item.asReference() for item in parsed] == ["A1:B2", "D4:E5"]
    assert parsed.asReference() == written


def test_aListKeepsAnOrderThatIsNotSorted() -> None:
    """A multi-range function argument is positional, so re-emitting it sorted
    would change what it says."""
    written = "D4:E5,A1:B2"
    assert CellRangeList.parse(written).asReference() == written


# ── AC 6: a table addresses cells through these types and nothing else ───────

def test_aTableTakesAnAddressAndNotARowAndColumnPair() -> None:
    """The retired path is gone rather than deprecated: `cellAt` does not exist,
    and `cell` takes one address, so a bare pair is a type error at the call site
    before it is anything at runtime."""
    assert not hasattr(Table, "cellAt")
    parameters = list(inspect.signature(Table.cell).parameters)
    assert parameters == ["self", "address"]


def test_aTableAcceptsBothFormsOfAnAddress() -> None:
    table = sampleTable()
    assert table.cell("B2") is table.cell(CellReference(2, 2))


# AC 6.a
def test_aTableReturnsTheCellsARangeCovers() -> None:
    table = sampleTable()
    covered = [cell.reference.asReference() for cell in table.range("A1:B2")]
    assert covered == ["A1", "B1", "A2", "B2"]


def test_aTableReturnsTheCellsEveryRangeInAListCovers() -> None:
    table = sampleTable()
    covered = [cell.reference.asReference() for cell in table.range("A1,C3")]
    assert covered == ["A1", "C3"]


def test_anUnboundedRangeIsBoundedByTheTablesOwnExtent() -> None:
    """A range knows nothing about the table it is used against, so the extent is
    the only thing that can answer what `A` covers."""
    table = sampleTable()
    covered = [cell.reference.asReference() for cell in table.range("A")]
    assert covered == ["A1", "A2", "A3"]
    assert [cell.reference.asReference() for cell in table.range("1")] == [
        "A1", "B1", "C1"
    ]


def test_aRangeReachingPastTheGridIsRefusedByItsOwnName() -> None:
    """The refusal names the range the caller wrote. Letting the first cell past
    the edge raise instead reports an interior address nobody asked for, which is
    a worse answer to the same question."""
    table = sampleTable()
    with pytest.raises(ReferenceError) as raised:
        table.range("A1:Z99")
    assert "A1:Z99" in str(raised.value)
    with pytest.raises(ReferenceError) as listed:
        table.range("A1:B2,Z99")
    assert "Z99" in str(listed.value)


def test_aTableWithNoDeclaredGridHasNoExtentAndHoldsNoCells() -> None:
    empty = Table(name="Table 1")
    assert empty.extent is None
    assert empty.range("A") == []
    with pytest.raises(ReferenceError):
        empty.cell("A1")


def test_anExtentIsTheDeclaredGridAndNotWhatTheCellsReach() -> None:
    """Seven of the corpus's 74 tables declare more rows or columns than their
    populated cells reach, so a derived extent is a real rectangle that is too
    small and nothing about it looks wrong."""
    table = Table(name="Table 1", rowCount=10, colCount=5)
    table.cell("A1").value = "only this one"
    assert table.extent == CellRange(1, 1, 10, 5)
    assert len(table.range("A")) == 10


# ── AC 7: a merge carries a range, and covering is unchanged ─────────────────

def test_aMergeExpressesItsExtentAsARange() -> None:
    merge = MergeRange(CellRange.parse("A1:B1"))
    assert merge.extent == CellRange(1, 1, 1, 2)
    assert merge.anchor == CellReference(1, 1)
    assert merge.covers("B1") is True
    assert merge.covers("C1") is False


def test_aMergeCannotBeUnbounded() -> None:
    """A merged region covers a fixed block, which a whole-column range does not."""
    with pytest.raises(ReferenceError):
        MergeRange(CellRange.parse("A"))


def mergedTable() -> Table:
    """Return a one-by-three table whose first two cells are merged."""
    table = Table(name="Table 1", rowCount=1, colCount=3)
    table.mergeRanges.append(MergeRange(CellRange.parse("A1:B1")))
    table.cell("A1").value = "Hello"
    return table


def test_aCellSwallowedByAMergeIsNotAddressable() -> None:
    """A covered cell has NO record in the tile, so handing back an empty one on
    access files a record the archive never had, and a save would then emit it.
    That is the phantom merge anchor CLAUDE.md lists among the defects this
    project exists to avoid."""
    table = mergedTable()
    stored = len(table.cells)
    with pytest.raises(ReferenceError):
        table.cell("B1")
    assert len(table.cells) == stored
    assert table.cell("A1").value == "Hello"


def test_aRangeAcrossAMergeYieldsItsAnchorOnce() -> None:
    """A merged region is one cell, so a range over it returns one cell."""
    table = mergedTable()
    assert [cell.reference.asReference() for cell in table.range("A1:C1")] == [
        "A1", "C1"
    ]
    assert table.range("B1") == []
    assert table.addressable("A1") is True
    assert table.addressable("B1") is False


def test_mergeCoveringStillTellsACoveredCellFromAnEmptyOne() -> None:
    table = sampleTable()
    table.mergeRanges.append(MergeRange(CellRange.parse("A1:B1")))
    assert table.mergeCovering("B1") is not None
    assert table.mergeCovering("C2") is None


# ── AC 8: refusals name what was rejected, and one conversion exists ─────────

@pytest.mark.parametrize(
    "written", ["", "1A", "A1:C", "A:1", "$", "A1:B2:C3", "AB!", "A0"]
)
def test_anInvalidAddressIsRefusedByName(written: str) -> None:
    with pytest.raises(ReferenceError) as raised:
        CellRange.parse(written)
    assert written in str(raised.value) or repr(written) in str(raised.value)


def test_anEmptyRangeInAListIsRefused() -> None:
    with pytest.raises(ReferenceError):
        CellRangeList.parse("A1:B2,,D4")


def test_thereIsOneConversionBetweenAColumnLetterAndAColumnNumber() -> None:
    """The loose helpers `table.py` carried are retired, so the conversion has one
    home and a base-26 correction lands once."""
    assert pybers.columnLetter is referenceModule.columnLetter
    assert pybers.columnNumber is referenceModule.columnNumber
    for name in ("columnLetter", "columnNumber", "parseReference"):
        assert name not in vars(tableModule)
