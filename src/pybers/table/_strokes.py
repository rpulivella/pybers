#!/usr/bin/env python3
"""\
A table's borders carried through rows and columns added or removed.

Each row and each column owns one stroke layer, holding runs along the other
axis, so one map moves a layer by its index and the other moves the runs
inside it. Measured 2026-09-21 in the four `57-borders-*` documents.

Private. Part of the table feature's archive half.

UPDATES
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


__all__ = ["applyStrokeLayers", "listStrokeLayers"]
