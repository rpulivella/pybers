#!/usr/bin/env python3
"""\
A table's lines read from its table style, and written as a variation of its root.

A table names one table style, the theme's root or a variation of it overriding a
few properties, as each control in `100b-lines` and `101b-outline` wrote one. A
change is written as a fresh variation of the root stating only what differs from
it, since a document's created tables share one variation, and a style stating
nothing names the root itself, as Default Table Style does.

Which stroke each gridline and separator draws with is read from its field's name,
since Numbers offers no control for one, and a golden confirms it.

Private. Part of the table feature's archive half.

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

from google.protobuf.message import Message

from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSPMessages_pb2 as tsp
from pybers._generated import TSTArchives_pb2 as tst
from pybers._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from pybers._persistence.index import ArchiveIndex, findRoot
from pybers._persistence.metadata import PackageRegistry
from pybers.absence import MIXED
from pybers.style._read import readStroke
from pybers.style._write import addStyles, composeStroke
from pybers.table.tablestyle import TableLine, TableStyle, blankTableStyle

# Each line's visibility, None where no control hides it, and the stroke fields it
# draws with, the outline one per band.
lineFields: frozendict[str, tuple[str | None, tuple[str, ...]]] = frozendict({
    "bodyHorizontalGridlines": (
        "h_strokes_visible", ("table_body_horizontal_stroke",),
    ),
    "bodyVerticalGridlines": ("v_strokes_visible", ("table_body_vertical_stroke",)),
    "headerRowsVerticalGridlines": (
        "table_hr_divider_visible", ("header_row_vertical_stroke",),
    ),
    "headerColumnsHorizontalGridlines": (
        "table_hc_divider_visible", ("header_column_horizontal_stroke",),
    ),
    "footerRowsVerticalGridlines": (
        "table_footer_divider_visible", ("footer_row_vertical_stroke",),
    ),
    "headerRowsHorizontalGridlines": (None, ("header_row_horizontal_stroke",)),
    "headerColumnsVerticalGridlines": (None, ("header_column_vertical_stroke",)),
    "footerRowsHorizontalGridlines": (None, ("footer_row_horizontal_stroke",)),
    "headerRowsSeparator": ("hr_separator_visible", ("header_row_separator_stroke",)),
    "headerColumnsSeparator": (
        "hc_separator_visible", ("header_column_separator_stroke",),
    ),
    "footerRowsSeparator": (
        "footer_separator_visible", ("footer_row_separator_stroke",),
    ),
    "tableOutline": ("table_border_visible", (
        "header_row_border_stroke", "header_column_border_stroke",
        "footer_row_border_stroke", "table_body_horizontal_border_stroke",
        "table_body_vertical_border_stroke",
    )),
})


def readStyleChain(
    index: ArchiveIndex, reference: tsp.Reference
) -> list[tst.TableStyleArchive]:
    """Return a table style and each parent it inherits from, nearest first."""
    chain: list[tst.TableStyleArchive] = []
    seen: set[int] = set()
    identifier = reference.identifier
    while identifier and identifier not in seen:
        seen.add(identifier)
        style = index.identifierResolve(identifier, tst.TableStyleArchive)
        chain.append(style)
        identifier = style.super.parent.identifier
    return chain


def findStated(chain: list[tst.TableStyleArchive], name: str) -> Message:
    """Return the nearest properties in a chain stating a field, by its name."""
    stated: list[Message] = [style.table_properties for style in chain]
    return next(
        (properties for properties in stated if properties.HasField(name)), stated[-1]
    )


def readTableLine(chain: list[tst.TableStyleArchive], field: str) -> TableLine:
    """Return one line a table draws, `MIXED` where its strokes differ."""
    visibleName, strokeNames = lineFields[field]
    strokes = {
        readStroke(getattr(findStated(chain, name), name)) for name in strokeNames
    }
    return TableLine(
        visible=(
            True if visibleName is None
            else getattr(findStated(chain, visibleName), visibleName)
        ),
        stroke=strokes.pop() if len(strokes) == 1 else MIXED,
    )


def readTableStyle(index: ArchiveIndex, model: tst.TableModelArchive) -> TableStyle:
    """Return the lines a table draws, resolved through its style's parents."""
    chain = readStyleChain(index, model.table_style)
    return TableStyle(
        **{field: readTableLine(chain, field) for field in lineFields},
        tableTitle=model.table_name_enabled,
        tableOutlineTitle=model.table_name_border_enabled,
    )


def composeVariationProperties(
    wanted: TableStyle,
    root: tstStyles.TableStylePropertiesArchive,
    carried: tstStyles.TableStylePropertiesArchive,
) -> tstStyles.TableStylePropertiesArchive:
    """Return a variation's properties: each line where it differs from the root.

    What a variation states that pybers does not model is carried, and an outline
    `MIXED` keeps the strokes it holds.
    """
    properties = tstStyles.TableStylePropertiesArchive()
    properties.CopyFrom(carried)
    # Named by a variable, which the generated stubs type only as literals.
    named: Message = properties
    for field, (visibleName, strokeNames) in lineFields.items():
        line: TableLine = getattr(wanted, field)
        if visibleName is not None:
            named.ClearField(visibleName)
            if line.visible != getattr(root, visibleName):
                setattr(properties, visibleName, line.visible)
        if line.stroke is MIXED:
            continue
        composed = composeStroke(line.stroke)
        for name in strokeNames:
            named.ClearField(name)
            if readStroke(getattr(root, name)) != line.stroke:
                getattr(properties, name).CopyFrom(composed)
    return properties


def applyTableStyle(
    properties: tstStyles.TableStylePropertiesArchive, tableStyle: TableStyle
) -> None:
    """State every line of a table style, as a root style states all of its own."""
    for field, (visibleName, strokeNames) in lineFields.items():
        line: TableLine = getattr(tableStyle, field)
        if visibleName is not None:
            setattr(properties, visibleName, line.visible)
        if line.stroke is MIXED:
            continue
        composed = composeStroke(line.stroke)
        for name in strokeNames:
            getattr(properties, name).CopyFrom(composed)


def readThemeTableStyle(
    index: ArchiveIndex, network: tst.TableStyleNetworkArchive
) -> TableStyle:
    """Return the table style a theme's table preset gives a table it creates."""
    chain = readStyleChain(index, network.table_style)
    return TableStyle(
        **{field: readTableLine(chain, field) for field in lineFields},
        tableTitle=False,
        tableOutlineTitle=False,
    )


def readDocumentTableStyle(index: ArchiveIndex) -> TableStyle:
    """Return what a document's theme gives a table it adds, read without refusing.

    A theme with no table preset reads as the Blank theme's lines, since a table
    added to such a document is refused when saved, and the document still opens.
    """
    root = findRoot(index)
    if not root.HasField("theme"):
        return blankTableStyle
    theme = index.resolve(root.theme, tn.ThemeArchive)
    presets = theme.super.Extensions[tstStyles.ThemePresetsArchive.extension]
    if not presets.table_style_presets:
        return blankTableStyle
    preset = index.resolve(
        presets.table_style_presets[0], tstStyles.TableStylePresetArchive
    )
    network = index.resolve(preset.style_network, tst.TableStyleNetworkArchive)
    return readThemeTableStyle(index, network)


def composeTableStyleVariation(
    wanted: TableStyle, rootId: int, root: tst.TableStyleArchive,
    carried: tstStyles.TableStylePropertiesArchive,
) -> tst.TableStyleArchive | None:
    """Return a variation of a root stating what `wanted` changes, None for nothing."""
    properties = composeVariationProperties(wanted, root.table_properties, carried)
    stated = properties.ListFields()
    if not stated:
        return None
    style = tst.TableStyleArchive(override_count=len(stated))
    style.super.parent.identifier = rootId
    style.super.is_variation = True
    style.super.stylesheet.identifier = root.super.stylesheet.identifier
    style.table_properties.CopyFrom(properties)
    return style


def findRootStyle(
    index: ArchiveIndex, reference: tsp.Reference
) -> tuple[int, tst.TableStyleArchive]:
    """Return the root a table style is a variation of, or the style itself."""
    chain = readStyleChain(index, reference)
    identifier = reference.identifier
    for style in chain[:-1]:
        identifier = style.super.parent.identifier
    return identifier, chain[-1]


def writeTableStyle(
    index: ArchiveIndex, registry: PackageRegistry, modelId: int,
    model: tst.TableModelArchive, wanted: TableStyle,
) -> None:
    """Point a table at the style drawing what it wants, when what it names differs."""
    if readTableStyle(index, model) == wanted:
        return
    # Written only when it changes, so a table whose title never showed keeps no flag.
    if model.table_name_enabled != wanted.tableTitle:
        model.table_name_enabled = wanted.tableTitle
    model.table_name_border_enabled = wanted.tableOutlineTitle
    current = index.resolve(model.table_style, tst.TableStyleArchive)
    rootId, root = findRootStyle(index, model.table_style)
    carried = (
        current.table_properties if current.super.is_variation
        else tstStyles.TableStylePropertiesArchive()
    )
    variation = composeTableStyleVariation(wanted, rootId, root, carried)
    if variation is None:
        model.table_style.identifier = rootId
    else:
        identifier = registry.identifierAllocate()
        addStyles(
            index, registry, root.super.stylesheet.identifier,
            [(identifier, variation)], [(rootId, identifier)],
        )
        model.table_style.identifier = identifier
    index.archiveWrite(modelId, model, registry.referencesReconcile(modelId, model))


__all__ = [
    "applyTableStyle", "composeTableStyleVariation", "lineFields", "readTableStyle",
    "readDocumentTableStyle", "readThemeTableStyle", "writeTableStyle",
]
