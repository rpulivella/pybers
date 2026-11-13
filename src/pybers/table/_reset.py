#!/usr/bin/env python3
"""\
The reset's styles, which every text, cell and table slot of a created table names.

The table style and the cell style are variations of the theme's first table style
preset, written as `52-table-reset-styled` wrote them, and every text slot names
`pybers-base`, the named paragraph style of `53-paragraph-style-named`, created once
per document and found again by name. See docs/decisions.md.

Private. Part of the table feature's archive half, reached by table creation.

UPDATES
2026-11-12  Styles registered through the style feature's `addStyles`, and the reset's
            cell style composed from a `CellStyle`, for PYB-265.
2026-11-06  Black comes from `Color`, for PYB-264.
2026-11-02  The reset's table and cell properties applied in one place each, which a
            created theme's table preset shares, for PYB-261.
2026-11-02  Each style is composed field by field rather than copied from a
            template, for PYB-276.
2026-09-22  Split out of table creation for PYB-113.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/14"

from dataclasses import dataclass

from google.protobuf.message import Message

from .._generated import TNArchives_pb2 as tn
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSSArchives_pb2 as tss
from .._generated import TSTArchives_pb2 as tst
from .._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from .._generated import TSWPArchives_pb2 as tswp
from .._persistence.index import ArchiveIndex, findRoot
from .._persistence.metadata import PackageRegistry
from .._persistence.types import findArchiveTypeId, readArchiveTypeId
from ..color._archive import composeColor
from ..color.colors import Color
from ..errors import WriteError
from ..style._write import addStyles, composeCellProperties
from .cells import resetCellStyle

baseStyleName: str = "pybers-base"
namedStyleKey: str = "text-{}-paragraphstyle"

# The properties each variation overrides, as `52-table-reset-styled` counted them.
tableStyleOverrides: int = 3
cellStyleOverrides: int = 1
baseStyleOverrides: int = 57

character = tswp.CharacterStylePropertiesArchive
paragraph = tswp.ParagraphStylePropertiesArchive


@dataclass(frozen=True, slots=True)
class DocumentStyles:
    """The theme's first table style preset, its network, and its stylesheet."""

    preset: int
    network: tst.TableStyleNetworkArchive
    stylesheet: int


@dataclass(frozen=True, slots=True)
class ResetStyles:
    """The three styles every text, cell and table slot of a created table names."""

    tableStyle: int
    cellStyle: int
    textStyle: int


def findTheme(index: ArchiveIndex) -> tuple[int, tn.ThemeArchive]:
    """Return the document's theme archive and its identifier."""
    root = findRoot(index)
    return root.theme.identifier, index.resolve(root.theme, tn.ThemeArchive)


def findDocumentStyles(index: ArchiveIndex) -> DocumentStyles:
    """Return the theme's first table style preset and the network it names."""
    _, theme = findTheme(index)
    presets = theme.super.Extensions[tstStyles.ThemePresetsArchive.extension]
    if not presets.table_style_presets:
        raise WriteError("This document's theme carries no table style preset.")
    presetReference = presets.table_style_presets[0]
    preset = index.resolve(presetReference, tstStyles.TableStylePresetArchive)
    network = index.resolve(preset.style_network, tst.TableStyleNetworkArchive)
    stylesheet = index.resolve(network.table_style, tst.TableStyleArchive)
    return DocumentStyles(
        preset=presetReference.identifier,
        network=network,
        stylesheet=stylesheet.super.stylesheet.identifier,
    )


def findNamedStyle(index: ArchiveIndex, stylesheetId: int) -> int | None:
    """Return the `pybers-base` paragraph style this document already holds, if any."""
    stylesheet = index.resolve(
        tsp.Reference(identifier=stylesheetId), tss.StylesheetArchive
    )
    for reference in stylesheet.styles:
        archive = index.byIdentifier.get(reference.identifier)
        if archive is None or readArchiveTypeId(archive) != findArchiveTypeId(
            tswp.ParagraphStyleArchive
        ):
            continue
        style = index.resolve(reference, tswp.ParagraphStyleArchive)
        if style.super.name == baseStyleName:
            return int(reference.identifier)
    return None


def applyResetTable(style: tst.TableStyleArchive) -> None:
    """Give a table style the reset's properties: no strokes and no border."""
    properties = style.table_properties
    properties.v_strokes_visible = False
    properties.h_strokes_visible = False
    properties.table_border_visible = False


def applyResetCell(style: tst.CellStyleArchive) -> None:
    """Give a cell style the reset's properties: text that does not wrap."""
    style.cell_properties.MergeFrom(
        composeCellProperties(resetCellStyle, tstStyles.CellStylePropertiesArchive())
    )


def composeTableStyle(parent: int, stylesheet: int) -> tst.TableStyleArchive:
    """Return the reset's table style, a variation of a theme's table style."""
    style = tst.TableStyleArchive(override_count=tableStyleOverrides)
    style.super.parent.identifier = parent
    style.super.is_variation = True
    style.super.stylesheet.identifier = stylesheet
    applyResetTable(style)
    return style


def composeCellStyle(parent: int, stylesheet: int) -> tst.CellStyleArchive:
    """Return the reset's cell style, a variation of a theme's cell style."""
    style = tst.CellStyleArchive(override_count=cellStyleOverrides)
    style.super.parent.identifier = parent
    style.super.is_variation = True
    style.super.stylesheet.identifier = stylesheet
    applyResetCell(style)
    return style


def composeBaseStyle(
    key: str, stylesheet: int, listStyle: int
) -> tswp.ParagraphStyleArchive:
    """Return `pybers-base`: Avenir Next 11 pt on exact 15.5 pt lines.

    Numbers resolves every property of a named root style, so all 57 are stated, as
    `53-paragraph-style-named` holds them. See docs/decisions.md.
    """
    style = tswp.ParagraphStyleArchive()
    style.super.name = baseStyleName
    style.super.style_identifier = key
    style.super.stylesheet.identifier = stylesheet
    chars = style.char_properties
    chars.bold = False
    chars.italic = False
    chars.font_size = 11.0
    chars.font_name = "AvenirNext-Regular"
    chars.font_color.CopyFrom(composeColor(Color.black))
    chars.language_null = True
    chars.superscript = character.kNoScript
    chars.underline = character.kNoUnderline
    chars.strikethru = character.kNoStrikethru
    chars.capitalization = character.kNoCaps
    chars.baseline_shift = 0.0
    chars.kerning = 0.0
    chars.ligatures = character.kStandardLigatures
    chars.shadow_null = True
    chars.strikethru_color_null = True
    chars.strikethru_width = 1.0
    chars.background_color_null = True
    chars.tracking = 0.0
    chars.underline_color_null = True
    chars.underline_width = 1.0
    chars.word_strikethru = False
    chars.word_underline = False
    chars.font_features_null = True
    chars.writing_direction = tswp.kWritingDirectionNatural
    chars.emphasis_marks_null = True
    chars.compatibility_font_name_null = True
    chars.is_named_point_size = False
    chars.capitalization_uses_linguistics = False
    chars.tsd_stroke_null = True
    chars.tsd_fill.color.CopyFrom(composeColor(Color.black))
    chars.tsd_fill_should_fill_text_container = False
    paras = style.para_properties
    paras.alignment = paragraph.TATvalue4
    paras.decimal_tab = "."
    paras.default_tab_stops = 36.0
    paras.fill_null = True
    paras.first_line_indent = 0.0
    paras.hyphenate = True
    paras.keep_lines_together = False
    paras.keep_with_next = False
    paras.left_indent = 0.0
    paras.line_spacing.mode = tswp.LineSpacingArchive.kExactLineSpacing
    paras.line_spacing.amount = 15.5
    paras.page_break_before = False
    paras.deprecated_borders = paragraph.PBTvalue0
    paras.historical_rule_offset.x = 0.0
    paras.historical_rule_offset.y = 0.0
    paras.rule_width = 1.0
    paras.right_indent = 0.0
    paras.space_after = 0.0
    paras.space_before = 0.0
    paras.tabs.SetInParent()
    paras.widow_control = True
    paras.outline_level = 0xFFFFFFFF
    paras.outline_style = paragraph.OSTvalue0
    paras.stroke_null = True
    paras.list_style.identifier = listStyle
    paras.following_style_null = True
    paras.show_in_bookmarks_list = True
    paras.show_in_toc_navigator = False
    paras.border_positions = 0
    paras.rounded_corners = False
    style.override_count = baseStyleOverrides
    return style


def createResetStyles(
    index: ArchiveIndex, registry: PackageRegistry, styles: DocumentStyles
) -> ResetStyles:
    """Create the reset's two variations, and `pybers-base` unless it exists."""
    network = styles.network
    stylesheet = index.resolve(
        tsp.Reference(identifier=styles.stylesheet), tss.StylesheetArchive
    )
    existing = findNamedStyle(index, styles.stylesheet)
    created: list[tuple[int, Message]] = [
        (registry.identifierAllocate(), body) for body in (
            composeTableStyle(network.table_style.identifier, styles.stylesheet),
            composeCellStyle(network.body_cell_style.identifier, styles.stylesheet),
        )
    ]
    if existing is None:
        keys = {entry.identifier for entry in stylesheet.identifier_to_style_map}
        key = next(
            namedStyleKey.format(number)
            for number in range(len(keys) + 1)
            if namedStyleKey.format(number) not in keys
        )
        bodyText = index.resolve(network.body_text_style, tswp.ParagraphStyleArchive)
        textId = registry.identifierAllocate()
        created.append((textId, composeBaseStyle(
            key, styles.stylesheet, bodyText.para_properties.list_style.identifier
        )))
        stylesheet.identifier_to_style_map.add(
            identifier=key, style=tsp.Reference(identifier=textId)
        )
    reset = ResetStyles(
        tableStyle=created[0][0],
        cellStyle=created[1][0],
        textStyle=created[2][0] if existing is None else existing,
    )

    addStyles(index, registry, styles.stylesheet, created, (
        (network.table_style.identifier, reset.tableStyle),
        (network.body_cell_style.identifier, reset.cellStyle),
    ))

    if existing is None:
        themeId, theme = findTheme(index)
        presets = theme.super.Extensions[tswp.ThemePresetsArchive.extension]
        presets.paragraph_style_presets.add(identifier=reset.textStyle)
        themeReferences = registry.strongReferencesOf(themeId)
        themeReferences.append(reset.textStyle)
        registry.archiveReplace(themeId, theme, themeReferences)
    return reset


def findSlotStyle(slot: str, styles: DocumentStyles, reset: ResetStyles) -> int:
    """Return the style the reset puts in one of a table model's style slots.

    The table style, every cell style and every text style but the title's take the
    reset. The title's two take the theme's own, since a title stays hidden.
    """
    match slot:
        case "table_style":
            return reset.tableStyle
        case "table_name_style" | "table_name_shape_style":
            return int(getattr(styles.network, slot).identifier)
        case _ if slot.endswith("_text_style"):
            return reset.textStyle
        case _:
            return reset.cellStyle


__all__ = [
    "DocumentStyles",
    "applyResetCell",
    "applyResetTable",
    "composeBaseStyle",
    "ResetStyles",
    "createResetStyles",
    "namedStyleKey",
    "findDocumentStyles",
    "findSlotStyle",
]
