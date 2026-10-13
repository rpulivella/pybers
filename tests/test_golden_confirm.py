#!/usr/bin/env python3
"""\
The golden confirmation tool's report text, and the interpreter it refuses.

Only pure functions are exercised; nothing here drives Numbers.

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
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

scriptPath: Path = (
    Path(__file__).resolve().parent.parent / "scripts" / "golden-confirm.py"
)


def loadGoldenConfirm() -> ModuleType:
    """Return the tool, loaded by path since its file name holds a hyphen."""
    spec = importlib.util.spec_from_file_location("golden_confirm", scriptPath)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered first, because its dataclasses resolve their own module by name.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    assert loadGoldenConfirm().formatCodeSpan(value) == span


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
    assert loadGoldenConfirm().formatSpacedFormula(formula) == spaced


def testUnreadableFormulaTextIsShownAsWritten() -> None:
    assert loadGoldenConfirm().formatSpacedFormula('="open') == '="open'
