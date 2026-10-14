#!/usr/bin/env python3
"""\
The text the golden confirmation report shows, apart from the tool that drives Numbers.

Every function here returns a string and touches nothing else, so the report's text is
testable without Numbers, the helper or a logged-in Mac.

UPDATES
2026-10-13  Moved here from `scripts/golden_confirm_lib.py`, for PYB-204.
2026-10-13  Written for PYB-201.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/13"

import re

from pybers.formula.syntax import (
    FormulaSyntaxError,
    formulaMarker,
    percentSymbol,
    tokenize,
)


def formatCodeSpan(value: object) -> str:
    """Quote one reported value as a Markdown code span, fenced past its backticks."""
    if value is None:
        return "nothing"
    text = str(value).lower() if isinstance(value, bool) else str(value)
    if text == "":
        return "empty text"
    fence = "`" * (max((len(run) for run in re.findall("`+", text)), default=0) + 1)
    padding = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{padding}{text}{padding}{fence}"


def formatSpacedFormula(text: str) -> str:
    """Return a formula with one space each side of every binary operator, for reading.

    Only the report reads this; every check compares the exact text Numbers read.
    """
    body = text.removeprefix(formulaMarker)
    try:
        tokens = tokenize(body)
    except FormulaSyntaxError:
        return text
    pieces: list[str] = []
    expectsOperand = True
    for token in tokens[:-1]:
        piece = body[token.position:token.position + token.width]
        isOperator = token.kind == "operator" and token.text != percentSymbol
        pieces.append(f" {piece} " if isOperator and not expectsOperand else piece)
        expectsOperand = token.kind in ("open", "comma") or isOperator
    return text[:len(text) - len(body)] + "".join(pieces)
