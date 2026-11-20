#!/usr/bin/env python3
"""\
The properties a created theme's root styles state, measured from Numbers' documents.

Numbers states some properties on every root style of a type, a table style's 62 stroke
and layout properties among them, and fails when an action reaches a style missing one.
The census finds which, across every fixture and measurement, and their values are read
from the Blank theme of `00-baseline`, as are the styles Numbers looks up by key and its
gradient and shadow presets. Read by
`themestyles_extract.py`, and held to the documents by `tests/test_theme_styles.py`.
See findings-10-creation.md.

UPDATES
2026-11-20  `formatModule` writes the source Python reads back, for PYB-309.
2026-11-16  Reads each style Numbers looks up by key, and counts a role's overrides
            from the properties it keeps, for PYB-292.
2026-11-03  Written for PYB-261.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/03"

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
from typing import Any, cast

from google.protobuf.message import Message

from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSCHArchives_pb2 as tsch
from pybers._generated import TSDArchives_pb2 as tsd
from pybers._generated import TSSArchives_pb2 as tss
from pybers._generated import TSTArchives_pb2 as tst
from pybers._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from pybers._persistence import readPackage
from pybers._persistence.index import ArchiveIndex, findRoot
from pybers._persistence.types import parseArchive, readArchiveTypeId

repositoryRoot: Path = Path(__file__).resolve().parents[3]
baselinePath: Path = repositoryRoot / "tests" / "fixtures" / "00-baseline.numbers"
surveyFolders: tuple[Path, ...] = (
    repositoryRoot / "tests" / "fixtures",
    repositoryRoot / "tests" / "measurements",
)
modulePath: Path = repositoryRoot / "src" / "pybers" / "_generated" / "themestyles.py"

# The style types whose root styles the census reads, by role in a created theme.
roleTypes: dict[str, int] = {
    "table": 6003, "media": 3016, "chart": 5022, "legend": 5024, "axis": 5026,
    "series": 5028, "referenceLine": 5030,
}

# The styles Numbers looks up by key, and composes on opening a document missing one.
stickyCommentSizes: tuple[int, ...] = (12, 13, 14, 15, 16, 18, 22, 24, 28)
keyedStyleNames: tuple[str, ...] = (
    "text-0-liststyle-None",
    "sheet-0-sheetStyle",
    "drop-cap-style-default",
    "paragraph-style-default",
    *(f"stickyComment-0-paragraphstyle-{size}" for size in stickyCommentSizes),
    "stickyComment-0-shapeStyle",
    "equation-0-imageStyle",
    "captions-0-shapestyle-Object Title",
    "captions-0-shapestyle-Object Caption",
)
# The drawable presets Numbers composes on opening a theme offering none.
drawablePresetNames: tuple[str, ...] = ("gradient_fill_presets", "shadow_presets")

Path_ = tuple[str, ...]


def findFieldName(field: object) -> str:
    """Return a field's name, an extension's in brackets."""
    return (f"[{field.full_name}]" if field.is_extension  # type: ignore[attr-defined]
            else field.name)  # type: ignore[attr-defined]


def checkNested(field: object) -> bool:
    """Report whether a field holds properties one level down."""
    return (field.message_type is not None  # type: ignore[attr-defined]
            and not field.is_repeated  # type: ignore[attr-defined]
            and (field.is_extension  # type: ignore[attr-defined]
                 or field.name.endswith("properties")))  # type: ignore[attr-defined]


def listStatedPaths(style: Message) -> frozenset[Path_]:
    """Return every property a style states, one level into a properties message."""
    stated: set[Path_] = set()
    for field, value in style.ListFields():
        name = findFieldName(field)
        if name in ("super", "override_count"):
            continue
        if checkNested(field):
            inner = {(name, findFieldName(each)) for each, _ in value.ListFields()}
            stated |= inner or {(name,)}
        else:
            stated.add((name,))
    return frozenset(stated)


def checkVariation(style: Message) -> bool:
    """Report whether a style is a variation of another rather than a root."""
    holder = style
    while holder.DESCRIPTOR.full_name != "TSS.StyleArchive":
        holder = holder.super  # type: ignore[attr-defined]
    return bool(holder.is_variation)  # type: ignore[attr-defined]


def surveyAlwaysStated(documents: Iterable[Path]) -> dict[int, frozenset[Path_]]:
    """Return, by type, the properties every root style in the documents states."""
    always: dict[int, frozenset[Path_]] = {}
    wanted = set(roleTypes.values())
    for document in documents:
        for member in readPackage(document).iwaFiles:
            for archive in member.archives:
                typeId = readArchiveTypeId(archive)
                if typeId not in wanted:
                    continue
                style = parseArchive(archive)
                if checkVariation(style):
                    continue
                paths = listStatedPaths(style)
                always[typeId] = always[typeId] & paths if typeId in always else paths
    return always


def listSurveyDocuments() -> list[Path]:
    """Return every fixture and measurement Numbers made."""
    return sorted([*folder.glob("*.numbers") for folder in surveyFolders])


def findRoleStyles(index: ArchiveIndex) -> dict[str, int]:
    """Return the Blank theme's style for each role, from its first preset where any."""
    root = findRoot(index)
    theme = index.resolve(root.theme, tn.ThemeArchive)
    table = index.resolve(
        theme.super.Extensions[tstStyles.ThemePresetsArchive.extension].table_style_presets[0],
        tstStyles.TableStylePresetArchive,
    )
    network = index.resolve(table.style_network, tst.TableStyleNetworkArchive)
    chart = index.resolve(
        theme.super.Extensions[tsch.ChartPresetsArchive.extension].chart_presets[0],
        tsch.ChartStylePreset,
    )
    lines = chart.Extensions[tsch.preset_reference_line_styles]
    drawables = theme.super.Extensions[tsd.ThemePresetsArchive.extension]
    return {
        "table": network.table_style.identifier,
        "media": drawables.image_style_presets[0].identifier,
        "chart": chart.chart_style.identifier,
        "legend": chart.legend_style.identifier,
        "axis": chart.value_axis_styles[0].identifier,
        "series": chart.series_styles[0].identifier,
        "referenceLine": lines.reference_line_styles[0].identifier,
    }


def readValue(field: object, value: object) -> object:
    """Return one field's value as plain data, a message as a dict of its fields."""
    if field.message_type is None:  # type: ignore[attr-defined]
        return value
    convert: Callable[[Message], object] = readMessageValues
    if field.is_repeated:  # type: ignore[attr-defined]
        return tuple(convert(item) for item in value)  # type: ignore[attr-defined]
    return convert(value)  # type: ignore[arg-type]


def readMessageValues(message: Message) -> dict[str, object]:
    """Return every field a message sets as plain data, references left out."""
    values: dict[str, object] = {}
    for field, value in message.ListFields():
        if field.message_type is not None and field.message_type.full_name in (
            "TSP.Reference", "TSP.DataReference",
        ):
            continue
        values[findFieldName(field)] = readValue(field, value)
    return values


def readRoleValues(
    index: ArchiveIndex, identifier: int, always: frozenset[Path_]
) -> dict[str, object]:
    """Return what one style states among the properties Numbers always states."""
    style = parseArchive(index.archive(identifier))
    values: dict[str, object] = {}
    counted = "override_count" in style.DESCRIPTOR.fields_by_name
    if counted and style.HasField("override_count"):
        values["override_count"] = style.override_count  # type: ignore[attr-defined]
    for field, value in style.ListFields():
        name = findFieldName(field)
        if name in ("super", "override_count"):
            continue
        if checkNested(field):
            kept = {
                findFieldName(inner): readValue(inner, innerValue)
                for inner, innerValue in value.ListFields()
                if (name, findFieldName(inner)) in always
            }
            if kept or (name,) in always:
                values[name] = kept
        elif (name,) in always:
            values[name] = readValue(field, value)
    # Numbers recounts a style's overrides from what its properties message states.
    nested = [name for name in values if name.endswith("properties")]
    if counted and nested:
        values["override_count"] = sum(
            len(cast(dict[str, object], values[name])) for name in nested
        )
    return values


def findStyleBase(style: Message) -> Message:
    """Return the `TSS.StyleArchive` at the root of a style's `super` chain."""
    holder = style
    while holder.DESCRIPTOR.full_name != "TSS.StyleArchive":
        holder = holder.super  # type: ignore[attr-defined]
    return holder


def listStyleReferences(message: Message, path: Path_ = ()) -> list[tuple[Path_, int]]:
    """Return every style a style references, by field path, its stylesheet aside."""
    found: list[tuple[Path_, int]] = []
    for field, value in message.ListFields():
        skipped = field.is_repeated or field.name == "stylesheet"
        if field.message_type is None or skipped:
            continue
        if field.message_type.full_name == "TSP.Reference":
            found.append(((*path, field.name), value.identifier))
        else:
            found += listStyleReferences(value, (*path, field.name))
    return found


def readKeyedStyles(index: ArchiveIndex) -> dict[str, dict[str, object]]:
    """Return each keyed style as the Blank theme states it, a reference by its key."""
    stylesheet = index.resolve(
        index.resolve(findRoot(index).theme, tn.ThemeArchive).super.document_stylesheet,
        tss.StylesheetArchive,
    )
    # A key sits in the stylesheet's own map or in one of its versioned lists.
    maps = {
        entry.identifier: name
        for name, holder in (
            ("identifier_to_style_map", stylesheet),
            *((field.name, value) for field, value in stylesheet.ListFields()
              if field.name.startswith("styles_for_")),
        )
        for entry in holder.identifier_to_style_map
    }
    byKey: dict[str, int] = {}
    keyOf: dict[int, str] = {}
    for reference in stylesheet.styles:
        base: Any = findStyleBase(parseArchive(index.archive(reference.identifier)))
        if base.style_identifier:
            byKey[base.style_identifier] = reference.identifier
            keyOf[reference.identifier] = base.style_identifier
    keyed: dict[str, dict[str, object]] = {}
    for key in keyedStyleNames:
        archive = index.archive(byKey[key])
        style = parseArchive(archive)
        keyed[key] = {
            "type": readArchiveTypeId(archive),
            "map": maps.get(key),
            "values": readMessageValues(style),
            "references": tuple(
                (path, keyOf[target]) for path, target in listStyleReferences(style)
            ),
        }
    return keyed


@dataclass(frozen=True)
class ThemeStyleTables:
    """Each role's always-stated properties, each keyed style, and drawable presets."""

    roles: dict[str, dict[str, object]]
    keyed: dict[str, dict[str, object]]
    presets: dict[str, object]


def readDrawablePresets(index: ArchiveIndex) -> dict[str, object]:
    """Return the Blank theme's gradient and shadow presets as plain data."""
    theme = index.resolve(findRoot(index).theme, tn.ThemeArchive)
    drawables = readMessageValues(
        theme.super.Extensions[tsd.ThemePresetsArchive.extension]
    )
    return {name: drawables[name] for name in drawablePresetNames}


def buildThemeStyles() -> ThemeStyleTables:
    """Return both tables, valued as the Blank theme states them."""
    always = surveyAlwaysStated(listSurveyDocuments())
    index = ArchiveIndex(readPackage(baselinePath))
    return ThemeStyleTables(
        roles={
            role: readRoleValues(index, identifier, always[roleTypes[role]])
            for role, identifier in findRoleStyles(index).items()
        },
        keyed=readKeyedStyles(index),
        presets=readDrawablePresets(index),
    )


def formatModule(tables: ThemeStyleTables) -> str:
    """Return the generated module's source, every value a plain literal."""
    roles = pformat(tables.roles, width=88, sort_dicts=True)
    keyed = pformat(tables.keyed, width=88, sort_dicts=True)
    presets = pformat(tables.presets, width=88, sort_dicts=True)
    return f'''#!/usr/bin/env python3
"""\\
The properties a created theme's root styles state, the styles Numbers looks up by key,
and its gradient and shadow presets, valued as Numbers' Blank theme states them.
Generated by `tools/local/themestyles_extract.py` from `tests/fixtures/` and
`tests/measurements/`, so it is regenerated rather than edited. See
findings-10-creation.md.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/03"

themeStyles: frozendict[str, dict[str, object]] = frozendict({roles})

keyedStyles: frozendict[str, dict[str, object]] = frozendict({keyed})

drawablePresets: frozendict[str, object] = frozendict({presets})
'''


__all__ = ["ThemeStyleTables", "buildThemeStyles", "modulePath", "formatModule"]
