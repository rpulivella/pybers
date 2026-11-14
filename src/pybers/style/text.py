#!/usr/bin/env python3
"""\
A cell style's text form: each property it states as a CSS declaration.

`background: #ffd60aff; padding: 6pt; vertical-align: middle; text-wrap: nowrap` is
what `pybers show` prints and `pybers set --cell-style` reads, each name the CSS one,
and `none` sets no style.

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

import re
from decimal import Decimal

from pybers.color.colors import Color, ColorError
from pybers.errors import PybersError
from pybers.format.text import splitDeclarations
from pybers.style.cells import (
    CellStyle,
    CellStylePaddingSides,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
)
from pybers.style.fills import Fill, FillGradient, FillImage, FillNone

lengthPattern: re.Pattern[str] = re.compile(r"(\d+(?:\.\d+)?)pt|0")
properties: tuple[str, ...] = ("background", "padding", "vertical-align", "text-wrap")
otherFills: frozendict[str, Fill] = frozendict({
    "none": FillNone(), "gradient": FillGradient(), "image": FillImage(),
})


class CellStyleError(PybersError, ValueError):
    """A cell style's text form names a property or a value a cell style lacks."""


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


def parseFill(text: str) -> Fill:
    """Return the fill a CSS background value specifies, a color or a fill's type."""
    if text in otherFills:
        return otherFills[text]
    try:
        return Color.parse(text)
    except ColorError as exc:
        raise CellStyleError(f"background: {exc}") from exc


def parsePadding(text: str) -> Decimal | CellStylePaddingSides:
    """Return one length in points, or four in CSS order, from `6pt` or `0pt 2pt…`."""
    lengths = []
    for each in text.split():
        found = lengthPattern.fullmatch(each)
        if found is None:
            raise CellStyleError(
                f"padding is a length in points such as 6pt, and {each!r} is not one."
            )
        lengths.append(Decimal(found[1] or 0))
    if len(lengths) == 1:
        return lengths[0]
    if len(lengths) != 4:
        raise CellStyleError(
            f"padding is one length, or four in CSS order, and is {len(lengths)}."
        )
    top, right, bottom, left = lengths
    return top, right, bottom, left


def parseKeyword[Keyword: (CellStyleVerticalAlign, CellStyleTextWrap)](
    name: str, text: str, keywords: type[Keyword]
) -> Keyword:
    """Return the keyword a property's value names, refusing one it does not offer."""
    try:
        return keywords(text)
    except ValueError as exc:
        choices = ", ".join(each.value for each in keywords)
        raise CellStyleError(f"{name} is one of {choices}, and is {text!r}.") from exc


def parseCellStyle(text: str) -> CellStyle | None:
    """Return the cell style CSS declarations specify, or None for `none`.

    `background: #ffd60aff; padding: 6pt; vertical-align: middle; text-wrap: nowrap`.
    """
    if text.strip() == "none":
        return None
    head, declarations = splitDeclarations(text)
    firstName, _, firstValue = head.partition(":")
    stated: dict[str, str] = {}
    for name, value in [(firstName.strip(), firstValue.strip()), *declarations]:
        if name not in properties:
            raise CellStyleError(
                f"A cell style states {', '.join(properties)}, and {name!r} is not one."
            )
        if name in stated:
            raise CellStyleError(f"A cell style states {name} once, and twice here.")
        stated[name] = value
    background, padding = stated.get("background"), stated.get("padding")
    verticalAlign, textWrap = stated.get("vertical-align"), stated.get("text-wrap")
    return CellStyle(
        background=None if background is None else parseFill(background),
        padding=None if padding is None else parsePadding(padding),
        verticalAlign=None if verticalAlign is None else parseKeyword(
            "vertical-align", verticalAlign, CellStyleVerticalAlign
        ),
        textWrap=None if textWrap is None else parseKeyword(
            "text-wrap", textWrap, CellStyleTextWrap
        ),
    )


__all__ = [
    "CellStyleError", "formatCellStyle", "formatFill", "formatPadding",
    "parseCellStyle", "parseFill", "parsePadding",
]
