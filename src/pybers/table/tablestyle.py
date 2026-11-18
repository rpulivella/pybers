#!/usr/bin/env python3
"""\
A table's lines and banding: gridlines, separators, outline, banded rows, as text.

Each region shows or hides one line drawn with one stroke, as the table's style
states them, and the outline also outlines the table's title. A cell's border
prevails over all of them at its edge. Banded rows paint every second body row
beneath any fill a cell states. See findings-06-styles.md.

UPDATES
2026-11-18  `TableBand`, a table's banded rows, and their text form, for PYB-267.
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
from typing import TYPE_CHECKING, Any

from pybers.absence import MIXED
from pybers.addressing.reference import TableReference
from pybers.color.colors import Color, ColorError, ColorSpace
from pybers.errors import PybersError, composeChoiceRefusal
from pybers.format.text import splitDeclarations
from pybers.style.fills import Fill, FillNone
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
from pybers.style.text import CellStyleError, formatFill, parseFill, parseLength
from pybers.table.headers import TableHeaders, TableRegion

if TYPE_CHECKING:
    from pybers.addressing.reference import CellAddress
    from pybers.table.cells import Table


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
class TableBand:
    """Whether a table bands its rows, and the fill it bands with, kept while off."""

    visible: bool
    fill: Fill


@dataclass(frozen=True, slots=True)
class TableStyle:
    """The lines a table draws, each region named for what it draws, and its band."""

    bodyHorizontalGridlines: TableLine
    bodyVerticalGridlines: TableLine
    headerRowsVerticalGridlines: TableLine
    headerColumnsHorizontalGridlines: TableLine
    footerRowsVerticalGridlines: TableLine
    headerRowsHorizontalGridlines: TableLine
    headerColumnsVerticalGridlines: TableLine
    footerRowsHorizontalGridlines: TableLine
    headerRowsSeparator: TableLine
    headerColumnsSeparator: TableLine
    footerRowsSeparator: TableLine
    tableOutline: TableLine
    tableTitle: bool
    tableOutlineTitle: bool
    bandedRows: TableBand


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


def buildTableStyle(
    base: TableStyle, lines: Mapping[str, object], held: TableStyle
) -> TableStyle:
    """Return a table style with lines named by field replaced, refusing any other.

    The one place a requested table style is checked, so nothing invalid is held.
    `held` is the style the table holds, whose band may be one pybers only carries.
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
        if name == "bandedRows":
            continue
        if name in flagNames.values():
            if not isinstance(value, bool):
                raise TableStyleError(
                    f"{name} is a bool, and was given {value!r}. Nothing was "
                    "written."
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
    built = replace(base, **update)
    refuseBand(built.bandedRows, held.bandedRows)
    hidden = sorted(name for name in alwaysShown if not getattr(built, name).visible)
    if hidden:
        raise TableStyleError(
            f"{hidden[0]} shows wherever its band has two lines, and no Numbers "
            "control hides it, so it takes a stroke but not none. Nothing was "
            "written."
        )
    return built


def refuseBand(value: object, held: TableBand) -> None:
    """Refuse a band that is not a visibility and a color, unless the table holds it.

    Numbers' Alternating Row Color offers only a color, so a band of another fill is
    carried where a document holds one and refused anywhere else.
    """
    if not isinstance(value, TableBand) or not isinstance(value.visible, bool):
        raise TableStyleError(
            f"bandedRows is a TableBand of a visibility and a fill, and was given "
            f"{value!r}. Nothing was written."
        )
    if isinstance(value.fill, Color) or value.fill == held.fill:
        return
    raise TableStyleError(f"{composeBandRefusal(value.fill)} Nothing was written.")


def composeBandRefusal(fill: Fill) -> str:
    """Return the sentence refusing a band of a fill other than a color.

    The one place it is worded, for a script and a command alike.
    """
    phrase = {"gradient": "a gradient", "image": "an image", "none": "no fill"}
    kind = str(getattr(fill, "fillType", ""))
    return f"Numbers cannot band rows with {phrase.get(kind, kind)}."


def findShownFill(table: Table, where: CellAddress) -> Fill:
    """Return the fill a cell displays, the one place a band meets a cell's own fill.

    A fill the cell states prevails. Every second body row, counted from the first,
    shows the band beneath a cell stating No Fill, and a header, a header column or
    a footer takes no band, as `102b-bands-on` and `103b-bands-one-header-on` show.
    Else the region's fill shows. A merge shows what its anchor shows, across every
    row it spans, as `104b-bands-merged-on` shows.
    """
    merge = table.mergeCovering(where)
    where = where if merge is None else merge.anchor
    cell = table.cells.get(where)
    stated = None if cell is None else cell.cellStyle
    own = None if stated is None else stated.background
    if own is not None and not isinstance(own, FillNone):
        return own
    band = table.tableStyle.bandedRows
    headers = table.headers
    banded = band.visible and (where.row - headers.headerRows) % 2 == 0 and (
        headers.regionFind(where, table.rowCount) is TableRegion.BODY
    )
    if banded:
        return band.fill
    return own or table._cellStyleInherited(where).background or FillNone()


def findTableLine(
    tableStyle: TableStyle, headers: TableHeaders, rowCount: int, colCount: int,
    row: int, column: int, horizontal: bool,
) -> TableLine:
    """Return the table line governing an edge, by the rows or columns it divides.

    `row` and `column` count from one and name the line before the edge, 0 for the
    table's top or left. A horizontal line follows the column it runs through and a
    vertical one its row, as each Gridlines tooltip names it, and a separator takes
    the edge where a header or footer meets the body, as
    `00-created-table-lines-set-by-pybers` and `-deep-bands-` show in Numbers 15.4.
    """
    if horizontal:
        if row in (0, rowCount):
            return tableStyle.tableOutline
        if headers.headerRows and row == headers.headerRows:
            return tableStyle.headerRowsSeparator
        if headers.footerRows and row == rowCount - headers.footerRows:
            return tableStyle.footerRowsSeparator
        # A header or footer row's own gridlines cross the header columns.
        if row < headers.headerRows:
            return tableStyle.headerRowsHorizontalGridlines
        if row > rowCount - headers.footerRows:
            return tableStyle.footerRowsHorizontalGridlines
        if column <= headers.headerColumns:
            return tableStyle.headerColumnsHorizontalGridlines
        return tableStyle.bodyHorizontalGridlines
    if column in (0, colCount):
        return tableStyle.tableOutline
    # A header or footer row's own gridlines cross the header columns' separator.
    if row <= headers.headerRows:
        return tableStyle.headerRowsVerticalGridlines
    if row > rowCount - headers.footerRows:
        return tableStyle.footerRowsVerticalGridlines
    if headers.headerColumns and column == headers.headerColumns:
        return tableStyle.headerColumnsSeparator
    if column < headers.headerColumns:
        return tableStyle.headerColumnsVerticalGridlines
    return tableStyle.bodyVerticalGridlines


# The Blank theme's lines, 0.35pt black and 0.75pt where a header or footer meets
# the body, as `00-baseline` and a created document both state them.
gridlineStroke: Stroke = Stroke(
    width=Decimal("0.35"), color=Color.black, pattern=StrokeSolid()
)
separatorStroke: Stroke = Stroke(
    width=Decimal("0.75"), color=Color.black, pattern=StrokeSolid()
)
# The Blank theme's band, off and gray, as `00-baseline` and every fixture state it.
bandGray: Color = Color(ColorSpace.SRGB, (Decimal("0.9601849"),) * 3, 1)
# The Blank theme's table style, every line shown, as `00-baseline` states it.
blankTableStyle: TableStyle = TableStyle(
    bodyHorizontalGridlines=TableLine(True, gridlineStroke),
    bodyVerticalGridlines=TableLine(True, gridlineStroke),
    headerRowsVerticalGridlines=TableLine(True, gridlineStroke),
    headerColumnsHorizontalGridlines=TableLine(True, gridlineStroke),
    footerRowsVerticalGridlines=TableLine(True, gridlineStroke),
    headerRowsHorizontalGridlines=TableLine(True, gridlineStroke),
    headerColumnsVerticalGridlines=TableLine(True, gridlineStroke),
    footerRowsHorizontalGridlines=TableLine(True, gridlineStroke),
    headerRowsSeparator=TableLine(True, separatorStroke),
    headerColumnsSeparator=TableLine(True, separatorStroke),
    footerRowsSeparator=TableLine(True, separatorStroke),
    tableOutline=TableLine(True, gridlineStroke),
    tableTitle=False,
    tableOutlineTitle=False,
    bandedRows=TableBand(False, bandGray),
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
    "header-rows-horizontal-gridlines": "headerRowsHorizontalGridlines",
    "header-columns-vertical-gridlines": "headerColumnsVerticalGridlines",
    "footer-rows-horizontal-gridlines": "footerRowsHorizontalGridlines",
    "header-rows-separator": "headerRowsSeparator",
    "header-columns-separator": "headerColumnsSeparator",
    "footer-rows-separator": "footerRowsSeparator",
})
# The lines no Numbers control hides, measured in `-deep-bands-`, so each shows.
alwaysShown: frozenset[str] = frozenset({
    "headerRowsHorizontalGridlines", "headerColumnsVerticalGridlines",
    "footerRowsHorizontalGridlines",
})
# Each setting that is yes or no rather than a line, by its CSS name.
flagNames: frozendict[str, str] = frozendict({
    "table-title": "tableTitle", "table-outline-title": "tableOutlineTitle",
})
# The band's shorthand, a fill or none, and its longhand, the fill alone.
bandName: str = "banded-rows"
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
    return [declarations[0], *flags, *declarations[1:], band]


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
        longhand = longhandPattern.fullmatch(name)
        if name in lineNames:
            field = lineNames[name]
            line = parseLineShorthand(value, getattr(changed, field), name)
        elif longhand is not None and longhand[1] in lineNames:
            field = lineNames[longhand[1]]
            line = parseLonghand(longhand[2], value, getattr(changed, field), name)
        else:
            raise TableStyleError(composeChoiceRefusal(name, "a table line", [
                *lineNames, *flagNames, bandName, bandFillName,
                *(f"{line}-{part}" for line in lineNames
                  for part in ("width", "style", "color")),
            ]))
        update: dict[str, Any] = {field: line}
        changed = replace(changed, **update)
    return changed


__all__ = [
    "TableBand", "TableLine", "TableStyle", "TableStyleChange", "TableStyleError",
    "buildTableStyle", "findShownFill", "findTableLine", "formatTableLine",
    "applyTableReset", "bandGray", "blankTableStyle", "formatTableBand",
    "formatTableStyle", "gridlineStroke",
    "lineNames", "parseTableStyle",
    "resetTableStyle", "separatorStroke",
    "tableStrokePresets",
]
