#!/usr/bin/env python3
"""\
A cell's style read from `TST.CellStyleArchive`, one frozen object per archive.

A table's `styleTable` holds its cell styles and paragraph styles under one key
space, so only the archive type a key resolves to says which it is. See
findings-09-cell-records.md.

Private. The archive half of the style feature.

UPDATES
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-17  A stroke read from `TSD.StrokeArchive`, for PYB-266.
2026-11-12  Written for PYB-265.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/12"

from decimal import Decimal

from pybers._generated import TSDArchives_pb2 as tsd
from pybers._generated import TSTArchives_pb2 as tst
from pybers._generated import TSWPArchives_pb2 as tswp
from pybers._persistence.index import ArchiveIndex
from pybers._persistence.types import findArchiveTypeId
from pybers.color._archive import readColor
from pybers.color.colors import findShortestDecimal
from pybers.errors import ReadError, composeFault, nothingRead
from pybers.style.cells import (
    CellStyle,
    CellStylePaddingSides,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
    numbersCellStyle,
)
from pybers.style.fills import Fill, FillGradient, FillImage, FillNone
from pybers.style.strokes import (
    Stroke,
    StrokeBrush,
    StrokeCap,
    StrokeDash,
    StrokeEmpty,
    StrokeFrame,
    StrokeJoin,
    StrokePattern,
    StrokePatterned,
    StrokeSolid,
)

# By stored value, the three the inspector offers; the shared text frame's justify, 3,
# is never a cell's.
verticalAligns: tuple[CellStyleVerticalAlign, ...] = (
    CellStyleVerticalAlign.TOP, CellStyleVerticalAlign.MIDDLE,
    CellStyleVerticalAlign.BOTTOM,
)


def readFill(archive: tsd.FillArchive) -> Fill:
    """Return the fill an archive holds, an empty one being no fill."""
    if archive.HasField("color"):
        return readColor(archive.color)
    if archive.HasField("gradient"):
        return FillGradient()
    if archive.HasField("image"):
        return FillImage()
    return FillNone()


strokeCaps: tuple[StrokeCap, ...] = (StrokeCap.BUTT, StrokeCap.ROUND, StrokeCap.SQUARE)
strokeJoins: tuple[StrokeJoin, ...] = (
    StrokeJoin.MITER, StrokeJoin.ROUND, StrokeJoin.BEVEL,
)


def readStrokePattern(archive: tsd.StrokeArchive) -> StrokePattern:
    """Return what a stroke draws, a brush, frame or pattern before its stored pattern.

    A brush stores a solid pattern, so trusting the pattern alone misreads it.
    """
    if archive.HasField("smart_stroke"):
        brush = archive.smart_stroke
        seed = brush.random_seed if brush.HasField("random_seed") else None
        return StrokeBrush(name=brush.stroke_name, seed=seed)
    if archive.HasField("frame"):
        return StrokeFrame()
    if archive.HasField("patterned_stroke"):
        return StrokePatterned()
    pattern = archive.pattern
    match pattern.type:
        case tsd.StrokePatternArchive.TSDSolidPattern:
            return StrokeSolid()
        case tsd.StrokePatternArchive.TSDEmptyPattern:
            return StrokeEmpty()
        case tsd.StrokePatternArchive.TSDPattern if 0 < pattern.count <= len(
            pattern.pattern
        ):
            return StrokeDash(
                lengths=tuple(
                    findShortestDecimal(each)
                    for each in pattern.pattern[:pattern.count]
                ),
                phase=findShortestDecimal(pattern.phase),
            )
    raise ReadError(composeFault(
        "A stroke", f"holds pattern type {pattern.type} with {pattern.count} of "
        f"{len(pattern.pattern)} dash lengths live, which pybers does not recognize",
        nothingRead,
    ))


def readStroke(archive: tsd.StrokeArchive) -> Stroke:
    """Return the line a stroke archive holds."""
    if not 0 <= archive.cap < len(strokeCaps):
        raise ReadError(composeFault(
            "A stroke", f"holds line cap {archive.cap}, which pybers does not "
            "recognize", nothingRead,
        ))
    if not 0 <= archive.join < len(strokeJoins):
        raise ReadError(composeFault(
            "A stroke", f"holds line join {archive.join}, which pybers does not "
            "recognize", nothingRead,
        ))
    return Stroke(
        width=findShortestDecimal(archive.width),
        color=readColor(archive.color),
        pattern=readStrokePattern(archive),
        cap=strokeCaps[archive.cap],
        join=strokeJoins[archive.join],
        miterLimit=findShortestDecimal(archive.miter_limit),
    )


def readPadding(archive: tswp.PaddingArchive) -> Decimal | CellStylePaddingSides:
    """Return one length for an even padding, else each side; Numbers omits a zero."""
    sides = tuple(
        findShortestDecimal(side)
        for side in (archive.top, archive.right, archive.bottom, archive.left)
    )
    if len(set(sides)) == 1:
        return sides[0]
    top, right, bottom, left = sides
    return top, right, bottom, left


def readCellStyle(archive: tst.CellStyleArchive) -> CellStyle:
    """Return what a cell style archive states about the box, nothing it inherits."""
    properties = archive.cell_properties
    verticalAlign = None
    if properties.HasField("vertical_alignment"):
        stored = properties.vertical_alignment
        if not 0 <= stored < len(verticalAligns):
            raise ReadError(composeFault(
                "A cell style", f"holds vertical alignment {stored}, and a cell "
                "aligns only top, middle or bottom", nothingRead,
            ))
        verticalAlign = verticalAligns[stored]
    textWrap = None
    if properties.HasField("text_wrap"):
        wraps = properties.text_wrap
        textWrap = CellStyleTextWrap.WRAP if wraps else CellStyleTextWrap.NOWRAP
    return CellStyle(
        background=(
            readFill(properties.cell_fill) if properties.HasField("cell_fill") else None
        ),
        padding=(
            readPadding(properties.padding) if properties.HasField("padding") else None
        ),
        verticalAlign=verticalAlign,
        textWrap=textWrap,
    )


def readInheritedCellStyle(index: ArchiveIndex, identifier: int) -> CellStyle:
    """Return a style resolved through its parents, each property the nearest stated.

    A property no ancestor states is Numbers' own default, `numbersCellStyle`.
    """
    chain: list[CellStyle] = []
    seen: set[int] = set()
    while identifier and identifier not in seen:
        seen.add(identifier)
        archive = index.identifierResolve(identifier, tst.CellStyleArchive)
        chain.append(readCellStyle(archive))
        identifier = int(archive.super.parent.identifier)
    chain.append(numbersCellStyle)
    return CellStyle(
        background=next(each.background for each in chain if each.background),
        padding=next(each.padding for each in chain if each.padding is not None),
        verticalAlign=next(each.verticalAlign for each in chain if each.verticalAlign),
        textWrap=next(each.textWrap for each in chain if each.textWrap),
    )


def readCellStyles(
    index: ArchiveIndex, dataStore: tst.DataStore
) -> dict[int, CellStyle]:
    """Return each cell style a table's `styleTable` holds, by the key records name."""
    if not dataStore.HasField("styleTable"):
        return {}
    cellStyleType = findArchiveTypeId(tst.CellStyleArchive)
    dataList = index.resolve(dataStore.styleTable, tst.TableDataList)
    return {
        int(entry.key): readCellStyle(
            index.resolve(entry.reference, tst.CellStyleArchive)
        )
        for entry in dataList.entries
        if index.typeOf(entry.reference) == cellStyleType
    }


__all__ = [
    "readCellStyle", "readCellStyles", "readFill", "readInheritedCellStyle",
    "readPadding", "readStroke", "readStrokePattern",
]
