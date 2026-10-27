#!/usr/bin/env python3
"""\
The report lines more than one command prints, so the same fact always reads alike.

A line is `label: value`, a count names its noun in the number it agrees with, and a
document's outline is a tree per sheet holding each table and its size. See
`docs/cli-design.md`.

UPDATES
2026-10-27  Written for PYB-260, out of `check`, which `show` shares.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/27"

from collections.abc import Sequence
from typing import Protocol

from rich.text import Text

from pybers.cli._console import TreeCompact


class TableOutline(Protocol):
    """A table as an outline shows it: its name and its size."""

    @property
    def name(self) -> str: ...

    @property
    def rowCount(self) -> int: ...

    @property
    def colCount(self) -> int: ...


class SheetOutline(Protocol):
    """A sheet as an outline shows it: its name and its tables."""

    @property
    def name(self) -> str: ...

    @property
    def tables(self) -> Sequence[TableOutline]: ...


def formatLine(label: str, *value: str | tuple[str, str]) -> Text:
    """Return `label: value`, the label dimmed and a bare string as a bold value."""
    parts = [(part, "value") if isinstance(part, str) else part for part in value]
    return Text.assemble((f"{label}: ", "label"), *parts)


def formatCount(count: int, noun: str) -> str:
    """Return a count with its noun, `1 row` or `10 rows`."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def formatTableSize(table: TableOutline) -> str:
    """Return a table's size as `10 rows, 7 columns`."""
    return (
        f"{formatCount(table.rowCount, 'row')}, "
        f"{formatCount(table.colCount, 'column')}"
    )


def formatSheetTree(sheet: SheetOutline) -> TreeCompact:
    """Return a sheet as a tree holding each of its tables and its size."""
    tree = TreeCompact(Text(sheet.name, "value"), guide_style="label")
    for table in sheet.tables:
        tree.add(Text.assemble(
            (table.name, "value"), (": ", "label"), (formatTableSize(table), "value")
        ))
    return tree


__all__ = [
    "SheetOutline",
    "TableOutline",
    "formatCount",
    "formatLine",
    "formatSheetTree",
    "formatTableSize",
]
