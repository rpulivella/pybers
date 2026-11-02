#!/usr/bin/env python3
"""\
Compose a created document's theme and stylesheet: a preset of each kind a person adds.

Numbers fails when a person inserts a table, chart, shape, line, text box or image into
a document whose theme offers no preset for it, and reads nothing else from a preset
but its references. Each preset is therefore a skeleton naming its styles, every text
slot names `pybers-base`, and the table preset carries the reset. A chart preset keeps
the lengths of Numbers' lists, one style shared along each. Measured 2026-11-02 in
findings-10-creation.md. See docs/decisions.md.

Private. The document feature's archive half, reached by document creation.

UPDATES
2026-11-02  Written for PYB-261.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/02"

from collections.abc import Iterator
from dataclasses import dataclass, field

from google.protobuf.message import Message

from .._generated import TNArchives_pb2 as tn
from .._generated import TSAArchives_pb2 as tsa
from .._generated import TSCHArchives_Common_pb2 as tschStyles
from .._generated import TSCHArchives_pb2 as tsch
from .._generated import TSDArchives_pb2 as tsd
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSSArchives_pb2 as tss
from .._generated import TSTArchives_pb2 as tst
from .._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from .._generated import TSWPArchives_pb2 as tswp
from ..table._reset import (
    applyResetCell,
    applyResetTable,
    composeBaseStyle,
    namedStyleKey,
)

# Numbers looks each up by name, and cannot read a document missing either.
drawingLineStyle: str = "drawingline-0-drawinglineStyle"
svgImportStyle: str = "svgimport-0-shapestyle"

# The lengths of the chart preset's lists in Numbers' Blank theme, kept so a chart
# reaching an entry by position finds one.
chartValueAxes: int = 2
chartCategoryAxes: int = 1
chartSeries: int = 6
chartParagraphs: int = 30

# The palette a created theme offers, see docs/decisions.md: six grays, then each hue
# light, as is and dark. Numbers refuses fewer than 27 slots.
themeGrays: tuple[float, ...] = (1.0, 0.9, 0.7, 0.5, 0.3, 0.0)
themeHues: tuple[str, ...] = (
    "C8553D", "D98E32", "D8B43A", "5E9E6E", "2F8F8C", "3F6FB5", "7A5BA6", "C4577E",
)
themeTintToWhite: float = 0.6
themeShadeToBlack: float = 0.3


@dataclass
class ComposedTheme:
    """A created theme's archives, by member, and the styles a created sheet names."""

    stylesheet: int
    theme: int
    sheetStyle: int
    baseStyle: int
    listStyle: int
    document: list[tuple[int, Message]] = field(default_factory=list)
    styles: list[tuple[int, Message]] = field(default_factory=list)


def composeStyle[StyleT: Message](styleClass: type[StyleT], stylesheet: int) -> StyleT:
    """Return a style naming its stylesheet and nothing else, at any depth."""
    style = styleClass()
    holder: Message = style
    while holder.DESCRIPTOR.full_name != "TSS.StyleArchive":
        holder = holder.super  # type: ignore[attr-defined]
    holder.stylesheet.identifier = stylesheet  # type: ignore[attr-defined]
    return style


def composeThemeColor(hue: str, toward: float, amount: float) -> tsp.Color:
    """Return an sRGB color mixed from a hex hue toward white (1) or black (0)."""
    red, green, blue = (
        int(hue[start:start + 2], 16) / 255 for start in range(0, 6, 2)
    )
    return tsp.Color(
        model=tsp.Color.rgb,
        r=red + (toward - red) * amount,
        g=green + (toward - green) * amount,
        b=blue + (toward - blue) * amount,
        a=1.0,
        rgbspace=tsp.Color.srgb,
    )


def composeColorSlots(theme: tn.ThemeArchive) -> None:
    """Fill a theme's 30 color slots with the pybers palette."""
    slots = theme.super.color_presets
    for level in themeGrays:
        slots.add(model=tsp.Color.white, w=level, a=1.0)
    tones = ((1.0, themeTintToWhite), (0.0, 0.0), (0.0, themeShadeToBlack))
    for toward, amount in tones:
        slots.extend(composeThemeColor(hue, toward, amount) for hue in themeHues)


def composeTableNetwork(
    tableStyle: int, cellStyle: int, textStyle: int, nameShapeStyle: int
) -> tst.TableStyleNetworkArchive:
    """Return a network naming one table, one cell and one text style in every slot."""
    network = tst.TableStyleNetworkArchive()
    for slot in tst.TableStyleNetworkArchive.DESCRIPTOR.fields:
        if slot.message_type is None:
            continue
        if slot.name == "table_style":
            target = tableStyle
        elif slot.name == "table_name_shape_style":
            target = nameShapeStyle
        elif slot.name.endswith("_text_style") or slot.name == "table_name_style":
            target = textStyle
        else:
            target = cellStyle
        getattr(network, slot.name).identifier = target
    return network


def composeChartPreset(
    chart: int, legend: int, axis: int, series: int, referenceLine: int, text: int
) -> tsch.ChartStylePreset:
    """Return a chart preset with Numbers' list lengths, one style shared along each."""
    preset = tsch.ChartStylePreset()
    preset.chart_style.identifier = chart
    preset.legend_style.identifier = legend
    for target, count, style in (
        (preset.value_axis_styles, chartValueAxes, axis),
        (preset.category_axis_styles, chartCategoryAxes, axis),
        (preset.series_styles, chartSeries, series),
        (preset.paragraph_styles, chartParagraphs, text),
    ):
        for _ in range(count):
            target.add(identifier=style)
    lines = preset.Extensions[tsch.preset_reference_line_styles]
    lines.reference_line_styles.add(identifier=referenceLine)
    return preset


def composeTheme(identifiers: Iterator[int]) -> ComposedTheme:
    """Return a theme of 30 color slots and one preset of each kind, with its styles."""
    stylesheet = next(identifiers)
    styleIds: dict[str, int] = {}

    def styleAdd(name: str, body: Message) -> int:
        identifier = next(identifiers)
        styleIds[name] = identifier
        composed.styles.append((identifier, body))
        return identifier

    composed = ComposedTheme(
        stylesheet=stylesheet, theme=next(identifiers), sheetStyle=0, baseStyle=0,
        listStyle=0,
    )
    composed.listStyle = styleAdd(
        "list", composeStyle(tswp.ListStyleArchive, stylesheet)
    )
    composed.baseStyle = styleAdd(
        "base",
        composeBaseStyle(namedStyleKey.format(0), stylesheet, composed.listStyle),
    )
    composed.sheetStyle = styleAdd(
        "sheet", composeStyle(tn.SheetStyleArchive, stylesheet)
    )
    for name, styleClass in (
        ("character", tswp.CharacterStyleArchive),
        ("dropcap", tswp.DropCapStyleArchive),
        ("image", tsd.MediaStyleArchive),
        ("movie", tsd.MediaStyleArchive),
        ("line", tswp.ShapeStyleArchive),
        ("shape", tswp.ShapeStyleArchive),
        ("textbox", tswp.ShapeStyleArchive),
        ("tableName", tswp.ShapeStyleArchive),
        ("drawingLine", tswp.ShapeStyleArchive),
        ("svgImport", tswp.ShapeStyleArchive),
        ("chart", tschStyles.ChartStyleArchive),
        ("legend", tschStyles.LegendStyleArchive),
        ("axis", tschStyles.ChartAxisStyleArchive),
        ("series", tschStyles.ChartSeriesStyleArchive),
        ("referenceLine", tschStyles.ReferenceLineStyleArchive),
    ):
        styleAdd(name, composeStyle(styleClass, stylesheet))
    tableStyle = composeStyle(tst.TableStyleArchive, stylesheet)
    applyResetTable(tableStyle)
    styleAdd("table", tableStyle)
    cellStyle = composeStyle(tst.CellStyleArchive, stylesheet)
    applyResetCell(cellStyle)
    styleAdd("cell", cellStyle)

    sheet = tss.StylesheetArchive(is_locked=False)
    for identifier, _ in composed.styles:
        sheet.styles.add(identifier=identifier)
    for key, name in (
        (drawingLineStyle, "drawingLine"), (svgImportStyle, "svgImport"),
        (namedStyleKey.format(0), "base"),
    ):
        sheet.identifier_to_style_map.add(identifier=key).style.identifier = (
            styleIds[name]
        )
    composed.styles.insert(0, (stylesheet, sheet))

    network = next(identifiers)
    tablePreset = next(identifiers)
    chartPreset = next(identifiers)
    composed.document += [
        (network, composeTableNetwork(
            styleIds["table"], styleIds["cell"], composed.baseStyle,
            styleIds["tableName"],
        )),
        (tablePreset, tstStyles.TableStylePresetArchive(
            style_network=tsp.Reference(identifier=network)
        )),
        (chartPreset, composeChartPreset(
            styleIds["chart"], styleIds["legend"], styleIds["axis"], styleIds["series"],
            styleIds["referenceLine"], composed.baseStyle,
        )),
    ]

    theme = tn.ThemeArchive()
    theme.super.document_stylesheet.identifier = stylesheet
    composeColorSlots(theme)
    drawables = theme.super.Extensions[tsd.ThemePresetsArchive.extension]
    for presets, name in (
        (drawables.line_style_presets, "line"),
        (drawables.shape_style_presets, "shape"),
        (drawables.textbox_style_presets, "textbox"),
        (drawables.image_style_presets, "image"),
        (drawables.movie_style_presets, "movie"),
        (drawables.drawing_line_style_presets, "drawingLine"),
    ):
        presets.add(identifier=styleIds[name])
    text = theme.super.Extensions[tswp.ThemePresetsArchive.extension]
    text.list_style_presets.add(identifier=composed.listStyle)
    text.character_style_presets.add(identifier=styleIds["character"])
    text.paragraph_style_presets.add(identifier=composed.baseStyle)
    text.dropcap_style_presets.add(identifier=styleIds["dropcap"])
    theme.super.Extensions[tsch.ChartPresetsArchive.extension].chart_presets.add(
        identifier=chartPreset
    )
    theme.super.Extensions[tstStyles.ThemePresetsArchive.extension].table_style_presets.add(
        identifier=tablePreset
    )
    theme.super.Extensions[tsa.ThemePresetsArchive.extension].caption_style_presets.add(
        identifier=composed.baseStyle
    )
    composed.document.insert(0, (composed.theme, theme))
    return composed


__all__ = ["ComposedTheme", "composeTheme"]
