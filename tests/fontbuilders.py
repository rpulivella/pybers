#!/usr/bin/env python3
"""\
Font files a test builds for itself, each holding only the names and bits it states.

No system font is committed, so a test of the font reader builds the face it reads.

UPDATES
2026-11-24  Written for PYB-315.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"

from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection, TTFont

italicSelection: int = 1 << 0
obliqueSelection: int = 1 << 9


def buildFont(
    family: str, style: str, postScriptName: str, weight: int = 400,
    selection: int = 0, axes: list[tuple[str, float, float, float, str]] | None = None,
    instances: list[dict[str, object]] | None = None,
) -> TTFont:
    """Return a font of one empty glyph, its names, weight and selection bits stated."""
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder([".notdef"])
    builder.setupCharacterMap({})
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((0, 1))
    pen.lineTo((1, 0))
    pen.closePath()
    builder.setupGlyf({".notdef": pen.glyph()})
    builder.setupHorizontalMetrics({".notdef": (500, 0)})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({
        "familyName": family, "styleName": style, "psName": postScriptName,
    })
    builder.setupOS2(usWeightClass=weight, fsSelection=selection)
    builder.setupPost()
    if axes is not None:
        builder.setupFvar(axes, instances or [])
    return builder.font


def saveFont(font: TTFont, path: Path) -> Path:
    """Write a font to a path and return the path."""
    font.save(path)
    return path


def saveCollection(fonts: list[TTFont], path: Path) -> Path:
    """Write several fonts as one collection and return its path."""
    collection = TTCollection()
    collection.fonts = fonts
    collection.save(path)
    return path


__all__ = [
    "buildFont", "italicSelection", "obliqueSelection", "saveCollection", "saveFont",
]
