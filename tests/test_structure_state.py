#!/usr/bin/env python3
"""\
Borders, bands, spills and merges carried through a structural edit.

Each against one edit Numbers made to `57-structure-refusals-base`.

UPDATES
2026-09-29  A line added beside one with no border, for PYB-118.
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
    readTableFacts,
)

import pybers
from conftest import findDocumentPath
from pybers._persistence import readPackage
from pybers._persistence.difference import listPackageDifferences
from pybers.errors import WriteError

# One edit each against the table of `57-structure-refusals-base` it belongs to,
# with the measurement Numbers made of the same edit.
refusalMeasurements: dict[str, tuple[str, Callable[[pybers.Table], object]]] = {
    "57-borders-row-inserted": ("Borders", lambda table: table.rowAdd(3)),
    "57-borders-row-deleted": ("Borders", lambda table: table.rowRemove(3)),
    "57-borders-column-inserted": ("Borders", lambda table: table.columnAdd(3)),
    "57-borders-column-deleted": ("Borders", lambda table: table.columnRemove(3)),
    "57-bands-header-row-inserted": ("Bands", lambda table: table.rowAdd(2)),
    "57-bands-header-row-deleted": ("Bands", lambda table: table.rowRemove(1)),
    "57-bands-row-inserted-before-footer": ("Bands", lambda table: table.rowAdd(8)),
    "57-bands-footer-row-deleted": ("Bands", lambda table: table.rowRemove(8)),
    "57-bands-column-inserted-before-header": (
        "Bands", lambda table: table.columnAdd(1)
    ),
    "57-bands-header-column-deleted": ("Bands", lambda table: table.columnRemove(1)),
    "57-engine-column-inserted": ("Engine", lambda table: table.columnAdd(3)),
}


@pytest.mark.parametrize("name", sorted(refusalMeasurements))
def testBordersBandsAndSpillsFollowTheEdit(name: str, tmp_path: Path) -> None:
    """PYB-17: the state that has no cells of its own, against Numbers' own edit."""
    table, edit = refusalMeasurements[name]
    document = pybers.open(findDocumentPath("57-structure-refusals-base"))
    edit(document.sheet(1).table(table))
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    ours = readTableFacts(target)[table]
    theirs = readTableFacts(findDocumentPath(name))[table]
    for key in ("size", "sidecar", "bands", "strokes", "records", "spills", "volatile"):
        assert ours[key] == theirs[key], key


@pytest.mark.parametrize(
    "edit",
    [
        lambda table: table.rowAdd(2),
        lambda table: table.rowRemove(2),
        lambda table: table.columnRemove(4),
    ],
)
def testAnEditInsideASpillIsRefused(
    edit: Callable[[pybers.Table], object], tmp_path: Path
) -> None:
    """Numbers re-flows a spill an edit cuts, which means evaluating the formula."""
    document = pybers.open(findDocumentPath("57-structure-refusals-base"))
    edit(document.sheet(1).table("Engine"))
    with pytest.raises(WriteError, match="inside a formula's spill"):
        document.save(tmp_path / "refused.numbers")


mergeMeasurements: dict[str, tuple[str, Callable[[pybers.Table], object]]] = {
    "57-anchors-anchor-row-deleted": ("Anchors", lambda table: table.rowRemove(2)),
    "57-anchors-anchor-column-deleted": (
        "Anchors", lambda table: table.columnRemove(2)
    ),
    "57-collapse-row-deleted": ("Collapse", lambda table: table.rowRemove(3)),
    "57-collapse-column-deleted": ("Collapse", lambda table: table.columnRemove(3)),
}


@pytest.mark.parametrize("name", sorted(mergeMeasurements))
def testAMergeLosingItsAnchorOrItsSecondCell(name: str, tmp_path: Path) -> None:
    """PYB-17 AC 3: the merged value outlives its anchor, and one cell unmerges."""
    tableName, edit = mergeMeasurements[name]
    document = pybers.open(findDocumentPath("57-structure-refusals-base"))
    edit(document.sheet(1).table(tableName))
    ours = document.sheet(1).table(tableName)
    theirs = pybers.open(findDocumentPath(name)).sheet(1).table(tableName)
    assert [str(merge.extent) for merge in ours.mergeRanges] == [
        str(merge.extent) for merge in theirs.mergeRanges
    ]
    assert {str(reference): cell.value for reference, cell in ours.cells.items()} == {
        str(reference): cell.value for reference, cell in theirs.cells.items()
    }
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    for key in ("size", "records", "merges"):
        assert readTableFacts(target)[tableName][key] == readTableFacts(
            findDocumentPath(name)
        )[tableName][key], key


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        (lambda table: table.rowAdd(2), {
            "left": [(2, [(3, 1, 3.0)])], "right": [(2, [(3, 1, 3.0)])],
            "top": [(3, [(2, 1, 3.0)])], "bottom": [(3, [(2, 1, 3.0)])],
        }),
        (lambda table: table.columnAdd(2), {
            "left": [(3, [(2, 1, 3.0)])], "right": [(3, [(2, 1, 3.0)])],
            "top": [(2, [(3, 1, 3.0)])], "bottom": [(2, [(3, 1, 3.0)])],
        }),
    ],
)
def testALineAddedBesideOneWithNoBorderGainsNone(
    edit: Callable[[pybers.Table], object], expected: dict[str, object],
    tmp_path: Path,
) -> None:
    """Only `C3` has a border, so the line displaced by the insertion stores none."""
    document = pybers.open(findDocumentPath("61-move-styles-base"))
    edit(document.sheet(1).table("Table 1"))
    target = tmp_path / "inserted.numbers"
    document.save(target)
    assert readTableFacts(target)["Table 1"]["strokes"] == expected


def testTheBorderGoldenMatchesWhatThisLibraryProduces(tmp_path: Path) -> None:
    """A row and a column added beside lines with no border, as Numbers confirmed."""
    name = "61-lines-added-beside-no-border-by-pybers"
    document = pybers.open(findDocumentPath("61-move-styles-base"))
    table = document.sheet(1).table("Table 1")
    table.rowAdd(2)
    table.columnAdd(2)
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    golden = Path(__file__).resolve().parent / "golden" / f"{name}.numbers"
    differences = listPackageDifferences(readPackage(golden), readPackage(target))
    # An added line takes a random identity, so only the UID map may differ.
    assert {
        difference.typeName for difference in differences
        if difference.identifier is not None
    } <= {"TST.ColumnRowUIDMapArchive"}
    assert readTableFacts(golden)["Table 1"]["strokes"] == {
        "left": [(3, [(3, 1, 3.0)])], "right": [(3, [(3, 1, 3.0)])],
        "top": [(3, [(3, 1, 3.0)])], "bottom": [(3, [(3, 1, 3.0)])],
    }
