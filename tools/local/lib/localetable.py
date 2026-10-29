#!/usr/bin/env python3
"""\
The table of each region's formatting symbols, rendered as the module pybers imports.

Fields follow `TSK.FormattingSymbolsArchive`'s own order, so the module reads as the
archive does and a diff after a new extraction lands on the field macOS changed.

UPDATES
2026-10-28  Written for PYB-272.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/28"

import importlib.util
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pybers._generated import TSKArchives_pb2 as tsk
from tools.local.lib.icudata import Field, IcuVersions

# The archive's fields in the order it declares them.
fieldOrder: tuple[str, ...] = tuple(
    each.name for each in tsk.FormattingSymbolsArchive.DESCRIPTOR.fields
)

type LocaleTable = Mapping[str, Mapping[str, Field]]


@dataclass(frozen=True, slots=True)
class TableComparison:
    """How an extracted table differs from the committed one."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[tuple[str, str], ...]


def renderField(value: Field) -> str:
    """Return a field as the Python literal the module holds."""
    if isinstance(value, str):
        return repr(value)
    return "(" + ", ".join(renderField(each) if not isinstance(each, str)
                           else repr(each) for each in value) + ",)"


def renderModule(table: LocaleTable, versions: IcuVersions, macOS: str) -> str:
    """Return the module holding every region's formatting symbols."""
    lines = [
        "#!/usr/bin/env python3",
        '"""\\',
        "Each region's formatting symbols, by locale identifier. Machine output, do",
        "not edit.",
        "",
        f"Written by tools/local/locales_extract.py from macOS {macOS}, ICU",
        f"{versions.icu}, CLDR {versions.cldr} and CoreFoundation "
        f"{versions.coreFoundation}.",
        "A correction made here is destroyed by the next extraction; correct the",
        "extractor instead.",
        "",
        "Each entry holds every field of `TSK.FormattingSymbolsArchive` in the",
        "archive's own order, as Numbers writes it for that region, and a currency's",
        "symbol only where the region's differs from its ISO code.",
        "",
        f"{len(table)} regions.",
        '"""',
        "",
        "locales: frozendict[str, frozendict[str, object]] = frozendict({",
    ]
    for identifier in sorted(table):
        lines.append(f"    {identifier!r}: frozendict({{")
        fields = table[identifier]
        for name in fieldOrder:
            lines.append(f"        {name!r}: {renderField(fields[name])},")
        lines.append("    }),")
    lines.append("})")
    return "\n".join(lines) + "\n"


def readCommitted(path: Path) -> LocaleTable | None:
    """Return the committed table, or None when there is none yet."""
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("committedLocales", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed: LocaleTable = module.locales
    return committed


def compareTables(extracted: LocaleTable, committed: LocaleTable) -> TableComparison:
    """Return the regions added, removed, and each field changed, by region."""
    return TableComparison(
        added=tuple(sorted(set(extracted) - set(committed))),
        removed=tuple(sorted(set(committed) - set(extracted))),
        changed=tuple(
            (identifier, name)
            for identifier in sorted(set(extracted) & set(committed))
            for name in fieldOrder
            if extracted[identifier][name] != committed[identifier][name]
        ),
    )


__all__ = [
    "LocaleTable",
    "TableComparison",
    "compareTables",
    "fieldOrder",
    "readCommitted",
    "renderModule",
]
