#!/usr/bin/env python3
"""\
Where each stored row and column of a table lands after a structural edit.

**The edit is derived, never recorded.** The stored UID map says which line
held which identity, and the model says where each identity is now, so
comparing the two gives the whole mapping from stored lines to new ones.

Private. Part of the table feature's archive half.

UPDATES
2026-09-21  Split out of `_structure` for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/21"

from collections.abc import Sequence
from dataclasses import dataclass

from .._generated import TSTArchives_pb2 as tst
from .._persistence.index import ArchiveIndex
from ..errors import WriteError
from ._read import readLineIdentities
from .cells import Table


@dataclass(frozen=True, slots=True)
class LineMap:
    """Where each stored line of one axis lands, counted from zero, None if removed."""

    lines: tuple[int | None, ...]
    count: int

    @property
    def changed(self) -> bool:
        """Report whether any line moved, went, or arrived."""
        return self.count != len(self.lines) or any(
            line != moved for line, moved in enumerate(self.lines)
        )

    def lineMap(self, line: int) -> int | None:
        """Return where one stored line lands, or None when it was removed."""
        return self.lines[line] if line < len(self.lines) else None

    def spanMap(self, begin: int, end: int) -> tuple[int, int] | None:
        """Return where a span lands, its first and last surviving lines kept."""
        kept = [
            moved for moved in (self.lineMap(line) for line in range(begin, end + 1))
            if moved is not None
        ]
        if not kept:
            return None
        return (min(kept), max(kept))


@dataclass(frozen=True, slots=True)
class GridMaps:
    """Both axes of one table's structural change, stored lines to new ones."""

    rows: LineMap
    columns: LineMap

    @property
    def changed(self) -> bool:
        """Report whether either axis changed."""
        return self.rows.changed or self.columns.changed


def buildLineMap(
    stored: Sequence[int], wanted: Sequence[int], axis: str, name: str
) -> LineMap:
    """Return where each stored line went, refusing lines that changed order.

    Added and removed lines are the only edits this library makes, so every line
    both sides hold keeps its order, and an identity only the model holds is new.
    """
    position = {identity: at for at, identity in enumerate(wanted)}
    lines = tuple(position.get(identity) for identity in stored)
    kept = [line for line in lines if line is not None]
    if kept != sorted(kept):
        raise WriteError(
            f"The {axis} of {name!r} are in a different order from the file's, and "
            "only adding and removing them is written."
        )
    return LineMap(lines, len(wanted))


def buildGridMaps(
    index: ArchiveIndex, model: tst.TableModelArchive, table: Table
) -> GridMaps:
    """Return how the model's rows and columns relate to the stored ones."""
    rows, columns = readLineIdentities(index, model)
    if len(rows) != model.number_of_rows or len(columns) != model.number_of_columns:
        raise WriteError(
            f"{table.name!r} declares {model.number_of_rows} by "
            f"{model.number_of_columns} and its UID map holds {len(rows)} by "
            f"{len(columns)}, so which line is which cannot be told."
        )
    return GridMaps(
        buildLineMap(rows, table._rowIdentities, "rows", table.name),
        buildLineMap(columns, table._columnIdentities, "columns", table.name),
    )


def findDisplacedLine(lines: LineMap, line: int) -> int | None:
    """Return the stored line an added line took the place of, or None at the end."""
    for stored, moved in enumerate(lines.lines):
        if moved is not None and moved > line:
            return stored
    return None


def listAddedLines(lines: LineMap) -> list[int]:
    """Return every new line the edit added, as its index afterward."""
    held = {moved for moved in lines.lines if moved is not None}
    return [line for line in range(lines.count) if line not in held]


__all__ = [
    "GridMaps",
    "LineMap",
    "buildGridMaps",
    "findDisplacedLine",
    "listAddedLines",
]
