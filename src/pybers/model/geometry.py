#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Absolute placement for objects that float on a sheet (text boxes, images, shapes)
as opposed to cells, which are placed by row/column in a table's grid.

UPDATES
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


@dataclass(frozen=True, slots=True)
class Size:
    """A width/height in points."""

    width: float
    height: float
