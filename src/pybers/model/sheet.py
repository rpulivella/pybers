#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A sheet holds tables (row/column grids) and graphical objects (things that float on
the sheet at an absolute position, text boxes, images, shapes) side by side, since
Numbers lets both live on the same sheet independently. A workbook is a list of sheets.

UPDATES
2026-08-12  Initial scaffold.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pybers.model.shapes import GraphicalObject
from pybers.model.table import Table


@dataclass(slots=True)
class Sheet:
    """One sheet (tab) in a workbook: its tables and its floating graphical objects."""

    name: str
    tables: list[Table] = field(default_factory=list)
    graphicalObjects: list[GraphicalObject] = field(default_factory=list)


@dataclass(slots=True)
class Workbook:
    """The root of the pybers object model, one .numbers document's sheets."""

    sheets: list[Sheet] = field(default_factory=list)
