#!/usr/bin/env python3
"""\
Check whether pybers can read a document, for a bug report that cannot share it.

`report` holds what a check found and `_read` the walk that finds it. A report
holds versions, type identifiers and counts, and names only when asked for them.

UPDATES
2026-10-07  Written for PYB-169.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/07"

from pybers.check._read import checkDocument
from pybers.check.report import (
    Check,
    CheckCell,
    CheckEnvironment,
    CheckFailure,
    CheckNames,
    CheckSheet,
    CheckTable,
    NumbersVersion,
)

__all__ = [
    "Check",
    "CheckCell",
    "CheckEnvironment",
    "CheckFailure",
    "CheckNames",
    "CheckSheet",
    "CheckTable",
    "NumbersVersion",
    "checkDocument",
]
