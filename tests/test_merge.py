#!/usr/bin/env python3
"""\
Merging and unmerging a block of cells, at the model level.

The destructive half is the part worth stating: a merge discards the cells it
covers and unmerging does not bring them back. That is not a design choice made
here. `22-merge-2x2` and its unmerged twin `22b` hold the same 18 cells, so
Numbers itself discarded them, and a library that preserved them would be
inventing behavior the format does not have.

The write half, putting a merge back into the file so Numbers opens it, lives
in `test_writer.py` beside the rest of the write path.

UPDATES
2026-09-02  Written for #16.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/02"

from decimal import Decimal

import pytest

import pybers
from conftest import documentPath
from pybers.addressing import ReferenceError
from pybers.table import MergeRange, Table


def unmergedTable() -> Table:
    """Return `22b`'s table, the unmerged twin, as a starting point."""
    return pybers.open(
        documentPath("22b-merge-2x2-unmerged")
    ).sheet(1).table(1)


# ── AC 1: a merge makes one cell, anchored top-left ──────────────────────────

def test_aMergeIsReportedForEveryPositionItCovers() -> None:
    table = unmergedTable()
    merge = table.mergeAdd("A1:B1")

    assert isinstance(merge, MergeRange)
    assert merge.anchor == pybers.toCellReference("A1")
    assert table.mergeCovering("A1") is merge
    assert table.mergeCovering("B1") is merge
    assert table.mergeCovering("C1") is None


def test_aMergeAcrossRowsAndColumnsCoversTheWholeBlock() -> None:
    """A merge is a rectangle, not a run, so both axes have to be walked."""
    table = unmergedTable()
    table.mergeAdd("A1:B2")
    covered = [
        reference
        for reference in ("A1", "B1", "A2", "B2")
        if table.mergeCovering(reference) is not None
    ]
    assert covered == ["A1", "B1", "A2", "B2"]


def test_theCoveredCellsAreRemovedFromTheTable() -> None:
    """AC 1.i. A covered cell has no record in the file, so one left behind would
    be written out as a cell Numbers never had."""
    table = unmergedTable()
    table.cell("A1").value = "anchor"
    table.cell("B1").value = "covered"
    stored = len(table.cells)

    table.mergeAdd("A1:B1")

    assert len(table.cells) == stored - 1
    assert pybers.toCellReference("B1") not in table.cells


def test_theAnchorKeepsItsValueAndTheCoveredCellsLoseTheirs() -> None:
    """AC 1.ii, and it is permanent: see the twin fixtures."""
    table = unmergedTable()
    table.cell("A1").value = Decimal(42)
    table.cell("B1").value = Decimal(99)

    table.mergeAdd("A1:B1")

    assert table.cell("A1").value == Decimal(42)
    with pytest.raises(ReferenceError):
        table.cell("B1")


def test_aCoveredCellCannotBeReachedThroughTheTable() -> None:
    """The anchor is the only way in, which is what makes a merge one cell."""
    table = unmergedTable()
    table.mergeAdd("A1:B1")

    assert table.addressable("A1") is True
    assert table.addressable("B1") is False


# ── AC 2: unmerging returns ordinary, empty cells ────────────────────────────

def test_unmergingReturnsTheBlockToOrdinaryCells() -> None:
    table = unmergedTable()
    table.mergeAdd("A1:B1")

    removed = table.mergeRemove("B1")

    assert removed.extent == pybers.CellRange(1, 1, 1, 2)
    assert table.mergeRanges == []
    assert table.addressable("B1") is True


def test_aCoveredValueDoesNotComeBack() -> None:
    """AC 2. The value went when the merge was made, and nothing restores it.

    Measured, not chosen: `22-merge-2x2` and `22b` hold the same 18 cells, and `B1`
    is absent from the unmerged file as well as the merged one.
    """
    table = unmergedTable()
    table.cell("B1").value = "gone"
    table.mergeAdd("A1:B1")
    table.mergeRemove("A1")

    assert table.cell("B1").value is None


def test_unmergingTakesAnyCellOfTheBlock() -> None:
    """Two merges can never claim one cell, so any of them names the merge."""
    for reference in ("A1", "B1"):
        table = unmergedTable()
        table.mergeAdd("A1:B1")
        assert table.mergeRemove(reference).extent == pybers.CellRange(1, 1, 1, 2)


def test_unmergingWhereThereIsNoMergeIsRefused() -> None:
    table = unmergedTable()
    with pytest.raises(ReferenceError, match="No merge"):
        table.mergeRemove("A1")


# ── AC 3: an overlapping merge raises ────────────────────────────────────────

def test_aMergeOverlappingAnotherIsRefused() -> None:
    table = unmergedTable()
    table.mergeAdd("A1:B1")

    with pytest.raises(ReferenceError, match="overlaps"):
        table.mergeAdd("B1:C1")


def test_aRefusedMergeLeavesTheTableExactlyAsItWas() -> None:
    """Checked before anything is discarded, so a refusal cannot half-apply."""
    table = unmergedTable()
    table.mergeAdd("A1:B1")
    table.cell("C1").value = "kept"
    stored = len(table.cells)

    with pytest.raises(ReferenceError):
        table.mergeAdd("B1:C1")

    assert len(table.mergeRanges) == 1
    assert len(table.cells) == stored
    assert table.cell("C1").value == "kept"


def test_twoMergesThatDoNotTouchAreBothKept() -> None:
    table = unmergedTable()
    table.mergeAdd("A1:B1")
    table.mergeAdd("C1:D1")

    assert [str(merge.extent) for merge in table.mergeRanges] == ["A1:B1", "C1:D1"]


# ── AC 4: unbounded or out of range is refused ───────────────────────────────

@pytest.mark.parametrize(
    "address, reason",
    [
        ("A:B", "unbounded"),
        ("1:2", "unbounded"),
        ("A1:Z1", "reaches outside"),
        ("A1:A9", "reaches outside"),
        ("A1:B1,C1:D1", "names 2"),
        ("A1:A1", "one cell"),
        ("A1", "one cell"),
    ],
)
def test_aMergeThatCannotBeABlockIsRefused(address: str, reason: str) -> None:
    """`22b` is 2 rows by 13 columns, so `Z1` and `A9` are both off the grid.

    A single cell is refused for a different reason: Numbers offers no way to make a
    one-cell merge, so writing the formula for one would put an unconfirmed construct
    into the file.
    """
    table = unmergedTable()
    with pytest.raises(ReferenceError, match=reason):
        table.mergeAdd(address)


def test_aRefusedMergeAddsNothing() -> None:
    table = unmergedTable()
    with pytest.raises(ReferenceError):
        table.mergeAdd("A:B")
    assert table.mergeRanges == []


# ── the fixture pair the destructive rule was measured from ──────────────────

def test_theTwinFixturesAgreeOnWhatAMergeDiscarded() -> None:
    """The evidence behind AC 1.ii and AC 2, asserted rather than cited.

    If this ever fails, the rule those criteria encode was wrong and both need
    revisiting before the code does.
    """
    merged = pybers.open(
        documentPath("22-merge-2x2")
    ).sheet(1).table(1)
    unmerged = unmergedTable()

    assert len(merged.mergeRanges) == 5
    assert unmerged.mergeRanges == []
    assert len(merged.cells) == len(unmerged.cells) == 18
    assert sorted(str(r) for r in merged.cells) == sorted(
        str(r) for r in unmerged.cells
    )
