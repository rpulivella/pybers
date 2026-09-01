#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A table's grid, cells, addressed by row/column, and their merge ranges.

UPDATES
2026-08-17  Typed Cell.value, and pinned numbers to Decimal rather than float. Numbers
            stores them as IEEE-754 decimal128, measured in the fixtures, so a float
            would introduce binary rounding error into documents that never had any.
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
import re
from dataclasses import dataclass, field
from decimal import Context, Decimal

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


# Rows and columns count from ONE throughout the model, because that is what
# Numbers shows and what a caller means by "row 1" or "column A". The archive
# counts from zero, and the two systems meet only at the read and write boundary
# in `pybers.reader`. Nothing here ever holds an archive coordinate.
firstRow: int = 1
firstColumn: int = 1

# Twenty-six letters, so a column label is base-26 with no zero digit: Z is 26
# and AA is 27, which is why this cannot be written as an ordinary base
# conversion.
alphabetSize: int = 26

referencePattern: re.Pattern = re.compile(r"^\$?([A-Za-z]+)\$?([0-9]+)$")


class ReferenceError(ValueError):
    """A cell reference that is not a valid A1-style address."""


def columnLetter(col: int) -> str:
    """Return the letter label for a column number, 1 to A and 27 to AA."""
    if col < firstColumn:
        raise ReferenceError(f"Column {col} is before column {firstColumn}.")
    letters = ""
    while col > 0:
        col, remainder = divmod(col - 1, alphabetSize)
        letters = chr(ord("A") + remainder) + letters
    return letters


def columnNumber(letters: str) -> int:
    """Return the column number for a letter label, A to 1 and AA to 27."""
    if not letters or not letters.isalpha():
        raise ReferenceError(f"{letters!r} is not a column label.")
    col = 0
    for letter in letters.upper():
        col = col * alphabetSize + (ord(letter) - ord("A") + 1)
    return col


def parseReference(reference: str) -> tuple[int, int]:
    """Return the (row, col) a single A1-style reference addresses.

    Accepts the dollar signs Numbers writes for an absolute reference and ignores
    them. Locking is a property of a formula, not of an address, so `$A$1` and
    `A1` name the same cell and both resolve here.
    """
    match = referencePattern.match(reference.strip())
    if match is None:
        raise ReferenceError(f"{reference!r} is not an A1-style cell reference.")
    return int(match.group(2)), columnNumber(match.group(1))


@dataclass(frozen=True, slots=True)
class MergeRange:
    """A rectangular block of cells merged into one, anchored at its top-left cell.

    Counted from one, like everything else in the model.
    """

    anchorRow: int
    anchorCol: int
    rowSpan: int
    colSpan: int

    def covers(self, row: int, col: int) -> bool:
        """Report whether this range occupies a cell, its anchor included."""
        return (
            self.anchorRow <= row < self.anchorRow + self.rowSpan
            and self.anchorCol <= col < self.anchorCol + self.colSpan
        )


@dataclass(slots=True)
class Cell:
    """One cell's value, optional formula, and style, at a specific row/column.

    `row` and `col` count from one.
    """

    row: int
    col: int
    value: CellValue = None
    formula: str | None = None
    style: Style = field(default_factory=Style)

    @property
    def reference(self) -> str:
        """Return this cell's A1-style address."""
        return f"{columnLetter(self.col)}{self.row}"


@dataclass(slots=True)
class Table:
    """A single table on a sheet, a sparse grid of cells plus its merge ranges."""

    name: str
    cells: dict[tuple[int, int], Cell] = field(default_factory=dict)
    mergeRanges: list[MergeRange] = field(default_factory=list)

    def cellAt(self, row: int, col: int) -> Cell:
        """Return the cell at (row, col), creating an empty one on first access.

        A cell absent from the archive is empty rather than missing, so reading
        one is not an error and must not shift its neighbors.
        """
        if row < firstRow or col < firstColumn:
            raise ReferenceError(
                f"({row}, {col}) is outside the grid, which starts at "
                f"({firstRow}, {firstColumn}). Rows and columns count from one."
            )
        key = (row, col)
        if key not in self.cells:
            self.cells[key] = Cell(row=row, col=col)
        return self.cells[key]

    def cell(self, reference: str) -> Cell:
        """Return the cell an A1-style reference addresses."""
        return self.cellAt(*parseReference(reference))

    def mergeCovering(self, row: int, col: int) -> MergeRange | None:
        """Return the merge occupying this cell, or None when none does.

        This is how a covered cell is told from an empty one, and there is no
        other way: a merged region's covered cells have NO record in the tile at
        all, so the grid cannot distinguish them. Derived from `mergeRanges` on
        every call rather than stored on the cell, because a copy of this would
        go stale the moment a merge changed.
        """
        for merge in self.mergeRanges:
            if merge.covers(row, col):
                return merge
        return None
