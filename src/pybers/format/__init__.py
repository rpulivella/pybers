#!/usr/bin/env python3
"""\
The format feature: the format a cell shows its value with, its control, and both
archive halves.

UPDATES
2026-11-10  A format's text form, `formatCellFormat` and `parseCellFormat`, for
            PYB-145.
2026-11-09  Written for PYB-145, taking in the control family from `pybers.table`.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/09"

from pybers.format.controls import (
    CellControl,
    CellControlBase,
    CellControlCheckbox,
    CellControlPopUpMenu,
    CellControlSlider,
    CellControlStarRating,
    CellControlStepper,
    CellControlType,
    CellControlUnknown,
)
from pybers.format.formats import (
    CellFormat,
    CellFormatAutomatic,
    CellFormatBase,
    CellFormatBoolean,
    CellFormatCheckbox,
    CellFormatCurrency,
    CellFormatDateTime,
    CellFormatDuration,
    CellFormatFamily,
    CellFormatFraction,
    CellFormatNumber,
    CellFormatNumberCustom,
    CellFormatNumeralSystem,
    CellFormatPercent,
    CellFormatScientific,
    CellFormatShown,
    CellFormatStarRating,
    CellFormatText,
    CellFormatUnknown,
)
from pybers.format.text import CellFormatError, formatCellFormat, parseCellFormat

__all__ = [
    "CellControl",
    "CellControlBase",
    "CellControlCheckbox",
    "CellControlPopUpMenu",
    "CellControlSlider",
    "CellControlStarRating",
    "CellControlStepper",
    "CellControlType",
    "CellControlUnknown",
    "CellFormat",
    "CellFormatAutomatic",
    "CellFormatBase",
    "CellFormatBoolean",
    "CellFormatCheckbox",
    "CellFormatCurrency",
    "CellFormatDateTime",
    "CellFormatDuration",
    "CellFormatError",
    "CellFormatFamily",
    "CellFormatFraction",
    "CellFormatNumber",
    "CellFormatNumberCustom",
    "CellFormatNumeralSystem",
    "CellFormatPercent",
    "CellFormatScientific",
    "CellFormatShown",
    "CellFormatStarRating",
    "CellFormatText",
    "CellFormatUnknown",
    "formatCellFormat",
    "parseCellFormat",
]
