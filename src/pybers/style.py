#!/usr/bin/env python3
"""Appearance, the properties shared by cells, shapes, and text runs.

UPDATES
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
class Style:
    """One cell or shape's visual formatting, fill, font, and alignment together.

    Frozen and hashable on purpose. Numbers shares one style archive between many
    objects, so a mutable one lets an edit to a cell silently restyle unrelated
    shapes. Immutability makes that unrepresentable: swap in a new Style instead.
    """

    bgColor: str | None = None
    fontColor: str | None = None
    fontName: str | None = None
    fontSize: float | None = None
    bold: bool = False
    italic: bool = False
    horizontalAlignment: str = "auto"
    verticalAlignment: str = "bottom"
