#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A table's grid — cells, addressed by row/column, and their merge ranges.

UPDATES
2026-08-17  Typed Cell.value, and pinned numbers to Decimal rather than float. Numbers
            stores them as IEEE-754 decimal128, measured in the fixtures, so a float
            would introduce binary rounding error into documents that never had any.
2026-08-12  Initial scaffold.
"""

from __future__ import annotations

import datetime
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
# 1.21, where float64 gets both wrong. Division still rounds — 1/3 * 3 is 0.999...9 —
# but that is inherent to decimal arithmetic and Numbers, using the same decimal128,
# behaves identically. Matching its rounding is the point.
#
# Scaled integers, the fixed-point trick from finance software, were considered and
# rejected: that works because money has a fixed scale, whereas a spreadsheet cell
# ranges from 1e-300 to 1e300. It would also mean converting between two number systems
# on every read and write, which reintroduces exactly the error being avoided.
#
# THE TRAP, and the reason to build values from strings: Decimal(0.1) carries the
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


@dataclass(frozen=True, slots=True)
class MergeRange:
    """A rectangular block of cells merged into one, anchored at its top-left cell."""

    anchorRow: int
    anchorCol: int
    rowSpan: int
    colSpan: int


@dataclass(slots=True)
class Cell:
    """One cell's value, optional formula, and style, at a specific row/column."""

    row: int
    col: int
    value: CellValue = None
    formula: str | None = None
    style: Style = field(default_factory=Style)


@dataclass(slots=True)
class Table:
    """A single table on a sheet — a sparse grid of cells plus its merge ranges."""

    name: str
    cells: dict[tuple[int, int], Cell] = field(default_factory=dict)
    mergeRanges: list[MergeRange] = field(default_factory=list)

    def cellAt(self, row: int, col: int) -> Cell:
        """Return the cell at (row, col), creating an empty one on first access."""
        key = (row, col)
        if key not in self.cells:
            self.cells[key] = Cell(row=row, col=col)
        return self.cells[key]
