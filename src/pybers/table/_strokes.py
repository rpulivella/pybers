#!/usr/bin/env python3
"""\
A table's borders carried through lines added or removed, or cells moved or copied.

Each row and each column owns one stroke layer, holding runs along the other
axis, so one map moves a layer by its index and the other moves the runs
inside it. Measured 2026-09-21 in the four `57-borders-*` documents.

Private. Part of the table feature's archive half.

UPDATES
2026-09-29  A copied cell takes exactly its source's borders, for PYB-136.
2026-09-29  A line added beside one holding no border gains none, rather than
            raising, found by PYB-118.
2026-09-23  Borders follow cells moved as a block, for PYB-18.
2026-09-22  Archives written through the save's index, for PYB-109.
2026-09-21  Split out of `_structure` for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/21"

from collections.abc import Iterable, Mapping

from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSTArchives_pb2 as tst
from .._persistence.index import ArchiveIndex
from .._persistence.metadata import PackageRegistry, createSiblingArchive
from ._lines import GridMaps, LineMap, findDisplacedLine, listAddedLines


def mapStrokeRuns(
    layer: tst.StrokeLayerArchive, lines: LineMap
) -> list[tst.StrokeLayerArchive.StrokeRunArchive]:
    """Return one layer's runs after the edit, split where a removed line sat.

    **A removal splits a run rather than shortening it**, measured in
    `57-borders-row-deleted`: one run over six rows became two, of two lines and
    three, carrying the same stroke. Lines added inside a run are covered by it,
    which is how an inserted row takes the border of the run it fell into.
    """
    mapped: list[tst.StrokeLayerArchive.StrokeRunArchive] = []
    segment: list[int] = []
    for run in layer.stroke_runs:
        segment = []
        for line in range(run.origin, run.origin + run.length):
            if lines.lineMap(line) is None:
                if segment:
                    mapped.append(buildStrokeRun(run, segment, lines))
                segment = []
                continue
            segment.append(line)
        if segment:
            mapped.append(buildStrokeRun(run, segment, lines))
    return mapped


def buildStrokeRun(
    run: tst.StrokeLayerArchive.StrokeRunArchive,
    segment: list[int],
    lines: LineMap,
) -> tst.StrokeLayerArchive.StrokeRunArchive:
    """Return one run of a layer, covering where a stretch of lines landed."""
    first, last = lines.lineMap(segment[0]), lines.lineMap(segment[-1])
    assert first is not None and last is not None
    moved = tst.StrokeLayerArchive.StrokeRunArchive()
    moved.CopyFrom(run)
    moved.origin = first
    moved.length = last - first + 1
    return moved


def applyStrokeLayers(
    index: ArchiveIndex,
    registry: PackageRegistry,
    sidecar: tst.StrokeSidecarArchive,
    maps: GridMaps,
) -> None:
    """Move every border with the line it belongs to, as `57-borders-*` measured.

    A layer belongs to one row or column and holds runs along the other axis, so
    each list follows one map by its index and the other inside its runs. An added
    line takes a copy of the layer of the line it displaced, which is how an
    inserted column arrived carrying its neighbor's border.
    """
    lists = (
        (sidecar.left_column_stroke_layers, maps.columns, maps.rows),
        (sidecar.right_column_stroke_layers, maps.columns, maps.rows),
        (sidecar.top_row_stroke_layers, maps.rows, maps.columns),
        (sidecar.bottom_row_stroke_layers, maps.rows, maps.columns),
    )
    for references, keys, runs in lists:
        if not len(references):
            continue
        stored = {}
        for reference in references:
            layer = index.resolve(reference, tst.StrokeLayerArchive)
            stored[layer.row_column_index] = (reference.identifier, layer)
        placed: dict[int, tuple[int, tst.StrokeLayerArchive]] = {}
        for line, (identifier, layer) in stored.items():
            moved = keys.lineMap(line)
            if moved is None:
                registry.archiveRemove(identifier)
                continue
            layer.row_column_index = moved
            placed[moved] = (identifier, layer)
        sibling = next(iter(stored.values()))[0]
        for line in listAddedLines(keys):
            displaced = findDisplacedLine(keys, line)
            # Only a line holding a border stores a layer, so this one has none to copy.
            if displaced is not None and displaced not in stored:
                continue
            copied = tst.StrokeLayerArchive()
            if displaced is not None:
                copied.CopyFrom(stored[displaced][1])
            copied.row_column_index = line
            placed[line] = (
                createSiblingArchive(registry, sibling, copied),
                copied,
            )
        for identifier, layer in placed.values():
            rewritten = mapStrokeRuns(layer, runs)
            del layer.stroke_runs[:]
            layer.stroke_runs.extend(rewritten)
            index.archiveWrite(identifier, layer)
        del references[:]
        for line in sorted(placed):
            references.add(identifier=placed[line][0])


# A stroke run as it applies to one cell edge: the run with its span cleared.
type StrokeEdges = dict[tuple[int, int], tst.StrokeLayerArchive.StrokeRunArchive]


def readStrokeEdges(
    index: ArchiveIndex, references: Iterable[tsp.Reference]
) -> StrokeEdges:
    """Return each cell edge a layer list strokes, keyed by (line, position)."""
    edges: StrokeEdges = {}
    for reference in references:
        layer = index.resolve(reference, tst.StrokeLayerArchive)
        for run in layer.stroke_runs:
            for position in range(run.origin, run.origin + run.length):
                edge = tst.StrokeLayerArchive.StrokeRunArchive()
                edge.CopyFrom(run)
                edge.ClearField("origin")
                edge.ClearField("length")
                edges[(layer.row_column_index, position)] = edge
    return edges


def buildEdgeRuns(
    edges: StrokeEdges, line: int
) -> list[tst.StrokeLayerArchive.StrokeRunArchive]:
    """Return one line's edges as runs, joining neighbors that draw the same stroke."""
    runs: list[tst.StrokeLayerArchive.StrokeRunArchive] = []
    for position in sorted(held for owner, held in edges if owner == line):
        edge = edges[(line, position)]
        last = runs[-1] if runs else None
        if last is not None and last.origin + last.length == position:
            probe = tst.StrokeLayerArchive.StrokeRunArchive()
            probe.CopyFrom(last)
            probe.ClearField("origin")
            probe.ClearField("length")
            if probe.SerializeToString(deterministic=True) == edge.SerializeToString(
                deterministic=True
            ):
                last.length += 1
                continue
        run = tst.StrokeLayerArchive.StrokeRunArchive()
        run.CopyFrom(edge)
        run.origin = position
        run.length = 1
        runs.append(run)
    return runs


def moveStrokeEdges(
    index: ArchiveIndex,
    registry: PackageRegistry,
    sidecar: tst.StrokeSidecarArchive,
    moves: Mapping[tuple[int, int], tuple[int, int]],
) -> None:
    """Carry each moved cell's four edges to where it landed, as `61-move-*` measured.

    `moves` maps a stored (row, column) to its new one. A layer left with no edge is
    removed, as Numbers left none behind at the vacated border.
    """
    placeStrokeEdges(index, registry, sidecar, moves.items(), keepSource=False)


def copyStrokeEdges(
    index: ArchiveIndex,
    registry: PackageRegistry,
    sidecar: tst.StrokeSidecarArchive,
    copies: Mapping[tuple[int, int], tuple[int, int]],
) -> None:
    """Give each copied cell exactly its source's four edges, as `64b` and `64d` show.

    `copies` maps where a copy landed to the stored (row, column) it copies, so two
    copies of one cell each draw its edges. An edge the source lacks is removed.
    """
    placeStrokeEdges(
        index, registry, sidecar,
        [(source, landed) for landed, source in copies.items()], keepSource=True,
    )


def placeStrokeEdges(
    index: ArchiveIndex,
    registry: PackageRegistry,
    sidecar: tst.StrokeSidecarArchive,
    carries: Iterable[tuple[tuple[int, int], tuple[int, int]]],
    keepSource: bool,
) -> None:
    """Carry each stored (row, column)'s edges to a new one, lifting or keeping them.

    A column's layers key their edges by (column, row) and a row's by (row, column).
    Keeping them is a copy, which also removes each new edge the source lacks.
    """
    carried = list(carries)
    lists = (
        (sidecar.left_column_stroke_layers, True),
        (sidecar.right_column_stroke_layers, True),
        (sidecar.top_row_stroke_layers, False),
        (sidecar.bottom_row_stroke_layers, False),
    )
    sibling = next(
        (reference.identifier for references, _ in lists for reference in references),
        None,
    )
    spent: list[int] = []
    for references, byColumn in lists:
        keyed = [
            (
                (column, row) if byColumn else (row, column),
                (newColumn, newRow) if byColumn else (newRow, newColumn),
            )
            for (row, column), (newRow, newColumn) in carried
        ]
        edges = readStrokeEdges(index, references)
        lifted = {key: edges[key] for key, _ in keyed if key in edges}
        cleared = [
            new for key, new in keyed
            if keepSource and key not in lifted and new in edges
        ]
        if not lifted and not cleared:
            continue
        if not keepSource:
            for key in lifted:
                del edges[key]
        for new in cleared:
            del edges[new]
        landed = [(new, lifted[key]) for key, new in keyed if key in lifted]
        for new, edge in landed:
            edges[new] = edge
        touched = (
            {line for line, _ in lifted} | {line for (line, _), _ in landed}
            | {line for line, _ in cleared}
        )
        layers = {
            index.resolve(reference, tst.StrokeLayerArchive).row_column_index:
            reference.identifier
            for reference in references
        }
        emptied = []
        for line in sorted(touched):
            runs = buildEdgeRuns(edges, line)
            identifier = layers.get(line)
            if not runs:
                if identifier is not None:
                    emptied.append(line)
                continue
            layer = tst.StrokeLayerArchive()
            layer.row_column_index = line
            layer.stroke_runs.extend(runs)
            if identifier is None:
                assert sibling is not None
                layers[line] = createSiblingArchive(registry, sibling, layer)
            else:
                index.archiveWrite(identifier, layer)
        spent.extend(layers.pop(line) for line in emptied)
        del references[:]
        for line in sorted(layers):
            references.add(identifier=layers[line])
    # Removed only after every created layer has copied its sibling's info.
    for identifier in spent:
        registry.archiveRemove(identifier)


def listStrokeLayers(sidecar: tst.StrokeSidecarArchive) -> list[int]:
    """Return every layer the sidecar points at, which is what it declares."""
    return [
        reference.identifier
        for references in (
            sidecar.left_column_stroke_layers, sidecar.right_column_stroke_layers,
            sidecar.top_row_stroke_layers, sidecar.bottom_row_stroke_layers,
        )
        for reference in references
    ]


__all__ = [
    "applyStrokeLayers", "copyStrokeEdges", "listStrokeLayers", "moveStrokeEdges",
]
