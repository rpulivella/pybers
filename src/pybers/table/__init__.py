#!/usr/bin/env python3
"""\
Tables: the grid a caller holds, and the tiles and records it is stored as.

One feature, whole. `cells` is what a caller reaches through, and `_read` and
`_write` are the archive halves, private because a caller wanting a cell asks the
table for one rather than walking a tile.

**A table is sparse and declares more than it holds.** The grid comes from what the
table declares, never from which cells hold something: 7 of the 74 tables in the
documents declare more rows or columns than their records reach, so an inferred size
is silently short.

**A merge discards what it covers, and unmerging does not bring it back.** That is
measured rather than chosen, and it is why a covered position has no record and
`Table.cell` refuses one by name.

UPDATES
2026-10-01  `CellKind`, `CellFormat` and `CellDescription`, for PYB-141.
2026-09-30  A fill under `CONTINUE_SERIES` continues a series, for PYB-137.
2026-09-29  `CellValueFill`, the value rule a fill names, for PYB-118.
2026-09-14  `TableRows` and `TableRow`, the grid walked row by row, for PYB-62.
2026-09-08  Made a package of its own for #58, gathering the model and both
            archive halves out of `pybers.model`, `reader` and `writer`.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from pybers.table.cells import Cell, CellValue, Table
from pybers.table.fill import CellValueFill
from pybers.table.kinds import CellDescription, CellFormat, CellKind
from pybers.table.merges import MergeRange
from pybers.table.rows import TableRow, TableRows

__all__ = [
    "Cell",
    "CellDescription",
    "CellFormat",
    "CellKind",
    "CellValue",
    "CellValueFill",
    "MergeRange",
    "Table",
    "TableRow",
    "TableRows",
]
