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

from pybers.color.colors import Color
from pybers.style.fills import Fill, FillGradient, FillImage, FillNone

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


# What a cell shows where no style states otherwise: no fill, 4pt, top, wrapping.
# Numbers' own region styles state these, measured in findings-03-structure.md.
numbersCellStyle: CellStyle = CellStyle(
    background=FillNone(), padding=Decimal(4),
    verticalAlign=CellStyleVerticalAlign.TOP, textWrap=CellStyleTextWrap.WRAP,
)


def findCellStyleRefusal(cellStyle: CellStyle) -> str | None:
    """Return why pybers cannot write a cell style, or None when it can."""
    background = cellStyle.background
    if isinstance(background, FillGradient | FillImage):
        return (f"A {background.fillType} fill is read and carried, and pybers does "
                "not yet write one.")
    if background is not None and not isinstance(background, Color | FillNone):
        return (f"A cell's background is a Color or FillNone, and was given "
                f"{type(background).__name__}.")
    padding = cellStyle.padding
    if isinstance(padding, tuple):
        return ("A cell's padding is one length for every side, the one value Numbers "
                f"offers, and was given {len(padding)}.")
    if padding is not None and (
        isinstance(padding, bool) or not isinstance(padding, Decimal | int)
    ):
        return (f"A cell's padding is a Decimal or an int number of points, and was "
                f"given {type(padding).__name__}.")
    if padding is not None and padding < 0:
        return f"A cell's padding cannot be negative, and was given {padding}."
    for name, kind in (("verticalAlign", CellStyleVerticalAlign),
                       ("textWrap", CellStyleTextWrap)):
        value = getattr(cellStyle, name)
        if value is not None and not isinstance(value, kind):
            choices = ", ".join(each.value for each in kind)
            return f"A cell's {name} is one of {choices}, and was given {value!r}."
    return None


def findOverrides(
    cellStyle: CellStyle | None, inherited: CellStyle
) -> CellStyle | None:
    """Return what a style states beyond what the cell inherits, None when nothing.

    The one place an override equal to the inherited value is dropped: a request
    is reduced here, and the save writes what the cell asked for.
    """
    if cellStyle is None:
        return None
    background, padding = cellStyle.background, cellStyle.padding
    verticalAlign, textWrap = cellStyle.verticalAlign, cellStyle.textWrap
    overrides = CellStyle(
        background=None if background == inherited.background else background,
        padding=None if padding == inherited.padding else padding,
        verticalAlign=(
            None if verticalAlign == inherited.verticalAlign else verticalAlign
        ),
        textWrap=None if textWrap == inherited.textWrap else textWrap,
    )
    return None if overrides == CellStyle() else overrides


__all__ = [
    "CellStyle", "CellStylePaddingSides", "CellStyleTextWrap", "CellStyleVerticalAlign",
    "findCellStyleRefusal", "findOverrides", "numbersCellStyle",
]
