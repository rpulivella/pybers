#!/usr/bin/env python3
"""\
The engine's register of the rectangles and whole lines each formula reads.

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

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSPArchiveMessages_pb2 as tspArchive
from .._persistence import PackageRegistry, createArchive
from .._persistence.index import ArchiveIndex
from .._persistence.types import findArchiveTypeId
from .dependencies import FormulaDependencies, RangeEdge
from .owners import TableOwner

# The version of the tile mirroring the range half of the register, as
# `20-formula-shapes` holds it.
rangePrecedentsTileVersion: tuple[int, ...] = (1, 0, 5)


# A rectangle's size counts from one, and Numbers omits an axis of one line.
singleLine: int = 1


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
                type=findArchiveTypeId(tsce.RangePrecedentsTileArchive), length=0
            )
            message.version.extend(rangePrecedentsTileVersion)
            registry.archiveAdd(
                componentId, createArchive(info, [tile.SerializeToString()]), tile
            )
            continue
        index.archiveWrite(identifier, tile)
    return sorted(created)


__all__ = [
    "rewriteRangeDependencies",
]
