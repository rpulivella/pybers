#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A table's grid, the cells in it, and the regions merged across it.

Addressing lives in `pybers.model.reference` and `pybers.model.ranges`. Nothing
here takes a bare row and column pair, so the only way to name a cell is with an
address that has already been validated.

UPDATES
2026-09-01  Addressing moved out to the reference types (#9). `cellAt(row, col)`
            and the loose reference helpers are gone; `MergeRange` now carries a
            `CellRange` rather than repeating the span arithmetic itself.
2026-08-17  Typed Cell.value, and pinned numbers to Decimal rather than float.
            Numbers stores them as IEEE-754 decimal128, measured in the fixtures,
            so a float would introduce binary rounding error into documents that
            never had any.
2026-08-12  Initial scaffold.
"""

from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/12"

import datetime
from dataclasses import dataclass, field
from decimal import Context, Decimal

from pybers.model.ranges import CellRange, RangeAddress, toCellRanges
from pybers.model.reference import (
    CellAddress,
    CellReference,
    ReferenceError,
    firstColumn,
    firstRow,
    toCellReference,
)
from pybers.model.style import Style

# IEEE-754 decimal128, which is exactly what Numbers stores a numeric cell as: 34
# significant digits with this exponent range. Declared here so that any arithmetic a
# caller performs through this library rounds the way Numbers itself rounds, rather
# than the way Python's 28-digit default happens to.
decimal128Context: Context = Context(prec=34, Emax=6144, Emin=-6143)

# What a cell may hold. Deliberately not `float` anywhere.
#
# Decimal is not a compromise here, it is the matching type. Verified 2026-08-17:
# Decimal("0.1") + Decimal("0.2") == Decimal("0.3") is True, and 1.1 * 1.1 is exactly
# 1.21, where float64 gets both wrong. Division still rounds (1/3 * 3 is 0.999...9)
# but that is inherent to decimal arithmetic and Numbers, using the same decimal128,
# behaves identically. Matching its rounding is the point.
#
# Scaled integers, the fixed-point trick from finance software, were considered and
# rejected: that works because money has a fixed scale, whereas a spreadsheet cell
# ranges from 1e-300 to 1e300. It would also mean converting between two number systems
# on every read and write, which reintroduces exactly the error being avoided.
#
# THE FAILURE THIS PREVENTS, and the reason to build values from strings: Decimal(0.1) carries the
# float's binary error straight in, yielding 0.1000000000000000055511151231257827...
# Decimal("0.1") does not. Never construct a cell value from a float.
CellValue = (
    Decimal
    | str
    | bool
    | datetime.datetime
    | datetime.timedelta
    | None
)


@dataclass(frozen=True, slots=True)
class MergeRange:
    """A rectangular block of cells merged into one, anchored at its top-left cell.

    The extent is a `CellRange` rather than four numbers of its own, so that the
    question of which cells a merge covers has one answer in the codebase. A merge
    is always bounded, unlike a range in general, which is checked rather than
    assumed.
    """

    extent: CellRange

    def __post_init__(self) -> None:
        """Reject an unbounded extent, which no merged region can have."""
        if self.extent.rowsUnbounded or self.extent.colsUnbounded:
            raise ReferenceError(
                f"A merge covers a fixed block of cells, and {self.extent} is "
                "unbounded."
            )

    @property
    def anchor(self) -> CellReference:
        """Return the top-left cell, the one that holds the merged region's value."""
        anchor = self.extent.start
        if anchor is None:
            raise ReferenceError(f"{self.extent} has no anchor cell.")
        return anchor

    def covers(self, address: CellAddress) -> bool:
        """Report whether this merge occupies a cell, its anchor included."""
        return self.extent.covers(address)


@dataclass(slots=True)
class Cell:
    """One cell's value, optional formula, and style, at an address."""

    reference: CellReference
    value: CellValue = None
    formula: str | None = None
    style: Style = field(default_factory=Style)


@dataclass(slots=True)
class Table:
    """A single table on a sheet, a sparse grid of cells plus its merged regions."""

    name: str
    rowCount: int = 0
    colCount: int = 0
    cells: dict[CellReference, Cell] = field(default_factory=dict)
    mergeRanges: list[MergeRange] = field(default_factory=list)

    def cell(self, address: CellAddress) -> Cell:
        """Return the cell at an address, creating an empty one on first access.

        A cell absent from the archive is empty rather than missing, so reading one
        inside the grid is not an error and must not shift its neighbors. Outside
        the grid is a different thing entirely and raises, because a Numbers table
        is a fixed number of rows and columns rather than an endless sheet.
        """
        # Unlocked before it is used as a key, because `$A$1` and `A1` compare
        # unequal and are one cell. Without this the same cell files itself under
        # four spellings and a write through one is invisible to the other three.
        key = toCellReference(address).asUnlocked()
        extent = self.extent
        if extent is None or not extent.covers(key):
            raise ReferenceError(
                f"{key} is outside {self.name!r}, which is {self.rowCount} rows "
                f"by {self.colCount} columns."
            )
        if key not in self.cells:
            self.cells[key] = Cell(reference=key)
        return self.cells[key]

    def range(self, address: RangeAddress) -> list[Cell]:
        """Return the cells one or more ranges cover, in the order they name them.

        An unbounded range is bounded by this table's own extent, which is the only
        place that extent is known. A table with nothing in it has no extent, so an
        unbounded range over one covers nothing.
        """
        extent = self.extent
        found: list[Cell] = []
        for item in toCellRanges(address):
            if item.rowsUnbounded or item.colsUnbounded:
                if extent is None:
                    continue
                item = item.boundedBy(extent)
            found.extend(self.cell(reference) for reference in item)
        return found

    @property
    def extent(self) -> CellRange | None:
        """Return the grid this table declares, or None when it has none.

        Read from the table's own declared size rather than derived from the cells
        that happen to hold something. A Numbers table is a fixed number of rows and
        columns, and 7 of the 74 tables in the fixture corpus have a declared size
        larger than their populated cells reach, so deriving it returns a real
        rectangle that is smaller than the table.
        """
        if self.rowCount < 1 or self.colCount < 1:
            return None
        return CellRange(firstRow, firstColumn, self.rowCount, self.colCount)

    def mergeCovering(self, address: CellAddress) -> MergeRange | None:
        """Return the merge occupying this cell, or None when none does.

        This is how a covered cell is told from an empty one, and there is no other
        way: a merged region's covered cells have NO record in the tile at all, so
        the grid cannot distinguish them. Derived from `mergeRanges` on every call
        rather than stored on the cell, because a copy of this would go stale the
        moment a merge changed.
        """
        reference = toCellReference(address)
        for merge in self.mergeRanges:
            if merge.covers(reference):
                return merge
        return None
