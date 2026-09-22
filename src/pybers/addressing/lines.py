#!/usr/bin/env python3
"""Where each row or column of a table lands after lines are added or removed.

A structural edit is one mapping from old lines to new ones, and everything that
names a line by its number follows it: cells, merges and every formula reference.
Holding the mapping here keeps those three from each deriving their own.

**A removed line takes a range's end with it, never the whole range.** Measured
2026-09-18 in `56g-row-deleted-in-merge`: deleting row 3 turned `SUM(A3:A4)` into
`SUM(A3:A3)` and `SUM(A2:A3)` into `SUM(A2:A2)`, and a range losing every line it
covered became `#REF!` in `56c-row-deleted`.

UPDATES
2026-09-21  An edit is also a mapping of each axis, which is what a formula
            follows, for PYB-17.
2026-09-18  Written for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/18"

from dataclasses import dataclass
from typing import Protocol


class LineMapping(Protocol):
    """Where each line of one axis lands after an edit, counted from one."""

    def lineMap(self, line: int) -> int | None:
        """Return where a line lands, or None when the edit removes it."""
        ...

    def spanMap(self, begin: int, end: int) -> tuple[int, int] | None:
        """Return where a span of lines lands, or None when it loses every line."""
        ...


@dataclass(frozen=True, slots=True)
class LinesUnchanged:
    """The axis an edit leaves alone, where every line lands where it was."""

    def lineMap(self, line: int) -> int | None:
        """Return the line itself."""
        return line

    def spanMap(self, begin: int, end: int) -> tuple[int, int] | None:
        """Return the span itself."""
        return (begin, end)


@dataclass(frozen=True, slots=True)
class GridEdit:
    """Lines added to or removed from one axis of a table, counted from one.

    Added lines take the numbers `at` through `at + count - 1`, and whatever held
    those numbers moves on. Removed lines are exactly those numbers.
    """

    rows: bool
    at: int
    count: int
    removing: bool = False

    @property
    def last(self) -> int:
        """Return the last line this edit adds or removes."""
        return self.at + self.count - 1

    def lineMap(self, line: int) -> int | None:
        """Return where a line lands, or None when this edit removes it."""
        if line < self.at:
            return line
        if not self.removing:
            return line + self.count
        if line <= self.last:
            return None
        return line - self.count

    def spanMap(self, begin: int, end: int) -> tuple[int, int] | None:
        """Return where a span of lines lands, or None when it loses every line.

        An insertion inside the span grows it, since each end moves only when the
        insertion is at or before it. A removal keeps the first and last lines
        that survive, which is what Numbers does to a range.
        """
        if not self.removing:
            first, final = self.lineMap(begin), self.lineMap(end)
            assert first is not None and final is not None
            return (first, final)
        first = begin if begin < self.at else max(begin - self.count, self.at)
        final = end if end < self.at else max(end - self.count, self.at - 1)
        if first > final:
            return None
        return (first, final)

    def axisMaps(self) -> tuple[LineMapping, LineMapping]:
        """Return this edit as a row mapping and a column mapping, in that order."""
        if self.rows:
            return self, LinesUnchanged()
        return LinesUnchanged(), self
