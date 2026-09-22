#!/usr/bin/env python3
"""\
How a cell and a rectangle of cells are named, which every feature reaches for.

Public, and below the features rather than inside one: a formula names a cell, a
table is indexed by one, and a merge covers a rectangle of them, so addressing
belongs to none of the three and is used by all of them.

Split in two by what each has to represent. A single cell always has a row and a
column, and only a range has to express the absence of one, since a whole-column
reference is a column with no row at all.

Two things here return a valid-looking wrong answer rather than raising, which is
why each carries its own guard in the module that owns it:

- **Column labels are base-26 with no zero digit.** Z is 26 and AA is 27, so an
  ordinary base conversion is off by one at every 26 boundary and names a real
  column, simply not the requested one.
- **The dollar sign is a per-axis fact.** One formula holds an absolute column
  beside a relative row and then the reverse, so a single flag per reference
  cannot represent what Numbers stores.

UPDATES
2026-09-18  `GridEdit`, where lines land after a structural edit, for PYB-17.
2026-09-08  Made a package of its own for #58, out of `pybers.model`.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from pybers.addressing.lines import GridEdit, LineMapping, LinesUnchanged
from pybers.addressing.ranges import (
    AxisBound,
    CellRange,
    CellRangeList,
    RangeAddress,
    RangeEndpoint,
    listSeparator,
    parseEndpoint,
    rangeSeparator,
    renderEndpoint,
    toCellRanges,
)
from pybers.addressing.reference import (
    CellAddress,
    CellReference,
    ReferenceError,
    absoluteMarker,
    alphabetSize,
    cellPattern,
    chooseMarker,
    firstColumn,
    firstRow,
    tableNameSeparator,
    toCellReference,
    toColumnLetter,
    toColumnNumber,
)

__all__ = [
    "AxisBound",
    "CellAddress",
    "CellRange",
    "CellRangeList",
    "CellReference",
    "GridEdit",
    "LineMapping",
    "LinesUnchanged",
    "RangeAddress",
    "RangeEndpoint",
    "ReferenceError",
    "absoluteMarker",
    "alphabetSize",
    "cellPattern",
    "toColumnLetter",
    "toColumnNumber",
    "renderEndpoint",
    "firstColumn",
    "firstRow",
    "listSeparator",
    "chooseMarker",
    "parseEndpoint",
    "rangeSeparator",
    "tableNameSeparator",
    "toCellRanges",
    "toCellReference",
]
