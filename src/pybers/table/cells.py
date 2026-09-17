#!/usr/bin/env python3
"""A table's grid, the cells in it, and the regions merged across it.

Addressing lives in `pybers.addressing`. Nothing
here takes a bare row and column pair: a cell is named by an address, or by `row=`
and `col=` spelled out, so the two axes cannot be passed in the wrong order.

UPDATES
2026-09-16  A cell holds text Numbers will not interpret, and says whether its
            format was chosen rather than decided (PYB-83).
2026-09-15  A fresh table identity is a version 4 UUID in file byte order (PYB-86).
2026-09-14  A table walks its declared grid, a cell is reached by row and column,
            and a cell says which merge it anchors (PYB-62). A merge drops the
            locking markers it was written with, which had discarded its anchor.
2026-09-08  A cell reads and writes its formula as text, and knows the table
            and the document it sits in so neither has to be passed (#45).
2026-09-02  Merging and unmerging a block of cells (#16). A merge discards
            the cells it covers, which is measured rather than chosen.
2026-09-01  Addressing moved out to the reference types (#9). `cellAt(row, col)`
            and the loose reference helpers are gone, and `MergeRange` now carries
            a `CellRange` rather than repeating the span arithmetic itself. A table
            also holds its declared row and column count, and two kinds of address
            name nothing and raise: one beyond that grid, and one swallowed by a
            merge.
2026-08-17  Typed Cell.value, and pinned numbers to Decimal rather than float.
            Numbers stores them as IEEE-754 decimal128, measured in the documents,
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
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from decimal import Context, Decimal
from typing import TYPE_CHECKING

from pybers.addressing.ranges import CellRange, RangeAddress, toCellRanges
from pybers.addressing.reference import (
    CellAddress,
    CellReference,
    ReferenceError,
    firstColumn,
    firstRow,
    toCellReference,
)
from pybers.errors import WriteError
from pybers.formula.nodes import Formula
from pybers.formula.parse import parseFormula
from pybers.formula.render import renderFormula
from pybers.geometry import Position
from pybers.style import Style
from pybers.table.rows import TableRows

if TYPE_CHECKING:
    # Guarded because `sheet` imports this module, and the link back is a type
    # reference rather than anything this module calls.
    from pybers.document.sheets import Document

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


# A new table's owner identity leaves its low byte clear, because Numbers derives each
# of a table's owners by adding the owner's kind to it, and the kinds reach 35.
ownerBaseMask: int = ~0xFF


def generateOwnerIdentity() -> str:
    """Return a fresh table identity, spelled as a formula spells it, low word first.

    Built from the version 4 UUID's bytes in file order, which is how every table
    identity Numbers writes reads. Measured 2026-09-15, findings-10-creation.md.
    """
    value = int.from_bytes(uuid.uuid4().bytes, "little") & ownerBaseMask
    return "".join(f"{value >> shift & 0xFFFFFFFF:08x}" for shift in (0, 32, 64, 96))


def toCellReferenceNamed(
    address: CellAddress | None, row: int | None, col: int | None
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


@dataclass(frozen=True, slots=True)
class MergeRange:
    """A rectangular block of cells merged into one, anchored at its top-left cell.

    A `CellRange` rather than four numbers, so which cells a merge covers has one
    answer. A merge is always bounded, unlike a range, and that is checked.
    """

    extent: CellRange

    def __post_init__(self) -> None:
        """Reject an unbounded extent, and drop the locking markers of a bounded one."""
        extent = self.extent
        if extent.rowsUnbounded or extent.colsUnbounded:
            raise ReferenceError(
                f"A merge covers a fixed block of cells, and {extent} is unbounded."
            )
        # A marked anchor never equals the unlocked key `Table.cell` files a cell under.
        object.__setattr__(
            self,
            "extent",
            CellRange(extent.startRow, extent.startCol, extent.endRow, extent.endCol),
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

        `__post_init__` rejects an unbounded extent, so all four are present. Saying so
        in the return type spares every caller a re-check: a merge that cannot be
        unbounded should not look like one that can.
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

    `value` is the result Numbers last cached, never derived from `formula`, so the
    two disagree until it recalculates. `errored` says a formula failed and no more,
    because the file records no reason, except a broken reference.
    """

    reference: CellReference
    value: CellValue = None
    formula: Formula | None = None
    errored: bool = False
    style: Style = field(default_factory=Style)
    # Read from the record and set only by `textLiteralSet`, so the model never holds
    # a chosen format beside something no document has been measured carrying one on.
    _formatChosen: bool = field(default=False, kw_only=True)
    # The table this belongs to, so that reading or writing a formula as text needs
    # neither the cell's own address nor the names of the other tables passed in.
    # Excluded from equality and `repr` for the reason `Document._package` is: it is
    # where this cell sits rather than what it holds.
    table: Table | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )

    @property
    def formulaText(self) -> str | None:
        """This cell's formula as Numbers displays it, or None when it holds none.

        Assignable: `cell.formulaText = "=SUM(B1:B5)"` parses against this cell,
        which is what an unlocked reference is an offset from, so the wrong host
        cannot be passed. Use `formulaSet` to name an address rather than write it.
        """
        if self.formula is None:
            return None
        return renderFormula(self.formula, self.reference, tables=self.tableNames)

    @formulaText.setter
    def formulaText(self, text: str) -> None:
        """Give this cell the formula a written expression describes."""
        self.formulaSet(text)

    def formulaSet(
        self, text: str, **pieces: CellRange | CellReference
    ) -> Formula:
        """Give this cell the formula text describes, and return what was stored.

        A keyword argument fills a `{name}` in the text with an address this library
        already validated, so `formulaSet("=SUM({sales})", sales=extent)` never
        splices one into a string and parses it back out.
        """
        self.formula = parseFormula(
            text, self.reference, tables=self.tableNames, pieces=pieces
        )
        return self.formula

    @property
    def formatChosen(self) -> bool:
        """Whether Numbers shows a chosen Data Format here rather than Automatic."""
        return self._formatChosen

    def textLiteralSet(self, text: str) -> None:
        """Hold text Numbers will not interpret, as a cell formatted Text before typing.

        `=SUM(A1:A5)` then stays that text when somebody edits the cell. Refused on a
        cell holding a formula, which this would discard.
        """
        if not isinstance(text, str):
            raise WriteError(
                f"{self.reference} holds literal text, and was given "
                f"{type(text).__name__}."
            )
        if self.formula is not None:
            raise WriteError(
                f"{self.reference} is backed by a formula, so holding literal text "
                "would discard it. Clear the formula first."
            )
        self.value = text
        self._formatChosen = True

    @property
    def tableNames(self) -> Mapping[str, str]:
        """Return the names this cell's document knows its tables by, or nothing.

        Computed from the document each time rather than cached, because a table
        renamed after a cached copy was taken would write a formula pointing at
        whichever table now answers to the old name.
        """
        document = None if self.table is None else self.table.document
        return {} if document is None else document.tableIdentities

    @property
    def mergeAnchored(self) -> MergeRange | None:
        """Return the merge this cell anchors, or None when it anchors none."""
        if self.table is None:
            return None
        merge = self.table.mergeCovering(self.reference)
        if merge is None or merge.anchor != self.reference.asUnlocked():
            return None
        return merge


@dataclass(slots=True)
class Table:
    """A single table on a sheet, a sparse grid of cells plus its merged regions.

    `identifier` is what a formula in another table names this one by, and it lives
    in the calculation engine rather than on the table, which is why a table built
    by hand has none until a document gives it one.
    """

    name: str
    rowCount: int = 0
    colCount: int = 0
    cells: dict[CellReference, Cell] = field(default_factory=dict)
    mergeRanges: list[MergeRange] = field(default_factory=list)
    identifier: str = ""
    # The archive this table was read from or saved as, and None until it has one.
    _identifier: int | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )
    # Where a table added to a sheet puts its top-left corner when it is created. Read
    # only then, so it is not a table's position and says nothing about one read.
    _origin: Position | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )
    # The document this belongs to, so a formula naming another table can be written
    # as the text Numbers shows without the caller supplying the names. Excluded from
    # equality and `repr`, the same as `Cell.table`.
    document: Document | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )

    def cell(
        self,
        address: CellAddress | None = None,
        *,
        row: int | None = None,
        col: int | None = None,
    ) -> Cell:
        """Return the cell at an address or at `row=` and `col=`, creating it if absent.

        A cell absent from the file is empty, not missing, so reading one inside
        the grid is never an error. Two addresses raise: one outside the declared
        grid, and one swallowed by a merge, reached through its anchor.
        """
        # Unlocked before it is used as a key, because `$A$1` and `A1` compare
        # unequal and are one cell. Without this the same cell files itself under
        # four spellings and a write through one is invisible to the other three.
        key = toCellReferenceNamed(address, row, col).asUnlocked()
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
            self.cells[key] = Cell(reference=key, table=self)
        return self.cells[key]

    @property
    def rows(self) -> TableRows:
        """Return the declared grid row by row, creating no cell until one is reached.

        A merged block is in its anchor's row once. A table with no grid has no rows.
        """
        last = self.rowCount if self.extent is not None else firstRow - 1
        return TableRows(self, range(firstRow, last + 1))

    def gridIterate(self) -> Iterator[Cell]:
        """Yield each cell of the declared grid once, row by row, a merge at its anchor.

        Every cell yielded is kept, so a write through one reaches the file. Unlike
        `Document.cellsIterate`, an empty cell is yielded too.
        """
        for row in self.rows:
            yield from row

    def range(self, address: RangeAddress) -> list[Cell]:
        """Return the cells one or more ranges cover, in the order they name them.

        An unbounded range is bounded by this table's extent, and an empty table has
        none, so an unbounded range over one covers nothing. Positions swallowed by a
        merge are skipped, so a merged block yields its anchor once.
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

        Read from the declared size, never derived from populated cells: 7 of the 74
        tables in the documents declare more than their cells reach, so deriving it
        returns a real rectangle smaller than the table.
        """
        if self.rowCount < 1 or self.colCount < 1:
            return None
        return CellRange(firstRow, firstColumn, self.rowCount, self.colCount)

    def formulaFill(self, source: CellAddress, through: RangeAddress) -> int:
        """Give every cell of a range the formula one cell holds, as dragging does.

        Relative references follow each row and locked ones stay put, with no
        special cases: the file stores ONE formula and every filled cell points at
        it. Positions a merge swallowed are skipped. Returns how many were filled.
        """
        origin = self.cell(source)
        if origin.formula is None:
            raise ReferenceError(
                f"{toCellReference(source)} holds no formula to fill from."
            )
        filled = 0
        for cell in self.range(through):
            if cell.reference == origin.reference:
                continue
            cell.formula = origin.formula
            filled += 1
        return filled

    def mergeAdd(self, address: RangeAddress) -> MergeRange:
        """Merge a block of cells into one, anchored at its top-left, and return it.

        **The covered cells are discarded permanently, and unmerging does not restore
        them.** Measured, not chosen: `22-merge-2x2` and its unmerged twin hold the
        same 18 cells, and Numbers writes no record at a position its own merge
        covers. A merge IMPORTED from Excel is the exception and keeps a style-only
        record at each one, which a save preserves rather than cleans up.
        """
        extent = self.rangeSingle(address, "merge")
        # A single cell is refused because Numbers cannot produce one: no document holds
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

        Takes any cell of the block rather than its extent, since two merges can never
        claim one cell. Every covered position reads as empty afterward: the values
        went when the merge was made, and nothing restores them.
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

        An unbounded range is refused rather than bounded by the table, because a block
        that follows the grid as it grows is not a block.
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

        The only way to tell a covered cell from an empty one, since a covered
        position holds no value whatever wrote the merge. Derived on every call rather
        than stored, because a copy would go stale the moment a merge changed.
        """
        reference = toCellReference(address)
        for merge in self.mergeRanges:
            if merge.covers(reference):
                return merge
        return None
