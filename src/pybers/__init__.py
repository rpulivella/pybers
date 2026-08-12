#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pybers — a clean, round-trip-tested library for reading and writing Apple Numbers documents.

Built in deep respect for Apple Numbers itself: the goal is for editing a .numbers file
programmatically to be as reliable as using Numbers by hand. This package replaces an ad
hoc numbers-parser fork after four real correctness bugs (style loss on write, a shared
mutable Style object corrupting an unrelated cell, a row-insert regex that shifted the
wrong end of a formula range, a crash decoding certain number formats) made continued
patching untrustworthy. See CLAUDE.md for the full origin story and design contract.

UPDATES
2026-08-12  Initial scaffold.
"""

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "TBD"
__version__ = "0.1.0"
__email__ = "rpulivella@icloud.com"
__status__ = "Development"
__date__ = "2026/08/12"

from pybers.model import (
    Cell,
    GraphicalObject,
    Image,
    MergeRange,
    Paragraph,
    Position,
    RichText,
    Shape,
    Sheet,
    Size,
    Style,
    Table,
    TextBox,
    TextRun,
    Workbook,
)

__all__ = [
    "Cell",
    "GraphicalObject",
    "Image",
    "MergeRange",
    "Paragraph",
    "Position",
    "RichText",
    "Shape",
    "Sheet",
    "Size",
    "Style",
    "Table",
    "TextBox",
    "TextRun",
    "Workbook",
]
