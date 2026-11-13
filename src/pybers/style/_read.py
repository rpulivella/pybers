#!/usr/bin/env python3
"""\
A cell's style read from `TST.CellStyleArchive`, one frozen object per archive.

A table's `styleTable` holds its cell styles and paragraph styles under one key
space, so only the archive type a key resolves to says which it is. See
findings-09-cell-records.md.

Private. The archive half of the style feature.

UPDATES
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
from pybers.errors import ReadError
from pybers.style.cells import (
    CellStyle,
    CellStylePaddingSides,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
    numbersCellStyle,
)
from pybers.style.fills import Fill, FillGradient, FillImage, FillNone

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
            raise ReadError(f"A cell style holds vertical alignment {stored}, and a "
                            f"cell aligns only top, middle or bottom.")
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
    "readPadding",
]
