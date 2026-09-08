#!/usr/bin/env python3
"""\
A merge whose covered positions carry records, which only an import produces.

Numbers writes no record at a position its own merge covers. Excel writes a
`<c>` element for every cell of a merged range, a covered one carrying a style
and no value, and Numbers keeps each of them on import and across every later
edit. So a document that began life as a spreadsheet holds records the reader
had no cell to put them in, and refused to open at all.

`22e-merge-imported` is that document, converted from a generated workbook.
`22c-merge-overpaints` is the control: four gestures in Numbers itself, none of
which produces a covered record. Both measured 2026-09-07; see
tests/fixtures/README.md.

UPDATES
2026-09-07  Written for #49.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/07"

import shutil
from pathlib import Path

import pytest

import pybers
from conftest import archiveBodies, recordedColumns, tableModelType
from pybers._generated import TSTArchives_pb2 as tst
from pybers.archives import ArchiveIndex
from pybers.model import MergeRange, Table
from pybers.model.reference import ReferenceError as CellReferenceError
from pybers.numbersfile import readPackage
from pybers.numbersfile.types import archiveTypeId

fixtures: Path = Path(__file__).parent / "fixtures"
importedFixture: Path = fixtures / "22e-merge-imported.numbers"
overpaintFixture: Path = fixtures / "22c-merge-overpaints.numbers"
goldenDirectory: Path = Path(__file__).resolve().parent / "golden"

# The covered positions of the imported fixture's three merges, A1:B1, C1:E1
# and F1:G1. G1 is absent: Excel gave it a style AND a value, and Numbers
# discarded it, which is why a covered record never carries one.
coveredPositions: tuple[str, ...] = ("B1", "D1", "E1")


def firstTable(document: pybers.Document) -> Table:
    """Return the document's first table."""
    return document.sheets[0].tables[0]


def testAnImportedMergeOpensAtAll() -> None:
    """The defect: the reader raised on the first covered record it decoded."""
    table = firstTable(pybers.open(importedFixture))
    assert table.cell("A1").value == "two wide, anchor"


def testEveryAnchorReportsTheValueNumbersShows() -> None:
    """Three merges, two and three and two wide, each labeling itself."""
    table = firstTable(pybers.open(importedFixture))
    assert table.cell("C1").value == "three wide, anchor"
    assert table.cell("F1").value == "covered holds a value, anchor"


@pytest.mark.parametrize("reference", coveredPositions)
def testACoveredPositionIsStillRefused(reference: str) -> None:
    """The guard that stopped the phantom-anchor defect is unchanged.

    Reading a record at a covered position and handing out a cell there are two
    different questions, and only the second is refused.
    """
    table = firstTable(pybers.open(importedFixture))
    with pytest.raises(CellReferenceError, match="covered by the merge"):
        table.cell(reference)


def testTheCoveredRecordsSurviveARoundTrip() -> None:
    """A save must not strip records the document arrived with."""
    assert recordedColumns(importedFixture, 0) == {0, 1, 2, 3, 4, 5}


def testTheImportedFixtureWritesBackUnchanged(tmp_path: Path) -> None:
    """The base contract, on the one fixture holding covered records."""
    target = tmp_path / "written.numbers"
    pybers.open(importedFixture).save(target)
    assert archiveBodies(readPackage(target)) == archiveBodies(
        readPackage(importedFixture)
    )


def testNoGestureInNumbersProducesACoveredRecord() -> None:
    """The control, and the reason this ticket cost four rounds of fixtures.

    Row 5 of the overpaint fixture holds three merges made after its cells were
    filled, then had a whole-row fill painted over it. Every empty cell the fill
    touched gained a record and every covered position stayed absent.
    """
    recorded = recordedColumns(overpaintFixture, 4)
    assert recorded.isdisjoint({1, 3, 5, 6})
    assert {0, 2, 4}.issubset(recorded)


def testAMergePybersMakesStillClearsItsCoveredPositions(tmp_path: Path) -> None:
    """Preserve what we find, clean up what we create.

    `M3` carries a style-only record until pybers merges over it, which is a
    stricter cleanup than Numbers performs and the one Numbers itself opens.
    """
    target = tmp_path / "merged.numbers"
    document = pybers.open(overpaintFixture)
    document.sheets[0].tables[0].mergeAdd("L3:M3")
    document.save(target)
    assert 12 in recordedColumns(overpaintFixture, 2)
    assert 12 not in recordedColumns(target, 2)


def testAMergeAlreadyInTheFileIsNotTreatedAsAdded() -> None:
    """The distinction the writer turns on, checked without writing anything."""
    from pybers.writer import mergesAdded

    index = ArchiveIndex(readPackage(importedFixture))
    document = pybers.open(importedFixture)
    table = firstTable(document)
    for identifier in index.byIdentifier:
        archive = index.archive(identifier)
        if archiveTypeId(archive) != tableModelType:
            continue
        model = tst.TableModelArchive()
        model.ParseFromString(archive.messages[0].data)
        assert mergesAdded(table, model) == []
        table.mergeRanges.append(MergeRange(table.rangeSingle("A4:B4", "merge")))
        assert len(mergesAdded(table, model)) == 1
        return
    raise AssertionError("No table model in the imported fixture.")


def testAMergeOverACoveredRecordMatchesItsGoldenFile(tmp_path: Path) -> None:
    """Dropping a real record is stricter than Numbers itself, so it earns a golden.

    Every other check here compares pybers against pybers, which can agree with
    itself while both halves are wrong. See `tests/golden/README.md` for the
    confirmation state of this file.
    """
    golden = goldenDirectory / "22c-merged-by-pybers.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    working = Path(
        shutil.copy(overpaintFixture, tmp_path / "22c.numbers")
    )
    document = pybers.open(working)
    document.sheets[0].tables[0].mergeAdd("L3:M3")
    document.save()

    assert archiveBodies(readPackage(golden)) == archiveBodies(
        readPackage(working)
    ), "the writer no longer produces the merge Numbers confirmed"
