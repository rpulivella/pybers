#!/usr/bin/env python3
"""\
The font feature: the fonts pybers knows, where it found each, and reading font files.

UPDATES
2026-11-24  The feature named for typefaces, for PYB-318.
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

from pybers.typeface._files import TypefaceError
from pybers.typeface.fonts import (
    TypefaceFont,
    TypefaceSlant,
    TypefaceSource,
    fontSuffixes,
)
from pybers.typeface.typefaces import Typefaces, openTypefaces

__all__ = [
    "TypefaceError", "TypefaceFont", "TypefaceSlant", "TypefaceSource", "Typefaces",
    "fontSuffixes",
    "openTypefaces",
]
