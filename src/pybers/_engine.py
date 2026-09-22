#!/usr/bin/env python3
"""\
The calculation engine: what it knows that a table does not, and what it is told.

A table records neither its internal owner id nor the identity a formula in another
table names it by. Both live on the engine's dependency entry for it, so finding
either means walking the tracker rather than reading the table, and reading the
table the obvious way finds nothing at all.

Writing back, there are three registers and none of them is optional. Each one is
silent when it is wrong, which is why they live together rather than beside
whichever feature trips over one first.

**The register of which cells hold a formula is stored TWICE**, and a cell missing
from either is never evaluated. Updating only the first shows the formula in the
formula bar beside the cell's old value, which is the most misleading state
available, because the cell looks correct to anyone who clicks it. Measured for
PYB-42, and recorded in findings-02-formulas.md.

**Numbers does not recalculate on open**, so an edited cell has to be named in
`refs_to_dirty` or its dependents keep showing what they last computed. Naming only
the cells that changed is enough: Numbers walks its own dependency graph from
there, across tables and across sheets.

Private, and named so. Nothing here belongs to the surface `import pybers` offers,
and nothing here knows a model type: the one thing that did was the merge formula,
which went to the feature that owns merges.

UPDATES
2026-09-22  Every archive it writes is written through the save's index, and the
            table owner kind lives here, for PYB-109.
2026-09-21  The engine's cell-keyed records follow a structural edit, for PYB-17.
2026-09-16  A formula declares the cells, rectangles and whole lines it reads, in
            three registers kept twice each, for PYB-86.
2026-09-15  An owner with no dependency tile gains its first, for PYB-86.
2026-09-08  The two halves joined for #58, and the merge formula left for the
            feature that owns it, which took the last model type out.
2026-09-08  Split out of the reader and the writer for #45, unchanged.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from google.protobuf.internal.containers import RepeatedCompositeFieldContainer

from ._generated import TSCEArchives_pb2 as tsce
from ._generated import TSPArchiveMessages_pb2 as tspArchive
from ._generated import TSPMessages_pb2 as tsp
from ._persistence import PackageRegistry, createArchive
from ._persistence.index import ArchiveIndex, wordBits, wordMask
from ._persistence.types import calculationEngineTypeId, readArchiveTypeId
from .errors import ReadError, WriteError

# The `owner_kind` a table's dependency entry carries, as against the other owners
# the calculation engine tracks.
tableOwnerKind: int = 1


def findCalculationEngine(index: ArchiveIndex) -> tsce.CalculationEngineArchive:
    """Return the document's one calculation engine, or refuse and say why.

    Exactly one archive in a document carries this type, the same way exactly one
    carries `TN.DocumentArchive`. All 46 documents have one, so a document without
    one is not what this library expects rather than a case to work around.
    """
    found = [
        archive for archive in index.byIdentifier.values()
        if readArchiveTypeId(archive) == calculationEngineTypeId
    ]
    if len(found) != 1:
        raise ReadError(
            f"Expected exactly one TSCE.CalculationEngineArchive, found {len(found)}. "
            "Without it a table has no identity, and neither a merge nor a "
            "recalculation request can be written."
        )
    return index.identifierResolve(
        found[0].identifier, tsce.CalculationEngineArchive
    )


@dataclass(frozen=True, slots=True)
class TableOwner:
    """One table's calculation-engine entry, and the archive holding it.

    The identifier travels with the message because registering a formula cell
    changes that archive and it has to be written back. Looking it up a second
    time would mean walking the dependency tracker again to find what this walk
    already had in hand.
    """

    identifier: int
    dependencies: tsce.FormulaOwnerDependenciesArchive


def readTableOwnerEntries(
    index: ArchiveIndex, engine: tsce.CalculationEngineArchive
) -> dict[int, TableOwner]:
    """Return each table's dependency entry, keyed by its `TST.TableInfoArchive`.

    Read the long way round because there is no short one: a table records neither
    its internal owner id nor its owner uid. Both live here, on the entry whose
    `owner_kind` is 1 and whose `formula_owner` points back at the table. Measured
    2026-09-02, see findings-02-formulas.md and findings-03-structure.md.
    """
    entries: dict[int, TableOwner] = {}
    for reference in engine.dependency_tracker.formula_owner_dependencies:
        dependencies = index.resolve(reference, tsce.FormulaOwnerDependenciesArchive)
        if dependencies.owner_kind != tableOwnerKind:
            continue
        if not dependencies.HasField("formula_owner"):
            continue
        entries[dependencies.formula_owner.identifier] = TableOwner(
            identifier=reference.identifier, dependencies=dependencies
        )
    return entries


def readOwnerUuid(uid: tsp.UUID) -> str:
    """Return a table's owner uid as the hexadecimal a formula names it by.

    A formula spells the identity as four 32-bit words and the owner entry spells
    it as two 64-bit halves, low half first. The two are the same value, matched
    across `20-formula-shapes` on 2026-09-08, and this is the only conversion
    between them on the read path.
    """
    words = (
        uid.lower & wordMask,
        uid.lower >> wordBits,
        uid.upper & wordMask,
        uid.upper >> wordBits,
    )
    return "".join(f"{word:08x}" for word in words)


def readTableIdentities(index: ArchiveIndex) -> dict[int, str]:
    """Return each table's formula identity, keyed by its `TST.TableInfoArchive`."""
    return {
        identifier: readOwnerUuid(owner.dependencies.formula_owner_uid)
        for identifier, owner in readTableOwnerEntries(
            index, findCalculationEngine(index)
        ).items()
    }


__all__ = [
    "TableOwner",
    "findCalculationEngine",
    "readTableIdentities",
    "readTableOwnerEntries",
]


# A merge is written as `SUM($A$1:$B$1)`, so it carries SUM's index in Apple's own
# function table. The number is theirs and is not derivable from the schemas.
sumFunctionIndex: int = 168

# The calculation engine tiles its register of formula-bearing cells 32 columns
# wide. Measured 2026-09-04: `40-table-bands` carries eight tiles beginning at
# columns 0, 32, 64 and so on to 224, and every tile in the documents begins at row
# zero, so the row extent of a tile is not established and is never assumed here.
dependencyTileColumns: int = 32

# The type and version of the tile Numbers created in `55-table-inserted-formula`.
cellRecordTileTypeId: int = 4009
cellRecordTileVersion: tuple[int, ...] = (1, 0, 5)

# The tile mirroring the range half of the register, as `20-formula-shapes` holds it.
rangePrecedentsTileTypeId: int = 4010
rangePrecedentsTileVersion: tuple[int, ...] = (1, 0, 5)

# A rectangle's size counts from one, and Numbers omits an axis of one line.
singleLine: int = 1


@dataclass(frozen=True, slots=True)
class CellEdge:
    """One cell a formula reads, its owner named only when it is another table."""

    row: int
    column: int
    owner: int | None = None


@dataclass(frozen=True, slots=True)
class RangeEdge:
    """One bounded rectangle a formula reads, in the owner that holds it."""

    top: int
    left: int
    bottom: int
    right: int
    owner: int


@dataclass(frozen=True, slots=True)
class SpanEdge:
    """Whole columns or whole rows a formula reads, in the owner that holds them."""

    begin: int
    end: int
    columns: bool
    owner: int


@dataclass(frozen=True, slots=True)
class FormulaDependencies:
    """Everything one formula reads, which is what makes it recompute again.

    Numbers evaluates an undeclared formula once, on open, in an order of its own,
    so a formula reading a cell computed after it caches that cell's stale state.
    See findings-02-formulas.md.
    """

    cells: tuple[CellEdge, ...] = ()
    ranges: tuple[RangeEdge, ...] = ()
    spans: tuple[SpanEdge, ...] = ()

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


def rewriteRangeDependencies(
    index: ArchiveIndex,
    registry: PackageRegistry,
    owner: TableOwner,
    added: Mapping[tuple[int, int], FormulaDependencies],
    removed: list[tuple[int, int]],
) -> list[int]:
    """Record the rectangles and whole columns the formulas read, and drop the rest.

    A range is kept twice, as `20-formula-shapes` keeps it: once on the owner as a
    back dependency, and once in a tile per owner the ranges belong to. Whole
    columns and whole rows are a third register, since they grow with the table.
    """
    dependencies = owner.dependencies
    dropping = set(removed) | set(added)
    backDependencies = [
        entry for entry in dependencies.range_dependencies.back_dependency
        if (entry.cell_coord_row, entry.cell_coord_column) not in dropping
    ]
    del dependencies.range_dependencies.back_dependency[:]
    for entry in backDependencies:
        dependencies.range_dependencies.back_dependency.add().CopyFrom(entry)
    for (row, column), formula in added.items():
        for extent in formula.ranges:
            fresh = dependencies.range_dependencies.back_dependency.add(
                cell_coord_row=row, cell_coord_column=column
            )
            fresh.internal_range_reference.owner_id = extent.owner
            assignRange(fresh.internal_range_reference.range, extent)

    for spanning, columns in (
        (dependencies.spanning_column_dependencies, True),
        (dependencies.spanning_row_dependencies, False),
    ):
        keptSpans = [
            entry for entry in spanning.coord_refers_to_spans
            if (entry.coordinate.row, entry.coordinate.column) not in dropping
        ]
        del spanning.coord_refers_to_spans[:]
        for keptSpan in keptSpans:
            spanning.coord_refers_to_spans.add().CopyFrom(keptSpan)
        for (row, column), formula in added.items():
            spans = [span for span in formula.spans if span.columns is columns]
            if not spans:
                continue
            refers = spanning.coord_refers_to_spans.add()
            refers.coordinate.row = row
            refers.coordinate.column = column
            for span in spans:
                context = refers.ranges_by_table_context.add(
                    owner_id=span.owner,
                    range_context=tsce.SpanningDependenciesExpandedArchive.DEFAULT,
                )
                lines = context.ranges.add(extent_begin=span.begin)
                if span.end != span.begin:
                    lines.extent_end = span.end

    return rewriteRangeTiles(index, registry, owner, added, removed)


def assignRange(target: tsce.RangeCoordinateArchive, extent: RangeEdge) -> None:
    """Set a range coordinate from a rectangle the engine was given."""
    target.top_left_row = extent.top
    target.top_left_column = extent.left
    target.bottom_right_row = extent.bottom
    target.bottom_right_column = extent.right


def rewriteRangeTiles(
    index: ArchiveIndex,
    registry: PackageRegistry,
    owner: TableOwner,
    added: Mapping[tuple[int, int], FormulaDependencies],
    removed: list[tuple[int, int]],
) -> list[int]:
    """Keep the tiled copy of the range register in step, one tile per owner read.

    Returns the tiles created, which the owner has to declare as its own.
    """
    references = owner.dependencies.tiled_range_dependencies.range_precedents_tile
    tiles = {
        reference.identifier: index.resolve(
            reference, tsce.RangePrecedentsTileArchive
        )
        for reference in references
    }
    byOwner = {tile.to_owner_id: identifier for identifier, tile in tiles.items()}
    wanted = {
        extent.owner for formula in added.values() for extent in formula.ranges
    }
    created: set[int] = set()
    for target in sorted(wanted - set(byOwner)):
        identifier = registry.identifierAllocate()
        tiles[identifier] = tsce.RangePrecedentsTileArchive(to_owner_id=target)
        byOwner[target] = identifier
        references.add(identifier=identifier)
        created.add(identifier)

    dropping = set(removed) | set(added)
    componentId = registry.componentRequire(owner.identifier)
    for identifier, tile in tiles.items():
        kept = [
            entry for entry in tile.from_to_range
            if (entry.from_coord.row, entry.from_coord.column) not in dropping
        ]
        fresh = [
            (cell, extent)
            for cell, formula in added.items()
            for extent in formula.ranges
            if byOwner.get(extent.owner) == identifier
        ]
        untouched = len(kept) == len(tile.from_to_range) and not fresh
        if identifier not in created and untouched:
            continue
        del tile.from_to_range[:]
        for entry in kept:
            tile.from_to_range.add().CopyFrom(entry)
        for (row, column), extent in fresh:
            entry = tile.from_to_range.add()
            entry.from_coord.row = row
            entry.from_coord.column = column
            entry.refers_to_rect.origin.row = extent.top
            entry.refers_to_rect.origin.column = extent.left
            entry.refers_to_rect.size.SetInParent()
            if extent.bottom - extent.top + 1 != singleLine:
                entry.refers_to_rect.size.num_rows = extent.bottom - extent.top + 1
            if extent.right - extent.left + 1 != singleLine:
                entry.refers_to_rect.size.num_columns = extent.right - extent.left + 1
        if identifier in created:
            info = tspArchive.ArchiveInfo(identifier=identifier)
            message = info.message_infos.add(
                type=rangePrecedentsTileTypeId, length=0
            )
            message.version.extend(rangePrecedentsTileVersion)
            registry.archiveAdd(
                componentId, createArchive(info, [tile.SerializeToString()]), tile
            )
            continue
        index.archiveWrite(identifier, tile)
    return sorted(created)


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
            "Creating a tile beyond column 0 has never been measured."
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
            message = info.message_infos.add(type=cellRecordTileTypeId, length=0)
            message.version.extend(cellRecordTileVersion)
            registry.archiveAdd(
                componentId, createArchive(info, [tile.SerializeToString()]), tile
            )
            continue
        index.archiveWrite(identifier, tile)
    index.archiveWrite(owner.identifier, owner.dependencies, ownerReferences)


class LineMapping(Protocol):
    """Where each stored row, or each stored column, of a table lands after an edit.

    Named here as a shape rather than imported, so the engine knows no table type.
    """

    @property
    def growth(self) -> int:
        """Return how many lines the edit added, less how many it removed."""
        ...

    def lineMap(self, line: int) -> int | None:
        """Return where one stored line lands, or None when the edit removed it."""
        ...

    def spanCut(self, begin: int, end: int) -> bool:
        """Report whether the edit removes a line of a span or adds one inside it."""
        ...


def refuseUnmovableEngineState(
    dependencies: tsce.FormulaOwnerDependenciesArchive, name: str
) -> None:
    """Refuse engine state keyed by cell that a structural edit does not move."""
    if dependencies.whole_owner_dependencies.dependent_cells.ByteSize():
        raise WriteError(
            f"{name!r} holds a formula the engine records as reading the whole "
            "table, and moving that record is not measured."
        )


def remapCoordinateSet(
    coordinates: tsce.CellCoordSetArchive, rows: LineMapping, columns: LineMapping
) -> None:
    """Move every cell a set names, dropping those whose line is gone.

    The set is columns, each holding row ranges, which is how `NOW()` and `RAND()`
    are recorded in `57-structure-refusals-base`.
    """
    moved: dict[int, set[int]] = {}
    for entry in coordinates.column_entries:
        column = columns.lineMap(entry.column)
        if column is None:
            continue
        for extent in entry.row_set.entries:
            begin = extent.range_begin
            last = extent.range_end if extent.HasField("range_end") else begin
            for stored in range(begin, last + 1):
                row = rows.lineMap(stored)
                if row is not None:
                    moved.setdefault(column, set()).add(row)
    del coordinates.column_entries[:]
    for column in sorted(moved):
        entry = coordinates.column_entries.add()
        entry.column = column
        for row in sorted(moved[column]):
            entry.row_set.entries.add(range_begin=row)


def remapSpills(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
    rows: LineMapping,
    columns: LineMapping,
    name: str,
) -> None:
    """Move each spill with its formula, refusing an edit that lands inside one.

    **Numbers re-flows a spill cut by an edit**, measured 2026-09-21 in
    `57-engine-row-inserted`: a row added inside `SEQUENCE(3)` left the spilled
    cells where they were and moved the row below instead. Following that means
    evaluating the formula. An edit outside a spill moves it whole, as
    `57-engine-column-inserted` moved `C4:D4` to `D4:E4`, which is ordinary movement.
    """
    for spill in dependencies.spill_range_sizes.spills:
        row, column = spill.coordinate.row, spill.coordinate.column
        height = spill.spill_size.num_rows or 1
        width = spill.spill_size.num_columns or 1
        if rows.spanCut(row, row + height - 1) or columns.spanCut(
            column, column + width - 1
        ):
            raise WriteError(
                f"{name!r} has a row or column added or removed inside a formula's "
                "spill, and Numbers re-flows a spill rather than moving it, which "
                "means evaluating the formula."
            )
    # A moved spill is listed first, as Numbers listed it in both measurements
    # where one moved and one stayed.
    moved: list[tsce.CellSpillSizesArchive.SpillForCell] = []
    stayed: list[tsce.CellSpillSizesArchive.SpillForCell] = []
    for spill in dependencies.spill_range_sizes.spills:
        movedRow = rows.lineMap(spill.coordinate.row)
        movedColumn = columns.lineMap(spill.coordinate.column)
        assert movedRow is not None and movedColumn is not None
        copy = tsce.CellSpillSizesArchive.SpillForCell()
        copy.CopyFrom(spill)
        copy.coordinate.row = movedRow
        copy.coordinate.column = movedColumn
        unchanged = (movedRow, movedColumn) == (
            spill.coordinate.row, spill.coordinate.column
        )
        (stayed if unchanged else moved).append(copy)
    del dependencies.spill_range_sizes.spills[:]
    dependencies.spill_range_sizes.spills.extend(moved + stayed)


def remapOwnerCoordinates(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
    rows: LineMapping,
    columns: LineMapping,
    name: str,
) -> None:
    """Move the engine's cell-keyed records that no formula registration rewrites.

    Errors follow their cells, or go with a removed one, and the table's own
    extent follows its size. The errors' text is left for the recalculation every
    moved formula is marked for.
    """
    refuseUnmovableEngineState(dependencies, name)
    volatile = dependencies.volatile_dependencies
    for kind in (
        "volatile_time_cells", "volatile_random_cells", "volatile_locale_cells",
        "volatile_sheet_table_name_cells", "volatile_remote_data_cells",
    ):
        remapCoordinateSet(getattr(volatile, kind), rows, columns)
    remapSpills(dependencies, rows, columns, name)
    for spanning in (
        dependencies.spanning_column_dependencies,
        dependencies.spanning_row_dependencies,
    ):
        for extent in (spanning.total_range_for_table, spanning.body_range_for_table):
            if not extent.ByteSize():
                continue
            extent.bottom_right_row += rows.growth
            extent.bottom_right_column += columns.growth
    errors = dependencies.cell_errors
    for field in ("errors", "enhanced_errors"):
        entries = getattr(errors, field)
        kept = []
        for entry in entries:
            row = rows.lineMap(entry.coordinate.row)
            column = columns.lineMap(entry.coordinate.column)
            if row is None or column is None:
                continue
            entry.coordinate.row = row
            entry.coordinate.column = column
            kept.append(entry)
        copies = [type(entry)() for entry in kept]
        for copy, entry in zip(copies, kept, strict=True):
            copy.CopyFrom(entry)
        del entries[:]
        entries.extend(copies)


def listRegisteredCells(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
) -> list[tuple[int, int]]:
    """Return every cell the engine registers a formula at, as stored."""
    return [
        (record.row, record.column)
        for record in dependencies.cell_dependencies.cell_record
    ]


def buildDirtySet(
    edits: dict[int, list[tuple[int, int]]]
) -> tsce.ReferencesToDirtyArchive:
    """Return the archive naming every cell that moved, grouped as Numbers groups them.

    Owners hold columns, columns hold a set of row ranges. Contiguous rows collapse
    into one range, which is how Numbers writes its own, and a run of one omits
    `range_end` rather than repeating the beginning.
    """
    dirty = tsce.ReferencesToDirtyArchive()
    for ownerId, cells in sorted(edits.items()):
        dirty.to_dirty_owner_ids.entries.add(range_begin=ownerId)
        owner = dirty.to_dirty_cells.owner_entries.add()
        owner.owner_id = ownerId
        byColumn: dict[int, list[int]] = {}
        for row, column in sorted(set(cells)):
            byColumn.setdefault(column, []).append(row)
        for column, rows in sorted(byColumn.items()):
            entry = owner.coord_set.column_entries.add()
            entry.column = column
            runs: list[list[int]] = []
            for row in rows:
                if runs and row == runs[-1][1] + 1:
                    runs[-1][1] = row
                else:
                    runs.append([row, row])
            for begin, end in runs:
                added = entry.row_set.entries.add(range_begin=begin)
                if end != begin:
                    added.range_end = end
    return dirty


def findOwnerEntry(
    entries: dict[int, TableOwner],
    identifier: int,
    name: str,
) -> TableOwner:
    """Return one table's dependency entry, or refuse naming the table."""
    entry = entries.get(identifier)
    if entry is None:
        raise WriteError(
            f"{name!r} has no calculation-engine owner entry, so neither its merges "
            "nor its edited cells can be written. Every table in the documents "
            "has one."
        )
    return entry


def readTableOwnerIds(
    index: ArchiveIndex, engine: tsce.CalculationEngineArchive
) -> dict[int, int]:
    """Return each table's internal owner id, keyed by its own archive."""
    return {
        identifier: owner.dependencies.internal_formula_owner_id
        for identifier, owner in readTableOwnerEntries(index, engine).items()
    }


def requestRecalculation(
    index: ArchiveIndex, written: dict[int, list[tuple[int, int]]]
) -> int:
    """Tell Numbers which cells moved, so it recalculates whatever depends on them.

    **A formula caches its result and opening the document does not refresh it**, so a
    save without this displays arithmetic that disagrees with its own operands, with
    no prompt. Naming the edited cells is enough: Numbers walks its own graph from
    there, transitively and across sheets, which is why this library never evaluates.
    Measured 2026-09-02 both broadly and minimally, in findings-02-formulas.md.
    """
    if not written:
        return 0
    engine = findCalculationEngine(index)
    if not engine.HasField("refs_to_dirty"):
        raise WriteError(
            "The calculation engine carries no refs_to_dirty reference, so the cells "
            "that changed cannot be marked and the saved file would display stale "
            "formula results."
        )

    ownerIds = readTableOwnerIds(index, engine)
    edits: dict[int, list[tuple[int, int]]] = {}
    for tableIdentifier, cells in written.items():
        ownerId = ownerIds.get(tableIdentifier)
        if ownerId is None:
            raise WriteError(
                f"The table in archive {tableIdentifier} has no calculation-engine "
                "owner id, so the cells edited in it cannot be marked for "
                "recalculation and the saved file would display stale results."
            )
        edits.setdefault(ownerId, []).extend(cells)

    index.archiveWrite(engine.refs_to_dirty.identifier, buildDirtySet(edits))
    return sum(len(cells) for cells in edits.values())


__all__ = [
    "LineMapping",
    "buildDirtySet",
    "listRegisteredCells",
    "remapOwnerCoordinates",
    "findOwnerEntry",
    "registerFormulaCells",
    "requestRecalculation",
    "readTableOwnerIds",
]
