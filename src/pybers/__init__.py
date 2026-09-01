#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pybers, a clean, round-trip-tested library for reading and writing Apple Numbers documents.

Built in deep respect for Apple Numbers itself, and standing on the shoulders of
numbers-parser (https://github.com/masaccio/numbers-parser), whose reverse-engineering of
Apple's undocumented .numbers archive format is the foundation this project depends on.
The goal here is for editing a .numbers file programmatically to be as reliable as using
Numbers by hand, built as a clean, dataclass-based design with a library-and-CLI/TUI split
and first-class named styles from the start. See CLAUDE.md for the full origin story and
design contract.

UPDATES
2026-08-12  Initial scaffold.
"""

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/12"

from pybers.model import (
    Cell,
    CellAddress,
    CellRange,
    CellRangeList,
    CellReference,
    CellValue,
    RangeAddress,
    ReferenceError,
    columnLetter,
    columnNumber,
    toCellRanges,
    toCellReference,
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
    Document,
)
from pybers.reader import open

__all__ = [
    "Cell",
    "CellAddress",
    "CellRange",
    "CellRangeList",
    "CellReference",
    "CellValue",
    "RangeAddress",
    "ReferenceError",
    "columnLetter",
    "columnNumber",
    "open",
    "toCellRanges",
    "toCellReference",
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
    "Document",
]
