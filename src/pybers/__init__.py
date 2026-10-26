#!/usr/bin/env python3
"""pybers, a clean, round-trip-tested library for reading and writing Apple Numbers
documents.

Built in deep respect for Apple Numbers itself, and standing on the shoulders of
numbers-parser (https://github.com/masaccio/numbers-parser), whose reverse-engineering
of Apple's undocumented .numbers archive format is the foundation this project depends
on. The goal here is for editing a .numbers file programmatically to be as reliable as
using Numbers by hand, built as a clean, dataclass-based design with a
library-and-CLI/TUI split and first-class named styles from the start. See CLAUDE.md for
the full origin story and design contract.

UPDATES
2026-10-24  The unread style, rich text and drawable scaffold and `Size` removed,
            for PYB-259.
2026-10-24  `CellControlType` re-exported, for PYB-259.
2026-10-22  The cell controls and CellPresentation re-exported, replacing
            CellDescription, for PYB-255.
2026-10-22  The currency names re-exported, for PYB-220.
2026-10-20  MachineTimeZone, TimeZoneError, TimeZoneLike and formatCellValue
            re-exported, for PYB-144.
2026-10-20  `parseCellValue` re-exported, for PYB-217.
2026-10-20  `CellChange` re-exported, for PYB-217.
2026-10-12  NOT_REQUESTED, UNDETERMINED and WITHHELD re-exported, for PYB-190.
2026-10-09  Re-exports made lazy, so the command line skips protobuf, for PYB-181.
2026-10-07  checkDocument and what it reports re-exported, for PYB-169.
2026-10-01  CellKind, CellFormat and CellDescription re-exported, for PYB-141.
2026-09-29  CellValueFill re-exported, for PYB-118.
2026-09-23  FormulaReferenceRelocation re-exported, for PYB-18.
2026-09-21  FormulaReferenceLoss re-exported, for PYB-17.
2026-09-14  TableRow and TableRows re-exported (PYB-62).
2026-09-08  ReferenceLocation re-exported (#13).
2026-09-02  SelectionError re-exported (#14).
2026-08-12  Initial scaffold.
"""

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/12"

lazy from pybers.absence import NOT_REQUESTED, UNDETERMINED, WITHHELD
lazy from pybers.addressing import (
    CellAddress,
    CellOffset,
    CellRange,
    CellRangeLike,
    CellRangeList,
    CellReference,
    CellReferenceLike,
    ReferenceError,
    SheetReference,
    TableReference,
    toCellRanges,
    toCellReference,
    toColumnLetter,
    toColumnNumber,
)
lazy from pybers.check import (
    Check,
    CheckCell,
    CheckEnvironment,
    CheckFailure,
    CheckNames,
    CheckSheet,
    CheckTable,
    NumbersVersion,
    checkDocument,
)
lazy from pybers.currency import (
    Currency,
    CurrencyAmount,
    CurrencyError,
    currencies,
    findCurrency,
)
lazy from pybers.document import (
    Document,
    ReferenceLocation,
    SelectionError,
    Sheet,
    open,
)
lazy from pybers.errors import PybersError, ReadError, WriteError
lazy from pybers.formula import (
    ArgumentCountError,
    Coordinate,
    Formula,
    FormulaBinding,
    FormulaError,
    FormulaFunctionCall,
    FormulaGroup,
    FormulaLambda,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FormulaReferenceLoss,
    FormulaReferenceRelocation,
    FormulaSyntaxError,
    FormulaUnknownCall,
    FormulaVariable,
    NumbersFunction,
    Span,
    UnknownFunctionError,
    findFunction,
    findFunctionIndex,
    findFunctionName,
    findFunctionNamed,
    parseFormula,
    renderFormula,
)
lazy from pybers.geometry import Position
lazy from pybers.table import (
    Cell,
    CellChange,
    CellControl,
    CellControlBase,
    CellControlCheckbox,
    CellControlPopUpMenu,
    CellControlSlider,
    CellControlStarRating,
    CellControlStepper,
    CellControlType,
    CellControlUnknown,
    CellFormat,
    CellKind,
    CellPresentation,
    CellValue,
    CellValueFill,
    MergeRange,
    Table,
    TableRow,
    TableRows,
    formatCellValue,
    parseCellValue,
)
lazy from pybers.timezone import MachineTimeZone, TimeZoneError, TimeZoneLike

__all__ = [
    "NOT_REQUESTED",
    "UNDETERMINED",
    "WITHHELD",
    "ArgumentCountError",
    "NumbersFunction",
    "UnknownFunctionError",
    "findFunction",
    "findFunctionIndex",
    "findFunctionNamed",
    "findFunctionName",
    "FormulaUnknownCall",
    "Span",
    "FormulaFunctionCall",
    "FormulaGroup",
    "FormulaReference",
    "FormulaReferenceLoss",
    "FormulaReferenceRelocation",
    "FormulaRange",
    "PybersError",
    "ReadError",
    "WriteError",
    "FormulaNode",
    "FormulaError",
    "FormulaSyntaxError",
    "FormulaBinding",
    "FormulaVariable",
    "FormulaLambda",
    "Formula",
    "formatCellValue",
    "parseCellValue",
    "Currency",
    "CurrencyAmount",
    "CurrencyError",
    "currencies",
    "findCurrency",
    "parseFormula",
    "renderFormula",
    "Coordinate",
    "Check",
    "CheckCell",
    "CheckEnvironment",
    "CheckFailure",
    "CheckNames",
    "CheckSheet",
    "CheckTable",
    "NumbersVersion",
    "checkDocument",
    "Cell",
    "CellChange",
    "CellControl",
    "CellControlBase",
    "CellControlCheckbox",
    "CellControlPopUpMenu",
    "CellControlSlider",
    "CellControlStarRating",
    "CellControlStepper",
    "CellControlType",
    "CellControlUnknown",
    "CellReferenceLike",
    "CellPresentation",
    "CellFormat",
    "CellKind",
    "CellRange",
    "CellRangeList",
    "CellAddress",
    "CellOffset",
    "CellReference",
    "CellValue",
    "CellValueFill",
    "CellRangeLike",
    "ReferenceError",
    "SheetReference",
    "TableReference",
    "toColumnLetter",
    "toColumnNumber",
    "open",
    "toCellRanges",
    "toCellReference",
    "MergeRange",
    "Position",
    "SelectionError",
    "Sheet",
    "Table",
    "TableRow",
    "TableRows",
    "Document",
    "ReferenceLocation",
    "MachineTimeZone",
    "TimeZoneError",
    "TimeZoneLike",
]
