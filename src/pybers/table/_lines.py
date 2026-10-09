#!/usr/bin/env python3
"""\
Where each stored row and column of a table lands after a structural edit.

**The edit is derived, never recorded.** The stored UID map says which line
held which identity, and the model says where each identity is now, so
comparing the two gives the whole mapping from stored lines to new ones.

Private. Part of the table feature's archive half.

UPDATES
2026-09-22  The UID map is written here, by creation and by a structural edit alike, for
            PYB-113.
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
from .._persistence.index import ArchiveIndex, assignUuid
from ..addressing.reference import originOffset
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

    @property
    def growth(self) -> int:
        """Return how many lines the edit added, less how many it removed."""
        return self.count - len(self.lines)

    def spanCut(self, begin: int, end: int) -> bool:
        """Report whether the edit removes a line of a span or adds one inside it.

        A line added before the span's first line moves the whole span, and one
        added after its last line leaves it alone, so neither cuts it.
        """
        if any(self.lineMap(line) is None for line in range(begin, end + 1)):
            return True
        return any(
            begin < (len(self.lines) if displaced is None else displaced) <= end
            for displaced in (
                findDisplacedLine(self, added) for added in listAddedLines(self)
            )
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
class ModelLines:
    """A stored line map read in the model's counting, from one, as a formula needs."""

    stored: LineMap

    def lineMap(self, line: int) -> int | None:
        """Return where a line counted from one lands, or None when it was removed."""
        moved = self.stored.lineMap(line - originOffset)
        return None if moved is None else moved + originOffset

    def spanMap(self, begin: int, end: int) -> tuple[int, int] | None:
        """Return where a span counted from one lands, None when it lost every line."""
        mapped = self.stored.spanMap(begin - originOffset, end - originOffset)
        if mapped is None:
            return None
        return (mapped[0] + originOffset, mapped[1] + originOffset)


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
            "reordering them is not supported."
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


def assignUids(uidMap: tst.ColumnRowUIDMapArchive, table: Table) -> None:
    """Write a table's row and column identities, in the order Numbers keeps.

    The UIDs are sorted by value, upper half first, and each index list is the
    permutation between that order and the table's own. Measured from `48`.
    """
    for axis, uids in (
        ("column", table._columnIdentities), ("row", table._rowIdentities)
    ):
        ordered = sorted(range(len(uids)), key=lambda position: uids[position])
        sortedField = getattr(uidMap, f"sorted_{axis}_uids")
        indexForUid = getattr(uidMap, f"{axis}_index_for_uid")
        uidForIndex = getattr(uidMap, f"{axis}_uid_for_index")
        del sortedField[:]
        del indexForUid[:]
        del uidForIndex[:]
        for position in ordered:
            assignUuid(sortedField.add(), uids[position])
        indexForUid.extend(ordered)
        rank = {position: slot for slot, position in enumerate(ordered)}
        uidForIndex.extend(rank[position] for position in range(len(uids)))


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
    "ModelLines",
    "assignUids",
    "buildGridMaps",
    "findDisplacedLine",
    "listAddedLines",
]
