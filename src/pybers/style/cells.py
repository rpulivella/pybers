#!/usr/bin/env python3
"""\
A cell's box: its fill, padding, vertical alignment and text wrap.

A `CellStyle` holds what a cell's own style states, as a CSS inline style does, so a
property is None while the cell inherits it from its table. Frozen, because Numbers
shares one style among every cell styled alike.

UPDATES
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-19  `CellStyleProperty`, each property by its CSS name, and
            `updateCellStyles`, moved from the table's archive half, and
            `findUnwritablePart`, for PYB-290.
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

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum

from pybers.color.colors import Color
from pybers.errors import composeRefusal
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


class CellStyleProperty(StrEnum):
    """One property a cell style states, by the name CSS gives it."""

    BACKGROUND = "background"
    PADDING = "padding"
    VERTICAL_ALIGN = "vertical-align"
    TEXT_WRAP = "text-wrap"

    @property
    def fieldName(self) -> str:
        """Return the `CellStyle` field holding this property, `verticalAlign`."""
        head, *rest = self.value.split("-")
        return head + "".join(each.title() for each in rest)


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
# Numbers' own section styles state these, measured in findings-03-structure.md.
numbersCellStyle: CellStyle = CellStyle(
    background=FillNone(), padding=Decimal(4),
    verticalAlign=CellStyleVerticalAlign.TOP, textWrap=CellStyleTextWrap.WRAP,
)

# The cell style every section of a table pybers adds specifies, the reset: no wrapping.
resetCellStyle: CellStyle = CellStyle(textWrap=CellStyleTextWrap.NOWRAP)
# What every cell of a table pybers adds shows: Numbers' own box, not wrapping.
createdCellStyle: CellStyle = replace(
    numbersCellStyle, textWrap=CellStyleTextWrap.NOWRAP
)


def findUnwritablePart(cellStyle: CellStyle) -> str | None:
    """Return what a style holds that pybers cannot write, `a gradient fill`, or None.

    The one place a style a cell already holds is judged, so a change over it refuses
    in the reader's terms.
    """
    background = cellStyle.background
    if isinstance(background, FillGradient | FillImage):
        return {"gradient": "a gradient fill", "image": "an image fill"}[
            background.fillType.value
        ]
    return "uneven padding" if isinstance(cellStyle.padding, tuple) else None


def findCellStyleRefusal(
    cellStyle: CellStyle, notDone: str | None = None
) -> str | None:
    """Return why pybers cannot write a cell style, or None when it can."""
    background = cellStyle.background
    if isinstance(background, FillGradient | FillImage):
        return composeRefusal(
            f"A {background.fillType} fill", "is read and carried, and writing one is "
            "not supported", notDone=notDone,
        )
    if background is not None and not isinstance(background, Color | FillNone):
        return composeRefusal(
            f"The background {type(background).__name__}", "is not a Color or FillNone",
            notDone=notDone,
        )
    padding = cellStyle.padding
    if isinstance(padding, tuple):
        return composeRefusal(
            f"A padding of {len(padding)} sides", "is not supported, since Numbers "
            "offers one length for every side", "Give one length", notDone,
        )
    if padding is not None and (
        isinstance(padding, bool) or not isinstance(padding, Decimal | int)
    ):
        return composeRefusal(
            f"The padding {type(padding).__name__}",
            "is not a Decimal or an int number of points", notDone=notDone,
        )
    if padding is not None and padding < 0:
        return composeRefusal(
            f"A padding of {padding}", "is negative, and a padding is 0 or more",
            notDone=notDone,
        )
    for name, kind in (("verticalAlign", CellStyleVerticalAlign),
                       ("textWrap", CellStyleTextWrap)):
        value = getattr(cellStyle, name)
        if value is not None and not isinstance(value, kind):
            choices = ", ".join(each.value for each in kind)
            return composeRefusal(
                f"The {name} {value!r}", f"is not a {kind.__name__}",
                f"Give one of {choices}", notDone,
            )
    return None


def updateCellStyles(*styles: CellStyle) -> CellStyle:
    """Return one style stating each property the first of `styles` to state it does."""
    return CellStyle(**{
        each.fieldName: next((
            getattr(style, each.fieldName) for style in styles
            if getattr(style, each.fieldName) is not None
        ), None)
        for each in CellStyleProperty
    })


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
    "CellStyle", "CellStylePaddingSides", "CellStyleProperty", "CellStyleTextWrap",
    "CellStyleVerticalAlign", "createdCellStyle", "findCellStyleRefusal",
    "findOverrides", "findUnwritablePart", "numbersCellStyle", "resetCellStyle",
    "updateCellStyles",
]
