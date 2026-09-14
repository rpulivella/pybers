#!/usr/bin/env python3
"""\
Adding a sheet to a document: where it lands, what it is written as, and what it leaves
alone.

`20-formula-shapes` is the source because a formula on its first sheet reads a table on
its second, so a sheet inserted between them is exactly what would break a reference
resolved by position. The golden was made from it the same way.

UPDATES
2026-09-14  Written for PYB-63.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/14"

from pathlib import Path

import pytest

import pybers
from conftest import archiveBodies
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSKArchives_pb2 as tsk
from pybers._generated import TSWPArchives_pb2 as tswp
from pybers._persistence import PackageRegistry, readPackage
from pybers._persistence.index import ArchiveIndex, findRoot
from pybers.document import Document, SelectionError
from pybers.errors import WriteError
from pybers.table import Table

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"
goldenDirectory: Path = Path(__file__).resolve().parent / "golden"

metadataMember: str = "Index/Metadata.iwa"


def shapes() -> Document:
    """Return `20-formula-shapes`, two sheets and a formula reading across them."""
    return pybers.open(fixtureDirectory / "20-formula-shapes.numbers")


def savedWithSheets(tmp_path: Path) -> Path:
    """Save the golden's two insertions, and return where they were written."""
    document = shapes()
    document.sheetAdd("Inserted", position=2)
    document.sheetAdd("Appended")
    destination = tmp_path / "sheets-added.numbers"
    document.save(destination)
    return destination


def sheetArchive(path: Path, name: str) -> tuple[ArchiveIndex, tn.SheetArchive]:
    """Return a file's index and the sheet archive carrying a name."""
    index = ArchiveIndex(readPackage(path))
    for reference in findRoot(index).sheets:
        sheet = index.resolve(reference, tn.SheetArchive)
        if sheet.name == name:
            return index, sheet
    raise AssertionError(f"No sheet named {name!r} in {path.name}.")


# ── AC 1: a new tab, named, where it was added ───────────────────────────────


def testASheetIsAddedLastByDefault() -> None:
    document = shapes()

    added = document.sheetAdd("Appended")

    assert document.sheets[-1] is added
    assert [sheet.name for sheet in document.sheets] == [
        "Sheet 1",
        "Sheet 2",
        "Appended",
    ]


def testASheetIsAddedAtAPositionCountedFromOne() -> None:
    document = shapes()

    document.sheetAdd("First", position=1)
    document.sheetAdd("Between", position=3)

    assert [sheet.name for sheet in document.sheets] == [
        "First",
        "Sheet 1",
        "Between",
        "Sheet 2",
    ]


def testANameAnotherSheetCarriesIsAccepted() -> None:
    document = shapes()

    document.sheetAdd("Sheet 1")

    assert [sheet.name for sheet in document.sheets].count("Sheet 1") == 2


@pytest.mark.parametrize("position", [0, 4, -1, True, 2.0, "2"])
def testAPositionOutsideTheTabsIsRefused(position: object) -> None:
    document = shapes()

    with pytest.raises(SelectionError):
        document.sheetAdd("Nowhere", position=position)  # type: ignore[arg-type]
    assert len(document.sheets) == 2


@pytest.mark.parametrize("name", ["", None, 7])
def testASheetWithoutANameIsRefused(name: object) -> None:
    document = shapes()

    with pytest.raises(SelectionError):
        document.sheetAdd(name)  # type: ignore[arg-type]
    assert len(document.sheets) == 2


def testAnAddedSheetReadsBackNamedAndInPlace(tmp_path: Path) -> None:
    reopened = pybers.open(savedWithSheets(tmp_path))

    assert [(sheet.name, len(sheet.tables)) for sheet in reopened.sheets] == [
        ("Sheet 1", 2),
        ("Inserted", 0),
        ("Sheet 2", 1),
        ("Appended", 0),
    ]


def testSavingTwiceCreatesTheSheetOnce(tmp_path: Path) -> None:
    document = shapes()
    document.sheetAdd("Once")
    document.save(tmp_path / "first.numbers")

    document.save(tmp_path / "second.numbers")

    names = [sheet.name for sheet in pybers.open(tmp_path / "second.numbers").sheets]
    assert names == ["Sheet 1", "Sheet 2", "Once"]


def testAnAddedSheetIsListedInTheSidebarInTabOrder(tmp_path: Path) -> None:
    index = ArchiveIndex(readPackage(savedWithSheets(tmp_path)))
    root = findRoot(index)

    listed = [
        index.resolve(node, tsk.TreeNode).object.identifier
        for node in index.resolve(root.sidebar_order, tsk.TreeNode).children
    ]

    assert listed == [reference.identifier for reference in root.sheets]


# ── The pybers reset ─────────────────────────────────────────────────────────


def testAnAddedSheetPrintsOneToOneWithTheResetMargins(tmp_path: Path) -> None:
    _, sheet = sheetArchive(savedWithSheets(tmp_path), "Inserted")

    assert not sheet.is_autofit_on
    assert sheet.content_scale == 1.0
    assert not sheet.show_page_numbers
    margins = sheet.print_margins
    assert (margins.top, margins.left, margins.bottom, margins.right) == (
        72.0,
        54.0,
        72.0,
        54.0,
    )


def testEveryHeaderAndFooterOfAnAddedSheetIsEmpty(tmp_path: Path) -> None:
    index, sheet = sheetArchive(savedWithSheets(tmp_path), "Inserted")

    storages = [
        index.resolve(reference, tswp.StorageArchive)
        for reference in [*sheet.headers, *sheet.footers]
    ]

    assert len(storages) == 6
    assert all(not storage.text for storage in storages)
    assert all(not storage.table_attachment.entries for storage in storages)


def testAnAddedSheetSharesTheStyleOfTheFirstSheet(tmp_path: Path) -> None:
    path = savedWithSheets(tmp_path)
    _, first = sheetArchive(path, "Sheet 1")
    _, added = sheetArchive(path, "Appended")

    assert added.style.identifier == first.style.identifier


def testAnAddedSheetFollowsTheRegistryRules(tmp_path: Path) -> None:
    path = savedWithSheets(tmp_path)
    registry = PackageRegistry(readPackage(path))
    _, added = sheetArchive(path, "Inserted")

    uuids = {
        entry.identifier
        for entry in registry.components[1].object_uuid_map_entries
    }
    assert {added.userDefinedGuideStorage.identifier, *[
        reference.identifier for reference in [*added.headers, *added.footers]
    ]} <= uuids
    for identifier, component in registry.components.items():
        stored = {
            (reference.component_identifier, reference.object_identifier)
            for reference in component.external_references
            if not reference.is_weak
        }
        assert registry.strongReferencesDerive(identifier) == stored


# ── AC 4: everything already there is untouched ──────────────────────────────


def testAddingASheetRewritesOnlyTheRootTheSidebarAndTheRegistry(
    tmp_path: Path,
) -> None:
    source = readPackage(fixtureDirectory / "20-formula-shapes.numbers")
    written = readPackage(savedWithSheets(tmp_path))
    index = ArchiveIndex(source)
    root = findRoot(index)
    rewritten = {1, root.sidebar_order.identifier}

    before = {
        (member, identifier): body
        for member, identifier, body in archiveBodies(source)
        if member != metadataMember and identifier not in rewritten
    }
    after = {
        key: body
        for member, identifier, body in archiveBodies(written)
        if (key := (member, identifier)) in before
    }

    assert after == before


def testAFormulaReadingAcrossSheetsStillNamesTheSameTable(tmp_path: Path) -> None:
    reopened = pybers.open(savedWithSheets(tmp_path))

    cell = reopened.sheet("Sheet 1").table("Table 1").cell("H11")

    assert cell.formulaText == "=Sheet 2::Table 1::A1"


# ── Refused, and refused before anything is written ──────────────────────────


def testARefusedSaveUndoesTheSheetsItHadCreated(tmp_path: Path) -> None:
    document = shapes()
    package = document._package
    assert package is not None
    before = archiveBodies(package)
    added = document.sheetAdd("With an empty table")
    added.tables.append(Table("No grid"))

    with pytest.raises(WriteError, match="at least one of each"):
        document.save(tmp_path / "refused.numbers")

    assert archiveBodies(package) == before
    assert added._identifier is None
    assert not (tmp_path / "refused.numbers").exists()


def testRemovingASheetIsRefused(tmp_path: Path) -> None:
    document = shapes()
    del document.sheets[1]

    with pytest.raises(WriteError, match="Removing or reordering"):
        document.save(tmp_path / "removed.numbers")


def testReorderingSheetsIsRefused(tmp_path: Path) -> None:
    document = shapes()
    document.sheets.reverse()

    with pytest.raises(WriteError, match="Removing or reordering"):
        document.save(tmp_path / "reordered.numbers")


# ── The golden ───────────────────────────────────────────────────────────────


def testTheGoldenIsWhatAddingTheSheetsWritesToday(tmp_path: Path) -> None:
    """Every sheet archive and the tab order match; only the random UUIDs may differ."""
    golden = goldenDirectory / "20-sheets-added.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    def sheetsOf(path: Path) -> list[bytes]:
        index = ArchiveIndex(readPackage(path))
        return [
            index.archive(reference.identifier).messages[0].data
            for reference in findRoot(index).sheets
        ]

    assert sheetsOf(savedWithSheets(tmp_path)) == sheetsOf(golden)


def testTheGoldenHoldsTheSheetsItClaims() -> None:
    """Guard the guard: a golden replaced by an unedited copy would pass the above."""
    reopened = pybers.open(goldenDirectory / "20-sheets-added.numbers")

    assert [sheet.name for sheet in reopened.sheets] == [
        "Sheet 1",
        "Inserted",
        "Sheet 2",
        "Appended",
    ]


# ── The two consumers ────────────────────────────────────────────────────────


def testAScriptPutsItsOutputOnASheetOfItsOwn(tmp_path: Path) -> None:
    """The `import pybers` consumer: a report tab added in two lines and saved."""
    document = shapes()
    document.sheetAdd("Report")
    document.save(tmp_path / "report.numbers")

    assert pybers.open(tmp_path / "report.numbers").sheet("Report").tables == []


def testACliAddsATabAtTheIndexItWasGiven(tmp_path: Path) -> None:
    """The `pybers sheet add NAME --at N` consumer, printing the tabs afterward."""
    document = shapes()
    document.sheetAdd("Summary", position=1)
    document.save(tmp_path / "summary.numbers")

    reopened = pybers.open(tmp_path / "summary.numbers")
    printed = [
        f"{position}. {sheet.name}"
        for position, sheet in enumerate(reopened.sheets, start=1)
    ]
    assert printed == ["1. Summary", "2. Sheet 1", "3. Sheet 2"]


def testEveryNameThisAddsIsReachableFromPybersAlone() -> None:
    """Neither consumer imports anything deeper than `pybers`."""
    assert hasattr(pybers.Document, "sheetAdd")
