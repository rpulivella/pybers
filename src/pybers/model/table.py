#!/usr/bin/env python3
"""A table's grid, the cells in it, and the regions merged across it.

Addressing lives in `pybers.model.reference` and `pybers.model.ranges`. Nothing
here takes a bare row and column pair, so the only way to name a cell is with an
address that has already been validated.

UPDATES
2026-09-02  Merging and unmerging a block of cells (#16). A merge discards
            the cells it covers, which is measured rather than chosen.
2026-09-01  Addressing moved out to the reference types (#9). `cellAt(row, col)`
            and the loose reference helpers are gone, and `MergeRange` now carries
            a `CellRange` rather than repeating the span arithmetic itself. A table
            also holds its declared row and column count, and two kinds of address
            name nothing and raise: one beyond that grid, and one swallowed by a
            merge.
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
__date__ = "2026/09/02"

import datetime
from dataclasses import dataclass, field
from decimal import Context, Decimal

from pybers.model.formula import Formula
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
# THE FAILURE THIS PREVENTS, and the reason to build values from strings:
# Decimal(0.1) carries the float's binary error straight in, yielding
# 0.1000000000000000055511151231257827...
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

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        """Return the block's corners as (startRow, startCol, endRow, endCol).

        `__post_init__` already rejects an unbounded extent, so these four are
        always present. Saying so in a return type rather than leaving four
        `int | None` for every caller to re-check is the point: a merge that cannot
        be unbounded should not look like one that can.
        """
        startRow, startCol = self.extent.startRow, self.extent.startCol
        endRow, endCol = self.extent.endRow, self.extent.endCol
        if startRow is None or startCol is None or endRow is None or endCol is None:
            raise ReferenceError(f"{self.extent} is unbounded and bounds no merge.")
        return (startRow, startCol, endRow, endCol)

    def covers(self, address: CellAddress) -> bool:
        """Report whether this merge occupies a cell, its anchor included."""
        return self.extent.covers(address)


@dataclass(slots=True)
class Cell:
    """One cell's value, optional formula, and style, at an address.

    `value` on a formula-backed cell is the result Numbers last computed and
    cached, not something derived from `formula`. Reading a value therefore never
    evaluates anything, and the two can disagree until Numbers recalculates.

    `errored` says the formula failed and nothing more, because nothing more is
    stored. The file records that a cell errored, never why: the error list is
    empty in every fixture, and division by zero is indistinguishable from any
    other failure. A broken reference is the one exception and is visible through
    the formula itself.
    """

    reference: CellReference
    value: CellValue = None
    formula: Formula | None = None
    errored: bool = False
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

        A cell absent from the file is empty rather than missing, so reading one
        inside the grid is not an error and must not shift its neighbors. Two
        addresses name nothing at all and raise instead: one outside the declared
        grid, because a Numbers table is a fixed number of rows and columns rather
        than an endless sheet, and one swallowed by a merge, because a merged region
        is a single cell reached through its anchor.
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
        merge = self.mergeCovering(key)
        if merge is not None and merge.anchor != key:
            # Creating one here is what produces a phantom record: a covered cell
            # has NO record in the tile, so a table read and then written back
            # would gain one Numbers never writes. See findings-03-structure.md.
            raise ReferenceError(
                f"{key} is covered by the merge {merge.extent}, whose anchor is "
                f"{merge.anchor}."
            )
        if key not in self.cells:
            self.cells[key] = Cell(reference=key)
        return self.cells[key]

    def range(self, address: RangeAddress) -> list[Cell]:
        """Return the cells one or more ranges cover, in the order they name them.

        An unbounded range is bounded by this table's own extent, which is the only
        place that extent is known. A table with nothing in it has no extent, so an
        unbounded range over one covers nothing.

        Positions swallowed by a merge are skipped, so a range across a merged block
        yields its anchor once rather than one cell for every position it occupies.
        """
        extent = self.extent
        found: list[Cell] = []
        for item in toCellRanges(address):
            if item.rowsUnbounded or item.colsUnbounded:
                if extent is None:
                    continue
                item = item.boundedBy(extent)
            # Checked whole and up front, rather than left to the first cell that
            # falls off the end, which would name an interior address the caller
            # never wrote. Both corners exist here because an unbounded axis was
            # filled in above.
            corners = [item.start, item.end]
            if extent is None or not all(
                corner is not None and extent.covers(corner) for corner in corners
            ):
                raise ReferenceError(
                    f"{item} reaches outside {self.name!r}, which is "
                    f"{self.rowCount} rows by {self.colCount} columns."
                )
            found.extend(
                self.cell(reference)
                for reference in item
                if self.addressable(reference)
            )
        return found

    def addressable(self, address: CellAddress) -> bool:
        """Report whether an address names a cell this table can hand over.

        False for a position swallowed by a merge, which is why a range over a
        merged block yields the anchor once rather than one cell per position.
        """
        reference = toCellReference(address).asUnlocked()
        merge = self.mergeCovering(reference)
        return merge is None or merge.anchor == reference

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

    def mergeAdd(self, address: RangeAddress) -> MergeRange:
        """Merge a block of cells into one, anchored at its top-left, and return it.

        **The covered cells are discarded, permanently, and unmerging does not bring
        them back.** That is measured rather than chosen: `22-merge-2x2` and its
        unmerged twin `22b` hold the same 18 cells, so `B1` is absent from the
        unmerged file too. Leaving them in the model would also write records Numbers
        never had, since a covered cell has no record in a tile at all.
        """
        extent = self.rangeSingle(address, "merge")
        # A single cell is refused because Numbers cannot produce one: no fixture holds
        # a merge covering one cell and the interface offers no way to make one, so
        # writing the formula for it would put a construct in the file that has never
        # been confirmed to open. Declining to invent is not the same as inventing a
        # rule.
        if extent.start == extent.end:
            raise ReferenceError(
                f"{extent} is one cell, and a merge joins two or more. Numbers has no "
                "way to make a single-cell merge, so neither does this."
            )
        merge = MergeRange(extent)
        # Checked against the whole block before anything is discarded, so a refused
        # merge leaves the table exactly as it was rather than half applied.
        for existing in self.mergeRanges:
            if any(existing.covers(reference) for reference in merge.extent):
                raise ReferenceError(
                    f"{merge.extent} overlaps the merge {existing.extent}, and two "
                    "merges cannot claim the same cell. Remove that one first."
                )
        self.mergeRanges.append(merge)
        for reference in merge.extent:
            if reference != merge.anchor:
                self.cells.pop(reference, None)
        return merge

    def mergeRemove(self, address: CellAddress) -> MergeRange:
        """Unmerge the block occupying a cell, and return the merge that was removed.

        Takes any cell of the block rather than its extent, because two merges can
        never claim one cell and the caller usually holds an address rather than a
        rectangle. Every position the merge covered reads as empty afterward: the
        values were discarded when it was made, and nothing restores them.
        """
        merge = self.mergeCovering(address)
        if merge is None:
            raise ReferenceError(
                f"No merge in {self.name!r} covers "
                f"{toCellReference(address).asUnlocked()}."
            )
        self.mergeRanges.remove(merge)
        return merge

    def rangeSingle(self, address: RangeAddress, action: str) -> CellRange:
        """Return the one bounded rectangle an address names, inside this table.

        Split out of `mergeAdd` rather than left inline because it is the whole of
        what "names a block of this table" means, and reads better named than as
        twenty lines before the first useful one. An unbounded range is refused rather
        than bounded by the table, because a block that follows the grid as it grows
        is not a block.
        """
        ranges = toCellRanges(address)
        if len(ranges) != 1:
            raise ReferenceError(
                f"A {action} covers one block, and {address} names {len(ranges)}."
            )
        item = ranges[0]
        if item.rowsUnbounded or item.colsUnbounded:
            raise ReferenceError(
                f"{item} is unbounded, and a {action} covers a fixed block of cells."
            )
        extent = self.extent
        corners = [item.start, item.end]
        if extent is None or not all(
            corner is not None and extent.covers(corner) for corner in corners
        ):
            raise ReferenceError(
                f"{item} reaches outside {self.name!r}, which is {self.rowCount} "
                f"rows by {self.colCount} columns."
            )
        return item

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
