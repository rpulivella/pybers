#!/usr/bin/env python3
"""\
Compose a created document's theme and stylesheet: a preset of each kind a person adds.

Numbers fails when a person inserts a table, chart, shape, line, text box or image into
a document whose theme offers no preset for it, and a person's later actions fail on a
root style missing what Numbers states on every one of its type. Each root style states
those, from the generated `themestyles` table, every text slot names `pybers-base`, and
the table preset carries the reset. A chart preset keeps the lengths of Numbers' lists,
one style shared along each. Measured 2026-11-03 in findings-10-creation.md.

Private. The document feature's archive half, reached by document creation.

UPDATES
2026-11-03  Root styles state what Numbers always states, for PYB-261.
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

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, cast

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
from .._generated.themestyles import themeStyles
from ..table._reset import (
    applyResetCell,
    applyResetTable,
    composeBaseStyle,
    namedStyleKey,
)

# Numbers looks each up by name, and cannot read a document missing either.
drawingLineStyle: str = "drawingline-0-drawinglineStyle"
svgImportStyle: str = "svgimport-0-shapestyle"

# The lengths of the chart preset's lists in Numbers' Blank theme, kept in case a chart
# reaches an entry by position.
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


def applyStyleValues(message: Message, values: Mapping[str, object]) -> None:
    """Set a message's fields from plain data, an extension named in brackets."""
    for name, value in values.items():
        extension = name.startswith("[")
        field = (
            message.DESCRIPTOR.file.pool.FindExtensionByName(name[1:-1]) if extension
            else message.DESCRIPTOR.fields_by_name[name]
        )
        # Only a message with an extension range carries `Extensions` at all.
        extensions: Any = message.Extensions if extension else None
        if field.message_type is None and not field.is_repeated:
            if extension:
                extensions[field] = value
            else:
                setattr(message, name, value)
            continue
        target: Any = extensions[field] if extension else getattr(message, name)
        if field.message_type is None:
            target.extend(value)
        elif field.is_repeated:
            for item in cast(tuple[Mapping[str, object], ...], value):
                applyStyleValues(target.add(), item)
        else:
            target.SetInParent()
            applyStyleValues(target, cast(Mapping[str, object], value))


def composeRootStyle[StyleT: Message](
    styleClass: type[StyleT], stylesheet: int, role: str
) -> StyleT:
    """Return a root style stating what Numbers states on every one of its type."""
    style = composeStyle(styleClass, stylesheet)
    applyStyleValues(style, themeStyles[role])
    return style


def composeSheetStyle(stylesheet: int) -> tn.SheetStyleArchive:
    """Return a sheet style filled white, its tab uncolored, as Numbers writes one."""
    style = composeRootStyle(tn.SheetStyleArchive, stylesheet, "sheet")
    style.sheet_properties.fill.color.CopyFrom(
        tsp.Color(model=tsp.Color.white, w=1.0, a=1.0)
    )
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
        "list", composeRootStyle(tswp.ListStyleArchive, stylesheet, "list")
    )
    composed.baseStyle = styleAdd(
        "base",
        composeBaseStyle(namedStyleKey.format(0), stylesheet, composed.listStyle),
    )
    composed.sheetStyle = styleAdd("sheet", composeSheetStyle(stylesheet))
    for name, styleClass in (
        ("character", tswp.CharacterStyleArchive),
        ("dropcap", tswp.DropCapStyleArchive),
        ("line", tswp.ShapeStyleArchive),
        ("shape", tswp.ShapeStyleArchive),
        ("textbox", tswp.ShapeStyleArchive),
        ("tableName", tswp.ShapeStyleArchive),
        ("drawingLine", tswp.ShapeStyleArchive),
        ("svgImport", tswp.ShapeStyleArchive),
    ):
        styleAdd(name, composeStyle(styleClass, stylesheet))
    rootStyles: tuple[tuple[str, type[Message], str], ...] = (
        ("image", tsd.MediaStyleArchive, "media"),
        ("movie", tsd.MediaStyleArchive, "media"),
        ("chart", tschStyles.ChartStyleArchive, "chart"),
        ("legend", tschStyles.LegendStyleArchive, "legend"),
        ("axis", tschStyles.ChartAxisStyleArchive, "axis"),
        ("series", tschStyles.ChartSeriesStyleArchive, "series"),
        ("referenceLine", tschStyles.ReferenceLineStyleArchive, "referenceLine"),
    )
    for name, rootClass, role in rootStyles:
        styleAdd(name, composeRootStyle(rootClass, stylesheet, role))
    tableStyle = composeRootStyle(tst.TableStyleArchive, stylesheet, "table")
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
