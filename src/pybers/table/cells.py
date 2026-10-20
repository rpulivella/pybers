#!/usr/bin/env python3
"""A table's grid, the cells in it, and the regions merged across it.

Addressing lives in `pybers.addressing`. Nothing
here takes a bare row and column pair: a cell is named by an address, or by `row=`
and `col=` spelled out, so the two axes cannot be passed in the wrong order.

UPDATES
2026-10-20  `Cell` moved to `cell`, keeping this module within its limit, for
            PYB-217.
2026-10-20  A cell sits at a `CellAddress`, and `cell.reference` names it from
            anywhere; a table finds its sheet, for PYB-217.
2026-10-14  `cells` is a read-only view of the table's own store, for PYB-193.
2026-10-14  A range is checked against the grid in `bounds`, for PYB-193.
2026-10-12  A changed kind describes its format as UNDETERMINED, for PYB-190.
2026-10-11  Table names are returned as a frozendict, for PYB-189.
2026-10-01  A cell describes the kind its record stores and the format it shows
            with, replacing `errored` and `formatChosen` (PYB-141).
2026-09-30  A cell keeps the rich text its record held, so a fill can tell it, for
            PYB-137.
2026-09-29  `MergeRange` moved to `merges`, keeping this module within its limit.
2026-09-29  A block of cells is copied to a new anchor, and a copied cell says
            whether its borders go with it (PYB-136).
2026-09-29  A block fills a range under the rules its caller names, replacing
            `formulaFill`, and a filled cell names the cell it copies (PYB-118).
2026-09-23  A block of cells moves to a new anchor, and a cell remembers where
            its record sits so a save can tell (PYB-18).
2026-09-22  A range reaching outside the grid is refused in one place (PYB-113).
2026-09-18  Rows and columns are added and removed, and each line carries the
            identity Numbers keys hidden state by (PYB-17).
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

import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from pybers.addressing.ranges import CellRange, CellRangeLike, toCellRanges
from pybers.addressing.reference import (
    CellAddress,
    CellReferenceLike,
    ReferenceError,
    firstColumn,
    firstRow,
    toCellReference,
    toCellReferenceNamed,
)
from pybers.formula.relocation import FormulaReferenceRelocation
from pybers.geometry import Position
from pybers.table.bounds import listRangePositions, refuseRangeOutside
from pybers.table.cell import Cell
from pybers.table.copy import copyCells
from pybers.table.fill import CellValueFill, fillCells
from pybers.table.merges import MergeRange
from pybers.table.relocation import moveCells
from pybers.table.rows import TableRows
from pybers.table.structure import (
    buildGridEdit,
    editGrid,
    generateLineIdentities,
)

if TYPE_CHECKING:
    # Guarded because `sheet` imports this module, and the link back is a type
    # reference rather than anything this module calls.
    from pybers.document.sheets import Document, Sheet

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
    # The feature's own store; a caller reads `cells`, which refuses a write.
    _cells: dict[CellAddress, Cell] = field(default_factory=dict)
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
    # Each row's and column's identity, in order, which Numbers keys hidden state by
    # and a broken reference names. Fresh for a table built rather than read.
    _rowIdentities: list[int] = field(
        default_factory=list, repr=False, compare=False, kw_only=True
    )
    _columnIdentities: list[int] = field(
        default_factory=list, repr=False, compare=False, kw_only=True
    )

    def __post_init__(self) -> None:
        """Identify every line of a table that arrived without identities."""
        if not self._rowIdentities:
            self._rowIdentities = generateLineIdentities(self.rowCount)
        if not self._columnIdentities:
            self._columnIdentities = generateLineIdentities(self.colCount)

    def rowAdd(self, row: int, count: int = 1) -> None:
        """Insert empty rows so the first is row `row`, moving the rest down.

        Every formula in the document follows, and a range growing past `row` moves
        only its far end. A merge the rows land inside grows.
        """
        editGrid(self, buildGridEdit(self, row, count, rows=True, removing=False))

    def rowRemove(self, row: int, count: int = 1) -> list[Cell]:
        """Delete rows starting at `row`, and return each cell left reading `#REF!`.

        A range losing some of its rows shrinks, and one losing all of them breaks,
        as Numbers does. A merge losing its anchor's row is refused.
        """
        return editGrid(self, buildGridEdit(self, row, count, rows=True, removing=True))

    def columnAdd(self, column: int | str, count: int = 1) -> None:
        """Insert empty columns so the first is `column`, a number or `"C"`.

        Every formula in the document follows, and a merge the columns land inside
        grows, exactly as `rowAdd` does sideways.
        """
        editGrid(self, buildGridEdit(self, column, count, rows=False, removing=False))

    def columnRemove(self, column: int | str, count: int = 1) -> list[Cell]:
        """Delete columns starting at `column`, returning each cell left `#REF!`.

        The sideways counterpart of `rowRemove`, with the same refusals.
        """
        return editGrid(
            self, buildGridEdit(self, column, count, rows=False, removing=True)
        )

    def cellsMove(
        self,
        source: CellRangeLike,
        anchor: CellReferenceLike,
        *,
        references: FormulaReferenceRelocation,
    ) -> list[Cell]:
        """Move a block so its top-left lands on `anchor`, carrying merges and styles.

        `references` has no default. Returns each cell whose formula now reads a
        cell the move emptied. Occupied destinations and cut merges raise.
        """
        return moveCells(self, source, anchor, references)

    def cellsCopy(
        self,
        source: CellRangeLike,
        anchor: CellReferenceLike,
        *,
        references: FormulaReferenceRelocation,
    ) -> CellRange:
        """Copy a block so its top-left lands on `anchor`, with merges and borders.

        `references` has no default. Returns where the copy landed. Occupied
        destinations, an overlap with the source and cut merges raise.
        """
        return copyCells(self, source, anchor, references)

    @property
    def cells(self) -> Mapping[CellAddress, Cell]:
        """Return the cells by address, read-only, since only the table edits them."""
        return MappingProxyType(self._cells)

    def cell(
        self,
        address: CellReferenceLike | None = None,
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
        key = toCellReferenceNamed(address, row, col).address
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
        if key not in self._cells:
            self._cells[key] = Cell(address=key, table=self)
        return self._cells[key]

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

    def range(self, address: CellRangeLike) -> list[Cell]:
        """Return the cells one or more ranges cover, in the order they name them.

        An unbounded range is bounded by this table's extent, and an empty table has
        none, so an unbounded range over one covers nothing. Positions swallowed by a
        merge are skipped, so a merged block yields its anchor once.
        """
        return [self.cell(reference) for reference in listRangePositions(self, address)]

    def addressable(self, address: CellReferenceLike) -> bool:
        """Report whether an address names a cell this table can hand over.

        False for a position swallowed by a merge, which is why a range over a
        merged block yields the anchor once rather than one cell per position.
        """
        reference = toCellReference(address).address
        merge = self.mergeCovering(reference)
        return merge is None or merge.anchor == reference

    @property
    def sheet(self) -> Sheet | None:
        """Return the sheet holding this table, found through its document, or None."""
        if self.document is None:
            return None
        return next(
            (
                sheet for sheet in self.document.sheets
                if any(table is self for table in sheet.tables)
            ),
            None,
        )

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

    def cellsFill(
        self, source: CellRangeLike, through: CellRangeLike, *,
        references: FormulaReferenceRelocation, values: CellValueFill,
    ) -> int:
        """Repeat a block of any content across a range, copying each cell whole.

        Neither rule has a default. Positions a merge covers are skipped, and a
        block holding a merge is refused. `CONTINUE_SERIES` continues each column
        that begins a series, in any one direction. Returns how many cells were filled.
        """
        return fillCells(self, source, through, references, values)

    def mergeAdd(self, address: CellRangeLike) -> MergeRange:
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
                f"{extent} is one cell, and a merge joins two or more."
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
                self._cells.pop(reference, None)
        return merge

    def mergeRemove(self, address: CellReferenceLike) -> MergeRange:
        """Unmerge the block occupying a cell, and return the merge that was removed.

        Takes any cell of the block rather than its extent, since two merges can never
        claim one cell. Every covered position reads as empty afterward: the values
        went when the merge was made, and nothing restores them.
        """
        merge = self.mergeCovering(address)
        if merge is None:
            raise ReferenceError(
                f"No merge in {self.name!r} covers "
                f"{toCellReference(address).address}."
            )
        self.mergeRanges.remove(merge)
        return merge

    def rangeSingle(self, address: CellRangeLike, action: str) -> CellRange:
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
        refuseRangeOutside(self, item)
        return item

    def mergeCovering(self, address: CellReferenceLike) -> MergeRange | None:
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
