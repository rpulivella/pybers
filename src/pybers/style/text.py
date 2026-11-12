#!/usr/bin/env python3
"""\
A cell style's text form: each property it states as a CSS declaration.

`background: #ffd60aff; padding: 6pt; vertical-align: middle; text-wrap: nowrap` is
what `pybers show` prints and `pybers set --cell-style` reads, each name the CSS one.

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

from pybers.color.colors import Color
from pybers.style.cells import CellStyle, CellStylePaddingSides
from pybers.style.fills import Fill


def formatFill(fill: Fill) -> str:
    """Return a fill as CSS writes it, a fill other than a color by its type."""
    return str(fill) if isinstance(fill, Color) else fill.fillType.value


def formatPadding(padding: Decimal | CellStylePaddingSides) -> str:
    """Return a padding in points, one length per side in CSS order when uneven."""
    sides = padding if isinstance(padding, tuple) else (padding,)
    return " ".join(f"{side}pt" for side in sides)


def formatCellStyle(cellStyle: CellStyle) -> str:
    """Return the declarations a cell style states, in its field order."""
    declarations = (
        ("background", None if cellStyle.background is None
         else formatFill(cellStyle.background)),
        ("padding", None if cellStyle.padding is None
         else formatPadding(cellStyle.padding)),
        ("vertical-align", None if cellStyle.verticalAlign is None
         else cellStyle.verticalAlign.value),
        ("text-wrap", None if cellStyle.textWrap is None else cellStyle.textWrap.value),
    )
    return "; ".join(f"{name}: {value}" for name, value in declarations if value)


__all__ = ["formatCellStyle", "formatFill", "formatPadding"]
