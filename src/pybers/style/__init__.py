#!/usr/bin/env python3
"""\
The style feature: a cell's box and the fills that paint it, and both archive halves.

UPDATES
2026-11-19  `CellStyleProperty` exported, for PYB-290.
2026-11-17  The stroke family, for PYB-266.
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

from pybers.style.cells import (
    CellStyle,
    CellStylePaddingSides,
    CellStyleProperty,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
)
from pybers.style.fills import Fill, FillGradient, FillImage, FillNone, FillType
from pybers.style.strokes import (
    Stroke,
    StrokeBrush,
    StrokeCap,
    StrokeDash,
    StrokeEmpty,
    StrokeError,
    StrokeFrame,
    StrokeJoin,
    StrokePattern,
    StrokePatterned,
    StrokePatternType,
    StrokeSolid,
    formatStroke,
)
from pybers.style.text import (
    CellStyleError,
    formatCellStyle,
    parseCellStyle,
    parseLength,
)

__all__ = [
    "CellStyle", "CellStylePaddingSides", "CellStyleProperty", "CellStyleTextWrap",
    "CellStyleVerticalAlign",
    "Fill", "FillGradient", "FillImage", "FillNone", "FillType", "CellStyleError",
    "formatCellStyle", "parseCellStyle", "parseLength", "formatStroke",
    "Stroke", "StrokeBrush", "StrokeCap", "StrokeDash", "StrokeEmpty", "StrokeError",
    "StrokeFrame", "StrokeJoin", "StrokePattern", "StrokePatternType",
    "StrokePatterned", "StrokeSolid",
]
