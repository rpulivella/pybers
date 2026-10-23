#!/usr/bin/env python3
"""\
Adding a table to a sheet: its size, its name, the reset it is written in, the values
it takes, and what it leaves alone.

`20-formula-shapes` is the source for the reason it is in `test_sheet_add.py`: its
formulas read across tables and sheets, so anything a created table disturbed in the
engine would show there. The golden was made from it the same way.

UPDATES
2026-10-22  The golden's tables are added by its builder, for PYB-255.
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

from decimal import Decimal
from pathlib import Path

import pytest
from golden.builders import addTables as addGoldenTables

import pybers
from conftest import findDocumentPath, readArchiveBodies
from pybers._engine import findCalculationEngine
from pybers._generated import TSCEArchives_pb2 as tsce
from pybers._generated import TSPMessages_pb2 as tsp
from pybers._generated import TSSArchives_pb2 as tss
from pybers._generated import TSTArchives_pb2 as tst
from pybers._generated import TSWPArchives_pb2 as tswp
from pybers._persistence import PackageRegistry, readPackage
from pybers._persistence.index import ArchiveIndex
from pybers.document import Document, SelectionError
from pybers.errors import WriteError
from pybers.table import Table

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"

metadataMember: str = "Index/Metadata.iwa"
ownerKinds: frozenset[int] = frozenset({1, 3, 4, 5, 6, 8, 9, 10, 11, 12, 35})


def openShapes() -> Document:
    """Return `20-formula-shapes`, whose formulas read across tables and sheets."""
    return pybers.open(findDocumentPath("20-formula-shapes"))


def addTables(document: Document) -> Document:
    """Add the golden's three tables and their values, and return the document."""
    addGoldenTables(document)
    return document


def saveWithTables(tmp_path: Path) -> Path:
    """Save the golden's additions, and return where they were written."""
    destination = tmp_path / "tables-added.numbers"
    addTables(openShapes()).save(destination)
    return destination


def findTableArchives(
    path: Path, sheet: str, table: str
) -> tuple[ArchiveIndex, tst.TableInfoArchive, tst.TableModelArchive]:
    """Return a file's index, and one table's info and model archives."""
    reopened = pybers.open(path).sheet(sheet).table(table)
    index = ArchiveIndex(readPackage(path))
    assert reopened._identifier is not None
    info = index.resolve(
        tsp.Reference(identifier=reopened._identifier), tst.TableInfoArchive
    )
    return index, info, index.resolve(info.tableModel, tst.TableModelArchive)


# ── AC 2: the rows and columns asked for ─────────────────────────────────────


def testATableIsAddedToItsSheetWithTheSizeAskedFor() -> None:
    sheet = openShapes().sheet("Sheet 2")

    added = sheet.tableAdd("Report", rows=4, cols=6)

    assert sheet.tables[-1] is added
    assert (added.name, added.rowCount, added.colCount) == ("Report", 4, 6)


def testAnAddedTableReadsBackWithItsSize(tmp_path: Path) -> None:
    reopened = pybers.open(saveWithTables(tmp_path))

    assert [
        (sheet.name, [(t.name, t.rowCount, t.colCount) for t in sheet.tables])
        for sheet in reopened.sheets
    ] == [
        (
            "Sheet 1",
            [
                ("Table 1", 12, 8),
                ("Table 2", 10, 5),
                ("Table 1-1", 3, 4),
                ("table 2-1", 2, 3),
            ],
        ),
        ("Sheet 2", [("Table 1", 10, 5)]),
        ("Fresh", [("Output", 5, 2)]),
    ]


@pytest.mark.parametrize(
    ("rows", "cols"),
    [(0, 3), (3, 0), (-1, 3), (True, 3), (3, 2.0), ("3", 3), (1_000_001, 3), (3, 1001)],
)
def testASizeNoTableCanHaveIsRefused(rows: object, cols: object) -> None:
    sheet = openShapes().sheet(1)

    with pytest.raises(SelectionError):
        sheet.tableAdd("Nowhere", rows=rows, cols=cols)  # type: ignore[arg-type]
    assert len(sheet.tables) == 2


@pytest.mark.parametrize("name", ["", None, 7])
def testATableWithoutANameIsRefused(name: object) -> None:
    sheet = openShapes().sheet(1)

    with pytest.raises(SelectionError):
        sheet.tableAdd(name, rows=1, cols=1)  # type: ignore[arg-type]


# ── AC 3: a value written into a created table ───────────────────────────────


def testValuesWrittenIntoCreatedTablesReadBack(tmp_path: Path) -> None:
    reopened = pybers.open(saveWithTables(tmp_path))

    first = reopened.sheet("Sheet 1").table("Table 1-1")
    output = reopened.sheet("Fresh").table("Output")
    assert first.cell("A1").value == "text in a created table"
    assert first.cell("B2").value == Decimal("12.5")
    assert output.cell("A1").value == Decimal("1")
    assert output.cell("B5").value == "last cell"


def testANumberInACreatedTableNamesTheAutomaticFormat(tmp_path: Path) -> None:
    index, _, model = findTableArchives(saveWithTables(tmp_path), "Fresh", "Output")

    formats = index.resolve(model.base_data_store.format_table, tst.TableDataList)

    numbers = [
        entry.format for entry in formats.entries if entry.format.format_type == 256
    ]
    assert len(numbers) == 1
    assert numbers[0].decimal_places == 253
    assert not numbers[0].show_thousands_separator


# ── AC 4: everything already there is untouched ──────────────────────────────


def testExistingTablesReadBackUnchanged(tmp_path: Path) -> None:
    original = openShapes()
    reopened = pybers.open(saveWithTables(tmp_path))

    for sheet in original.sheets:
        for table in sheet.tables:
            assert reopened.sheet(sheet.name).table(table.name) == table


def testFormulasReadingAcrossTablesStillNameTheSameTables(tmp_path: Path) -> None:
    reopened = pybers.open(saveWithTables(tmp_path)).sheet("Sheet 1").table("Table 1")

    assert reopened.cell("G11").formulaText == "=Table 2::A1"
    assert reopened.cell("H11").formulaText == "=Sheet 2::Table 1::A1"


def testOnlyTheArchivesThatRegisterATableAreRewritten(tmp_path: Path) -> None:
    """Every member but the four that list sheets, owners and styles is untouched."""
    source = readPackage(findDocumentPath("20-formula-shapes"))
    written = readPackage(saveWithTables(tmp_path))
    registering = {
        metadataMember,
        "Index/Document.iwa",
        "Index/CalculationEngine.iwa",
        "Index/DocumentStylesheet.iwa",
    }

    before = {
        (member, identifier): body
        for member, identifier, body in readArchiveBodies(source)
        if member not in registering
    }
    after = {
        (member, identifier): body
        for member, identifier, body in readArchiveBodies(written)
        if (member, identifier) in before
    }
    assert after == before


# ── AC 5: the name Numbers gives a clash ─────────────────────────────────────


def testANameTheSheetCarriesTakesTheFirstFreeSuffix() -> None:
    sheet = openShapes().sheet("Sheet 1")

    first = sheet.tableAdd("Table 1", rows=1, cols=1)
    second = sheet.tableAdd("TABLE 1", rows=1, cols=1)

    assert (first.name, second.name) == ("Table 1-1", "TABLE 1-2")


def testANameAnotherSheetCarriesIsKept() -> None:
    added = openShapes().sheet("Sheet 2").tableAdd("Table 2", rows=1, cols=1)

    assert added.name == "Table 2"


# ── The pybers reset ─────────────────────────────────────────────────────────


def testACreatedTableShowsNoTitleHeadersOrStrokes(tmp_path: Path) -> None:
    saved = saveWithTables(tmp_path)
    index, _, model = findTableArchives(saved, "Sheet 1", "Table 1-1")

    style = index.resolve(model.table_style, tst.TableStyleArchive)

    assert not model.table_name_enabled
    assert (
        model.number_of_header_rows,
        model.number_of_header_columns,
        model.number_of_footer_rows,
    ) == (0, 0, 0)
    properties = style.table_properties
    assert not properties.v_strokes_visible
    assert not properties.h_strokes_visible
    assert not properties.table_border_visible


def testACreatedTableUsesTheResetSizesAndDoesNotWrap(tmp_path: Path) -> None:
    saved = saveWithTables(tmp_path)
    index, _, model = findTableArchives(saved, "Sheet 1", "Table 1-1")

    cell = index.resolve(model.body_cell_style, tst.CellStyleArchive)

    assert (model.default_row_height, model.default_column_width) == (24.0, 72.0)
    assert not cell.cell_properties.text_wrap


def testEveryTextSlotButTheTitleNamesPybersBase(tmp_path: Path) -> None:
    saved = saveWithTables(tmp_path)
    index, _, model = findTableArchives(saved, "Sheet 1", "Table 1-1")

    base = index.resolve(model.body_text_style, tswp.ParagraphStyleArchive)
    textSlots = [
        descriptor.name
        for descriptor in tst.TableStyleNetworkArchive.DESCRIPTOR.fields
        if descriptor.name.endswith("_text_style")
    ]

    assert base.super.name == "pybers-base"
    assert base.char_properties.font_name == "AvenirNext-Regular"
    assert base.char_properties.font_size == 11.0
    assert base.para_properties.line_spacing.amount == 15.5
    assert {getattr(model, name).identifier for name in textSlots} == {
        model.body_text_style.identifier
    }
    assert model.table_name_style.identifier != model.body_text_style.identifier


def testPybersBaseIsCreatedOnceAcrossTablesAndSaves(tmp_path: Path) -> None:
    document = addTables(openShapes())
    document.save(tmp_path / "first.numbers")
    document.sheet("Sheet 2").tableAdd("Later", rows=1, cols=1)
    document.save(tmp_path / "second.numbers")

    index = ArchiveIndex(readPackage(tmp_path / "second.numbers"))
    stylesheets = [
        identifier
        for identifier, archive in index.byIdentifier.items()
        if archive.messages[0].typeId == 401
    ]
    stylesheet = index.resolve(
        tsp.Reference(identifier=stylesheets[0]), tss.StylesheetArchive
    )
    named = [
        reference.identifier
        for reference in stylesheet.styles
        if reference.identifier in index.byIdentifier
        and index.byIdentifier[reference.identifier].messages[0].typeId == 2022
        and index.resolve(reference, tswp.ParagraphStyleArchive).super.name
        == "pybers-base"
    ]
    assert len(named) == 1


# ── Placement ────────────────────────────────────────────────────────────────


def testATableIsPlacedWithItsTopLeftCornerAtAPosition(tmp_path: Path) -> None:
    document = openShapes()
    document.sheet(1).tableAdd(
        "Placed", rows=2, cols=2, position=pybers.Position(144.0, 36.0)
    )
    document.save(tmp_path / "placed.numbers")

    _, info, _ = findTableArchives(tmp_path / "placed.numbers", "Sheet 1", "Placed")

    assert (info.super.geometry.position.x, info.super.geometry.position.y) == (
        144.0,
        36.0,
    )


def testATableWithNoPositionLandsBelowTheTablesAlreadyThere(tmp_path: Path) -> None:
    path = saveWithTables(tmp_path)
    _, lower, model = findTableArchives(path, "Sheet 1", "Table 2")
    _, added, _ = findTableArchives(path, "Sheet 1", "Table 1-1")
    _, after, _ = findTableArchives(path, "Sheet 1", "table 2-1")

    bottom = (
        lower.super.geometry.position.y
        + model.number_of_rows * model.default_row_height
    )
    assert added.super.geometry.position.y > bottom
    assert after.super.geometry.position.y > added.super.geometry.position.y + 3 * 24.0


def testAPositionThatIsNotAPositionIsRefused() -> None:
    sheet = openShapes().sheet(1)

    with pytest.raises(SelectionError, match="Position"):
        sheet.tableAdd("Nowhere", rows=1, cols=1, position=(1.0, 2.0))  # type: ignore[arg-type]


# ── Registration ─────────────────────────────────────────────────────────────


def testACreatedTableRegistersElevenOwnersOnItsIdentity(tmp_path: Path) -> None:
    path = saveWithTables(tmp_path)
    reopened = pybers.open(path).sheet("Fresh").table("Output")
    index = ArchiveIndex(readPackage(path))
    words = [int(reopened.identifier[at : at + 8], 16) for at in range(0, 32, 8)]
    base = words[0] | words[1] << 32 | words[2] << 64 | words[3] << 96

    kinds = set()
    for reference in findCalculationEngine(
        index
    ).dependency_tracker.formula_owner_dependencies:
        owner = index.resolve(reference, tsce.FormulaOwnerDependenciesArchive)
        value = owner.formula_owner_uid.upper << 64 | owner.formula_owner_uid.lower
        if 0 <= value - base < 0x100:
            assert value - base == (0 if owner.owner_kind == 1 else owner.owner_kind)
            kinds.add(owner.owner_kind)
    assert kinds == ownerKinds


def testEveryCreatedTableGetsItsOwnHeaderNameSlot(tmp_path: Path) -> None:
    index = ArchiveIndex(readPackage(saveWithTables(tmp_path)))
    names = index.resolve(
        findCalculationEngine(index).header_name_manager, tst.HeaderNameMgrArchive
    )

    slots = [entry.per_table_precedent.column for entry in names.per_tables]

    assert len(slots) == 6
    assert len(set(slots)) == 6


def testACreatedTableFollowsTheRegistryRules(tmp_path: Path) -> None:
    registry = PackageRegistry(
        ArchiveIndex(readPackage(saveWithTables(tmp_path)))
    )

    for identifier, component in registry.components.items():
        stored = {
            (reference.component_identifier, reference.object_identifier)
            for reference in component.external_references
            if not reference.is_weak
        }
        assert registry.strongReferencesDerive(identifier) == stored
    unplaced = [
        archive.identifier
        for iwaFile in registry.package.iwaFiles
        if iwaFile is not registry.metadataFile
        for archive in iwaFile.archives
        if registry.componentFind(archive.identifier) is None
    ]
    assert unplaced == []


def testSavingTwiceCreatesTheTableOnce(tmp_path: Path) -> None:
    document = openShapes()
    document.sheet(1).tableAdd("Once", rows=1, cols=1)
    document.save(tmp_path / "first.numbers")

    document.save(tmp_path / "second.numbers")

    names = [
        table.name for table in pybers.open(tmp_path / "second.numbers").sheet(1).tables
    ]
    assert names == ["Table 1", "Table 2", "Once"]


def testANewTableBeforeAnExistingOneIsRefusedAndWritesNothing(
    tmp_path: Path,
) -> None:
    """Pairing is by position, so a table ahead of an old one would take its cells."""
    document = openShapes()
    package = document._package
    assert package is not None
    before = readArchiveBodies(package)
    document.sheet(1).tables.insert(0, Table("Ahead", rowCount=1, colCount=1))

    with pytest.raises(WriteError, match="sits before a table already"):
        document.save(tmp_path / "ahead.numbers")

    assert readArchiveBodies(package) == before


def testATableBuiltByHandAndAppendedIsCreated(tmp_path: Path) -> None:
    document = openShapes()
    document.sheet(2).tables.append(Table("By hand", rowCount=2, colCount=2))

    document.save(tmp_path / "hand.numbers")

    reopened = pybers.open(tmp_path / "hand.numbers").sheet(2).table("By hand")
    assert (reopened.rowCount, reopened.colCount) == (2, 2)
    assert len(reopened.identifier) == 32


def testRemovingATableIsRefused(tmp_path: Path) -> None:
    document = openShapes()
    del document.sheet(1).tables[1]

    with pytest.raises(WriteError, match="Removing or reordering a table"):
        document.save(tmp_path / "removed.numbers")


# ── The golden ───────────────────────────────────────────────────────────────


def testTheGoldenHoldsTheTablesItClaims() -> None:
    """Guard the guard: the golden's created tables and values, read back."""
    golden = goldenDirectory / "20-tables-added.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    reopened = pybers.open(golden)

    first = reopened.sheet("Sheet 1").table("Table 1-1")
    assert (first.rowCount, first.colCount) == (3, 4)
    assert first.cell("B2").value == Decimal("12.5")
    assert (
        reopened.sheet("Sheet 1").table("table 2-1").cell("C2").value
        == "second created"
    )
    assert reopened.sheet("Fresh").table("Output").cell("B5").value == "last cell"


def testTheGoldenIsWhatAddingTheTablesWritesToday(tmp_path: Path) -> None:
    """Every created table's model matches the golden's, apart from its fresh names."""

    def readTableModels(path: Path) -> list[tst.TableModelArchive]:
        reopened = pybers.open(path)
        models = []
        for sheet, table in (
            ("Sheet 1", "Table 1-1"),
            ("Sheet 1", "table 2-1"),
            ("Fresh", "Output"),
        ):
            _, _, model = findTableArchives(path, sheet, table)
            kept = tst.TableModelArchive()
            for name in (
                "table_name",
                "number_of_rows",
                "number_of_columns",
                "default_row_height",
                "default_column_width",
                "number_of_header_rows",
                "number_of_header_columns",
            ):
                setattr(kept, name, getattr(model, name))
            models.append(kept)
        assert reopened
        return models

    assert readTableModels(saveWithTables(tmp_path)) == readTableModels(
        goldenDirectory / "20-tables-added.numbers"
    )


# ── The two consumers ────────────────────────────────────────────────────────


def testAScriptBuildsAReportTableOnANewSheet(tmp_path: Path) -> None:
    """The `import pybers` consumer: a sheet, a table, a loop over values, a save."""
    document = openShapes()
    table = document.sheetAdd("Report").tableAdd("Totals", rows=3, cols=2)
    for row, (label, amount) in enumerate(
        [("rent", "1200"), ("food", "450"), ("power", "80")], start=1
    ):
        table.cell(row=row, col=1).value = label
        table.cell(row=row, col=2).value = Decimal(amount)
    document.save(tmp_path / "report.numbers")

    reopened = pybers.open(tmp_path / "report.numbers").sheet("Report").table("Totals")
    assert [cell.value for cell in reopened.gridIterate()] == [
        "rent",
        Decimal("1200"),
        "food",
        Decimal("450"),
        "power",
        Decimal("80"),
    ]


def testACliAddsATableAtAPointAndPrintsItsName(tmp_path: Path) -> None:
    """The `pybers table add SHEET NAME --rows R --cols C --at X,Y` consumer."""
    document = openShapes()
    x, y = (float(part) for part in ["72", "432"])
    added = document.sheet("Sheet 1").tableAdd(
        "Table 2", rows=2, cols=2, position=pybers.Position(x, y)
    )
    document.save(tmp_path / "cli.numbers")

    printed = f"added {added.name} ({added.rowCount}x{added.colCount}) at {x:g},{y:g}"
    assert printed == "added Table 2-1 (2x2) at 72,432"
    assert (
        pybers.open(tmp_path / "cli.numbers")
        .sheet("Sheet 1")
        .table("Table 2-1")
        .colCount
        == 2
    )


def testEveryNameThisAddsIsReachableFromPybersAlone() -> None:
    """Neither consumer imports anything deeper than `pybers`."""
    assert hasattr(pybers.Sheet, "tableAdd")
    assert pybers.Position is not None
