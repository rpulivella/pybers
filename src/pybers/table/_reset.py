#!/usr/bin/env python3
"""\
The reset's styles, which every text, cell and table slot of a created table names.

The table style and the cell style are variations of the theme's first table style
preset, written as `52-table-reset-styled` wrote them, and every text slot names
`pybers-base`, the named paragraph style of `53-paragraph-style-named`, created once
per document and found again by name. See docs/decisions.md.

Private. Part of the table feature's archive half, reached by table creation.

UPDATES
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
from pathlib import Path

from .._generated import TNArchives_pb2 as tn
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSSArchives_pb2 as tss
from .._generated import TSTArchives_pb2 as tst
from .._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from .._generated import TSWPArchives_pb2 as tswp
from .._persistence.index import ArchiveIndex, findRoot, generateUuid
from .._persistence.metadata import PackageRegistry
from .._persistence.template import ArchiveTemplate, copyTemplates, readTemplates
from .._persistence.types import findArchiveTypeId, readArchiveTypeId
from ..errors import WriteError

templateDirectory: Path = Path(__file__).resolve().parent / "_templates"


# The style objects the style templates name that belong to the document, as
# `48-table-inserted` numbered them.
templateStylesheet: int = 905039
templateListStyle: int = 903872
templateTableStyle: int = 904074
templateCellStyle: int = 904075


baseStyleName: str = "pybers-base"
namedStyleKey: str = "text-{}-paragraphstyle"


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


def createResetStyles(
    index: ArchiveIndex, registry: PackageRegistry, styles: DocumentStyles
) -> ResetStyles:
    """Create the reset's two variations, and `pybers-base` unless it exists."""
    network = styles.network
    bodyText = index.resolve(network.body_text_style, tswp.ParagraphStyleArchive)
    templates = readTemplates(templateDirectory / "styles")
    existing = findNamedStyle(index, styles.stylesheet)
    if existing is not None:
        templates = [
            template for template in templates if template.role != "text-style"
        ]
    copies = copyTemplates(
        registry,
        templates,
        {
            templateStylesheet: styles.stylesheet,
            templateTableStyle: network.table_style.identifier,
            templateCellStyle: network.body_cell_style.identifier,
            templateListStyle: bodyText.para_properties.list_style.identifier,
        },
    )
    stylesheet = index.resolve(
        tsp.Reference(identifier=styles.stylesheet), tss.StylesheetArchive
    )
    keys = {entry.identifier for entry in stylesheet.identifier_to_style_map}
    if existing is None:
        textCopy = copies["text-style"]
        key = next(
            namedStyleKey.format(number)
            for number in range(len(keys) + 1)
            if namedStyleKey.format(number) not in keys
        )
        body = textCopy.body
        if not isinstance(body, tswp.ParagraphStyleArchive):
            raise WriteError("The text style template is not a paragraph style.")
        body.super.style_identifier = key
        stylesheet.identifier_to_style_map.add(
            identifier=key, style=tsp.Reference(identifier=textCopy.identifier)
        )
    reset = ResetStyles(
        tableStyle=copies["table-style"].identifier,
        cellStyle=copies["cell-style"].identifier,
        textStyle=copies["text-style"].identifier if existing is None else existing,
    )

    componentId = registry.componentRequire(styles.stylesheet)
    copies.place(registry, {"DocumentStylesheet": componentId})
    created = [copy.identifier for copy in copies.copies.values()]
    for identifier in created:
        stylesheet.styles.add(identifier=identifier)
        registry.objectUuidAdd(componentId, identifier, generateUuid())
    for parent, child in (
        (network.table_style.identifier, reset.tableStyle),
        (network.body_cell_style.identifier, reset.cellStyle),
    ):
        entry = next(
            (
                entry for entry in stylesheet.parent_to_children_style_map
                if entry.parent.identifier == parent
            ),
            None,
        )
        if entry is None:
            entry = stylesheet.parent_to_children_style_map.add()
            entry.parent.identifier = parent
        entry.children.add(identifier=child)
    references = registry.strongReferencesOf(styles.stylesheet)
    references.extend(
        identifier for identifier in created if identifier not in references
    )
    registry.archiveReplace(
        styles.stylesheet, stylesheet, references
    )

    if existing is None:
        themeId, theme = findTheme(index)
        presets = theme.super.Extensions[tswp.ThemePresetsArchive.extension]
        presets.paragraph_style_presets.add(identifier=reset.textStyle)
        themeReferences = registry.strongReferencesOf(themeId)
        themeReferences.append(reset.textStyle)
        registry.archiveReplace(themeId, theme, themeReferences)
    return reset


def bindStyles(
    template: ArchiveTemplate, styles: DocumentStyles, reset: ResetStyles
) -> dict[int, int]:
    """Bind every style the table model template names to what the reset puts there.

    The table style, every cell style and every text style but the title's take the
    reset. The title's two styles take the theme's own, since a title stays hidden.
    """
    bindings: dict[int, int] = {}
    for descriptor in tst.TableStyleNetworkArchive.DESCRIPTOR.fields:
        if descriptor.message_type is None:
            continue
        name = descriptor.name
        if not template.body.HasField(name):
            continue
        if name == "table_style":
            target = reset.tableStyle
        elif name in ("table_name_style", "table_name_shape_style"):
            target = getattr(styles.network, name).identifier
        elif name.endswith("_text_style"):
            target = reset.textStyle
        else:
            target = reset.cellStyle
        source = getattr(template.body, name).identifier
        if bindings.setdefault(source, target) != target:
            raise WriteError(
                f"The table template names style {source} in two slots the reset "
                "fills differently."
            )
    return bindings


__all__ = [
    "DocumentStyles",
    "ResetStyles",
    "bindStyles",
    "createResetStyles",
    "findDocumentStyles",
    "templateDirectory",
]
