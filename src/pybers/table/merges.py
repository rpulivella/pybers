#!/usr/bin/env python3
"""A rectangular block of cells merged into one, anchored at its top-left cell.

The model half of a merge. How one is stored, as a formula in the merge store,
is `_merges`, and what it discards is `Table.mergeAdd`'s to say.

UPDATES
2026-09-29  Moved out of `cells` for PYB-136, which took that module past its limit.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/29"

from dataclasses import dataclass

from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import CellAddress, CellReference, ReferenceError


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


__all__ = ["MergeRange"]
