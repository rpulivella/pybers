#!/usr/bin/env python3
"""A place on a sheet in points, as opposed to a cell's place in a table's grid.

UPDATES
2026-10-24  `Size` removed with the drawable scaffold that alone used it, for
            PYB-259.
2026-09-08  Moved out of `pybers.model` for #58, unchanged.
2026-08-12  Initial scaffold.
"""

from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/12"

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Position:
    """A point on a sheet, in points, measured from the sheet's top-left corner."""

    x: float
    y: float

