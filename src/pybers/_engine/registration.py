#!/usr/bin/env python3
"""\
Formula registration: which cells hold a formula, told to the engine twice.

**The register of which cells hold a formula is stored TWICE**, and a cell missing
from either is never evaluated. Updating only the first shows the formula in the
formula bar beside the cell's old value, which is the most misleading state
available, because the cell looks correct to anyone who clicks it. Measured for
PYB-42, and recorded in findings-02-formulas.md.

UPDATES
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
from .._generated import TSPArchiveMessages_pb2 as tspArchive
from .._persistence import PackageRegistry, createArchive
from .._persistence.index import ArchiveIndex
from .._persistence.types import findArchiveTypeId
from ..errors import WriteError
from .dependencies import FormulaDependencies
from .owners import TableOwner
from .ranges import rewriteRangeDependencies

# The calculation engine tiles its register of formula-bearing cells 32 columns
# wide. Measured 2026-09-04: `40-table-bands` carries eight tiles beginning at
# columns 0, 32, 64 and so on to 224, and every tile in the documents begins at row
# zero, so the row extent of a tile is not established and is never assumed here.
dependencyTileColumns: int = 32


# The version of the tile Numbers created in `55-table-inserted-formula`.
cellRecordTileVersion: tuple[int, ...] = (1, 0, 5)


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


def checkTileCovers(tile: tsce.CellRecordTileArchive, row: int, column: int) -> bool:
    """Return whether a dependency tile's band holds a cell."""
    band = range(tile.tile_column_begin, tile.tile_column_begin + dependencyTileColumns)
    return column in band and row >= tile.tile_row_begin


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

    An owner with no tile gains the one at column 0, which is the only tile creation
    measured, in findings-10-creation.md. Coordinates count from zero here.
    """
    if not added and not removed:
        return
    references = owner.dependencies.tiled_cell_dependencies.cell_record_tiles
    tiles = {
        reference.identifier: index.resolve(reference, tsce.CellRecordTileArchive)
        for reference in references
    }
    firstTile = not tiles and any(
        column < dependencyTileColumns for _, column in added
    )
    uncovered = sorted(
        (row, column) for row, column in added
        if not (firstTile and column < dependencyTileColumns)
        and not any(checkTileCovers(tile, row, column) for tile in tiles.values())
    )
    if uncovered:
        raise WriteError(
            f"No dependency tile covers {uncovered}, so a formula written there would "
            "be registered in one of the engine's two registers and not the other. "
            "Creating a tile beyond column 0 is not supported."
        )

    componentId = registry.componentRequire(owner.identifier)
    createdTile: int | None = None
    gained: list[int] = []
    if firstTile:
        createdTile = registry.identifierAllocate()
        tiles[createdTile] = tsce.CellRecordTileArchive(
            internal_owner_id=owner.dependencies.internal_formula_owner_id,
            tile_column_begin=0,
            tile_row_begin=0,
        )
        references.add(identifier=createdTile)
        gained.append(createdTile)

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
        if identifier != createdTile and not inTile and not outTile:
            continue
        rewriteCellRecords(tile.cell_records, inTile, outTile)
        if identifier == createdTile:
            info = tspArchive.ArchiveInfo(identifier=identifier)
            message = info.message_infos.add(
                type=findArchiveTypeId(tsce.CellRecordTileArchive), length=0
            )
            message.version.extend(cellRecordTileVersion)
            registry.archiveAdd(
                componentId, createArchive(info, [tile.SerializeToString()]), tile
            )
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
