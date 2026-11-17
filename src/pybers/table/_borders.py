#!/usr/bin/env python3
"""\
A table's borders read from its stroke sidecar, and the sidecar written from them.

Each row and column owns one layer, holding runs along the other axis. A save
rewrites the layers only when the strokes they hold, side by side, differ from the
table's, so a table no edit touched keeps its archives byte for byte. A rewrite
joins neighbors drawing the same stroke at the same order into one run, as Numbers
writes a table it draws, where a deletion it made would have split one.

Private. Part of the table feature's archive half.

UPDATES
2026-11-17  Written for PYB-266, replacing `_strokes`, which mapped the archive at
            save time.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/17"

from collections.abc import Sequence

from google.protobuf.internal.containers import RepeatedCompositeFieldContainer

from pybers._generated import TSDArchives_pb2 as tsd
from pybers._generated import TSPMessages_pb2 as tsp
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence.index import ArchiveIndex
from pybers._persistence.metadata import PackageRegistry, composeArchive
from pybers.style._read import readStroke
from pybers.style._write import composeStroke
from pybers.table.borders import (
    BorderEdge,
    CellBorderSide,
    TableBorders,
    borderOrderInitial,
)
from pybers.table.cells import Table

# One stroke as a layer stores it: the run's stroke bytes and its order.
type StoredEdge = tuple[bytes, int]
# A layer list's strokes, keyed by (line, position along it), both from zero.
type StoredEdges = dict[tuple[int, int], StoredEdge]

sideLists: tuple[tuple[CellBorderSide, str], ...] = (
    (CellBorderSide.LEFT, "left_column_stroke_layers"),
    (CellBorderSide.RIGHT, "right_column_stroke_layers"),
    (CellBorderSide.TOP, "top_row_stroke_layers"),
    (CellBorderSide.BOTTOM, "bottom_row_stroke_layers"),
)


def listLayerReferences(
    sidecar: tst.StrokeSidecarArchive, name: str
) -> RepeatedCompositeFieldContainer[tsp.Reference]:
    """Return one of the sidecar's four layer lists."""
    references: RepeatedCompositeFieldContainer[tsp.Reference] = getattr(sidecar, name)
    return references


def readStoredEdges(
    index: ArchiveIndex, references: Sequence[tsp.Reference]
) -> StoredEdges:
    """Return every stroke one layer list holds, one per cell side."""
    edges: StoredEdges = {}
    for reference in references:
        layer = index.resolve(reference, tst.StrokeLayerArchive)
        for run in layer.stroke_runs:
            stored = run.stroke.SerializeToString(deterministic=True)
            for position in range(run.origin, run.origin + run.length):
                edges[(layer.row_column_index, position)] = (stored, run.order)
    return edges


def readTableBorders(
    index: ArchiveIndex, model: tst.TableModelArchive,
    rowIdentities: Sequence[int], columnIdentities: Sequence[int],
) -> TableBorders:
    """Return every stroke a table stores on a side of a cell, keyed by identity."""
    if not model.HasField("stroke_sidecar"):
        return TableBorders()
    sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
    borders = TableBorders(maxOrder=sidecar.max_order)
    for side, name in sideLists:
        byRow = side in (CellBorderSide.TOP, CellBorderSide.BOTTOM)
        for (line, position), (stored, order) in readStoredEdges(
            index, listLayerReferences(sidecar, name)
        ).items():
            row, column = (line, position) if byRow else (position, line)
            if row >= len(rowIdentities) or column >= len(columnIdentities):
                continue
            borders.edges[(rowIdentities[row], columnIdentities[column], side)] = (
                BorderEdge(
                    readStroke(tsd.StrokeArchive.FromString(stored)), order, stored
                )
            )
    return borders


def composeWantedEdges(table: Table) -> dict[str, StoredEdges]:
    """Return what each layer list should hold, by line and position from zero."""
    rows = {identity: at for at, identity in enumerate(table._rowIdentities)}
    columns = {identity: at for at, identity in enumerate(table._columnIdentities)}
    wanted: dict[str, StoredEdges] = {name: {} for _, name in sideLists}
    names = dict(sideLists)
    for (rowIdentity, columnIdentity, side), edge in table._borders.edges.items():
        row, column = rows.get(rowIdentity), columns.get(columnIdentity)
        if row is None or column is None:
            continue
        byRow = side in (CellBorderSide.TOP, CellBorderSide.BOTTOM)
        stored = edge.stored if edge.stored is not None else composeStroke(
            edge.stroke
        ).SerializeToString(deterministic=True)
        key = (row, column) if byRow else (column, row)
        wanted[names[side]][key] = (stored, edge.order)
    return wanted


def buildLayerRuns(
    edges: StoredEdges, line: int
) -> list[tst.StrokeLayerArchive.StrokeRunArchive]:
    """Return one line's strokes as runs, joining neighbors drawing the same one."""
    runs: list[tuple[int, int, StoredEdge]] = []
    for position in sorted(held for owner, held in edges if owner == line):
        edge = edges[(line, position)]
        if runs and runs[-1][0] + runs[-1][1] == position and runs[-1][2] == edge:
            origin, length, _ = runs[-1]
            runs[-1] = (origin, length + 1, edge)
            continue
        runs.append((position, 1, edge))
    return [
        tst.StrokeLayerArchive.StrokeRunArchive(
            origin=origin, length=length, order=order,
            stroke=tsd.StrokeArchive.FromString(stored),
        )
        for origin, length, (stored, order) in runs
    ]


def createStrokeSidecar(
    index: ArchiveIndex, registry: PackageRegistry, modelId: int,
    model: tst.TableModelArchive,
) -> None:
    """Give a created table the empty sidecar Numbers gives it on its first save.

    Measured in `99b-created-document-saved-unedited`: no layers, the order at 2,
    in the model's own member.
    """
    sidecar = tst.StrokeSidecarArchive(max_order=borderOrderInitial)
    identifier = registry.identifierAllocate()
    registry.archiveAdd(
        registry.componentRequire(modelId), composeArchive(identifier, sidecar),
        sidecar,
    )
    model.stroke_sidecar.identifier = identifier
    index.archiveWrite(modelId, model, registry.referencesReconcile(modelId, model))


def writeTableBorders(
    index: ArchiveIndex, registry: PackageRegistry, modelId: int,
    model: tst.TableModelArchive, table: Table,
) -> None:
    """Rewrite a table's sidecar from its borders, when what it holds differs.

    A created table has no sidecar until Numbers saves it, and gains one here only
    once it holds a border.
    """
    if not model.HasField("stroke_sidecar"):
        if not table._borders.edges:
            return
        createStrokeSidecar(index, registry, modelId, model)
    sidecarId = model.stroke_sidecar.identifier
    sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
    wanted = composeWantedEdges(table)
    sized = (sidecar.row_count, sidecar.column_count) == (
        table.rowCount, table.colCount
    )
    if sized and sidecar.max_order == table._borders.maxOrder and all(
        readStoredEdges(index, listLayerReferences(sidecar, name)) == wanted[name]
        for _, name in sideLists
    ):
        return
    componentId = registry.componentRequire(sidecarId)
    spent: list[int] = []
    for _, name in sideLists:
        references = listLayerReferences(sidecar, name)
        # Reused in line order, so a layer an edit only moved keeps its archive.
        held = [
            reference.identifier for reference in sorted(
                references,
                key=lambda each: index.resolve(
                    each, tst.StrokeLayerArchive
                ).row_column_index,
            )
        ]
        lines = sorted({line for line, _ in wanted[name]})
        placed: list[int] = []
        for at, line in enumerate(lines):
            layer = tst.StrokeLayerArchive(
                row_column_index=line, stroke_runs=buildLayerRuns(wanted[name], line)
            )
            if at < len(held):
                identifier = held[at]
                index.archiveWrite(identifier, layer)
            else:
                identifier = registry.identifierAllocate()
                registry.archiveAdd(
                    componentId, composeArchive(identifier, layer), layer
                )
            placed.append(identifier)
        spent.extend(held[len(lines):])
        del references[:]
        references.extend(tsp.Reference(identifier=each) for each in placed)
    sidecar.row_count = table.rowCount
    sidecar.column_count = table.colCount
    sidecar.max_order = table._borders.maxOrder
    index.archiveWrite(
        sidecarId, sidecar,
        [
            reference.identifier for _, name in sideLists
            for reference in listLayerReferences(sidecar, name)
        ],
    )
    for identifier in spent:
        registry.archiveRemove(identifier)


__all__ = ["readTableBorders", "writeTableBorders"]
