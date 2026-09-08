#!/usr/bin/env python3
"""One cell's address, and the column letter conversion everything else reaches for.

Rectangles live in `pybers.model.ranges`, which imports this module and never the
other way around. The split is by what each has to represent: a single cell always
has a row and a column, and only a range has to express the absence of one.

Two things here return a valid-looking wrong answer rather than raising, which is
why each carries its own guard:

- **Column labels are base-26 with no zero digit.** Z is 26 and AA is 27, so an
  ordinary base conversion is off by one at every 26 boundary and names a real
  column, simply not the requested one.
- **The dollar sign is a per-axis fact.** `$A1` locks the column and leaves the row
  free, and one formula holds an absolute column beside a relative row and then the
  reverse, so a single flag per reference cannot represent what Numbers stores.

UPDATES
2026-09-01  Written for #9, replacing the loose reference helpers in `table.py`.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/01"

import re
from dataclasses import dataclass, field

# Rows and columns count from ONE throughout the model, because that is what
# Numbers shows and what a caller means by "row 1". The file counts from zero,
# and the two meet only in `pybers.reader`. Nothing here ever holds a stored
# coordinate.
firstRow: int = 1
firstColumn: int = 1

# Twenty-six letters with no zero digit, which is why neither conversion below is
# an ordinary base conversion.
alphabetSize: int = 26

absoluteMarker: str = "$"

# What separates a table's name from an address inside it, and a sheet's name from
# a table's. Numbers writes `Table 2::A1` and qualifies it further when a bare table
# name would be ambiguous.
tableNameSeparator: str = "::"

cellPattern: re.Pattern[str] = re.compile(r"^(\$?)([A-Za-z]+)(\$?)([0-9]+)$")


class ReferenceError(ValueError):
    """An address that is not a valid A1-style reference, range or list."""


def columnLetter(col: int) -> str:
    """Return the letter label for a column number, 1 to A and 27 to AA.

    The only public conversion in this direction, so a base-26 correction lands in
    one place rather than in each caller that grew its own.
    """
    if col < firstColumn:
        raise ReferenceError(
            f"Column {col} is before column {firstColumn}. Columns count from one."
        )
    letters = ""
    while col > 0:
        col, remainder = divmod(col - 1, alphabetSize)
        letters = chr(ord("A") + remainder) + letters
    return letters


def columnNumber(letters: str) -> int:
    """Return the column number for a letter label, A to 1 and AA to 27."""
    if not letters or not letters.isascii() or not letters.isalpha():
        raise ReferenceError(f"{letters!r} is not a column label.")
    col = 0
    for letter in letters.upper():
        col = col * alphabetSize + (ord(letter) - ord("A") + 1)
    return col


def markerFor(absolute: bool) -> str:
    """Return the locking marker a coordinate is written with, or nothing."""
    return absoluteMarker if absolute else ""


@dataclass(frozen=True, slots=True)
class CellReference:
    """One cell's address, counted from one, carrying its locking on each axis.

    Frozen because an address is a value rather than a thing: two callers naming B2
    hold the same address, and neither may change what the other points at.
    """

    row: int
    col: int
    rowAbsolute: bool = field(default=False, kw_only=True)
    colAbsolute: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        """Reject a coordinate below one at construction rather than at use.

        The zero-based instinct then fails once, here, instead of in every method
        that takes an address.
        """
        if self.row < firstRow:
            raise ReferenceError(
                f"Row {self.row} is before row {firstRow}. Rows count from one."
            )
        if self.col < firstColumn:
            raise ReferenceError(
                f"Column {self.col} is before column {firstColumn}. "
                "Columns count from one."
            )

    @classmethod
    def parse(cls, reference: str) -> CellReference:
        """Return the cell an A1-style reference addresses, markers preserved.

        `$A1` and `A1` name the same cell and compare unequal, because locking is
        part of what was written and has to survive being read back out.
        """
        match = cellPattern.match(reference.strip())
        if match is None:
            raise ReferenceError(f"{reference!r} is not an A1-style cell reference.")
        colMarker, letters, rowMarker, digits = match.groups()
        # Checked against the written form rather than left to the constructor,
        # which would report row 0 without saying that `A0` is where it came from.
        if int(digits) < firstRow:
            raise ReferenceError(
                f"{reference!r} names row {int(digits)}, and rows count from "
                f"{firstRow}."
            )
        return cls(
            int(digits),
            columnNumber(letters),
            rowAbsolute=rowMarker == absoluteMarker,
            colAbsolute=colMarker == absoluteMarker,
        )

    def asReference(self) -> str:
        """Return this address as it would be written, markers included."""
        return (
            f"{markerFor(self.colAbsolute)}{columnLetter(self.col)}"
            f"{markerFor(self.rowAbsolute)}{self.row}"
        )

    def asRowColumn(self) -> tuple[int, int]:
        """Return this address as a (row, column) pair, both counted from one."""
        return (self.row, self.col)

    def asUnlocked(self) -> CellReference:
        """Return the same cell with its locking markers dropped.

        `$A$1` and `A1` are one cell written two ways, so anything keyed by address must
        agree on which of the four spellings it files them under. That agreement is why
        a table can be keyed by a reference at all.
        """
        if not self.rowAbsolute and not self.colAbsolute:
            return self
        return CellReference(self.row, self.col)

    def __str__(self) -> str:
        """Return the written form, so an error message reads as a reference."""
        return self.asReference()


# What a caller may hand to anything that addresses one cell. The string form is
# included deliberately: `table.cell("A1")` is how this library is meant to read at
# a call site, and the string is parsed at the boundary rather than carried around.
CellAddress = CellReference | str


def toCellReference(address: CellAddress) -> CellReference:
    """Return a `CellReference` for whichever of its forms was given."""
    if isinstance(address, str):
        return CellReference.parse(address)
    return address
