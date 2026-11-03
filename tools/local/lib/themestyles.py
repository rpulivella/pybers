#!/usr/bin/env python3
"""\
The properties a created theme's root styles state, measured from Numbers' documents.

Numbers states some properties on every root style of a type, a sheet style's fill and
a table style's 62 stroke and layout properties among them, and fails when an action
reaches a style missing one. The census finds which, across every fixture and
measurement, and their values are read from the Blank theme of `00-baseline`. Read by
`themestyles_extract.py`, and held to the documents by `tests/test_theme_styles.py`.
See findings-10-creation.md.

UPDATES
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
from pathlib import Path
from pprint import pformat

from google.protobuf.message import Message

from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSCHArchives_pb2 as tsch
from pybers._generated import TSDArchives_pb2 as tsd
from pybers._generated import TSTArchives_pb2 as tst
from pybers._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from pybers._generated import TSWPArchives_pb2 as tswp
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
    "sheet": 12050, "table": 6003, "list": 2023, "media": 3016, "chart": 5022,
    "legend": 5024, "axis": 5026, "series": 5028, "referenceLine": 5030,
}

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
    return sorted(
        path for folder in surveyFolders for path in folder.glob("*.numbers")
    )


def findRoleStyles(index: ArchiveIndex) -> dict[str, int]:
    """Return the Blank theme's style for each role, from its first preset where any."""
    root = findRoot(index)
    theme = index.resolve(root.theme, tn.ThemeArchive)
    sheet = index.resolve(root.sheets[0], tn.SheetArchive)
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
    text = theme.super.Extensions[tswp.ThemePresetsArchive.extension]
    return {
        "sheet": sheet.style.identifier,
        "table": network.table_style.identifier,
        "list": text.list_style_presets[0].identifier,
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
    return values


def buildThemeStyles() -> dict[str, dict[str, object]]:
    """Return each role's always-stated properties, valued as the Blank theme's."""
    always = surveyAlwaysStated(listSurveyDocuments())
    index = ArchiveIndex(readPackage(baselinePath))
    return {
        role: readRoleValues(index, identifier, always[roleTypes[role]])
        for role, identifier in findRoleStyles(index).items()
    }


def renderModule(styles: dict[str, dict[str, object]]) -> str:
    """Return the generated module's source, every value a plain literal."""
    body = pformat(styles, width=88, sort_dicts=True)
    return f'''#!/usr/bin/env python3
"""\\
The properties a created theme's root styles state, valued as Numbers' Blank theme
states them. Generated by `tools/local/themestyles_extract.py` from `tests/fixtures/`
and `tests/measurements/`, so it is regenerated rather than edited. See
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

themeStyles: frozendict[str, dict[str, object]] = frozendict({body})
'''


__all__ = ["buildThemeStyles", "modulePath", "renderModule"]
