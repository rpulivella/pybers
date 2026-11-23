#!/usr/bin/env python3
"""\
The reset's styles, which every text, cell and table slot of a created table names.

The table style and the cell style are variations of the theme's first table style
preset, written as `52-table-reset-styled` wrote them, and every text slot names
`pybers-base`, the named paragraph style of `53-paragraph-style-named`, created once
per document and found again by name. See docs/decisions.md.

Private. Part of the table feature's archive half, reached by table creation.

UPDATES
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-17  The reset's table style composed from the model's reset over the theme,
            for PYB-266.
2026-11-16  A variation stating only what its parent states is not written, since
            Numbers drops it, and the reset's text is composed apart from its name,
            for PYB-292.
2026-11-13  The reset's cell properties composed where its variation is, the
            theme's cell style stating a created table's whole box, for PYB-265.
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
from ..errors import WriteError, composeRefusal, nothingWritten
from ..style._write import addStyles, composeCellProperties, composeCellStyleArchive
from ..style.cells import resetCellStyle
from ._tablestyle import composeTableStyleVariation, readThemeTableStyle
from .tablestyle import applyTableReset

baseStyleName: str = "pybers-base"
namedStyleKey: str = "text-{}-paragraphstyle"

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
        raise WriteError(composeRefusal(
            "The document's theme", "carries no table style preset, so a new table "
            "has no style to take", notDone=nothingWritten,
        ))
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


def composeTableStyle(
    index: ArchiveIndex, network: tst.TableStyleNetworkArchive
) -> tst.TableStyleArchive:
    """Return the reset's table style, a variation of a theme's table style.

    An empty variation where the theme already states the reset, which the caller
    then does not write.
    """
    root = index.resolve(network.table_style, tst.TableStyleArchive)
    wanted = applyTableReset(readThemeTableStyle(index, network))
    style = composeTableStyleVariation(
        wanted, network.table_style.identifier, root,
        tstStyles.TableStylePropertiesArchive(),
    )
    return style if style is not None else tst.TableStyleArchive()


def composeBaseStyle(
    key: str, stylesheet: int, listStyle: int
) -> tswp.ParagraphStyleArchive:
    """Return `pybers-base`, the reset's text named and keyed."""
    style = composeResetText(stylesheet, listStyle)
    style.super.name = baseStyleName
    style.super.style_identifier = key
    return style


def composeResetText(stylesheet: int, listStyle: int) -> tswp.ParagraphStyleArchive:
    """Return the reset's text, unnamed: Avenir Next 11 pt on exact 15.5 pt lines.

    Numbers resolves every property of a named root style, so all 57 are stated, as
    `53-paragraph-style-named` holds them. See docs/decisions.md.
    """
    style = tswp.ParagraphStyleArchive()
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


def checkRestates(parent: Message, variation: Message) -> bool:
    """Report whether a variation restates only its parent, which Numbers drops.

    Measured 2026-11-16 in a created document, findings-10-creation.md.
    """
    return all(
        (field.is_repeated or parent.HasField(field.name))
        and getattr(parent, field.name) == value
        for field, value in variation.ListFields()
    )


def createResetStyles(
    index: ArchiveIndex, registry: PackageRegistry, styles: DocumentStyles
) -> ResetStyles:
    """Create the reset's variations their parents lack, and `pybers-base` if absent."""
    network = styles.network
    stylesheet = index.resolve(
        tsp.Reference(identifier=styles.stylesheet), tss.StylesheetArchive
    )
    tableParent = network.table_style.identifier
    cellParent = network.body_cell_style.identifier
    tableStyle = composeTableStyle(index, network)
    cellStyle = composeCellStyleArchive(
        styles.stylesheet,
        composeCellProperties(resetCellStyle, tstStyles.CellStylePropertiesArchive()),
        cellParent,
    )
    created: list[tuple[int, Message]] = []
    children: list[tuple[int, int]] = []
    chosen: list[int] = []
    tableRoot = index.resolve(network.table_style, tst.TableStyleArchive)
    cellRoot = index.resolve(network.body_cell_style, tst.CellStyleArchive)
    for parent, body, properties, variation in (
        (tableParent, tableStyle, tableRoot.table_properties,
         tableStyle.table_properties),
        (cellParent, cellStyle, cellRoot.cell_properties, cellStyle.cell_properties),
    ):
        if checkRestates(properties, variation):
            chosen.append(parent)
            continue
        identifier = registry.identifierAllocate()
        created.append((identifier, body))
        children.append((parent, identifier))
        chosen.append(identifier)
    existing = findNamedStyle(index, styles.stylesheet)
    textStyle = existing
    if textStyle is None:
        keys = {entry.identifier for entry in stylesheet.identifier_to_style_map}
        key = next(
            namedStyleKey.format(number)
            for number in range(len(keys) + 1)
            if namedStyleKey.format(number) not in keys
        )
        bodyText = index.resolve(network.body_text_style, tswp.ParagraphStyleArchive)
        textStyle = registry.identifierAllocate()
        created.append((textStyle, composeBaseStyle(
            key, styles.stylesheet, bodyText.para_properties.list_style.identifier
        )))
        stylesheet.identifier_to_style_map.add(
            identifier=key, style=tsp.Reference(identifier=textStyle)
        )
    reset = ResetStyles(tableStyle=chosen[0], cellStyle=chosen[1], textStyle=textStyle)

    if created:
        addStyles(index, registry, styles.stylesheet, created, children)

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
    "composeBaseStyle",
    "composeResetText",
    "ResetStyles",
    "createResetStyles",
    "namedStyleKey",
    "findDocumentStyles",
    "findSlotStyle",
]
