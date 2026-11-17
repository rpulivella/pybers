#!/usr/bin/env python3
"""\
Compose a created document's theme and stylesheet: a preset of each kind a person adds.

Numbers fails when a person inserts a table, chart, shape, line, text box or image into
a document whose theme offers no preset for it, and a person's later actions fail on a
root style missing what Numbers states on every one of its type. Each root style states
those, from the generated `themestyles` table, every table text slot names
`pybers-base`, and the table preset carries the reset. A chart preset keeps the lengths
of Numbers' lists, one style shared along each, its text its own. Every style Numbers
looks up by key is composed, so Numbers adds and rewrites no style on opening one.
Measured 2026-11-03 and 2026-11-16 in findings-10-creation.md.

Private. The document feature's archive half, reached by document creation.

UPDATES
2026-11-17  The table preset's table style states the model's reset, for PYB-266.
2026-11-16  Composes every style Numbers looks up by key, the chart's text of its own,
            and the presets and flags Numbers adds on opening, for PYB-292.
2026-11-13  The cell style states the whole box a created table shows, as each
            root cell style Numbers writes does, for PYB-265.
2026-11-06  The palette and the sheet's fill are `Color` values in sRGB, as Numbers
            stores them, for PYB-264.
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

import uuid
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
from .._generated.themestyles import drawablePresets, keyedStyles, themeStyles
from .._persistence.types import archiveTypes
from ..color._archive import composeColor
from ..color.colors import Color, ColorSpace
from ..style._write import composeCellProperties, composeCellStyleArchive
from ..table._reset import (
    composeBaseStyle,
    composeResetText,
    namedStyleKey,
)
from ..table._tablestyle import applyTableStyle
from ..table.cells import createdCellStyle
from ..table.tablestyle import resetTableStyle

# Numbers looks each up by name, and cannot read a document missing either.
drawingLineStyle: str = "drawingline-0-drawinglineStyle"
svgImportStyle: str = "svgimport-0-shapestyle"
# Keyed styles a created theme's presets name, from the generated `keyedStyles`.
listStyleKey: str = "text-0-liststyle-None"
sheetStyleKey: str = "sheet-0-sheetStyle"
dropCapStyleKey: str = "drop-cap-style-default"
defaultParagraphKey: str = "paragraph-style-default"

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


def composeKeyedStyle(
    key: str, stylesheet: int, styleIds: Mapping[str, int], baseStyle: int
) -> Message:
    """Return a style Numbers looks up by key, valued as the Blank theme's.

    A reference to a style no created theme holds names `pybers-base`, as Numbers
    chose when it composed these styles itself, findings-10-creation.md.
    """
    entry = keyedStyles[key]
    style = composeStyle(archiveTypes[cast(int, entry["type"])], stylesheet)
    applyStyleValues(style, cast(Mapping[str, object], entry["values"]))
    if key == defaultParagraphKey:
        # Numbers clears it on opening, measured 2026-11-16.
        paragraph = cast(tswp.ParagraphStyleArchive, style)
        paragraph.para_properties.show_in_bookmarks_list = False
    references = cast(tuple[tuple[tuple[str, ...], str], ...], entry["references"])
    for path, target in references:
        holder: Any = style
        for name in path:
            holder = getattr(holder, name)
        holder.identifier = styleIds.get(target, baseStyle)
    return style


def composeChartText(stylesheet: int, listStyle: int) -> tswp.ParagraphStyleArchive:
    """Return the reset's text centered, out of bookmarks, as Numbers sets chart text.

    Numbers rewrites the text style a chart preset names on opening a document, so a
    chart sharing `pybers-base` centered every table, findings-10-creation.md.
    """
    style = composeResetText(stylesheet, listStyle)
    style.para_properties.alignment = tswp.ParagraphStylePropertiesArchive.TATvalue2
    style.para_properties.show_in_bookmarks_list = False
    return style


def composeThemeColor(hue: str, toward: float, amount: float) -> Color:
    """Return an sRGB color mixed from a hex hue toward white (1) or black (0)."""
    channels = (int(hue[start:start + 2], 16) / 255 for start in range(0, 6, 2))
    mixed = tuple(each + (toward - each) * amount for each in channels)
    return Color(ColorSpace.SRGB, mixed, 1.0)


def listThemeColors() -> list[Color]:
    """Return the pybers palette: six grays, then each hue light, as is and dark."""
    grays = [Color.gray(level, 1.0) for level in themeGrays]
    tones = ((1.0, themeTintToWhite), (0.0, 0.0), (0.0, themeShadeToBlack))
    return grays + [
        composeThemeColor(hue, toward, amount)
        for toward, amount in tones for hue in themeHues
    ]


def composeColorSlots(theme: tn.ThemeArchive) -> None:
    """Fill a theme's 30 color slots with the pybers palette."""
    theme.super.color_presets.extend(composeColor(each) for each in listThemeColors())


def composeTableNetwork(
    tableStyle: int, cellStyle: int, textStyle: int, nameShapeStyle: int
) -> tst.TableStyleNetworkArchive:
    """Return a network naming one table, one cell and one text style in every slot."""
    network = tst.TableStyleNetworkArchive(preset_id=0)
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
    preset = tsch.ChartStylePreset(uuid=uuid.uuid4().bytes)
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
    # Keyed styles name one another, so each is numbered before any is composed.
    for key in keyedStyles:
        styleIds[key] = next(identifiers)
    composed.listStyle = styleIds[listStyleKey]
    composed.sheetStyle = styleIds[sheetStyleKey]
    composed.baseStyle = styleAdd(
        "base",
        composeBaseStyle(namedStyleKey.format(0), stylesheet, composed.listStyle),
    )
    composed.styles += [
        (styleIds[key],
         composeKeyedStyle(key, stylesheet, styleIds, composed.baseStyle))
        for key in keyedStyles
    ]
    styleAdd("chartText", composeChartText(stylesheet, composed.listStyle))
    for name, styleClass in (
        ("character", tswp.CharacterStyleArchive),
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
    applyTableStyle(tableStyle.table_properties, resetTableStyle)
    styleAdd("table", tableStyle)
    styleAdd("cell", composeCellStyleArchive(stylesheet, composeCellProperties(
        createdCellStyle, tstStyles.CellStylePropertiesArchive()
    )))

    sheet = tss.StylesheetArchive(is_locked=False, can_cull_styles=True)
    # Numbers keeps the list in identifier order and the maps in key order.
    for identifier, _ in sorted(composed.styles, key=lambda each: each[0]):
        sheet.styles.add(identifier=identifier)
    styleIds |= {drawingLineStyle: styleIds["drawingLine"],
                 svgImportStyle: styleIds["svgImport"],
                 namedStyleKey.format(0): composed.baseStyle}
    maps = {key: "identifier_to_style_map"
            for key in (drawingLineStyle, svgImportStyle, namedStyleKey.format(0))}
    maps |= {key: cast(str, entry["map"])
             for key, entry in keyedStyles.items() if entry["map"] is not None}
    for key in sorted(maps):
        holder: Any = sheet
        if maps[key] != "identifier_to_style_map":
            holder = getattr(sheet, maps[key])
            holder.styles.add(identifier=styleIds[key])
        holder.identifier_to_style_map.add(identifier=key).style.identifier = (
            styleIds[key]
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
            styleIds["referenceLine"], styleIds["chartText"],
        )),
    ]

    theme = tn.ThemeArchive()
    theme.super.document_stylesheet.identifier = stylesheet
    composeColorSlots(theme)
    drawables = theme.super.Extensions[tsd.ThemePresetsArchive.extension]
    applyStyleValues(drawables, drawablePresets)
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
    text.dropcap_style_presets.add(identifier=styleIds[dropCapStyleKey])
    theme.super.Extensions[tsch.ChartPresetsArchive.extension].chart_presets.add(
        identifier=chartPreset
    )
    theme.super.Extensions[tstStyles.ThemePresetsArchive.extension].table_style_presets.add(
        identifier=tablePreset
    )
    numbersPresets = theme.super.Extensions[tsa.ThemePresetsArchive.extension]
    numbersPresets.caption_style_presets.add(identifier=composed.baseStyle)
    numbersPresets.svg_import_style_presets.add(identifier=styleIds["svgImport"])
    composed.document.insert(0, (composed.theme, theme))
    return composed


__all__ = ["ComposedTheme", "composeTheme"]
