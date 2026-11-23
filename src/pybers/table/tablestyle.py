#!/usr/bin/env python3
"""\
A table's style: its lines, its band, and the box each section's cells inherit.

Each section shows or hides one line drawn with one stroke, as the table's style
states them, and the outline also outlines the table's title. A cell's border
prevails over all of them at its edge. Banded rows paint every second body row
beneath any fill a cell states. See findings-06-styles.md.

UPDATES
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-20  The text form moved to `tablestyletext`, for PYB-291.
2026-11-20  A table style carries the box each section's cells inherit, the Blank
            theme's and the reset's, for PYB-291.
2026-11-20  `findComputedCellStyle`, the box a cell displays, beside
            `findComputedFill`, for PYB-291.
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

from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pybers.absence import MIXED
from pybers.addressing.reference import TableReference
from pybers.color.colors import Color, ColorSpace
from pybers.errors import (
    PybersError,
    composeChoiceRefusal,
    composeRefusal,
    nothingWritten,
)
from pybers.style.cells import (
    CellStyle,
    CellStyleProperty,
    createdCellStyle,
    findCellStyleRefusal,
    numbersCellStyle,
    updateCellStyles,
)
from pybers.style.fills import Fill, FillNone
from pybers.style.strokes import (
    Stroke,
    StrokeCap,
    StrokeDash,
    StrokeJoin,
    StrokePresets,
    StrokeSolid,
)
from pybers.table.headers import TableHeaders, TableSection, formatHeaderName

if TYPE_CHECKING:
    from pybers.addressing.reference import CellAddress
    from pybers.table.cells import Table


class TableStyleError(PybersError, ValueError):
    """A table style's text form specifies a line or a value a table lacks."""


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
    """A table's lines, its band, and the box each section's cells inherit."""

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
    bodyCellStyle: CellStyle
    headerRowsCellStyle: CellStyle
    headerColumnsCellStyle: CellStyle
    footerRowsCellStyle: CellStyle


# The field holding each section's box, the one its cells inherit.
sectionCellStyleFields: frozendict[TableSection, str] = frozendict({
    TableSection.BODY: "bodyCellStyle",
    TableSection.HEADER_ROW: "headerRowsCellStyle",
    TableSection.HEADER_COLUMN: "headerColumnsCellStyle",
    TableSection.FOOTER_ROW: "footerRowsCellStyle",
})


@dataclass(frozen=True, slots=True)
class TableStyleChange:
    """What setting a table's style did: the style it held before and after."""

    reference: TableReference
    before: TableStyle
    after: TableStyle

    @property
    def changed(self) -> bool:
        """Report whether any line, flag, band or section box differs."""
        return self.before != self.after


def buildTableStyle(
    base: TableStyle, parts: Mapping[str, object], held: TableStyle
) -> TableStyle:
    """Return a table style with the parts given by field replaced, refusing any other.

    The one place a requested table style is checked, so nothing invalid is held.
    `held` is the style the table holds, whose band may be one pybers only carries.
    """
    if not isinstance(base, TableStyle):
        raise TableStyleError(composeRefusal(
            f"The table style {type(base).__name__}", "is not a TableStyle",
            notDone=nothingWritten,
        ))
    names = [each.name for each in fields(TableStyle)]
    for name, value in parts.items():
        if name not in names:
            raise composeChoiceRefusal(
                TableStyleError, name, "a table style field", names, nothingWritten
            )
        if name == "bandedRows" or name in sectionCellStyleFields.values():
            continue
        if name in flagNames.values():
            if not isinstance(value, bool):
                raise TableStyleError(composeRefusal(
                    f"The {name} {value!r}", "is not a bool", notDone=nothingWritten
                ))
            continue
        if not isinstance(value, TableLine) or not isinstance(value.visible, bool) or (
            not isinstance(value.stroke, Stroke)
            and value.stroke is not getattr(base, name).stroke
        ):
            raise TableStyleError(composeRefusal(
                f"The {name} {value!r}", "is not a TableLine of a visibility and a "
                "Stroke", notDone=nothingWritten,
            ))
    update: dict[str, Any] = dict(parts)
    built = replace(base, **update)
    refuseBand(built.bandedRows, held.bandedRows)
    refuseSectionBoxes(built, held)
    hidden = sorted(name for name in alwaysShown if not getattr(built, name).visible)
    if hidden:
        raise TableStyleError(composeRefusal(
            f"The {formatHeaderName(hidden[0])}", "cannot be hidden, since they show "
            "wherever their band has two lines and no Numbers control hides them",
            "Give them a stroke", nothingWritten,
        ))
    return built


def refuseSectionBoxes(built: TableStyle, held: TableStyle) -> None:
    """Refuse a section box that states less than every property or cannot be written.

    A box the table already holds is carried as it is, a fill pybers only reads
    included.
    """
    for field in sectionCellStyleFields.values():
        box = getattr(built, field)
        if box == getattr(held, field):
            continue
        if not isinstance(box, CellStyle) or None in (
            getattr(box, each.fieldName) for each in CellStyleProperty
        ):
            raise TableStyleError(composeRefusal(
                f"The {field} {box!r}", "is not a CellStyle stating every property",
                notDone=nothingWritten,
            ))
        refusal = findCellStyleRefusal(box, nothingWritten)
        if refusal is not None:
            raise TableStyleError(refusal)


def refuseBand(value: object, held: TableBand) -> None:
    """Refuse a band that is not a visibility and a color, unless the table holds it.

    Numbers' Alternating Row Color offers only a color, so a band of another fill is
    carried where a document holds one and refused anywhere else.
    """
    if not isinstance(value, TableBand) or not isinstance(value.visible, bool):
        raise TableStyleError(composeRefusal(
            f"The bandedRows {value!r}", "is not a TableBand of a visibility and a "
            "fill", notDone=nothingWritten,
        ))
    if isinstance(value.fill, Color) or value.fill == held.fill:
        return
    raise TableStyleError(composeBandRefusal(value.fill, nothingWritten))


def composeBandRefusal(fill: Fill, notDone: str | None = None) -> str:
    """Return the refusal of a band of a fill other than a color.

    The one place it is worded, for a script and a command alike.
    """
    place = {
        "gradient": "A gradient band", "image": "An image band",
        "none": "A band with no fill",
    }
    kind = str(getattr(fill, "fillType", ""))
    return composeRefusal(
        place.get(kind, f"A band of {kind}"), "is not one Numbers draws, since it "
        "bands rows with a color alone", "Give the band a color", notDone,
    )


def findComputedCellStyle(table: Table, where: CellAddress) -> CellStyle:
    """Return the box a cell displays, its own style over its section's.

    The fill is the one `findComputedFill` decides, so a band shows, and a merge shows
    what its anchor shows.
    """
    merge = table.mergeFind(where)
    where = where if merge is None else merge.anchor
    cell = table.cells.get(where)
    inherited = table._cellStyleInherited(where)
    own = None if cell is None else cell.cellStyle
    resolved = inherited if own is None else updateCellStyles(own, inherited)
    return replace(resolved, background=findComputedFill(table, where))


def findComputedFill(table: Table, where: CellAddress) -> Fill:
    """Return the fill a cell displays, the one place a band meets a cell's own fill.

    A fill the cell states prevails. Every second body row, counted from the first,
    shows the band beneath a cell stating No Fill, and a header, a header column or
    a footer takes no band, as `102b-bands-on` and `103b-bands-one-header-on` show.
    Else the section's fill shows. A merge shows what its anchor shows, across every
    row it spans, as `104b-bands-merged-on` shows.
    """
    merge = table.mergeFind(where)
    where = where if merge is None else merge.anchor
    cell = table.cells.get(where)
    stated = None if cell is None else cell.cellStyle
    own = None if stated is None else stated.background
    if own is not None and not isinstance(own, FillNone):
        return own
    band = table.tableStyle.bandedRows
    headers = table.headers
    banded = band.visible and (where.row - headers.headerRows) % 2 == 0 and (
        headers.sectionFind(where, table.rowCount) is TableSection.BODY
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
    vertical one its row, as each Gridlines tooltip labels it, and a separator takes
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
# The Blank theme's header fills, as `00-baseline` states them.
headerRowsGray: Color = Color(
    ColorSpace.SRGB,
    (Decimal("0.74361324"), Decimal("0.7537804"), Decimal("0.7506917")), 1,
)
headerColumnsGray: Color = Color(ColorSpace.SRGB, (Decimal("0.8624049"),) * 3, 1)
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
    bodyCellStyle=numbersCellStyle,
    headerRowsCellStyle=replace(numbersCellStyle, background=headerRowsGray),
    headerColumnsCellStyle=replace(numbersCellStyle, background=headerColumnsGray),
    footerRowsCellStyle=numbersCellStyle,
)


def applyTableReset(theme: TableStyle) -> TableStyle:
    """Return a theme's table style with the reset: no body gridlines, outline or wrap.

    As `52-table-reset-styled` encodes it, keeping the theme's own strokes.
    """
    return replace(
        theme,
        bodyCellStyle=createdCellStyle,
        headerRowsCellStyle=createdCellStyle,
        headerColumnsCellStyle=createdCellStyle,
        footerRowsCellStyle=createdCellStyle,
        bodyHorizontalGridlines=replace(theme.bodyHorizontalGridlines, visible=False),
        bodyVerticalGridlines=replace(theme.bodyVerticalGridlines, visible=False),
        tableOutline=replace(theme.tableOutline, visible=False),
        tableOutlineTitle=False,
    )


resetTableStyle: TableStyle = applyTableReset(blankTableStyle)

# The lines no Numbers control hides, measured in `-deep-bands-`, so each shows.
alwaysShown: frozenset[str] = frozenset({
    "headerRowsHorizontalGridlines", "headerColumnsVerticalGridlines",
    "footerRowsHorizontalGridlines",
})
# Each setting that is yes or no rather than a line, by its CSS name.
flagNames: frozendict[str, str] = frozendict({
    "table-title": "tableTitle", "table-outline-title": "tableOutlineTitle",
})


__all__ = [
    "TableBand", "TableLine", "TableStyle", "TableStyleChange", "TableStyleError",
    "alwaysShown", "applyTableReset", "bandGray", "blankTableStyle", "buildTableStyle",
    "composeBandRefusal", "findComputedCellStyle", "findComputedFill", "findTableLine",
    "flagNames", "gridlineStroke", "resetTableStyle", "sectionCellStyleFields",
    "separatorStroke", "tableStrokePresets",
]
