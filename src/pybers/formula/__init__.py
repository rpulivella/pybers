#!/usr/bin/env python3
"""\
Formulas: the nodes a file stores, the text a person types, and both directions.

One feature, whole. `nodes` is what a cell holds, `functions` names the calls,
`syntax` holds the operator table both text directions share, `parse` turns text
into nodes and `render` turns nodes back into the text Numbers displays. `_read`
and `_write` are the archive halves and are private, so adding a formula capability
touches this directory and no other.

**A formula is a postfix node array, never text.** `TSCE.FormulaArchive` has one
content field and no string to put a formula in, so the text here is a constructor
on the way in and a rendering on the way out. Nothing in this package puts text in
a file.

**A reference is a signed offset from the cell holding it**, which is why every
conversion between nodes and text takes that cell, and why one stored archive
serves every cell a formula was dragged into.

UPDATES
2026-09-21  FormulaReferenceLoss re-exported, for PYB-17.
2026-09-08  Made a package of its own for #58, gathering the model, the text and
            both archive halves that were spread across three directories.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from pybers.formula.functions import (
    ArgumentCountError,
    FunctionAvailability,
    NumbersFunction,
    UnknownFunctionError,
    findFunction,
    findFunctionIndex,
    findFunctionName,
    findFunctionNamed,
)
from pybers.formula.nodes import (
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
    FormulaUnknownCall,
    FormulaVariable,
    NodeContent,
    Span,
)
from pybers.formula.parse import parseFormula
from pybers.formula.render import renderFormula
from pybers.formula.syntax import FormulaSyntaxError

__all__ = [
    "ArgumentCountError",
    "Coordinate",
    "Formula",
    "FormulaBinding",
    "FormulaError",
    "FormulaFunctionCall",
    "FormulaGroup",
    "FormulaLambda",
    "FormulaNode",
    "FormulaRange",
    "FormulaReference",
    "FormulaReferenceLoss",
    "FormulaSyntaxError",
    "FormulaUnknownCall",
    "FormulaVariable",
    "FunctionAvailability",
    "NodeContent",
    "NumbersFunction",
    "Span",
    "UnknownFunctionError",
    "findFunction",
    "findFunctionIndex",
    "findFunctionName",
    "findFunctionNamed",
    "parseFormula",
    "renderFormula",
]
