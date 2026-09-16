#!/usr/bin/env python3
"""\
A merge that spans more than one row, which no document held until now.

All 35 merges measured on 2026-09-06 were one row tall, so the
vertical axis of an extent had never been read, while the example documents hold
twenty-seven vertical merges in a single table.

`22d-merge-multi-row` is seven columns by five rows, every cell naming its own
address, carrying a two-row merge at `A2:A3`, a two-by-two at `C2:D3` and a
three-row at `F2:F4`. Each was made over cells that already held their labels,
so the fixture also records what Numbers does with the content it swallows.

UPDATES
2026-09-07  Written for #54.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/07"

from pathlib import Path

import pytest

import pybers
from conftest import findDocumentPath, readArchiveBodies, readRecordedRows
from pybers._persistence import readPackage
from pybers.addressing.reference import ReferenceError as CellReferenceError
from pybers.table import Table

multiRowFixture: Path = findDocumentPath("22d-merge-multi-row")

# The extent of each merge, against the anchor that carries it.
extents: tuple[tuple[str, str], ...] = (
    ("A2", "A2:A3"),
    ("C2", "C2:D3"),
    ("F2", "F2:F4"),
)

coveredPositions: tuple[str, ...] = ("A3", "D2", "C3", "D3", "F3", "F4")

# Every cell sharing an edge with a merge. An extent read one row too tall or one
# column too wide lands on one of these, and each names the address it truly is.
neighbors: tuple[str, ...] = (
    "A1", "A4", "B2", "B3",
    "C1", "D1", "C4", "D4", "E2", "E3",
    "E4", "F1", "F5", "G2", "G3", "G4",
)

# Zero-based, and exact rather than a subset: the six covered positions hold no
# record and all twenty-nine other cells do.
recordLayout: dict[int, set[int]] = {
    0: {0, 1, 2, 3, 4, 5, 6},
    1: {0, 1, 2, 4, 5, 6},
    2: {1, 4, 6},
    3: {0, 1, 2, 3, 4, 6},
    4: {0, 1, 2, 3, 4, 5, 6},
}


def findFirstTable(document: pybers.Document) -> Table:
    """Return the document's first table."""
    return document.sheets[0].tables[0]


def testTheFixtureHoldsExactlyTheThreeMergesItWasMadeWith() -> None:
    """Every other check here looks a merge up, so none of them would see a fourth."""
    table = findFirstTable(pybers.open(multiRowFixture))
    assert len(table.mergeRanges) == len(extents)


@pytest.mark.parametrize(("anchor", "extent"), extents)
def testEachMergeReportsTheExtentNumbersDisplays(anchor: str, extent: str) -> None:
    table = findFirstTable(pybers.open(multiRowFixture))
    merge = table.mergeCovering(anchor)
    assert merge is not None
    assert str(merge.extent) == extent
    assert str(merge.anchor) == anchor


@pytest.mark.parametrize("reference", coveredPositions)
def testACoveredPositionIsRefused(reference: str) -> None:
    table = findFirstTable(pybers.open(multiRowFixture))
    with pytest.raises(CellReferenceError, match="covered by the merge"):
        table.cell(reference)


@pytest.mark.parametrize("reference", coveredPositions)
def testACoveredPositionResolvesToTheMergeThatCoversIt(reference: str) -> None:
    """`mergeCovering` answers on the vertical axis, which nothing had exercised."""
    table = findFirstTable(pybers.open(multiRowFixture))
    merge = table.mergeCovering(reference)
    assert merge is not None
    assert merge.covers(reference)


@pytest.mark.parametrize("reference", neighbors)
def testEveryCellBesideAMergeStillNamesItself(reference: str) -> None:
    table = findFirstTable(pybers.open(multiRowFixture))
    assert table.cell(reference).value == reference.lower()


def testNoCoveredPositionHoldsARecord() -> None:
    """The 22c result holds on the vertical axis: a covered cell has no record."""
    assert readRecordedRows(multiRowFixture) == recordLayout


def testMergingJoinsColumnsWithTabsAndRowsWithNewlines() -> None:
    """Extends the tab-joining finding, which only one row could establish.

    Numbers coerces the swallowed cells into one text value in row-major order,
    a tab between columns and a newline between rows. Measured 2026-09-07.
    """
    table = findFirstTable(pybers.open(multiRowFixture))
    assert table.cell("A2").value == "two rows tall, anchor\na3"
    assert table.cell("C2").value == "two by two, anchor\td2\nc3\td3"
    assert table.cell("F2").value == "three rows tall, anchor\nf3\nf4"


def testTheFixtureWritesBackUnchanged(tmp_path: Path) -> None:
    """The base contract, on the one fixture holding a merge taller than a row."""
    target = tmp_path / "written.numbers"
    pybers.open(multiRowFixture).save(target)
    assert readArchiveBodies(readPackage(target)) == readArchiveBodies(
        readPackage(multiRowFixture)
    )
