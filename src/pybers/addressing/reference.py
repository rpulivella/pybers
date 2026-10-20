#!/usr/bin/env python3
"""Where a cell is, how something points at it, and the column letter conversion.

Rectangles live in `pybers.addressing.ranges`, which imports this module and never the
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
2026-10-20  `CellOffset`, a signed distance, and the arithmetic between it and an
            address, for PYB-217.
2026-10-20  `CellAddress`, a position alone, and the table and sheet a reference
            names, for PYB-217.
2026-10-19  `CellReferenceLike`, what a call accepts for one cell, for PYB-217.
2026-09-23  `toCellReferenceNamed` moved here from the table model, for PYB-18.
2026-09-22  The offset between stored and model coordinates lives here, for PYB-109.
2026-09-13  An address past the far end of either axis is refused, for #67.
            `Ledger` read as column 144,936,576 and raised nothing.
2026-09-08  Moved into `pybers.addressing` for #58, unchanged.
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
from typing import overload

from pybers.errors import PybersError

# Rows and columns count from ONE throughout the model, because that is what
# Numbers shows and what a caller means by "row 1". Nothing here ever holds a stored
# coordinate.
firstRow: int = 1
firstColumn: int = 1

# The file counts rows and columns from zero, so an archive half subtracts this
# from a model coordinate and adds it to a stored one, and nowhere else converts.
originOffset: int = 1

# The far end of each axis, so a label nothing could have addressed is refused
# instead of becoming a coordinate. `LEDGER` is a valid base-26 label and reads as
# column 144,936,576, which a formula then stored as an offset with nothing
# raising. The column figure is this repository's own, measured for the
# over-255-column work and stated in findings-01-values.md. The row figure is
# Apple's published one and is not measured here, so a document disproving it
# changes this line.
lastColumn: int = 1000
lastRow: int = 1000000

# Twenty-six letters with no zero digit, which is why neither conversion below is
# an ordinary base conversion.
alphabetSize: int = 26

absoluteMarker: str = "$"

# What separates a table's name from an address inside it, and a sheet's name from
# a table's. Numbers writes `Table 2::A1` and qualifies it further when a bare table
# name would be ambiguous.
tableNameSeparator: str = "::"

cellPattern: re.Pattern[str] = re.compile(r"^(\$?)([A-Za-z]+)(\$?)([0-9]+)$")


class ReferenceError(PybersError, ValueError):
    """An address that is not a valid A1-style reference, range or list."""


def toColumnLetter(col: int) -> str:
    """Return the letter label for a column number, 1 to A and 27 to AA.

    The only public conversion in this direction, so a base-26 correction lands in
    one place rather than in each caller that grew its own. Bounded at both ends
    like `toColumnNumber`, so the two agree on which columns exist and stay inverses
    over every number either accepts.
    """
    if col < firstColumn:
        raise ReferenceError(
            f"Column {col} is before column {firstColumn}. Columns count from one."
        )
    if col > lastColumn:
        raise ReferenceError(
            f"Column {col} is past column {lastColumn}, which is the last column a "
            "Numbers table can hold."
        )
    letters = ""
    while col > 0:
        col, remainder = divmod(col - 1, alphabetSize)
        letters = chr(ord("A") + remainder) + letters
    return letters


def toColumnNumber(letters: str) -> int:
    """Return the column number for a letter label, A to 1 and AA to 27.

    Refuses a label past the last column a table can hold. Every letter is a valid
    base-26 digit, so `LEDGER` converts to 144,936,576 and reads as a column rather
    than as the word it is. A formula then stored that as an offset and nothing
    raised, which is the failure this whole library is built to avoid.
    """
    if not letters or not letters.isascii() or not letters.isalpha():
        raise ReferenceError(f"{letters!r} is not a column label.")
    col = 0
    for letter in letters.upper():
        col = col * alphabetSize + (ord(letter) - ord("A") + 1)
    if col > lastColumn:
        raise ReferenceError(
            f"{letters!r} is column {col}, past column {lastColumn}, which is the "
            "last column a Numbers table can hold."
        )
    return col


def chooseMarker(absolute: bool) -> str:
    """Return the locking marker a coordinate is written with, or nothing."""
    return absoluteMarker if absolute else ""


@dataclass(frozen=True, slots=True, order=True)
class CellAddress:
    """Where a cell sits in any table, counted from one, with no table and no `$`.

    A lock describes how a reference moves when a formula is copied, never where a
    cell is, so an address has none and two spellings of one cell are one address.
    """

    row: int
    col: int

    def __post_init__(self) -> None:
        """Reject a coordinate outside a real table at construction rather than at use.

        The zero-based instinct then fails once, here, instead of in every method
        that takes an address. The far end is checked for the same reason and was
        not: `=Ledger` parsed to column 144,936,576 and raised nothing, because six
        letters are a valid base-26 label.
        """
        for axis, value in (("Row", self.row), ("Column", self.col)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ReferenceError(f"{axis} {value!r} is not a whole number.")
        if self.row < firstRow:
            raise ReferenceError(
                f"Row {self.row} is before row {firstRow}. Rows count from one."
            )
        if self.col < firstColumn:
            raise ReferenceError(
                f"Column {self.col} is before column {firstColumn}. "
                "Columns count from one."
            )
        if self.row > lastRow:
            raise ReferenceError(
                f"Row {self.row} is past row {lastRow}, which is the last row a "
                "Numbers table can hold."
            )
        if self.col > lastColumn:
            raise ReferenceError(
                f"Column {self.col} is past column {lastColumn}, which is the last "
                "column a Numbers table can hold."
            )

    @classmethod
    def parse(cls, text: str) -> CellAddress:
        """Return the address `B3` names, refusing a `$`, which only a reference has."""
        reference = CellReference.parse(text)
        if reference.rowAbsolute or reference.colAbsolute:
            raise ReferenceError(
                f"{text!r} carries a lock, which belongs to a `CellReference`. An "
                "address is the position alone, such as "
                f"{reference.address}."
            )
        return reference.address

    def asRowColumn(self) -> tuple[int, int]:
        """Return this address as a (row, column) pair, both counted from one."""
        return (self.row, self.col)

    def __add__(self, offset: CellOffset) -> CellAddress:
        """Return the address `offset` away, refused when it leaves every table."""
        if not isinstance(offset, CellOffset):
            return NotImplemented
        return CellAddress(self.row + offset.rows, self.col + offset.cols)

    @overload
    def __sub__(self, other: CellAddress) -> CellOffset: ...

    @overload
    def __sub__(self, other: CellOffset) -> CellAddress: ...

    def __sub__(self, other: CellAddress | CellOffset) -> CellOffset | CellAddress:
        """Return the distance to another address, or the address an offset back."""
        if isinstance(other, CellAddress):
            return CellOffset(self.row - other.row, self.col - other.col)
        if isinstance(other, CellOffset):
            return self + -other
        return NotImplemented

    def __str__(self) -> str:
        """Return the address as it is written, `B3`."""
        return f"{toColumnLetter(self.col)}{self.row}"


@dataclass(frozen=True, slots=True)
class CellOffset:
    """A signed distance between two addresses, in rows and columns, zero included.

    Kept apart from `CellAddress` because an address counts from one and is bounded,
    and a distance is neither, as a `timedelta` is kept apart from a `datetime`.
    """

    rows: int
    cols: int

    def __post_init__(self) -> None:
        for axis, value in (("Rows", self.rows), ("Columns", self.cols)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ReferenceError(f"{axis} {value!r} is not a whole number.")

    def __add__(self, other: CellOffset) -> CellOffset:
        if not isinstance(other, CellOffset):
            return NotImplemented
        return CellOffset(self.rows + other.rows, self.cols + other.cols)

    def __sub__(self, other: CellOffset) -> CellOffset:
        if not isinstance(other, CellOffset):
            return NotImplemented
        return CellOffset(self.rows - other.rows, self.cols - other.cols)

    def __neg__(self) -> CellOffset:
        return CellOffset(-self.rows, -self.cols)


@dataclass(frozen=True, slots=True)
class SheetReference:
    """A sheet, by its name."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ReferenceError(f"A sheet is named, and {self.name!r} is no name.")

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True, kw_only=True)
class TableReference:
    """A table, by its name, and by its sheet's when another sheet shares the name."""

    sheet: SheetReference | None = None
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ReferenceError(f"A table is named, and {self.name!r} is no name.")

    def __str__(self) -> str:
        if self.sheet is None:
            return self.name
        return f"{self.sheet}{tableNameSeparator}{self.name}"


@dataclass(frozen=True, slots=True)
class CellReference:
    """How something points at a cell: its address, a lock per axis, and a table.

    The table is named only when the context needs it, as a path is relative or
    absolute. Frozen because a reference is a value: two callers naming B2 hold the
    same reference, and neither may change what the other points at.
    """

    row: int
    col: int
    rowAbsolute: bool = field(default=False, kw_only=True)
    colAbsolute: bool = field(default=False, kw_only=True)
    table: TableReference | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        """Check the position by building the address it stands on."""
        CellAddress(self.row, self.col)

    @property
    def address(self) -> CellAddress:
        """Return where this reference points, with its locks and table set aside."""
        return CellAddress(self.row, self.col)

    @property
    def sheet(self) -> SheetReference | None:
        """Return the sheet this reference names, or None when it names none."""
        return None if self.table is None else self.table.sheet

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
            toColumnNumber(letters),
            rowAbsolute=rowMarker == absoluteMarker,
            colAbsolute=colMarker == absoluteMarker,
        )

    def asReference(self) -> str:
        """Return this address as it would be written, markers included."""
        return (
            f"{chooseMarker(self.colAbsolute)}{toColumnLetter(self.col)}"
            f"{chooseMarker(self.rowAbsolute)}{self.row}"
        )

    def asRowColumn(self) -> tuple[int, int]:
        """Return the position as a (row, column) pair, both counted from one."""
        return (self.row, self.col)

    def __str__(self) -> str:
        """Return the written form, qualified by its table when it names one."""
        if self.table is None:
            return self.asReference()
        return f"{self.table}{tableNameSeparator}{self.asReference()}"


# What a caller may hand to anything that addresses one cell. The string form is
# included deliberately: `table.cell("A1")` is how this library is meant to read at
# a call site, and the string is parsed at the boundary rather than carried around.
CellReferenceLike = CellReference | CellAddress | str


def toCellReference(address: CellReferenceLike) -> CellReference:
    """Return a `CellReference` for whichever of its forms was given."""
    if isinstance(address, str):
        return CellReference.parse(address)
    if isinstance(address, CellAddress):
        return CellReference(address.row, address.col)
    return address


def toCellReferenceNamed(
    address: CellReferenceLike | None, row: int | None, col: int | None
) -> CellReference:
    """Return the cell an address names, or the one `row=` and `col=` name together.

    Refuses both forms at once and a lone axis. A `bool` is refused as a coordinate
    because Python counts `True` as 1, which no caller writing `row=True` meant.
    """
    if address is not None:
        if row is not None or col is not None:
            raise ReferenceError(
                f"A cell is named by {address} or by row and col, and both were given."
            )
        return toCellReference(address)
    if (
        isinstance(row, int)
        and isinstance(col, int)
        and not isinstance(row, bool)
        and not isinstance(col, bool)
    ):
        return CellReference(row, col)
    raise ReferenceError(
        "A cell is named by an address such as 'E3', or by row= and col= together "
        f"as numbers, and was given row={row!r}, col={col!r}."
    )
