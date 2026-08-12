#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A table's grid — cells, addressed by row/column, and their merge ranges.

UPDATES
2026-08-12  Initial scaffold.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pybers.model.style import Style


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
    value: object = None
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
