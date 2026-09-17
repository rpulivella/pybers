#!/usr/bin/env python3
"""\
A formula written into a table pybers created: its registration, what it reads, and
what it leaves alone.

`55-table-inserted-formula` is `48-table-inserted` with one formula typed into the
table Numbers inserted, whose owner held no dependency tile either, so replaying that
edit on `48` compares the tile pybers creates with the one Numbers created.

UPDATES
2026-09-15  Written for PYB-86.
"""

from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/15"

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from google.protobuf import text_format

import pybers
from conftest import findDocumentPath, readArchiveBodies
from pybers._engine import calculationEngine, tableOwnerEntries
from pybers._generated import TSCEArchives_pb2 as tsce
from pybers._generated import TSPMessages_pb2 as tsp
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import PackageRegistry, readPackage
from pybers._persistence.index import ArchiveIndex
from pybers.document import Document
from pybers.errors import WriteError
from pybers.formula.nodes import FormulaReference

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"


def openShapes() -> Document:
    """Return `20-formula-shapes`, whose formulas read across tables and sheets."""
    return pybers.open(findDocumentPath("20-formula-shapes"))


def addFormulas(document: Document) -> Document:
    """Add the golden's two tables and their formulas, and return the document."""
    inputs = document.sheet("Sheet 1").tableAdd("Inputs", rows=2, cols=2)
    inputs.cell("A1").value = Decimal("5")
    calc = document.sheet("Sheet 1").tableAdd("Calc", rows=3, cols=3)
    calc.cell("A1").value = Decimal("2")
    calc.cell("B1").formulaText = "=A1*3"
    calc.cell("C1").formulaText = "=Table 2::A1"
    calc.cell("A2").formulaText = "=Inputs::A1+1"
    calc.cell("A3").formulaText = "=SUM(A1:B1)"
    return document


def saveWithFormulas(tmp_path: Path) -> Path:
    """Save the golden's additions, and return where they were written."""
    destination = tmp_path / "formulas-added.numbers"
    addFormulas(openShapes()).save(destination)
    return destination


def readOwnerTiles(
    path: Path, sheet: str, table: str
) -> tuple[tsce.FormulaOwnerDependenciesArchive, list[tsce.CellRecordTileArchive]]:
    """Return one table's engine owner and the dependency tiles it lists."""
    identifier = pybers.open(path).sheet(sheet).table(table)._identifier
    assert identifier is not None
    index = ArchiveIndex(readPackage(path))
    owner = tableOwnerEntries(index, calculationEngine(index))[identifier].dependencies
    tiles = [
        index.resolve(reference, tsce.CellRecordTileArchive)
        for reference in owner.tiled_cell_dependencies.cell_record_tiles
    ]
    return owner, tiles


def readRegisteredPairs(records: object) -> set[tuple[int, int]]:
    """Return the (row, column) pairs a register holds."""
    return {(record.row, record.column) for record in records}  # type: ignore[attr-defined]


# ── AC 1: a formula in a created table reads back and is registered ─────────


def testFormulasWrittenIntoACreatedTableReadBack(tmp_path: Path) -> None:
    calc = pybers.open(saveWithFormulas(tmp_path)).sheet("Sheet 1").table("Calc")

    assert calc.cell("A1").value == Decimal("2")
    assert [calc.cell(ref).formulaText for ref in ("B1", "C1", "A2", "A3")] == [
        "=A1*3",
        "=Table 2::A1",
        "=Inputs::A1+1",
        "=SUM(A1:B1)",
    ]


def testACreatedTableGainsOneTileHoldingEveryFormulaCell(tmp_path: Path) -> None:
    owner, tiles = readOwnerTiles(saveWithFormulas(tmp_path), "Sheet 1", "Calc")

    formulaCells = {(0, 1), (0, 2), (1, 0), (2, 0)}
    assert len(tiles) == 1
    assert (tiles[0].tile_column_begin, tiles[0].tile_row_begin) == (0, 0)
    assert tiles[0].internal_owner_id == owner.internal_formula_owner_id
    assert readRegisteredPairs(tiles[0].cell_records) == formulaCells
    assert readRegisteredPairs(owner.cell_dependencies.cell_record) == formulaCells


def testATableWithNoFormulaGainsNoTile(tmp_path: Path) -> None:
    _, tiles = readOwnerTiles(saveWithFormulas(tmp_path), "Sheet 1", "Inputs")

    assert tiles == []


def testTheTileMatchesTheOneNumbersCreatedApartFromEdges(tmp_path: Path) -> None:
    """Replay `55` on `48`; edges stay empty until the golden shows they matter."""
    document = pybers.open(findDocumentPath("48-table-inserted"))
    table = document.sheet(1).table(1)
    table.cell("A1").value = Decimal("2")
    table.cell("B1").formulaText = "=A1*3"
    document.save(tmp_path / "replayed.numbers")

    def readTileShape(path: Path) -> list[tuple[int, int, int, set[tuple[int, int]]]]:
        _, tiles = readOwnerTiles(path, "Sheet 1", "Table 1")
        return [
            (
                tile.internal_owner_id,
                tile.tile_column_begin,
                tile.tile_row_begin,
                readRegisteredPairs(tile.cell_records),
            )
            for tile in tiles
        ]

    assert readTileShape(tmp_path / "replayed.numbers") == readTileShape(
        findDocumentPath("55-table-inserted-formula")
    )


def testTheCreatedTileFollowsTheRegistryRules(tmp_path: Path) -> None:
    registry = PackageRegistry(readPackage(saveWithFormulas(tmp_path)))

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
        if archive.identifier not in registry.componentOf
    ]
    assert unplaced == []


def testTheFormulaCellsAreMarkedForRecalculation(tmp_path: Path) -> None:
    path = saveWithFormulas(tmp_path)
    owner, _ = readOwnerTiles(path, "Sheet 1", "Calc")
    index = ArchiveIndex(readPackage(path))

    dirty = index.resolve(
        calculationEngine(index).refs_to_dirty, tsce.ReferencesToDirtyArchive
    )

    cells = {
        (row, column.column)
        for owned in dirty.to_dirty_cells.owner_entries
        if owned.owner_id == owner.internal_formula_owner_id
        for column in owned.coord_set.column_entries
        for entry in column.row_set.entries
        for row in range(
            entry.range_begin, max(entry.range_begin, entry.range_end) + 1
        )
    }
    assert {(0, 1), (0, 2), (1, 0), (2, 0)} <= cells


def encodeIdentityBytes(identity: str) -> bytes:
    """Return a table identity as the bytes its canonical UUID spells."""
    return b"".join(
        int(identity[at : at + 8], 16).to_bytes(4, "little") for at in range(0, 32, 8)
    )


def testACreatedTablesIdentityIsAVersionFourUuidAsNumbersStoresOne(
    tmp_path: Path,
) -> None:
    """Every table identity Numbers writes reads as one; pybers' laid out its bytes
    the other way round."""
    document = pybers.open(saveWithFormulas(tmp_path))

    for table in document.sheet("Sheet 1").tables:
        stored = encodeIdentityBytes(table.identifier)
        assert (stored[6] >> 4, stored[8] >> 6) == (4, 0b10), table.name


def testACreatedTablesIdIsItsIdentity(tmp_path: Path) -> None:
    """`table_id` is how Numbers finds a table's owners, and any other value costs it
    its whole owner family on open."""
    path = saveWithFormulas(tmp_path)

    document = pybers.open(path)
    index = ArchiveIndex(readPackage(path))
    for table in document.sheet("Sheet 1").tables:
        info = index.resolve(
            tsp.Reference(identifier=table._identifier), tst.TableInfoArchive
        )
        model = index.resolve(info.tableModel, tst.TableModelArchive)
        spelled = str(uuid.UUID(bytes=encodeIdentityBytes(table.identifier))).upper()
        assert model.table_id == spelled, table.name


# ── AC 2: what a formula declares that it reads ─────────────────────────────


def readRegisters(path: Path, sheet: str, table: str) -> list[str]:
    """Return one table's three precedent registers, as text, in file order."""
    owner, _ = readOwnerTiles(path, sheet, table)
    index = ArchiveIndex(readPackage(path))
    lines = [text_format.MessageToString(record, as_one_line=True)
             for record in owner.cell_dependencies.cell_record]
    lines += [text_format.MessageToString(entry, as_one_line=True)
              for entry in owner.range_dependencies.back_dependency]
    lines += [text_format.MessageToString(entry, as_one_line=True)
              for entry in owner.spanning_column_dependencies.coord_refers_to_spans]
    lines += [
        text_format.MessageToString(
            index.resolve(reference, tsce.RangePrecedentsTileArchive), as_one_line=True
        )
        for reference in owner.tiled_range_dependencies.range_precedents_tile
    ]
    return lines


def testRewritingNumbersOwnFormulasReproducesItsRegisters(tmp_path: Path) -> None:
    """Strip the eight formulas of `20-formula-shapes` and write them back."""
    source = findDocumentPath("20-formula-shapes")
    references = ("A11", "B11", "C11", "D11", "E11", "F11", "G11", "H11")
    kept = {
        reference: pybers.open(source).sheet("Sheet 1").table("Table 1")
        .cell(reference).formula
        for reference in references
    }
    stripped = pybers.open(source)
    for reference in references:
        stripped.sheet("Sheet 1").table("Table 1").cell(reference).formula = None
    stripped.save(tmp_path / "stripped.numbers")
    rewritten = pybers.open(tmp_path / "stripped.numbers")
    for reference, formula in kept.items():
        rewritten.sheet("Sheet 1").table("Table 1").cell(reference).formula = formula
    rewritten.save(tmp_path / "rewritten.numbers")

    rewritten = tmp_path / "rewritten.numbers"
    assert readRegisters(rewritten, "Sheet 1", "Table 1") == readRegisters(
        source, "Sheet 1", "Table 1"
    )


def testAFormulaInACreatedTableDeclaresTheCellItReads(tmp_path: Path) -> None:
    owner, tiles = readOwnerTiles(saveWithFormulas(tmp_path), "Sheet 1", "Calc")

    edges = {
        (record.row, record.column): (
            list(record.expanded_edges.edge_without_owner_rows),
            list(record.expanded_edges.edge_without_owner_columns),
            list(record.expanded_edges.internal_owner_id_for_edge),
        )
        for record in owner.cell_dependencies.cell_record
    }

    assert edges[(0, 1)] == ([0], [0], [])
    assert edges[(1, 0)][2] != [], "the reference into Inputs names that table's owner"
    assert edges == {
        (record.row, record.column): (
            list(record.expanded_edges.edge_without_owner_rows),
            list(record.expanded_edges.edge_without_owner_columns),
            list(record.expanded_edges.internal_owner_id_for_edge),
        )
        for record in tiles[0].cell_records
    }


def testARangeInACreatedTableIsDeclaredInBothRangeRegisters(tmp_path: Path) -> None:
    path = saveWithFormulas(tmp_path)
    owner, _ = readOwnerTiles(path, "Sheet 1", "Calc")
    index = ArchiveIndex(readPackage(path))

    backDependencies = [
        (entry.cell_coord_row, entry.cell_coord_column,
         entry.internal_range_reference.range.top_left_row,
         entry.internal_range_reference.range.bottom_right_column)
        for entry in owner.range_dependencies.back_dependency
    ]
    tiles = [
        index.resolve(reference, tsce.RangePrecedentsTileArchive)
        for reference in owner.tiled_range_dependencies.range_precedents_tile
    ]

    assert backDependencies == [(2, 0, 0, 1)]
    assert len(tiles) == 1
    assert [(entry.from_coord.row, entry.from_coord.column,
             entry.refers_to_rect.size.num_columns)
            for entry in tiles[0].from_to_range] == [(2, 0, 2)]


def testReplacingAFormulaRedeclaresWhatItReads(tmp_path: Path) -> None:
    """A swapped formula kept the precedent of the one it replaced, PYB-86."""
    document = addFormulas(openShapes())
    document.save(tmp_path / "first.numbers")
    reopened = pybers.open(tmp_path / "first.numbers")
    reopened.sheet("Sheet 1").table("Calc").cell("B1").formulaText = "=A2*3"
    reopened.save(tmp_path / "second.numbers")

    owner, tiles = readOwnerTiles(tmp_path / "second.numbers", "Sheet 1", "Calc")

    for records in (owner.cell_dependencies.cell_record, tiles[0].cell_records):
        edges = {
            (record.row, record.column): (
                list(record.expanded_edges.edge_without_owner_rows),
                list(record.expanded_edges.edge_without_owner_columns),
            )
            for record in records
        }
        assert edges[(0, 1)] == ([1], [0])


def testRemovingAFormulaDropsWhatItDeclared(tmp_path: Path) -> None:
    document = addFormulas(openShapes())
    document.save(tmp_path / "first.numbers")
    for reference in ("B1", "C1", "A2", "A3"):
        document.sheet("Sheet 1").table("Calc").cell(reference).formula = None
    document.save(tmp_path / "second.numbers")

    owner, _ = readOwnerTiles(tmp_path / "second.numbers", "Sheet 1", "Calc")

    assert list(owner.range_dependencies.back_dependency) == []
    assert list(owner.spanning_column_dependencies.coord_refers_to_spans) == []


# ── AC 3: a reference into another table ────────────────────────────────────


@pytest.mark.parametrize(
    ("reference", "table"), [("C1", "Table 2"), ("A2", "Inputs")]
)
def testAReferenceIntoAnotherTableNamesThatTablesIdentity(
    tmp_path: Path, reference: str, table: str
) -> None:
    reopened = pybers.open(saveWithFormulas(tmp_path))
    formula = reopened.sheet("Sheet 1").table("Calc").cell(reference).formula
    assert formula is not None

    identities = {
        node.content.tableId
        for node in formula.nodes
        if isinstance(node.content, FormulaReference)
    }

    assert identities == {reopened.sheet("Sheet 1").table(table).identifier}


# ── Lifecycle ───────────────────────────────────────────────────────────────


def testASecondSaveAddsToTheTileRatherThanCreatingAnother(tmp_path: Path) -> None:
    document = addFormulas(openShapes())
    document.save(tmp_path / "first.numbers")
    document.sheet("Sheet 1").table("Calc").cell("C3").formulaText = "=B1+1"
    document.save(tmp_path / "second.numbers")

    _, tiles = readOwnerTiles(tmp_path / "second.numbers", "Sheet 1", "Calc")

    assert len(tiles) == 1
    assert (2, 2) in readRegisteredPairs(tiles[0].cell_records)


def testRemovingTheFormulaEmptiesBothRegisters(tmp_path: Path) -> None:
    document = addFormulas(openShapes())
    document.save(tmp_path / "first.numbers")
    calc = document.sheet("Sheet 1").table("Calc")
    for ref in ("B1", "C1", "A2", "A3"):
        calc.cell(ref).formula = None
    document.save(tmp_path / "second.numbers")

    owner, tiles = readOwnerTiles(tmp_path / "second.numbers", "Sheet 1", "Calc")

    assert readRegisteredPairs(owner.cell_dependencies.cell_record) == set()
    assert readRegisteredPairs(tiles[0].cell_records) == set()


# ── AC 4: everything already there is untouched ────────────────────────────


def testExistingTablesAndTheirFormulasReadBackUnchanged(tmp_path: Path) -> None:
    original = openShapes()
    reopened = pybers.open(saveWithFormulas(tmp_path))

    for sheet in original.sheets:
        for table in sheet.tables:
            assert reopened.sheet(sheet.name).table(table.name) == table


def testMergesElsewhereReadBackUnchanged(tmp_path: Path) -> None:
    source = findDocumentPath("22-merge-2x2")
    document = pybers.open(source)
    added = document.sheet(1).tableAdd("Calc", rows=1, cols=2)
    added.cell("A1").value = Decimal("3")
    added.cell("B1").formulaText = "=A1+1"
    document.save(tmp_path / "merged.numbers")

    before = pybers.open(source).sheet(1).table(1)
    after = pybers.open(tmp_path / "merged.numbers").sheet(1).table(1)
    assert after.mergeRanges == before.mergeRanges
    assert after == before


def testOnlyTheArchivesThatRegisterAreRewritten(tmp_path: Path) -> None:
    source = readPackage(findDocumentPath("20-formula-shapes"))
    written = readPackage(saveWithFormulas(tmp_path))
    registering = {
        "Index/Metadata.iwa",
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


# ── AC 5: saving again with no edit ─────────────────────────────────────────


def testSavingAgainWithNoEditWritesEveryArchiveUnchanged(tmp_path: Path) -> None:
    first = saveWithFormulas(tmp_path)
    pybers.open(first).save(tmp_path / "again.numbers")

    again = readPackage(tmp_path / "again.numbers")
    assert readArchiveBodies(again) == readArchiveBodies(readPackage(first))


# ── Refusals ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("references", [["AN1"], ["B1", "AN1"]])
def testAFormulaPastTheFirstTileIsRefusedAndWritesNothing(
    tmp_path: Path, references: list[str]
) -> None:
    """Only the tile at column 0 was measured, so no tile is guessed beyond it."""
    document = openShapes()
    package = document._package
    assert package is not None
    before = readArchiveBodies(package)
    added = document.sheet(1).tableAdd("Wide", rows=1, cols=40)
    added.cell("A1").value = Decimal("1")
    for reference in references:
        added.cell(reference).formulaText = "=A1*2"

    with pytest.raises(WriteError, match="No dependency tile covers"):
        document.save(tmp_path / "refused.numbers")

    assert readArchiveBodies(package) == before
    assert added._identifier is None
    assert not (tmp_path / "refused.numbers").exists()


# ── The golden ──────────────────────────────────────────────────────────────


def testTheReplacedGoldenDeclaresTheCellItReadsNow() -> None:
    """Guard the guard: the golden's swapped formula, and what it says it reads."""
    golden = goldenDirectory / "20-formula-precedent-replaced.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    table = pybers.open(golden).sheet("Sheet 1").table("Table 2")
    owner, _ = readOwnerTiles(golden, "Sheet 1", "Table 2")

    assert table.cell("B1").formulaText == "=A2*3"
    edges = {
        (record.row, record.column): (
            list(record.expanded_edges.edge_without_owner_rows),
            list(record.expanded_edges.edge_without_owner_columns),
        )
        for record in owner.cell_dependencies.cell_record
    }
    assert edges[(0, 1)] == ([1], [0])


def testTheGoldenHoldsTheFormulasItClaims() -> None:
    """Guard the guard: the golden's created formulas, read back."""
    golden = goldenDirectory / "20-formulas-in-created-tables.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    calc = pybers.open(golden).sheet("Sheet 1").table("Calc")

    assert calc.cell("B1").formulaText == "=A1*3"
    assert calc.cell("A2").formulaText == "=Inputs::A1+1"


def testTheGoldenIsWhatWritingTheFormulasWritesToday(tmp_path: Path) -> None:
    """The created tile and both registers match the golden's."""

    def readRegisterShape(
        path: Path,
    ) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
        owner, tiles = readOwnerTiles(path, "Sheet 1", "Calc")
        return (
            readRegisteredPairs(owner.cell_dependencies.cell_record),
            {cell for tile in tiles for cell in readRegisteredPairs(tile.cell_records)},
        )

    assert readRegisterShape(saveWithFormulas(tmp_path)) == readRegisterShape(
        goldenDirectory / "20-formulas-in-created-tables.numbers"
    )


# ── The two consumers ───────────────────────────────────────────────────────


def testAScriptBuildsATableAndItsTotalInOnePass(tmp_path: Path) -> None:
    """The `import pybers` consumer: a table, a loop over values, a total, a save."""
    document = openShapes()
    table = document.sheetAdd("Budget").tableAdd("Costs", rows=4, cols=2)
    for row, (label, amount) in enumerate(
        [("rent", "1200"), ("food", "450"), ("power", "80")], start=1
    ):
        table.cell(row=row, col=1).value = label
        table.cell(row=row, col=2).value = Decimal(amount)
    table.cell("A4").value = "total"
    table.cell("B4").formulaText = "=SUM(B1:B3)"
    document.save(tmp_path / "budget.numbers")

    reopened = pybers.open(tmp_path / "budget.numbers").sheet("Budget").table("Costs")
    assert reopened.cell("B4").formulaText == "=SUM(B1:B3)"


def testACliWritesAFormulaIntoANewTableAndPrintsIt(tmp_path: Path) -> None:
    """The `pybers cell formula SHEET TABLE REF TEXT` consumer, after `table add`."""
    document = openShapes()
    table = document.sheet("Sheet 2").tableAdd("Scratch", rows=2, cols=2)
    arguments = ["Sheet 2", "Scratch", "B2", "=Sheet 2::Table 1::A1*2"]
    cell = document.sheet(arguments[0]).table(arguments[1]).cell(arguments[2])
    cell.formulaText = arguments[3]
    document.save(tmp_path / "cli.numbers")

    printed = f"{table.name}::{arguments[2]} {cell.formulaText}"
    assert printed == "Scratch::B2 =Sheet 2::Table 1::A1*2"
    reopened = pybers.open(tmp_path / "cli.numbers").sheet("Sheet 2").table("Scratch")
    assert reopened.cell("B2").formulaText == "=Sheet 2::Table 1::A1*2"
