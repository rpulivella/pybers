#!/usr/bin/env python3
"""\
A color read from `TSP.Color` and composed back, its float32 values untouched.

`TSP.Color` defaults alpha and headroom to 1 when a writer omits them, so reading a
color takes those defaults and composing one always states both.

Private. The archive half of the color feature.

UPDATES
2026-11-06  Written for PYB-264.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/06"

from pybers._generated import TSPMessages_pb2 as tsp
from pybers.color.colors import Color, ColorSpace


def readColor(archive: tsp.Color) -> Color:
    """Return the color an archive holds."""
    match archive.model:
        case tsp.Color.cmyk:
            return Color(
                ColorSpace.DEVICE_CMYK, (archive.c, archive.m, archive.y, archive.k),
                archive.a, archive.headroom,
            )
        case tsp.Color.white:
            return Color(
                ColorSpace.DEVICE_GRAY, (archive.w,), archive.a, archive.headroom
            )
    wide = archive.rgbspace == tsp.Color.p3
    space = ColorSpace.DISPLAY_P3 if wide else ColorSpace.SRGB
    return Color(space, (archive.r, archive.g, archive.b), archive.a, archive.headroom)


def composeColor(color: Color) -> tsp.Color:
    """Return the archive a color is stored as, its alpha and headroom always stated."""
    match color.colorSpace:
        case ColorSpace.DEVICE_CMYK:
            cyan, magenta, yellow, black = color.components
            return tsp.Color(
                model=tsp.Color.cmyk, c=cyan, m=magenta, y=yellow, k=black,
                a=color.alpha, headroom=color.headroom,
            )
        case ColorSpace.DEVICE_GRAY:
            return tsp.Color(
                model=tsp.Color.white, w=color.components[0],
                a=color.alpha, headroom=color.headroom,
            )
    red, green, blue = color.components
    wide = color.colorSpace is ColorSpace.DISPLAY_P3
    space = tsp.Color.p3 if wide else tsp.Color.srgb
    return tsp.Color(
        model=tsp.Color.rgb, r=red, g=green, b=blue, a=color.alpha,
        rgbspace=space, headroom=color.headroom,
    )


__all__ = ["composeColor", "readColor"]
