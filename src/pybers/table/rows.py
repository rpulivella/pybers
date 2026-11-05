#!/usr/bin/env python3
"""A table's declared grid as rows, each a sequence of the cells in it.

Views rather than lists, because `Table.cell` creates a cell on first access and
keeps it. A list would create every cell it held just to be measured or sliced,
so these hold row and column numbers and create a cell only when one is reached.

A position a merge swallowed is not in its row, which is `Table.addressable`
answering, so indexing a row counts the cells in it rather than its columns.

UPDATES
2026-09-14  Written for PYB-62.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/14"

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, overload

from pybers.addressing.reference import CellAddress, firstColumn

if TYPE_CHECKING:
    from pybers.table.cell import Cell
    from pybers.table.cells import Table


class TableRows(Sequence["TableRow"]):
    """A table's rows in order, each one a `TableRow`, indexed and sliced from zero.

    Holds row numbers rather than rows, so measuring or slicing creates no cell.
    """

    __slots__ = ("rowNumbers", "table")

    def __init__(self, table: Table, rowNumbers: range) -> None:
        """Hold the rows of a table named by their row numbers."""
        self.table = table
        self.rowNumbers = rowNumbers

    @overload
    def __getitem__(self, index: int) -> TableRow: ...

    @overload
    def __getitem__(self, index: slice) -> TableRows: ...

    def __getitem__(self, index: int | slice) -> TableRow | TableRows:
        """Return one row, or the rows a slice selects as another view."""
        if isinstance(index, slice):
            return TableRows(self.table, self.rowNumbers[index])
        columnNumbers = range(firstColumn, self.table.colCount + 1)
        return TableRow(self.table, self.rowNumbers[index], columnNumbers)

    def __len__(self) -> int:
        """Return how many rows this holds."""
        return len(self.rowNumbers)

    def __eq__(self, other: object) -> bool:
        """Report whether both name the same rows of the same table."""
        if not isinstance(other, TableRows):
            return NotImplemented
        return other.table is self.table and other.rowNumbers == self.rowNumbers

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        """Return which table and how many rows, without reaching a cell."""
        return f"TableRows({self.table.name!r}, {len(self)} rows)"


class TableRow(Sequence["Cell"]):
    """The cells of one row in order, indexed and sliced from zero.

    A merged block is in its anchor's row once and absent from the rest, so `row[3]`
    is the fourth cell and not column D. `Table.cell(row=, col=)` names a column.
    """

    __slots__ = ("columnNumbers", "rowNumber", "table")

    def __init__(
        self, table: Table, rowNumber: int, columnNumbers: Sequence[int]
    ) -> None:
        """Hold one row of a table, limited to the columns given."""
        self.table = table
        self.rowNumber = rowNumber
        self.columnNumbers = columnNumbers

    def cellAddresses(self) -> list[CellAddress]:
        """Return the address of every cell in this row, a covered position omitted.

        Asked of the table on every call rather than kept, because a merge made after
        this view was taken changes which positions hold a cell.
        """
        candidates = (CellAddress(self.rowNumber, col) for col in self.columnNumbers)
        return [
            reference for reference in candidates if self.table.addressable(reference)
        ]

    @overload
    def __getitem__(self, index: int) -> Cell: ...

    @overload
    def __getitem__(self, index: slice) -> TableRow: ...

    def __getitem__(self, index: int | slice) -> Cell | TableRow:
        """Return one cell, or the cells a slice selects as another view."""
        if isinstance(index, slice):
            selected = [reference.col for reference in self.cellAddresses()[index]]
            return TableRow(self.table, self.rowNumber, tuple(selected))
        return self.table.cell(self.cellAddresses()[index])

    def __iter__(self) -> Iterator[Cell]:
        """Yield each cell once, left to right, finding the addresses only once."""
        for reference in self.cellAddresses():
            yield self.table.cell(reference)

    def __len__(self) -> int:
        """Return how many cells this row holds, creating none."""
        return len(self.cellAddresses())

    def __contains__(self, candidate: object) -> bool:
        """Report whether a cell is one this row holds, creating none to find out."""
        # The inherited test walks the row, which would create every cell in it.
        return any(
            self.table.cells.get(reference) is candidate
            for reference in self.cellAddresses()
        )

    def __eq__(self, other: object) -> bool:
        """Report whether both name the same cells of the same table."""
        if not isinstance(other, TableRow):
            return NotImplemented
        return (
            other.table is self.table
            and other.rowNumber == self.rowNumber
            and tuple(other.columnNumbers) == tuple(self.columnNumbers)
        )

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        """Return which table and which row, without reaching a cell."""
        return f"TableRow({self.table.name!r}, row {self.rowNumber})"
