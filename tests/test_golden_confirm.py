#!/usr/bin/env python3
"""\
The golden confirmation tool's report text, and the interpreter it refuses.

Only `golden_confirm_lib` is imported, and the tool itself is read as source, so
nothing here drives Numbers.

UPDATES
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

import ast
import sys
from pathlib import Path

import pytest

scriptDirectory: Path = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scriptDirectory))

import golden_confirm_lib as report  # noqa: E402

scriptPath: Path = scriptDirectory / "golden-confirm.py"


def testNoFunctionImportsPybersLate() -> None:
    late = [
        node.lineno
        for function in ast.walk(ast.parse(scriptPath.read_text()))
        if isinstance(function, ast.FunctionDef)
        for node in ast.walk(function)
        if isinstance(node, ast.ImportFrom | ast.Import)
        and any(
            name.split(".")[0] == "pybers"
            for name in (
                [node.module or ""] if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
            )
        )
    ]
    assert late == []


@pytest.mark.parametrize(("value", "span"), [
    ("big", "`big`"),
    (111.0, "`111.0`"),
    (True, "`true`"),
    ("a`b", "``a`b``"),
    ("`x", "`` `x ``"),
    (None, "nothing"),
    ("", "empty text"),
])
def testAValueIsQuotedAsACodeSpan(value: object, span: str) -> None:
    assert report.formatCodeSpan(value) == span


@pytest.mark.parametrize(("formula", "spaced"), [
    ('=$A$1&" units"', '=$A$1 & " units"'),
    ("=Table 1::A11*2+1", "=Table 1::A11 * 2 + 1"),
    ('=IF(SUM(A1:A10)>10,"a&b","c")', '=IF(SUM(A1:A10) > 10,"a&b","c")'),
    ("=SUM(Sheet 1::Table 1::$B:$C)", "=SUM(Sheet 1::Table 1::$B:$C)"),
    ("=-A1^-2", "=-A1 ^ -2"),
    ("=(1+2)*-3", "=(1 + 2) * -3"),
    ("=50%*2", "=50% * 2"),
    ("=A1<>B1", "=A1 <> B1"),
])
def testAFormulaIsSpacedAroundEachOperator(formula: str, spaced: str) -> None:
    assert report.formatSpacedFormula(formula) == spaced


def testUnreadableFormulaTextIsShownAsWritten() -> None:
    assert report.formatSpacedFormula('="open') == '="open'
