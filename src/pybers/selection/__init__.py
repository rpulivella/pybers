#!/usr/bin/env python3
"""\
Selecting any sheet, table, range or cell one way, in the manner of CSS.

A selector is text, `Budget::Q*[kind=number]`, and the frozen `Selector` it parses
to. One resolver reads it relative to a document, a sheet or a table, and returns a
tuple of references. Matching is apart from acting: a selection changes
nothing, and each action states which selections it accepts.

UPDATES
2026-11-03  Written for PYB-223.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/03"

from pybers.addressing.ranges import SelectionMatch
from pybers.selection.selector import (
    Selector,
    SelectorError,
    SelectorLike,
    quoteSelectorName,
)

__all__ = [
    "SelectionMatch",
    "Selector",
    "SelectorError",
    "SelectorLike",
    "quoteSelectorName",
]
