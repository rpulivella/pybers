#!/usr/bin/env python3
"""\
A cell style's text form: each property it states as a CSS declaration.

`background: #ffd60aff; padding: 6pt; vertical-align: middle; text-wrap: nowrap` is
what `pybers show` prints and `pybers set --cell-style` reads, each name the CSS one,
and `none` sets no style.

UPDATES
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-19  Each property's name read from `CellStyleProperty`, for PYB-290.
2026-11-17  `parseLength`, one length in points, which a border's width shares, for
            PYB-266.
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
from pybers.errors import PybersError, composeChoiceRefusal, composeRefusal
from pybers.format.text import splitDeclarations
from pybers.style.cells import (
    CellStyle,
    CellStylePaddingSides,
    CellStyleProperty,
    CellStyleTextWrap,
    CellStyleVerticalAlign,
)
from pybers.style.fills import Fill, FillGradient, FillImage, FillNone

lengthPattern: re.Pattern[str] = re.compile(r"(\d+(?:\.\d+)?)pt|0")
properties: tuple[str, ...] = tuple(each.value for each in CellStyleProperty)
otherFills: frozendict[str, Fill] = frozendict({
    "none": FillNone(), "gradient": FillGradient(), "image": FillImage(),
})


class CellStyleError(PybersError, ValueError):
    """A cell style's text form states a property or a value a cell style lacks."""


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


def parseFill(text: str, name: str = "background") -> Fill:
    """Return the fill a CSS value specifies, a color or a fill's type, for `name`."""
    if text in otherFills:
        return otherFills[text]
    try:
        return Color.parse(text)
    except ColorError as exc:
        raise CellStyleError(str(exc)) from exc


def parseLength(text: str, name: str) -> Decimal:
    """Return a length in points from `6pt`, or `0`, refusing anything else."""
    found = lengthPattern.fullmatch(text.strip())
    if found is None:
        raise CellStyleError(composeRefusal(
            f"The {name} {text!r}", "is not a length in points", "Write it as `6pt`"
        ))
    return Decimal(found[1] or 0)


def parsePadding(text: str) -> Decimal | CellStylePaddingSides:
    """Return one length in points, or four in CSS order, from `6pt` or `0pt 2pt…`."""
    lengths = [parseLength(each, "padding") for each in text.split()]
    if len(lengths) == 1:
        return lengths[0]
    if len(lengths) != 4:
        raise CellStyleError(composeRefusal(
            f"The padding {text!r}", f"gives {len(lengths)} lengths",
            "Give one, or four in CSS order",
        ))
    top, right, bottom, left = lengths
    return top, right, bottom, left


def parseKeyword[Keyword: (CellStyleVerticalAlign, CellStyleTextWrap)](
    name: str, text: str, keywords: type[Keyword]
) -> Keyword:
    """Return the keyword a property's value specifies, refusing one it lacks."""
    try:
        return keywords(text)
    except ValueError as exc:
        raise composeChoiceRefusal(
            CellStyleError, text, f"a {name} value", [each.value for each in keywords]
        ) from exc


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
            raise composeChoiceRefusal(
                CellStyleError, name, "a cell style property", properties
            )
        if name in stated:
            raise CellStyleError(composeRefusal(
                f"The property {name}", "is stated twice", "State it once"
            ))
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
    "parseCellStyle", "parseFill", "parseLength", "parsePadding",
]
