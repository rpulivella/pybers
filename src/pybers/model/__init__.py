#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The pybers object model — typed dataclasses standing in for a .numbers document's real
structure, split by feature area rather than by class: style, geometry, rich text,
floating shapes, table/cell, sheet/workbook.

Nothing here knows how to read or write the underlying iWork archive format; that lives
in pybers.archive once it exists. Keeping the model isolated from the archive format is
deliberate: it is what makes the round-trip contract testable (build a model, write it,
read it back, assert equality) without needing a real .numbers file for every test.

UPDATES
2026-08-12  Initial scaffold: style, geometry, text, shapes, table, sheet.
"""

from pybers.model.geometry import Position, Size
from pybers.model.shapes import GraphicalObject, Image, Shape, TextBox
from pybers.model.sheet import Sheet, Workbook
from pybers.model.style import Style
from pybers.model.table import Cell, MergeRange, Table
from pybers.model.text import Paragraph, RichText, TextRun

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
