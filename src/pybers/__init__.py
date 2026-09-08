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

from pybers.model import (
    ArgumentCountError,
    Cell,
    CellAddress,
    CellRange,
    CellRangeList,
    CellReference,
    CellValue,
    Coordinate,
    Document,
    Formula,
    FormulaBinding,
    FormulaError,
    FormulaFunctionCall,
    FormulaLambda,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FormulaSyntaxError,
    FormulaUnknownCall,
    FormulaVariable,
    GraphicalObject,
    Image,
    MergeRange,
    NumbersFunction,
    Paragraph,
    Position,
    RangeAddress,
    ReferenceError,
    RichText,
    SelectionError,
    Shape,
    Sheet,
    Size,
    Span,
    Style,
    Table,
    TextBox,
    TextRun,
    UnknownFunctionError,
    columnLetter,
    columnNumber,
    functionFor,
    functionIndexFor,
    functionNamed,
    functionNameFor,
    parseFormula,
    renderFormula,
    toCellRanges,
    toCellReference,
)
from pybers.reader import open

__all__ = [
    "ArgumentCountError",
    "NumbersFunction",
    "UnknownFunctionError",
    "functionFor",
    "functionIndexFor",
    "functionNamed",
    "functionNameFor",
    "FormulaUnknownCall",
    "Span",
    "FormulaFunctionCall",
    "FormulaReference",
    "FormulaRange",
    "FormulaNode",
    "FormulaError",
    "FormulaSyntaxError",
    "FormulaBinding",
    "FormulaVariable",
    "FormulaLambda",
    "Formula",
    "parseFormula",
    "renderFormula",
    "Coordinate",
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
    "SelectionError",
    "Shape",
    "Sheet",
    "Size",
    "Style",
    "Table",
    "TextBox",
    "TextRun",
    "Document",
]
