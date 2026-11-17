#!/usr/bin/env python3
"""\
A table's lines: its gridlines, separators and outline, and its text form.

Each region shows or hides one line drawn with one stroke, as the table's style
states them, and the outline also outlines the table's title. A cell's border
prevails over all of them at its edge. See findings-06-styles.md.

UPDATES
2026-11-17  Written for PYB-266.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/17"

import re
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from decimal import Decimal
from typing import Any

from pybers.absence import MIXED
from pybers.addressing.reference import TableReference
from pybers.color.colors import Color, ColorError
from pybers.errors import PybersError, composeChoiceRefusal
from pybers.format.text import splitDeclarations
from pybers.style.strokes import (
    Stroke,
    StrokeCap,
    StrokeDash,
    StrokeError,
    StrokeJoin,
    StrokePresets,
    StrokeSolid,
    formatStroke,
)
from pybers.style.text import CellStyleError, parseLength
from pybers.table.headers import TableHeaders


class TableStyleError(PybersError, ValueError):
    """A table style's text form names a line or a value a table lacks."""


# The Table Outline menu's lines, as `100b-lines` stores them: dotted has a miter join.
tableStrokePresets: StrokePresets = frozendict({
    "solid": (StrokeSolid(), StrokeCap.BUTT, StrokeJoin.MITER),
    "dashed": (
        StrokeDash(lengths=(Decimal(2), Decimal(2))), StrokeCap.BUTT, StrokeJoin.MITER,
    ),
    "dotted": (
        StrokeDash(lengths=(Decimal("0.001"), Decimal(2))), StrokeCap.ROUND,
        StrokeJoin.MITER,
    ),
})


@dataclass(frozen=True, slots=True)
class TableLine:
    """One line a table draws: whether it shows, and its stroke, kept while hidden.

    The outline reads `MIXED` where its five stored strokes differ.
    """

    visible: bool
    stroke: Stroke | MIXED


@dataclass(frozen=True, slots=True)
class TableStyle:
    """The lines a table draws, each region named for what it draws."""

    bodyHorizontalGridlines: TableLine
    bodyVerticalGridlines: TableLine
    headerRowsVerticalGridlines: TableLine
    headerColumnsHorizontalGridlines: TableLine
    footerRowsVerticalGridlines: TableLine
    headerRowsSeparator: TableLine
    headerColumnsSeparator: TableLine
    footerRowsSeparator: TableLine
    tableOutline: TableLine
    tableOutlineTitle: bool


@dataclass(frozen=True, slots=True)
class TableStyleChange:
    """What setting a table's lines did: the lines it drew before and after."""

    reference: TableReference
    before: TableStyle
    after: TableStyle

    @property
    def changed(self) -> bool:
        """Report whether any line differs."""
        return self.before != self.after


def buildTableStyle(base: TableStyle, lines: Mapping[str, object]) -> TableStyle:
    """Return a table style with lines named by field replaced, refusing any other.

    The one place a requested table style is checked, so nothing invalid is held.
    """
    if not isinstance(base, TableStyle):
        raise TableStyleError(
            f"A table style is a TableStyle, and was given {type(base).__name__}. "
            "Nothing was written."
        )
    names = [each.name for each in fields(TableStyle)]
    for name, value in lines.items():
        if name not in names:
            raise TableStyleError(
                f"A table style holds {', '.join(names)}, and {name!r} is not one. "
                "Nothing was written."
            )
        if name == "tableOutlineTitle":
            if not isinstance(value, bool):
                raise TableStyleError(
                    f"tableOutlineTitle is a bool, and was given {value!r}. Nothing "
                    "was written."
                )
            continue
        if not isinstance(value, TableLine) or not isinstance(value.visible, bool) or (
            not isinstance(value.stroke, Stroke)
            and value.stroke is not getattr(base, name).stroke
        ):
            raise TableStyleError(
                f"{name} is a TableLine of a visibility and a Stroke, and was given "
                f"{value!r}. Nothing was written."
            )
    update: dict[str, Any] = dict(lines)
    return replace(base, **update)


def findTableLine(
    tableStyle: TableStyle, headers: TableHeaders, rowCount: int, colCount: int,
    row: int, column: int, horizontal: bool,
) -> TableLine:
    """Return the table line governing an edge, by the rows or columns it divides.

    `row` and `column` count from one and name the line before the edge, 0 for the
    table's top or left. A horizontal line follows the column it runs through and a
    vertical one its row, as each Gridlines tooltip names it, and a separator takes
    the edge where a header or footer meets the body.
    """
    if horizontal:
        if row in (0, rowCount):
            return tableStyle.tableOutline
        if headers.headerRows and row == headers.headerRows:
            return tableStyle.headerRowsSeparator
        if headers.footerRows and row == rowCount - headers.footerRows:
            return tableStyle.footerRowsSeparator
        if column <= headers.headerColumns:
            return tableStyle.headerColumnsHorizontalGridlines
        return tableStyle.bodyHorizontalGridlines
    if column in (0, colCount):
        return tableStyle.tableOutline
    if headers.headerColumns and column == headers.headerColumns:
        return tableStyle.headerColumnsSeparator
    if row <= headers.headerRows:
        return tableStyle.headerRowsVerticalGridlines
    if row > rowCount - headers.footerRows:
        return tableStyle.footerRowsVerticalGridlines
    return tableStyle.bodyVerticalGridlines


# The Blank theme's lines, 0.35pt black and 0.75pt where a header or footer meets
# the body, as `00-baseline` and a created document both state them.
gridlineStroke: Stroke = Stroke(
    width=Decimal("0.35"), color=Color.black, pattern=StrokeSolid()
)
separatorStroke: Stroke = Stroke(
    width=Decimal("0.75"), color=Color.black, pattern=StrokeSolid()
)
# The Blank theme's table style, every line shown, as `00-baseline` states it.
blankTableStyle: TableStyle = TableStyle(
    bodyHorizontalGridlines=TableLine(True, gridlineStroke),
    bodyVerticalGridlines=TableLine(True, gridlineStroke),
    headerRowsVerticalGridlines=TableLine(True, gridlineStroke),
    headerColumnsHorizontalGridlines=TableLine(True, gridlineStroke),
    footerRowsVerticalGridlines=TableLine(True, gridlineStroke),
    headerRowsSeparator=TableLine(True, separatorStroke),
    headerColumnsSeparator=TableLine(True, separatorStroke),
    footerRowsSeparator=TableLine(True, separatorStroke),
    tableOutline=TableLine(True, gridlineStroke),
    tableOutlineTitle=False,
)


def applyTableReset(theme: TableStyle) -> TableStyle:
    """Return a theme's table style with the reset: no body gridlines and no outline.

    As `52-table-reset-styled` encodes it, keeping the theme's own strokes.
    """
    return replace(
        theme,
        bodyHorizontalGridlines=replace(theme.bodyHorizontalGridlines, visible=False),
        bodyVerticalGridlines=replace(theme.bodyVerticalGridlines, visible=False),
        tableOutline=replace(theme.tableOutline, visible=False),
        tableOutlineTitle=False,
    )


resetTableStyle: TableStyle = applyTableReset(blankTableStyle)

# Each line's CSS name, in the order the text form writes them.
lineNames: frozendict[str, str] = frozendict({
    "table-outline": "tableOutline",
    "body-horizontal-gridlines": "bodyHorizontalGridlines",
    "body-vertical-gridlines": "bodyVerticalGridlines",
    "header-rows-vertical-gridlines": "headerRowsVerticalGridlines",
    "header-columns-horizontal-gridlines": "headerColumnsHorizontalGridlines",
    "footer-rows-vertical-gridlines": "footerRowsVerticalGridlines",
    "header-rows-separator": "headerRowsSeparator",
    "header-columns-separator": "headerColumnsSeparator",
    "footer-rows-separator": "footerRowsSeparator",
})
titleName: str = "table-outline-title"
longhandPattern: re.Pattern[str] = re.compile(r"(.+)-(width|style|color)")


def formatTableLine(line: TableLine) -> str:
    """Return a line as CSS writes a border, `hidden` before one set to none."""
    stroke = "mixed" if line.stroke is MIXED else formatStroke(
        line.stroke, tableStrokePresets
    )
    return stroke if line.visible else f"hidden {stroke}"


def formatTableStyle(tableStyle: TableStyle) -> list[str]:
    """Return each line a table draws as one CSS declaration, the outline first."""
    declarations = [
        f"{name}: {formatTableLine(getattr(tableStyle, field))}"
        for name, field in lineNames.items()
    ]
    title = "yes" if tableStyle.tableOutlineTitle else "no"
    declarations.insert(1, f"{titleName}: {title}")
    return declarations


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
        if name == titleName:
            if value not in ("yes", "no"):
                raise TableStyleError(f"{titleName} is yes or no, and is {value!r}.")
            changed = replace(changed, tableOutlineTitle=value == "yes")
            continue
        longhand = longhandPattern.fullmatch(name)
        if name in lineNames:
            field = lineNames[name]
            line = parseLineShorthand(value, getattr(changed, field), name)
        elif longhand is not None and longhand[1] in lineNames:
            field = lineNames[longhand[1]]
            line = parseLonghand(longhand[2], value, getattr(changed, field), name)
        else:
            raise TableStyleError(composeChoiceRefusal(name, "a table line", [
                *lineNames, titleName,
                *(f"{line}-{part}" for line in lineNames
                  for part in ("width", "style", "color")),
            ]))
        update: dict[str, Any] = {field: line}
        changed = replace(changed, **update)
    return changed


__all__ = [
    "TableLine", "TableStyle", "TableStyleChange", "TableStyleError",
    "buildTableStyle", "findTableLine", "formatTableLine",
    "applyTableReset", "blankTableStyle", "formatTableStyle", "gridlineStroke",
    "lineNames", "parseTableStyle",
    "resetTableStyle", "separatorStroke",
    "tableStrokePresets",
]
