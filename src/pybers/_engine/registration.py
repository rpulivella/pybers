#!/usr/bin/env python3
"""\
Formula registration: which cells hold a formula, told to the engine twice.

**The register of which cells hold a formula is stored TWICE**, and a cell missing
from either is never evaluated. Updating only the first shows the formula in the
formula bar beside the cell's old value, which is the most misleading state
available, because the cell looks correct to anyone who clicks it. Measured for
PYB-42, and recorded in findings-02-formulas.md.

UPDATES
2026-11-02  A cell is registered in the tile its 128-row by 32-column block names,
            created when missing, for PYB-276.
2026-11-02  A created tile is composed from its body, for PYB-276.
2026-09-22  Split out of the engine module for PYB-113, the tile's type identifier
            asked of the registry.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/22"

from collections.abc import Mapping

from google.protobuf.internal.containers import RepeatedCompositeFieldContainer

from .._generated import TSCEArchives_pb2 as tsce
from .._persistence import PackageRegistry, composeArchive
from .._persistence.index import ArchiveIndex
from .dependencies import FormulaDependencies
from .owners import TableOwner
from .ranges import rewriteRangeDependencies

# The calculation engine tiles its register of formula-bearing cells in blocks of
# 128 rows by 32 columns. Measured 2026-11-02: Numbers registered formulas it was
# typed at rows 129, 200 and 260 and column 38 in tiles beginning at rows 128 and 256
# and column 32, and ignored one pybers registered at row 129 in the tile at row 0.
dependencyTileRows: int = 128
dependencyTileColumns: int = 32


# The generated container both copies of that register are held in. Named so the
# one function updating either can say what it takes.
type CellRecordList = RepeatedCompositeFieldContainer[
    tsce.CellRecordExpandedArchive
]


def rewriteCellRecords(
    records: CellRecordList,
    added: Mapping[tuple[int, int], FormulaDependencies],
    removed: list[tuple[int, int]],
) -> None:
    """Add and drop entries in one register of formula-bearing cells.

    A cell already registered is rewritten rather than left, since its formula may
    now read something else.
    """
    dropping = set(removed) | set(added)
    kept = [
        record for record in records
        if (record.row, record.column) not in dropping
    ]
    del records[:]
    for record in kept:
        records.add().CopyFrom(record)
    for (row, column), dependencies in added.items():
        fresh = records.add()
        fresh.column = column
        fresh.row = row
        edges = fresh.expanded_edges
        edges.SetInParent()
        for cell in dependencies.cells:
            if cell.owner is None:
                edges.edge_without_owner_rows.append(cell.row)
                edges.edge_without_owner_columns.append(cell.column)
                continue
            edges.edge_with_owner_rows.append(cell.row)
            edges.edge_with_owner_columns.append(cell.column)
            edges.internal_owner_id_for_edge.append(cell.owner)


def findTileOrigin(row: int, column: int) -> tuple[int, int]:
    """Return the first row and column of the dependency tile a cell belongs in."""
    return row - row % dependencyTileRows, column - column % dependencyTileColumns


def checkTileCovers(tile: tsce.CellRecordTileArchive, row: int, column: int) -> bool:
    """Return whether a dependency tile's block holds a cell."""
    return findTileOrigin(row, column) == (tile.tile_row_begin, tile.tile_column_begin)


def registerFormulaCells(
    index: ArchiveIndex,
    registry: PackageRegistry,
    owner: TableOwner,
    added: Mapping[tuple[int, int], FormulaDependencies],
    removed: list[tuple[int, int]],
) -> None:
    """Tell the calculation engine which cells hold formulas now, and what they read.

    **Not optional, and its absence fails silently.** Setting the record flag and
    pooling the archive leaves a formula that is never evaluated, and the register is
    stored TWICE so both copies have to agree. Updating only `cell_dependencies`
    shows the formula in Numbers' formula bar while the cell keeps its old value.
    See findings-02-formulas.md, which records all three attempts.

    A cell whose block has no tile gains one, as Numbers creates it, measured in
    findings-02-formulas.md. Coordinates count from zero here.
    """
    if not added and not removed:
        return
    references = owner.dependencies.tiled_cell_dependencies.cell_record_tiles
    tiles = {
        reference.identifier: index.resolve(reference, tsce.CellRecordTileArchive)
        for reference in references
    }
    stored = {(tile.tile_row_begin, tile.tile_column_begin) for tile in tiles.values()}
    componentId = registry.componentRequire(owner.identifier)
    created: list[int] = []
    for origin in sorted({findTileOrigin(*cell) for cell in added} - stored):
        identifier = registry.identifierAllocate()
        tiles[identifier] = tsce.CellRecordTileArchive(
            internal_owner_id=owner.dependencies.internal_formula_owner_id,
            tile_row_begin=origin[0],
            tile_column_begin=origin[1],
        )
        created.append(identifier)
    if created:
        # Numbers lists an owner's tiles by row, then column, measured 2026-11-02.
        ordered = sorted(
            tiles,
            key=lambda key: (tiles[key].tile_row_begin, tiles[key].tile_column_begin),
        )
        del references[:]
        for identifier in ordered:
            references.add(identifier=identifier)
    gained = list(created)

    rewriteCellRecords(owner.dependencies.cell_dependencies.cell_record,
                       added, removed)
    gained.extend(rewriteRangeDependencies(index, registry, owner, added, removed))
    ownerReferences: list[int] | None = None
    if gained:
        ownerReferences = registry.strongReferencesOf(owner.identifier)
        ownerReferences.extend(gained)
    for identifier, tile in tiles.items():
        inTile = {
            cell: dependencies for cell, dependencies in added.items()
            if checkTileCovers(tile, *cell)
        }
        outTile = [cell for cell in removed if checkTileCovers(tile, *cell)]
        if identifier not in created and not inTile and not outTile:
            continue
        rewriteCellRecords(tile.cell_records, inTile, outTile)
        if identifier in created:
            registry.archiveAdd(componentId, composeArchive(identifier, tile), tile)
            continue
        index.archiveWrite(identifier, tile)
    index.archiveWrite(owner.identifier, owner.dependencies, ownerReferences)


def listRegisteredCells(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
) -> list[tuple[int, int]]:
    """Return every cell the engine registers a formula at, as stored."""
    return [
        (record.row, record.column)
        for record in dependencies.cell_dependencies.cell_record
    ]


__all__ = [
    "listRegisteredCells",
    "registerFormulaCells",
]
