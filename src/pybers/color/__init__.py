#!/usr/bin/env python3
"""\
The color feature: one value carrying its own color space, and both archive halves.

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

from pybers.color.colors import Color, ColorError, ColorNumber, ColorSpace

__all__ = ["Color", "ColorError", "ColorNumber", "ColorSpace"]
