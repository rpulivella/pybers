#!/usr/bin/env python3
"""\
The report lines more than one command prints, so the same fact always reads alike.

A line is `label: value`, and a count states its noun in the number it agrees with.
See `docs/cli-design.md`.

UPDATES
2026-11-24  `formatGrid`, rows of the same fields under a header, for PYB-315.
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-03  `formatBadge`, a word set apart by its meaning, for PYB-223.
2026-11-03  The sheet tree moved to `check`, its one caller, for PYB-223.
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
from dataclasses import dataclass
from enum import StrEnum

from rich.console import Group
from rich.text import Text

# What separates two columns of a grid, as two fields of a part's line are.
columnGap: str = "  "


def formatLine(label: str, *value: str | tuple[str, str]) -> Text:
    """Return `label: value`, the label dimmed and a bare string as a bold value."""
    parts = [(part, "value") if isinstance(part, str) else part for part in value]
    return Text.assemble((f"{label}: ", "label"), *parts)


class BadgeLevel(StrEnum):
    """How much a badge asks of the reader, each level one style in the theme."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    FAILURE = "failure"


def formatBadge(word: str, level: BadgeLevel) -> Text:
    """Return a word set apart as a badge, `UNRECOGNIZED`, styled by its level.

    The word is upper case and padded, so it stands out in a pasted report too.
    """
    return Text(f" {word.upper()} ", f"badge.{level}")


@dataclass(frozen=True, slots=True)
class GridColumn:
    """One column of a grid: its field's name in words, the style of its values,
    whether it is a number, and whether a value equal to the row above is left blank.
    """

    name: str
    style: str = "value"
    numeric: bool = False
    grouped: bool = False


def formatGrid(columns: Sequence[GridColumn], rows: Sequence[Sequence[str]]) -> Group:
    """Return rows of the same fields as a grid, under a header naming each field.

    Each column is as wide as its longest value and never cut, since a value may be
    copied whole, a number aligns right, and a grouped column shows a value once,
    on the first row of the rows sharing it.
    """
    widths = [
        max([len(column.name), *(len(row[index]) for row in rows)])
        for index, column in enumerate(columns)
    ]
    last = len(columns) - 1

    def formatRow(values: Sequence[str], styles: Sequence[str]) -> Text:
        shown = Text()
        for index, (column, value) in enumerate(zip(columns, values, strict=True)):
            if column.numeric:
                value = value.rjust(widths[index])
            elif index != last:
                value = value.ljust(widths[index])
            shown.append(value, styles[index])
            if index != last:
                shown.append(columnGap)
        return shown

    shown = [formatRow([column.name for column in columns], ["label"] * len(columns))]
    previous: Sequence[str] | None = None
    for row in rows:
        values = [
            "" if column.grouped and previous is not None
            and previous[index] == row[index] else row[index]
            for index, column in enumerate(columns)
        ]
        shown.append(formatRow(values, [column.style for column in columns]))
        previous = row
    return Group(*shown)


def formatCount(count: int, noun: str) -> str:
    """Return a count with its noun, `1 row` or `10 rows`."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


__all__ = [
    "BadgeLevel", "GridColumn", "formatBadge", "formatCount", "formatGrid",
    "formatLine",
]
