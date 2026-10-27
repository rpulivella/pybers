#!/usr/bin/env python3
"""A rectangle of cells, and a list of rectangles addressed at once.

Split from `pybers.addressing.reference` because only a range has to represent the
absence of a coordinate. A whole-column reference is a column with no row at all,
which is how the file stores one, and no single-cell address may hold that. A range
in the file holds a sentinel there instead, which the formula reader turns into
absence.

**Unboundedness is absence, never a sentinel.** A range standing in for `A` with
rows 1 through 1048576 would compare equal to a bounded range that happens to span
the same cells, and the two mean different things: one follows the table as it
grows and the other does not.

UPDATES
2026-10-27  A range names its table when its context needs one, as a reference
            does, for PYB-260.
2026-10-19  `CellRangeLike`, what a call accepts for a range, for PYB-217.
2026-10-13  A range in the file marks an unbounded axis with a sentinel, for PYB-139.
2026-09-13  A range endpoint past the last row is refused, for #67.
2026-09-08  Moved into `pybers.addressing` for #58, unchanged.
2026-09-01  Written for #9.
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
from collections.abc import Iterator
from dataclasses import dataclass, field, replace

from pybers.addressing.reference import (
    CellAddress,
    CellReference,
    CellReferenceLike,
    ReferenceError,
    TableReference,
    absoluteMarker,
    cellPattern,
    chooseMarker,
    firstColumn,
    firstRow,
    lastColumn,
    lastRow,
    splitTableName,
    tableNameSeparator,
    toCellReference,
    toColumnLetter,
    toColumnNumber,
)

rangeSeparator: str = ":"
listSeparator: str = ","

# The two endpoint forms a single cell cannot take. Matched separately rather than
# teased out of one expression with optional groups, because "A" and "1" have to be
# told apart by which one matched.
columnPattern: re.Pattern[str] = re.compile(r"^(\$?)([A-Za-z]+)$")
rowPattern: re.Pattern[str] = re.compile(r"^(\$?)([0-9]+)$")

# One end of one axis: its coordinate, absent when that axis is unbounded, and
# whether it was written locked.
AxisBound = tuple[int | None, bool]


@dataclass(frozen=True, slots=True)
class RangeEndpoint:
    """One side of a written range, with either coordinate free to be absent.

    Internal to parsing. It exists so that a column with no row has somewhere to
    live between the text and the range, which no address type may hold.
    """

    row: int | None
    col: int | None
    rowAbsolute: bool
    colAbsolute: bool


def parseEndpoint(text: str, whole: str) -> RangeEndpoint:
    """Return one endpoint of a written range, naming the whole range on failure.

    The original is carried through so that the bad half of `A1:C` reports what the
    caller actually wrote rather than the fragment it was split into.
    """
    candidate = text.strip()
    endpoint: RangeEndpoint | None = None
    cell = cellPattern.match(candidate)
    if cell is not None:
        colMarker, letters, rowMarker, digits = cell.groups()
        endpoint = RangeEndpoint(
            int(digits),
            toColumnNumber(letters),
            rowMarker == absoluteMarker,
            colMarker == absoluteMarker,
        )
    column = columnPattern.match(candidate)
    if endpoint is None and column is not None:
        marker, letters = column.groups()
        endpoint = RangeEndpoint(
            None, toColumnNumber(letters), False, marker == absoluteMarker
        )
    row = rowPattern.match(candidate)
    if endpoint is None and row is not None:
        marker, digits = row.groups()
        endpoint = RangeEndpoint(int(digits), None, marker == absoluteMarker, False)
    if endpoint is None:
        raise ReferenceError(f"{whole!r} is not a range: {text!r} addresses nothing.")
    # Checked here rather than left to the range constructor, which would report
    # row 0 without saying that `A0` is where it came from.
    if endpoint.row is not None and endpoint.row < firstRow:
        raise ReferenceError(
            f"{whole!r} names row {endpoint.row}, and rows count from {firstRow}."
        )
    if endpoint.row is not None and endpoint.row > lastRow:
        raise ReferenceError(
            f"{whole!r} names row {endpoint.row}, past row {lastRow}, "
            "which is the last row a Numbers table can hold."
        )
    return endpoint


def orderAxis(one: AxisBound, other: AxisBound) -> tuple[AxisBound, AxisBound]:
    """Return two bounds on one axis in ascending order, each keeping its marker.

    An unbounded axis passes through untouched, since there is nothing to order.
    """
    if one[0] is None or other[0] is None:
        return (one, other)
    return (one, other) if one[0] <= other[0] else (other, one)


def renderEndpoint(bound: RangeEndpoint) -> str:
    """Return one endpoint written out, omitting whichever axis is unbounded."""
    text = ""
    if bound.col is not None:
        text += f"{chooseMarker(bound.colAbsolute)}{toColumnLetter(bound.col)}"
    if bound.row is not None:
        text += f"{chooseMarker(bound.rowAbsolute)}{bound.row}"
    return text


@dataclass(frozen=True, slots=True)
class CellRange:
    """A rectangle of cells, with either axis free to be unbounded.

    An unbounded axis holds None at both of its ends, which is how a whole-column
    or whole-row reference is expressed. Unbounded on both axes would name every
    cell there is and is rejected, so a range always says something.
    """

    startRow: int | None
    startCol: int | None
    endRow: int | None
    endCol: int | None
    startRowAbsolute: bool = field(default=False, kw_only=True)
    startColAbsolute: bool = field(default=False, kw_only=True)
    endRowAbsolute: bool = field(default=False, kw_only=True)
    endColAbsolute: bool = field(default=False, kw_only=True)
    table: TableReference | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        """Reject a rectangle half-unbounded, inverted, or off either end.

        The far end is checked here as well as in `parseEndpoint`, because
        `fromAxes` builds a range without going through the text, which is the
        path `FormulaRange.resolve` takes.
        """
        for axis, origin, limit, low, high in (
            ("Row", firstRow, lastRow, self.startRow, self.endRow),
            ("Column", firstColumn, lastColumn, self.startCol, self.endCol),
        ):
            if (low is None) != (high is None):
                raise ReferenceError(
                    f"{axis} bounds {low} to {high}: an axis is unbounded at both "
                    "ends or at neither."
                )
            if low is None or high is None:
                continue
            if low < origin:
                raise ReferenceError(
                    f"{axis} {low} is before {axis.lower()} {origin}, which is "
                    "where a table starts."
                )
            if high > limit:
                raise ReferenceError(
                    f"{axis} {high} is past {axis.lower()} {limit}, which is where "
                    "a table ends."
                )
            if low > high:
                raise ReferenceError(f"{axis} bounds run backward, {low} to {high}.")
        if self.rowsUnbounded and self.colsUnbounded:
            raise ReferenceError("A range unbounded on both axes names every cell.")

    @property
    def rowsUnbounded(self) -> bool:
        """Report whether this range spans every row, as `A` does."""
        return self.startRow is None

    @property
    def colsUnbounded(self) -> bool:
        """Report whether this range spans every column, as `1` does."""
        return self.startCol is None

    @property
    def rowSpan(self) -> int | None:
        """Return how many rows this covers, or None when it covers them all."""
        if self.startRow is None or self.endRow is None:
            return None
        return self.endRow - self.startRow + 1

    @property
    def colSpan(self) -> int | None:
        """Return how many columns this covers, or None when it covers them all."""
        if self.startCol is None or self.endCol is None:
            return None
        return self.endCol - self.startCol + 1

    @property
    def start(self) -> CellReference | None:
        """Return the top-left cell, or None when either axis is unbounded.

        None rather than a substituted coordinate: a whole-column range has no
        first row, and answering with row 1 would be a guess the caller could not
        tell from a fact.
        """
        if self.startRow is None or self.startCol is None:
            return None
        return CellReference(
            self.startRow,
            self.startCol,
            rowAbsolute=self.startRowAbsolute,
            colAbsolute=self.startColAbsolute,
        )

    @property
    def end(self) -> CellReference | None:
        """Return the bottom-right cell, or None when either axis is unbounded."""
        if self.endRow is None or self.endCol is None:
            return None
        return CellReference(
            self.endRow,
            self.endCol,
            rowAbsolute=self.endRowAbsolute,
            colAbsolute=self.endColAbsolute,
        )

    @classmethod
    def fromAxes(
        cls,
        rows: tuple[AxisBound, AxisBound],
        cols: tuple[AxisBound, AxisBound],
    ) -> CellRange:
        """Return the rectangle two opposite corners bound, given in either order.

        Each axis is ordered on its own, since a caller's two corners are as often
        opposite ones as top-left and bottom-right. Locking travels with the coordinate
        it was written against, and both other constructors end here.
        """
        low, high = orderAxis(*rows)
        left, right = orderAxis(*cols)
        return cls(
            low[0],
            left[0],
            high[0],
            right[0],
            startRowAbsolute=low[1],
            startColAbsolute=left[1],
            endRowAbsolute=high[1],
            endColAbsolute=right[1],
        )

    @classmethod
    def fromReferences(
        cls, start: CellReference | CellAddress, end: CellReference | CellAddress
    ) -> CellRange:
        """Return the rectangle two cells bound, given in either order."""
        start, end = toCellReference(start), toCellReference(end)
        return cls.fromAxes(
            ((start.row, start.rowAbsolute), (end.row, end.rowAbsolute)),
            ((start.col, start.colAbsolute), (end.col, end.colAbsolute)),
        )

    @classmethod
    def parse(cls, reference: str) -> CellRange:
        """Return the rectangle a written range addresses.

        Accepts one cell (`B2`), a rectangle (`A1:C3`), a whole column (`A`), a
        whole row (`1`), and a span of either (`A:C`, `1:3`), each named by its
        table as far as the text names it, `Q3::B2:D5`. Both endpoints of a span
        have to be the same kind, since `A1:C` names no rectangle.
        """
        table, text = splitTableName(reference)
        parts = text.strip().split(rangeSeparator)
        if len(parts) > 2:
            raise ReferenceError(f"{reference!r} names more than two endpoints.")
        first = parseEndpoint(parts[0], reference)
        last = first if len(parts) == 1 else parseEndpoint(parts[1], reference)
        if (first.row is None) != (last.row is None) or (first.col is None) != (
            last.col is None
        ):
            raise ReferenceError(
                f"{reference!r} bounds one endpoint on an axis that the other "
                "leaves unbounded."
            )
        found = cls.fromAxes(
            ((first.row, first.rowAbsolute), (last.row, last.rowAbsolute)),
            ((first.col, first.colAbsolute), (last.col, last.colAbsolute)),
        )
        return found if table is None else replace(found, table=table)

    def covers(self, address: CellReferenceLike) -> bool:
        """Report whether a cell falls inside this range, its edges included."""
        reference = toCellReference(address)
        withinRows = self.startRow is None or (
            self.endRow is not None and self.startRow <= reference.row <= self.endRow
        )
        withinCols = self.startCol is None or (
            self.endCol is not None and self.startCol <= reference.col <= self.endCol
        )
        return withinRows and withinCols

    def boundedBy(self, extent: CellRange) -> CellRange:
        """Return this range with each unbounded axis filled in from an extent.

        A range knows nothing about the table it is used against, so a whole-column
        reference becomes real cells only through something that does. The extent
        has to be bounded on both axes, since it is what supplies the answer.
        """
        if extent.rowsUnbounded or extent.colsUnbounded:
            raise ReferenceError(
                f"An extent is bounded on both axes, and {extent} is not."
            )
        return CellRange(
            extent.startRow if self.rowsUnbounded else self.startRow,
            extent.startCol if self.colsUnbounded else self.startCol,
            extent.endRow if self.rowsUnbounded else self.endRow,
            extent.endCol if self.colsUnbounded else self.endCol,
            startRowAbsolute=self.startRowAbsolute,
            startColAbsolute=self.startColAbsolute,
            endRowAbsolute=self.endRowAbsolute,
            endColAbsolute=self.endColAbsolute,
            table=self.table,
        )

    def asReference(self) -> str:
        """Return this range as it would be written, markers included.

        A rectangle whose two endpoints are written identically comes back as the
        single cell it is, so what goes out is what a caller would have put in.
        """
        first = renderEndpoint(
            RangeEndpoint(
                self.startRow,
                self.startCol,
                self.startRowAbsolute,
                self.startColAbsolute,
            )
        )
        last = renderEndpoint(
            RangeEndpoint(
                self.endRow, self.endCol, self.endRowAbsolute, self.endColAbsolute
            )
        )
        if first == last:
            return first
        return f"{first}{rangeSeparator}{last}"

    def __iter__(self) -> Iterator[CellAddress]:
        """Yield every cell this range covers, row by row and left to right.

        An unbounded range cannot be walked, and refusing is better than inventing
        a limit. `boundedBy` supplies the missing end.
        """
        if self.startRow is None or self.endRow is None:
            raise ReferenceError(f"{self} spans every row and cannot be walked.")
        if self.startCol is None or self.endCol is None:
            raise ReferenceError(f"{self} spans every column and cannot be walked.")
        for row in range(self.startRow, self.endRow + 1):
            for col in range(self.startCol, self.endCol + 1):
                yield CellAddress(row, col)

    def __str__(self) -> str:
        """Return the written form, qualified by its table when it names one."""
        if self.table is None:
            return self.asReference()
        return f"{self.table}{tableNameSeparator}{self.asReference()}"


@dataclass(frozen=True, slots=True)
class CellRangeList:
    """Several rectangles named at once, in the order they were written.

    Order is preserved rather than normalized, because a multi-range argument to a
    formula is positional and re-emitting it in another order changes what it says.
    """

    ranges: tuple[CellRange, ...]

    def __post_init__(self) -> None:
        """Reject an empty list, which names nothing and reads as an oversight."""
        if not self.ranges:
            raise ReferenceError("A range list names at least one range.")

    @classmethod
    def parse(cls, reference: str) -> CellRangeList:
        """Return the ranges a comma-separated list names, in the order written."""
        parts = reference.split(listSeparator)
        if any(not part.strip() for part in parts):
            raise ReferenceError(f"{reference!r} has an empty range in it.")
        return cls(tuple(CellRange.parse(part) for part in parts))

    def asReference(self) -> str:
        """Return the list as it would be written, in its own order."""
        return listSeparator.join(item.asReference() for item in self.ranges)

    def covers(self, address: CellReferenceLike) -> bool:
        """Report whether any range in the list covers a cell."""
        return any(item.covers(address) for item in self.ranges)

    def __iter__(self) -> Iterator[CellRange]:
        """Yield each range in the order it was written."""
        return iter(self.ranges)

    def __len__(self) -> int:
        """Return how many ranges this list names."""
        return len(self.ranges)

    def __str__(self) -> str:
        """Return the written form, so an error message reads as a list."""
        return self.asReference()


# What a caller may hand to anything that addresses more than one cell. A plain
# string covers both a single range and a comma-separated list of them.
CellRangeLike = CellRange | CellRangeList | str


def toCellRanges(address: CellRangeLike) -> tuple[CellRange, ...]:
    """Return the ranges an address names, as a tuple even when there is one.

    One range and a list of them are treated the same way everywhere downstream, so
    the difference is settled here rather than at each call site.
    """
    if isinstance(address, str):
        return CellRangeList.parse(address).ranges
    if isinstance(address, CellRangeList):
        return address.ranges
    return (address,)
