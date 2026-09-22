#!/usr/bin/env python3
"""\
Conditional highlighting rewritten through a structural edit, as Numbers rewrites it.

Ten edits across `57-conditions-*` and `59-conditions-relative-*`, each rule
compared by content and each cell by the rule it names.

UPDATES
2026-09-21  Split out of `test_structure` for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/21"

from collections.abc import Callable
from pathlib import Path

import pytest
from structurefacts import (
    readConditionalRules,
)

import pybers
from conftest import findDocumentPath

conditionalMeasurements: dict[
    str, tuple[str, str, Callable[[pybers.Table], object]]
] = {
    "57-conditions-row-inserted": (
        "57-structure-refusals-base", "Conditions", lambda table: table.rowAdd(3)
    ),
    "57-conditions-row-deleted": (
        "57-structure-refusals-base", "Conditions", lambda table: table.rowRemove(3)
    ),
    "57-conditions-column-inserted": (
        "57-structure-refusals-base", "Conditions", lambda table: table.columnAdd(2)
    ),
    "57-conditions-column-deleted": (
        "57-structure-refusals-base", "Conditions",
        lambda table: table.columnRemove(3),
    ),
    "59-conditions-relative-row-inserted": (
        "59-conditions-relative-base", "Relative", lambda table: table.rowAdd(3)
    ),
    "59-conditions-relative-row-deleted": (
        "59-conditions-relative-base", "Relative", lambda table: table.rowRemove(3)
    ),
    "59-conditions-relative-column-inserted": (
        "59-conditions-relative-base", "Relative", lambda table: table.columnAdd(2)
    ),
    "59-conditions-relative-column-b-deleted": (
        "59-conditions-relative-base", "Relative",
        lambda table: table.columnRemove(2),
    ),
    "59-conditions-relative-column-a-deleted": (
        "59-conditions-relative-base", "Relative",
        lambda table: table.columnRemove(1),
    ),
    "59-conditions-relative-column-c-deleted": (
        "59-conditions-relative-base", "Relative",
        lambda table: table.columnRemove(3),
    ),
}


@pytest.mark.parametrize("name", sorted(conditionalMeasurements))
def testConditionalHighlightingIsRewrittenAsNumbersRewritesIt(
    name: str, tmp_path: Path
) -> None:
    """A moved rule is renewed, a broken one copied per cell, an added line inherits."""
    source, tableName, edit = conditionalMeasurements[name]
    document = pybers.open(findDocumentPath(source))
    edit(document.sheet(1).table(tableName))
    target = tmp_path / f"{name}.numbers"
    document.save(target)
    assert readConditionalRules(target, tableName) == readConditionalRules(
        findDocumentPath(name), tableName
    )
