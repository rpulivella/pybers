#!/usr/bin/env python3
"""\
The style feature: a cell's box and the fills that paint it, and both archive halves.

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

from pybers.style.cells import (
    CellStyle,
    CellStylePaddingSides,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
)
from pybers.style.fills import Fill, FillGradient, FillImage, FillNone, FillType
from pybers.style.text import formatCellStyle

__all__ = [
    "CellStyle", "CellStylePaddingSides", "CellStyleTextWrap", "CellStyleVerticalAlign",
    "Fill", "FillGradient", "FillImage", "FillNone", "FillType", "formatCellStyle",
]
