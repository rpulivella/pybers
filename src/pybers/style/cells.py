#!/usr/bin/env python3
"""\
A cell's box: its fill, padding, vertical alignment and text wrap.

A `CellStyle` holds what a cell's own style states, as a CSS inline style does, so a
property is None while the cell inherits it from its table. Frozen, because Numbers
shares one style among every cell styled alike.

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

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from pybers.style.fills import Fill

# One length per side, in CSS order: top, right, bottom, left.
type CellStylePaddingSides = tuple[Decimal, Decimal, Decimal, Decimal]


class CellStyleVerticalAlign(StrEnum):
    """Where a cell's text sits between its top and bottom padding."""

    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


class CellStyleTextWrap(StrEnum):
    """Whether a cell's text wraps within its width."""

    WRAP = "wrap"
    NOWRAP = "nowrap"


@dataclass(frozen=True, slots=True)
class CellStyle:
    """What a cell's own style states about its box, each property None when inherited.

    `padding` is points on every side, or one per side for a table imported uneven.
    """

    background: Fill | None = None
    padding: Decimal | CellStylePaddingSides | None = None
    verticalAlign: CellStyleVerticalAlign | None = None
    textWrap: CellStyleTextWrap | None = None


__all__ = [
    "CellStyle", "CellStylePaddingSides", "CellStyleTextWrap", "CellStyleVerticalAlign",
]
