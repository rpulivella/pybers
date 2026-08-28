#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Appearance, the properties shared by cells, shapes, and text runs.

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
class Style:
    """One cell or shape's visual formatting, fill, font, and alignment together.

    Frozen and hashable on purpose: the old numbers-parser fork this library replaces
    shared one mutable Style object by reference across cells, so mutating one cell's
    style silently corrupted an unrelated cell's formatting at save time. Making Style
    immutable makes that bug class unrepresentable, a cell (or shape) can only ever swap
    in a whole new Style, never mutate a shared one out from under another object.
    """

    bgColor: str | None = None
    fontColor: str | None = None
    fontName: str | None = None
    fontSize: float | None = None
    bold: bool = False
    italic: bool = False
    horizontalAlignment: str = "auto"
    verticalAlignment: str = "bottom"
