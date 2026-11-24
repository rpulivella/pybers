#!/usr/bin/env python3
"""\
A face, one design of a font family at one weight and slant, and where pybers found it.

A style names a face by its PostScript name, `AvenirNext-DemiBold`, which is the one
name every system agrees on, so a `FontFace` carries it beside the names a person
reads.

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

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePath

# The suffixes a font file carries, each a font or a collection of them.
fontSuffixes: frozenset[str] = frozenset({".otf", ".ttf", ".ttc", ".otc"})


class FontSlant(StrEnum):
    """Whether a face is upright, italic or oblique, as CSS `font-style` names them."""

    NORMAL = "normal"
    ITALIC = "italic"
    OBLIQUE = "oblique"


class FontSource(StrEnum):
    """Where pybers found a face: its catalog, this machine, a font file or a caller."""

    CATALOG = "catalog"
    MACHINE = "machine"
    FILE = "file"
    CALLER = "caller"


@dataclass(frozen=True, slots=True)
class FontFace:
    """One face: its font family, its name in it, its PostScript name and its design.

    `weight` is 1 to 1000, as CSS `font-weight`, and `file` is None for a face a caller
    stated by its PostScript name alone.
    """

    fontFamily: str
    name: str
    postScriptName: str
    weight: int
    slant: FontSlant
    source: FontSource
    file: PurePath | None = None


__all__ = ["FontFace", "FontSlant", "FontSource", "fontSuffixes"]
