#!/usr/bin/env python3
"""\
A structural edit saved, against the archives Numbers wrote for the same edit.

Records by position, header buckets, hidden lines, tiles, declared references,
the engine's registers, and the goldens confirmed in Numbers.

UPDATES
2026-09-21  Split out of `test_structure` for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/21"

from collections.abc import Callable
from pathlib import Path

import pytest
from structurefacts import (
    baseFixture,
    measuredEdits,
    openBase,
    readTableFacts,
    recomputedOnOpen,
)

import pybers
from conftest import findDocumentPath
from pybers._persistence import readPackage
from pybers._persistence.difference import listPackageDifferences


@pytest.mark.parametrize("name", sorted(measuredEdits))
def testASavedEditWritesTheArchivesNumbersWrote(name: str, tmp_path: Path) -> None:
    """PYB-17 AC 1, 2 and 5, down to what the engine says each formula reads."""
    document = openBase()
    measuredEdits[name](document.sheets[0].table("Table 1"))
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    ours = readTableFacts(target)
    theirs = readTableFacts(findDocumentPath(name))
    expected = recomputedOnOpen.get(name, set())
    for tableName, facts in theirs.items():
        for key, value in facts.items():
            if key == "records":
                assert isinstance(value, dict)
                cached = {
                    (row, column) for table, row, column in expected
                    if table == tableName
                }
                assert {
                    position: kind for position, kind in value.items()
                    if position not in cached
                } == {
                    position: kind for position, kind in ours[tableName][key].items()
                    if position not in cached
                }, tableName
                continue
            assert ours[tableName][key] == value, (tableName, key)


def testABrokenReferenceIsWrittenAsNumbersWritesIt(tmp_path: Path) -> None:
    """`B5` reads `$A$8` and `B6` reads `A8`, and deleting row 8 breaks both.

    A locked axis marks its sentinel absolute and sets its begin bit only, which
    an unmeasured rule had written as both ends and no sentinel lock.
    """
    document = openBase()
    document.sheet(1).table("Table 1").rowRemove(8)
    target = tmp_path / "row-8.numbers"
    document.save(target)
    ours = pybers.open(target).sheet(1).table("Table 1")
    theirs = pybers.open(findDocumentPath("56h-row-8-deleted")).sheet(1).table(
        "Table 1"
    )
    for address in ("B5", "B6"):
        ourFormula = ours.cell(address).formula
        theirFormula = theirs.cell(address).formula
        assert ourFormula is not None and theirFormula is not None
        assert [node.raw for node in ourFormula] == [node.raw for node in theirFormula]


def testHiddenLinesStayHiddenAcrossASave(tmp_path: Path) -> None:
    """PYB-17 AC 5: row 9 and column H, wherever the edit moved them."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    table.rowAdd(1)
    table.columnAdd("A")
    target = tmp_path / "hidden.numbers"
    document.save(target)
    assert readTableFacts(target)["Table 1"]["hidden"] == [(0, 8), (1, 9)]


def testAddingThenRemovingTheSameRowSavesTheDocumentUnchanged(tmp_path: Path) -> None:
    """The identity a row gains goes with it, so nothing reads as changed."""
    document = openBase()
    table = document.sheets[0].table("Table 1")
    table.rowAdd(4)
    table.rowRemove(4)
    target = tmp_path / "unchanged.numbers"
    document.save(target)
    differences = listPackageDifferences(readPackage(baseFixture), readPackage(target))
    assert [
        difference for difference in differences if difference.identifier is not None
    ] == []


def testRowsCrossTileBoundariesInALargeTable(tmp_path: Path) -> None:
    """`27-big-table` spans eight tiles, so every row past the edit changes tile."""
    document = pybers.open(findDocumentPath("27-big-table"))
    table = document.sheets[0].tables[0]
    before = [table.cell(row=row, col=1).value for row in (1, 256, 257, 2001)]
    table.rowAdd(1)
    target = tmp_path / "big.numbers"
    document.save(target)
    reopened = pybers.open(target).sheets[0].tables[0]
    assert reopened.rowCount == 2002
    after = [reopened.cell(row=row, col=1).value for row in (2, 257, 258, 2002)]
    assert after == before
    assert reopened.cell(row=1, col=1).value is None


@pytest.mark.parametrize(
    ("name", "source", "edit"),
    [
        ("58-buckets-row-inserted", "58-buckets-base",
         lambda table: table.rowAdd(1)),
        ("58-buckets-row-deleted", "58-buckets-base",
         lambda table: table.rowRemove(1)),
        ("58-buckets-created", "58-buckets-at-limit",
         lambda table: table.rowAdd(1)),
    ],
)
def testRowHeadersSpreadOverTheirBucketsAsNumbersSpreadsThem(
    name: str, source: str, edit: Callable[[pybers.Table], object], tmp_path: Path
) -> None:
    """A sparse table keeps its sixteen buckets, and tiles only where rows are."""
    document = pybers.open(findDocumentPath(source))
    edit(document.sheets[0].tables[0])
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    ours = readTableFacts(target)["Table 1"]
    theirs = readTableFacts(findDocumentPath(name))["Table 1"]
    for key in (
        "size", "records", "rowHeaders", "tiles", "rowTileTree", "nextRowStripID",
        "declared",
    ):
        assert ours[key] == theirs[key], key


@pytest.mark.parametrize(
    ("name", "edit"),
    [
        ("27b-rows-inserted-into-a-new-tile",
         lambda table: table.rowAdd(100, 60)),
        ("27c-rows-deleted-emptying-a-tile",
         lambda table: table.rowRemove(1, 300)),
    ],
)
def testTilesAreCreatedAndDroppedAsNumbersDoes(
    name: str, edit: Callable[[pybers.Table], object], tmp_path: Path
) -> None:
    """`27-big-table` spans eight tiles, and an edit crossing them moves every row."""
    document = pybers.open(findDocumentPath("27-big-table"))
    edit(document.sheets[0].tables[0])
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    ours = readTableFacts(target)["Table 1"]
    theirs = readTableFacts(findDocumentPath(name))["Table 1"]
    for key in (
        "size", "sidecar", "records", "rowHeaders", "columnHeaders",
        "tiles", "rowTileTree", "nextRowStripID", "declared",
    ):
        assert ours[key] == theirs[key], key


goldenDirectory: Path = Path(__file__).resolve().parent / "golden"

# Each golden and the edit that made it. An added line takes a random identity, as
# Numbers gives one, so the UID map is the one archive allowed to differ.
goldenEdits: dict[str, tuple[Callable[[pybers.Table], object], set[str]]] = {
    "56-row-added-by-pybers": (
        lambda table: table.rowAdd(3), {"TST.ColumnRowUIDMapArchive"}
    ),
    "56-row-removed-by-pybers": (lambda table: table.rowRemove(8), set()),
    "56-column-added-by-pybers": (
        lambda table: table.columnAdd("E"), {"TST.ColumnRowUIDMapArchive"}
    ),
    "56-column-removed-by-pybers": (lambda table: table.columnRemove("E"), set()),
}


@pytest.mark.parametrize("name", sorted(goldenEdits))
def testTheStructureGoldensMatchWhatThisLibraryProduces(
    name: str, tmp_path: Path
) -> None:
    """PYB-17 AC 6: each edit again, against the file Numbers confirmed."""
    edit, allowed = goldenEdits[name]
    expected = goldenDirectory / f"{name}.numbers"
    document = openBase()
    table = document.sheet(1).table("Table 1")
    stored = set(table._rowIdentities) | set(table._columnIdentities)
    edit(table)
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    differences = listPackageDifferences(readPackage(expected), readPackage(target))
    assert {
        difference.typeName for difference in differences
        if difference.identifier is not None
    } <= allowed
    golden = pybers.open(expected).sheet(1).table("Table 1")
    for ours, theirs in (
        (table._rowIdentities, golden._rowIdentities),
        (table._columnIdentities, golden._columnIdentities),
    ):
        assert [line for line in ours if line in stored] == [
            line for line in theirs if line in stored
        ]
