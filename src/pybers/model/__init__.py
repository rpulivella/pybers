#!/usr/bin/env python3
"""The pybers object model, typed dataclasses standing in for a .numbers document's real
structure, split by feature area rather than by class: style, geometry, rich text,
floating shapes, table/cell, sheet/document.

Nothing here knows how to read or write the underlying file format; that lives in
pybers._persistence. Keeping the model isolated from the stored format is
deliberate: it is what makes the round-trip contract testable (build a model, write it,
read it back, assert equality) without needing a real .numbers file for every test.

UPDATES
2026-09-04  Function names for formula call indices (#44).
2026-09-02  The document cell iteration (#14).
2026-09-02  Sheet and table selection (#14).
2026-09-01  Addressing added as its own feature area (#9): reference, ranges.
2026-08-12  Initial scaffold: style, geometry, text, shapes, table, sheet.
"""

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/12"

from pybers.model.formula import (
    Coordinate,
    Formula,
    FormulaBinding,
    FormulaError,
    FormulaFunctionCall,
    FormulaLambda,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FormulaUnknownCall,
    FormulaVariable,
    Span,
)
from pybers.model.formulaparse import parseFormula
from pybers.model.formularender import renderFormula
from pybers.model.formulasyntax import FormulaSyntaxError
from pybers.model.functions import (
    ArgumentCountError,
    NumbersFunction,
    UnknownFunctionError,
    functionFor,
    functionIndexFor,
    functionNamed,
    functionNameFor,
)
from pybers.model.geometry import Position, Size
from pybers.model.ranges import CellRange, CellRangeList, RangeAddress, toCellRanges
from pybers.model.reference import (
    CellAddress,
    CellReference,
    ReferenceError,
    columnLetter,
    columnNumber,
    toCellReference,
)
from pybers.model.shapes import GraphicalObject, Image, Shape, TextBox
from pybers.model.sheet import Document, SelectionError, Sheet
from pybers.model.style import Style
from pybers.model.table import Cell, CellValue, MergeRange, Table
from pybers.model.text import Paragraph, RichText, TextRun

# Re-exported explicitly, which a type checker requires of a package that hands on
# names it did not define. The leaf modules carry no `__all__` of their own: a name
# defined in the module it lives in is already public there, and a second list
# repeating it is one more thing to forget.
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
    "GraphicalObject",
    "Image",
    "MergeRange",
    "RangeAddress",
    "ReferenceError",
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
    "columnLetter",
    "columnNumber",
    "toCellRanges",
    "toCellReference",
]
