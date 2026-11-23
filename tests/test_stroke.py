#!/usr/bin/env python3
"""\
A stroke read from every document pybers holds, composed back, and refused when invalid.

Measured against `100b-lines` for the cell border presets and `38-text-outline-shadow`
for the brush strokes, which the text-outline menu offers and the cell menu does not.

UPDATES
2026-11-17  Written for PYB-266.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/17"

from collections.abc import Iterator
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
from google.protobuf.message import Message

from conftest import documentDirectories, findDocumentPath
from pybers import (
    Color,
    ColorSpace,
    Stroke,
    StrokeBrush,
    StrokeCap,
    StrokeDash,
    StrokeEmpty,
    StrokeError,
    StrokeJoin,
    StrokeSolid,
)
from pybers._generated import TSDArchives_pb2 as tsd
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence.container import readPackage
from pybers._persistence.index import ArchiveIndex
from pybers._persistence.types import archiveTypes, readArchiveTypeId
from pybers.errors import WriteError
from pybers.style._read import readStroke
from pybers.style._write import composeStroke


def walkStrokes(message: Message) -> Iterator[tsd.StrokeArchive]:
    """Yield every stroke a message holds, at any depth."""
    if isinstance(message, tsd.StrokeArchive):
        yield message
        return
    for field, value in message.ListFields():
        if field.message_type is None:
            continue
        values = value if field.is_repeated else [value]
        for each in values:
            if isinstance(each, Message):
                yield from walkStrokes(each)


@cache
def readDocumentStrokes(path: Path) -> tuple[tsd.StrokeArchive, ...]:
    """Return every stroke stored anywhere in a document."""
    index = ArchiveIndex(readPackage(path))
    return tuple(
        stroke
        for identifier, archive in index.byIdentifier.items()
        if readArchiveTypeId(archive) in archiveTypes
        for stroke in walkStrokes(
            index.identifierResolve(
                identifier, archiveTypes[readArchiveTypeId(archive)]
            )
        )
    )


@cache
def readBorderStrokes(stem: str, table: str) -> tuple[Stroke, ...]:
    """Return every border stroke of one table, in sidecar order."""
    index = ArchiveIndex(readPackage(findDocumentPath(stem)))
    for identifier, archive in index.byIdentifier.items():
        if readArchiveTypeId(archive) != 6001:
            continue
        model = index.identifierResolve(identifier, tst.TableModelArchive)
        if model.table_name != table:
            continue
        sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
        return tuple(
            readStroke(run.stroke)
            for references in (
                sidecar.left_column_stroke_layers, sidecar.right_column_stroke_layers,
                sidecar.top_row_stroke_layers, sidecar.bottom_row_stroke_layers,
            )
            for reference in references
            for run in index.resolve(reference, tst.StrokeLayerArchive).stroke_runs
        )
    raise AssertionError(f"{stem} holds no table named {table}")


def test_every_solid_dashed_or_empty_stroke_composes_back_to_its_bytes() -> None:
    documents = [
        path for directory in documentDirectories
        for path in sorted(directory.glob("*.numbers"))
    ]
    composed = 0
    for path in documents:
        for stored in readDocumentStrokes(path):
            stroke = readStroke(stored)
            if not isinstance(stroke.pattern, StrokeSolid | StrokeDash | StrokeEmpty):
                continue
            assert composeStroke(stroke).SerializeToString(
                deterministic=True
            ) == stored.SerializeToString(deterministic=True), path.name
            composed += 1
    assert composed > 1000


def test_a_border_chosen_by_style_alone_takes_the_gridline_stroke() -> None:
    assert readBorderStrokes("100b-lines", "Table 1")[0] == Stroke(
        width=Decimal("0.35"), color=Color.black, pattern=StrokeSolid()
    )


@pytest.mark.parametrize("width", [Decimal(1), Decimal(5)])
def test_a_cell_border_dash_is_in_multiples_of_its_width(width: Decimal) -> None:
    strokes = readBorderStrokes("100b-lines", "Table 1")
    dashed = {each.pattern for each in strokes
              if each.width == width and isinstance(each.pattern, StrokeDash)}
    assert dashed == {
        StrokeDash(lengths=(Decimal(2), Decimal(2))),
        StrokeDash(lengths=(Decimal("0.001"), Decimal(2))),
    }


def test_a_dotted_cell_border_has_a_round_cap_and_join() -> None:
    strokes = readBorderStrokes("100b-lines", "Table 1")
    dot = StrokeDash(lengths=(Decimal("0.001"), Decimal(2)))
    dotted = {(each.cap, each.join) for each in strokes if each.pattern == dot}
    assert dotted == {(StrokeCap.ROUND, StrokeJoin.ROUND)}


def test_a_border_color_keeps_its_alpha() -> None:
    strokes = readBorderStrokes("100b-lines", "Table 1")
    translucent = {each.color for each in strokes if each.color.alpha != 1}
    assert translucent == {Color(ColorSpace.SRGB, (1, 0, 0), Decimal("0.5"))}


def test_a_brush_reads_by_its_name_before_its_solid_pattern() -> None:
    brushes = [
        stroke for stored in readDocumentStrokes(
            findDocumentPath("38-text-outline-shadow")
        )
        if isinstance((stroke := readStroke(stored)).pattern, StrokeBrush)
    ]
    assert {each.pattern for each in brushes} == {
        StrokeBrush(name=name)
        for name in ("Chalk2", "Feathered Brush", "Calligraphy", "Dry Brush", "Pen")
    }


def test_a_brush_is_carried_and_never_composed() -> None:
    stroke = Stroke(width=Decimal(8), color=Color.black,
                    pattern=StrokeBrush(name="Pen", seed=7), cap=StrokeCap.ROUND)
    with pytest.raises(WriteError, match="brush stroke is read and carried"):
        composeStroke(stroke)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"width": Decimal(-1)}, "width of -1 is negative"),
        ({"width": True}, "width True is not a number"),
        ({"width": Decimal("NaN")}, "width NaN is not finite"),
        ({"color": "#000000ff"}, "color str is not a Color"),
        ({"pattern": "dashed"}, "pattern str is not a StrokePattern"),
        ({"cap": "round"}, "cap 'round' is not a StrokeCap. Give one of butt"),
        ({"join": StrokeCap.ROUND}, "is not a StrokeJoin"),
    ],
)
def test_a_stroke_numbers_cannot_store_is_refused(
    arguments: dict[str, object], message: str
) -> None:
    stated: dict[str, object] = {
        "width": Decimal(1), "color": Color.black, "pattern": StrokeSolid(),
    } | arguments
    with pytest.raises(StrokeError, match=message):
        Stroke(**stated)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("lengths", "message"),
    [
        ((), "0 lengths is not supported, since Numbers stores from 1 to 6"),
        (tuple(Decimal(1) for _ in range(7)), "7 lengths is not supported"),
        ((Decimal(1), Decimal(-1)), "1, -1 hold a negative length"),
    ],
)
def test_a_dash_numbers_cannot_store_is_refused(
    lengths: tuple[Decimal, ...], message: str
) -> None:
    with pytest.raises(StrokeError, match=message):
        StrokeDash(lengths=lengths)
