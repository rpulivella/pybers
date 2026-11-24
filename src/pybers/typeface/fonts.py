#!/usr/bin/env python3
"""\
A font, one weight and slant of a typeface's design, and where pybers found it.

A style names a font by its PostScript name, `AvenirNext-DemiBold`, which is the one
name every system agrees on, so a `TypefaceFont` carries it beside the names a person
reads.

UPDATES
2026-11-24  A font's design is its `typeface`, for PYB-318.
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

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePath

# The suffixes a font file carries, each a font or a collection of them.
fontSuffixes: frozenset[str] = frozenset({".otf", ".ttf", ".ttc", ".otc"})


class TypefaceSlant(StrEnum):
    """Whether a font is upright, italic or oblique, as CSS `font-style` names them."""

    NORMAL = "normal"
    ITALIC = "italic"
    OBLIQUE = "oblique"


class TypefaceSource(StrEnum):
    """Where pybers found a font: its catalog, this machine or a font file."""

    CATALOG = "catalog"
    MACHINE = "machine"
    FILE = "file"


@dataclass(frozen=True, slots=True)
class TypefaceFont:
    """One font: its typeface, its name in it, its PostScript name and its design.

    `weight` is 1 to 1000, as CSS `font-weight`.
    """

    typeface: str
    name: str
    postScriptName: str
    weight: int
    slant: TypefaceSlant
    source: TypefaceSource
    file: PurePath


__all__ = ["TypefaceFont", "TypefaceSlant", "TypefaceSource", "fontSuffixes"]
