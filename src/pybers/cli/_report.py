#!/usr/bin/env python3
"""\
The lines and parts every command prints with, so the same fact always reads alike.

A line is `label: value`, and a count states its noun in the number it agrees with.
See `docs/cli-design.md`.

UPDATES
2026-11-24  `composeOutcome` and `formatSkip`, the outcome of a write and a part it
            skipped, for PYB-319.
2026-11-24  A part's line, a line of fields and the blank line between parts, moved
            from `show`, so every command prints a part alike, for PYB-315.
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


from collections.abc import Iterable, Sequence
from enum import StrEnum
from pathlib import Path

from rich.console import Group, RenderableType
from rich.text import Text

import pybers
from pybers.cli._console import TreeCompact


class BadgeLevel(StrEnum):
    """How much a badge or a line asks of the reader, each level one style."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    FAILURE = "failure"


def formatLine(label: str, value: str, level: BadgeLevel | None = None) -> Text:
    """Return `label: value`, the value bold, or in the style of its level."""
    style = "value" if level is None else level.value
    return Text.assemble((f"{label}: ", "label"), (value, style))


def formatBadge(word: str, level: BadgeLevel) -> Text:
    """Return a word set apart as a badge, `UNRECOGNIZED`, styled by its level.

    The word is upper case and padded, so it stands out in a pasted report too.
    """
    return Text(f" {word.upper()} ", f"badge.{level}")


# How far a part's children sit under it, and what separates what one line holds.
childIndent: int = 2
segmentGap: str = "  "
fieldGap: str = "   "

def formatYesNo(flag: bool) -> str:
    """Return a flag as `yes` or `no`."""
    return "yes" if flag else "no"


def formatSegments(indent: int, label: str, name: str, *segments: str) -> Text:
    """Return a part's line: its label and name, then each segment holding something.

    An empty segment is left out, so a count of zero or an empty list never prints.
    """
    # A part's own label is full weight, as the tree in `check` draws one.
    shown = Text.assemble(" " * indent, (f"{label}: ", "value"), (name, "identifier"))
    for segment in segments:
        if segment:
            shown.append(segmentGap).append(segment, "value")
    return shown


def formatFields(indent: int, *fields: tuple[str, str]) -> Text:
    """Return several labeled fields folded onto one line."""
    shown = Text(" " * indent)
    for index, (label, value) in enumerate(fields):
        if index:
            shown.append(fieldGap)
        shown.append_text(formatLine(label, value))
    return shown


def formatCountShown(count: int, noun: str) -> str:
    """Return a count with its noun, or nothing when the count is zero."""
    return formatCount(count, noun) if count else ""


def listChildren(children: Sequence[RenderableType]) -> list[RenderableType]:
    """Return each child of a part, a blank line before each."""
    return [shown for child in children for shown in (Text(""), child)]


def formatParts(parts: Sequence[RenderableType]) -> Group:
    """Return parts one after another, a blank line between each."""
    return Group(*parts[:1], *listChildren(parts[1:]))


def formatDetail(text: str, indent: int = 0) -> Text:
    """Return a secondary line, a traceback frame or what a write did not do."""
    return Text(" " * indent + text, "detail")


def formatHeading(label: str, indent: int = 0) -> Text:
    """Return `Label:` over the lines that follow it."""
    return Text(f"{' ' * indent}{label}:", "label")


def formatListed(label: str, items: Iterable[str], indent: int = 0) -> Group:
    """Return a heading, then each item a value on its own line beneath it."""
    return Group(
        formatHeading(label, indent),
        *(Text(" " * (indent + childIndent) + item, "value") for item in items),
    )


def formatTree(root: Text) -> TreeCompact:
    """Return a tree growing from a root node, its guides drawn as labels are."""
    return TreeCompact(root, guide_style="label")


def formatTreeNode(name: str, value: str | None = None) -> Text:
    """Return a tree's node: a name, and what describes it after a colon."""
    shown = Text(name, "value")
    if value is not None:
        shown.append(": ", "label").append(value, "value")
    return shown


def formatBadgedNode(name: str, badge: Text, note: str) -> Text:
    """Return a tree's node set apart by a badge, `B7  UNRECOGNIZED  cell type 4`."""
    return Text.assemble((name, "identifier"), " ", badge, (f" {note}", "detail"))


def formatRefusal(command: str, reason: str) -> Text:
    """Return the one line a refused command prints, `pybers show: …`."""
    return Text.assemble((f"pybers {command}: ", "failure"), reason)


def composeOutcome(changed: bool, target: Path | None, unchanged: str) -> Text:
    """Return whether a write wrote, and where, or the phrase saying why it did not."""
    if not changed:
        return formatDetail(f"Nothing written: {unchanged}")
    if target is None:
        return formatDetail("Nothing written: previewing only")
    return formatLine("Written", str(target))


def formatSkip(skip: pybers.PartSkip) -> Text:
    """Return a part a call skipped, `Skipped: Budget::Q3::B4  holds a formula`."""
    return formatLine("Skipped", f"{skip.place}{segmentGap}{skip.reason}")


def formatCount(count: int, noun: str) -> str:
    """Return a count with its noun, `1 row` or `10 rows`."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


__all__ = [
    "BadgeLevel", "childIndent", "composeOutcome", "fieldGap", "formatBadge",
    "formatBadgedNode",
    "formatCount", "formatCountShown", "formatDetail", "formatFields", "formatHeading",
    "formatLine", "formatListed", "formatParts", "formatRefusal", "formatSegments",
    "formatSkip",
    "formatTree", "formatTreeNode",
    "formatYesNo", "listChildren", "segmentGap",
]
