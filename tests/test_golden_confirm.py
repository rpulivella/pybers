#!/usr/bin/env python3
"""\
The golden confirmation report's text, as the report shows it.

Only `lib/golden_confirm.py` is imported, so nothing here drives Numbers.

UPDATES
2026-10-21  The Data Format settings the helper names, and a recipe's setting key,
            for PYB-219.
2026-10-13  The late-import check moved to `test_tooling_layout.py`, which covers
            every script, for PYB-204.
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



import pytest

from tools.local.lib import golden_confirm as report  # noqa: E402


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


def testDataFormatSettingsAreKeyedByTheNameTheHelperGave() -> None:
    elements = [
        {"role": "AXStaticText", "value": "Decimals:", "setting": ""},
        {"role": "AXTextField", "value": "2", "setting": "Decimals"},
        {"role": "AXPopUpButton", "value": "(100)",
         "setting": "Unlabeled PopUpButton 1"},
    ]
    assert report.readDataFormatSettings(elements) == {
        "Decimals": "2", "Unlabeled PopUpButton 1": "(100)",
    }


def testPopUpMenuItemsJoinUnderOneSetting() -> None:
    elements = [
        {"role": "AXTextField", "value": "Item 1", "setting": "Items"},
        {"role": "AXTextField", "value": "Item 2", "setting": "Items"},
    ]
    assert report.readDataFormatSettings(elements) == {"Items": "Item 1, Item 2"}


def testEveryCommittedRecipeHoldsOnlyKeysTheHelperTakes() -> None:
    recipePaths = report.measurementDirectory.glob(f"*{report.recipeSuffix}")
    names = sorted(path.name.removesuffix(report.recipeSuffix) for path in recipePaths)
    recipes = [report.readMeasurementRecipe(name) for name in names]
    steps = [step for recipe in recipes for step in recipe.steps]
    assert any(step.get("setting") == "Rule" for step in steps)
