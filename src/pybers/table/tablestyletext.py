#!/usr/bin/env python3
"""\
A table style as text: each line, flag, band and section box as a CSS declaration.

What `pybers show` prints and `pybers set --table-style` reads, so a table's style
pastes back. A line's longhand, such as `table-outline-color`, changes one part, and a
section's box is one declaration per property, such as `header-rows-padding`, each
value written as `--cell-style` writes it.

UPDATES
2026-11-20  Written for PYB-291, moved from `tablestyle`, with each section's box.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/20"

import re
from dataclasses import replace
from decimal import Decimal
from typing import Any

from pybers.absence import MIXED
from pybers.color.colors import Color, ColorError
from pybers.errors import composeChoiceRefusal
from pybers.format.text import splitDeclarations
from pybers.style.cells import CellStyle, CellStyleProperty, updateCellStyles
from pybers.style.fills import Fill
from pybers.style.strokes import (
    Stroke,
    StrokeError,
    StrokeSolid,
    formatStroke,
)
from pybers.style.text import (
    CellStyleError,
    formatCellStyle,
    formatFill,
    parseCellStyle,
    parseFill,
    parseLength,
)
from pybers.table.tablestyle import (
    TableBand,
    TableLine,
    TableStyle,
    TableStyleError,
    composeBandRefusal,
    flagNames,
    tableStrokePresets,
)

# Each line's CSS name, in the order the text form writes them.
lineNames: frozendict[str, str] = frozendict({
    "table-outline": "tableOutline",
    "body-horizontal-gridlines": "bodyHorizontalGridlines",
    "body-vertical-gridlines": "bodyVerticalGridlines",
    "header-rows-vertical-gridlines": "headerRowsVerticalGridlines",
    "header-columns-horizontal-gridlines": "headerColumnsHorizontalGridlines",
    "footer-rows-vertical-gridlines": "footerRowsVerticalGridlines",
    "header-rows-horizontal-gridlines": "headerRowsHorizontalGridlines",
    "header-columns-vertical-gridlines": "headerColumnsVerticalGridlines",
    "footer-rows-horizontal-gridlines": "footerRowsHorizontalGridlines",
    "header-rows-separator": "headerRowsSeparator",
    "header-columns-separator": "headerColumnsSeparator",
    "footer-rows-separator": "footerRowsSeparator",
})


# The band's shorthand, a fill or none, and its longhand, the fill alone.
bandName: str = "banded-rows"


# Each section's box by the name its declarations open with, `header-rows-padding`.
sectionNames: frozendict[str, str] = frozendict({
    "body": "bodyCellStyle", "header-rows": "headerRowsCellStyle",
    "header-columns": "headerColumnsCellStyle", "footer-rows": "footerRowsCellStyle",
})


sectionDeclarations: frozendict[str, tuple[str, CellStyleProperty]] = frozendict({
    f"{name}-{styleProperty.value}": (field, styleProperty)
    for name, field in sectionNames.items() for styleProperty in CellStyleProperty
})


bandFillName: str = "banded-rows-background"


longhandPattern: re.Pattern[str] = re.compile(r"(.+)-(width|style|color)")


def formatTableLine(line: TableLine) -> str:
    """Return a line as CSS writes a border, `hidden` before one set to none."""
    stroke = "mixed" if line.stroke is MIXED else formatStroke(
        line.stroke, tableStrokePresets
    )
    return stroke if line.visible else f"hidden {stroke}"


def formatTableBand(band: TableBand) -> str:
    """Return a band as its fill, `hidden` before one banding is off but keeps."""
    fill = formatFill(band.fill)
    return fill if band.visible else f"hidden {fill}"


def parseBandFill(text: str, name: str) -> Fill:
    """Return the fill a band's text specifies, refusing text that is not one."""
    try:
        return parseFill(text, name)
    except CellStyleError as exc:
        raise TableStyleError(str(exc)) from exc


def parseTableBand(text: str, band: TableBand, name: str) -> TableBand:
    """Return a band from `none`, a fill, or `hidden` and a fill, as `show` prints."""
    if text == "none":
        return replace(band, visible=False)
    hidden, _, rest = text.partition(" ")
    if hidden == "hidden":
        return TableBand(False, parseBandColor(rest.strip(), band, name))
    return TableBand(True, parseBandColor(text, band, name))


def parseBandColor(text: str, band: TableBand, name: str) -> Fill:
    """Return a band's color, or the other fill the table already holds, as written."""
    fill = parseBandFill(text, name)
    if isinstance(fill, Color) or fill == band.fill:
        return fill
    raise TableStyleError(composeBandRefusal(fill))


def formatTableStyle(tableStyle: TableStyle) -> list[str]:
    """Return each line a table draws as one CSS declaration, the outline first."""
    declarations = [
        f"{name}: {formatTableLine(getattr(tableStyle, field))}"
        for name, field in lineNames.items()
    ]
    flags = [
        f"{name}: {'yes' if getattr(tableStyle, field) else 'no'}"
        for name, field in flagNames.items()
    ]
    band = f"{bandName}: {formatTableBand(tableStyle.bandedRows)}"
    boxes = [
        f"{name}-{styleProperty.value}: {formatSectionProperty(box, styleProperty)}"
        for name, field in sectionNames.items()
        for box in (getattr(tableStyle, field),)
        for styleProperty in CellStyleProperty
    ]
    return [declarations[0], *flags, *declarations[1:], band, *boxes]


def formatSectionProperty(box: CellStyle, styleProperty: CellStyleProperty) -> str:
    """Return one property of a section's box as `--cell-style` writes its value."""
    field = styleProperty.fieldName
    stated = CellStyle(**{field: getattr(box, field)})
    return formatCellStyle(stated).partition(": ")[2]


def parseLineStyle(text: str, line: TableLine, name: str) -> TableLine:
    """Return a line given a style keyword, `none` hiding it and keeping its stroke."""
    if text == "none":
        return replace(line, visible=False)
    if text not in tableStrokePresets:
        choices = ", ".join(tableStrokePresets)
        raise TableStyleError(f"{name} is one of {choices} or none, and is {text!r}.")
    if line.stroke is MIXED:
        raise TableStyleError(
            f"{name} stores a different stroke in each band, so give its width, "
            "style and color together."
        )
    pattern, cap, join = tableStrokePresets[text]
    return TableLine(True, replace(line.stroke, pattern=pattern, cap=cap, join=join))


def parseLineShorthand(text: str, line: TableLine, name: str) -> TableLine:
    """Return a line from `none`, or `width style color` as CSS writes a border.

    `hidden` before a stroke hides the line keeping that stroke, and `mixed` keeps
    an outline's differing strokes, so whatever `pybers show` prints reads back.
    """
    words = text.split()
    visible = not (words and words[0] == "hidden")
    stroke = words[1:] if not visible else words
    if words == ["none"]:
        return replace(line, visible=False)
    if stroke == ["mixed"] and line.stroke is MIXED:
        return TableLine(visible, MIXED)
    if len(stroke) != 3:
        raise TableStyleError(
            f"{name} is none, or a width, a style and a color such as 1pt solid "
            f"black, and is {text!r}."
        )
    width, style, color = stroke
    shown = parseLineStyle(style, TableLine(True, Stroke(
        width=parseLineWidth(width, name), color=parseLineColor(color, name),
        pattern=StrokeSolid(),
    )), name)
    return replace(shown, visible=visible)


def parseLineWidth(text: str, name: str) -> Decimal:
    """Return a line's width in points, refusing anything else."""
    try:
        return parseLength(text, name)
    except CellStyleError as exc:
        raise TableStyleError(str(exc)) from exc


def parseLineColor(text: str, name: str) -> Color:
    """Return a line's color, refusing text that is not one."""
    try:
        return Color.parse(text)
    except ColorError as exc:
        raise TableStyleError(f"{name}: {exc}") from exc


def parseLonghand(
    part: str, text: str, line: TableLine, name: str
) -> TableLine:
    """Return a line with one part changed: its width, style or color."""
    if part == "style":
        return parseLineStyle(text, line, name)
    if line.stroke is MIXED:
        raise TableStyleError(
            f"{name} stores a different stroke in each band, so give its width, "
            "style and color together."
        )
    try:
        stroke = (
            replace(line.stroke, width=parseLineWidth(text, name)) if part == "width"
            else replace(line.stroke, color=parseLineColor(text, name))
        )
    except StrokeError as exc:
        raise TableStyleError(f"{name}: {exc}") from exc
    return TableLine(line.visible, stroke)


def parseTableStyle(text: str, tableStyle: TableStyle) -> TableStyle:
    """Return a table style with CSS declarations applied to it.

    `table-outline: 1pt dashed black; body-vertical-gridlines: none`. A longhand such
    as `table-outline-color` changes one part, and the rest stays as it is.
    """
    head, declarations = splitDeclarations(text)
    firstName, _, firstValue = head.partition(":")
    changed = tableStyle
    seen: set[str] = set()
    for name, value in [(firstName.strip(), firstValue.strip()), *declarations]:
        if name in seen:
            raise TableStyleError(f"A table style states {name} once, and twice here.")
        seen.add(name)
        if name in flagNames:
            if value not in ("yes", "no"):
                raise TableStyleError(f"{name} is yes or no, and is {value!r}.")
            flag: dict[str, Any] = {flagNames[name]: value == "yes"}
            changed = replace(changed, **flag)
            continue
        if name in (bandName, bandFillName):
            band = changed.bandedRows
            changed = replace(changed, bandedRows=(
                parseTableBand(value, band, name) if name == bandName
                else replace(band, fill=parseBandColor(value, band, name))
            ))
            continue
        if name in sectionDeclarations:
            field, styleProperty = sectionDeclarations[name]
            try:
                stated = parseCellStyle(f"{styleProperty.value}: {value}")
            except CellStyleError as exc:
                raise TableStyleError(f"{name}: {exc}") from exc
            box = updateCellStyles(stated or CellStyle(), getattr(changed, field))
            section: dict[str, Any] = {field: box}
            changed = replace(changed, **section)
            continue
        longhand = longhandPattern.fullmatch(name)
        if name in lineNames:
            field = lineNames[name]
            line = parseLineShorthand(value, getattr(changed, field), name)
        elif longhand is not None and longhand[1] in lineNames:
            field = lineNames[longhand[1]]
            line = parseLonghand(longhand[2], value, getattr(changed, field), name)
        else:
            raise TableStyleError(composeChoiceRefusal(name, "a table style property", [
                *lineNames, *flagNames, bandName, bandFillName, *sectionDeclarations,
                *(f"{line}-{part}" for line in lineNames
                  for part in ("width", "style", "color")),
            ]))
        update: dict[str, Any] = {field: line}
        changed = replace(changed, **update)
    return changed


__all__ = [
    "bandFillName", "bandName", "formatTableBand", "formatTableLine",
    "formatTableStyle", "lineNames", "parseTableStyle", "sectionDeclarations",
    "sectionNames",
]
