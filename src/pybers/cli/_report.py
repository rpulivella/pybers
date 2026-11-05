#!/usr/bin/env python3
"""\
The report lines more than one command prints, so the same fact always reads alike.

A line is `label: value`, and a count names its noun in the number it agrees with.
See `docs/cli-design.md`.

UPDATES
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


from enum import StrEnum

from rich.text import Text


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


def formatCount(count: int, noun: str) -> str:
    """Return a count with its noun, `1 row` or `10 rows`."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


__all__ = ["BadgeLevel", "formatBadge", "formatCount", "formatLine"]
