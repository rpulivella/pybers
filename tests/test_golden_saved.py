#!/usr/bin/env python3
"""\
Each cell Numbers changed when it saved a golden, named by what it changed.

A copy edited by pybers stands in for the copy Numbers saves, since what the check
compares is two files, whoever wrote the second.

UPDATES
2026-11-10  Written for PYB-145.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/10"

import datetime
import shutil
from decimal import Decimal
from pathlib import Path

import pybers
from tools.local.lib import golden_confirm as report
from tools.local.lib.golden_saved import (
    SavedCell,
    listCellChanges,
    readSavedCellChanges,
)

goldenDirectory: Path = report.goldenDirectory


def copyGolden(name: str, into: Path, edit: str | None = None) -> Path:
    """Return a copy of a golden, named for the edit a test makes to it."""
    copy = into / f"{name}-{edit or 'unchanged'}.numbers"
    shutil.copyfile(goldenDirectory / f"{name}.numbers", copy)
    return copy


def readDuration(entry: dict[str, str]) -> SavedCell:
    """Return a duration cell holding one format entry, to compare against another."""
    return SavedCell(
        "1h 30m", "duration", "none", "duration", "none", frozendict(entry)
    )


def testAGoldenSavedUnchangedHasNoChangedCell(tmp_path: Path) -> None:
    golden = goldenDirectory / "00-created-formats-chosen-by-pybers.numbers"
    copy = copyGolden("00-created-formats-chosen-by-pybers", tmp_path)
    assert readSavedCellChanges(golden, copy) == {}


def testACellWhoseValueChangedIsNamedWithBothValues(tmp_path: Path) -> None:
    golden = goldenDirectory / "00-created-formats-chosen-by-pybers.numbers"
    copy = copyGolden("00-created-formats-chosen-by-pybers", tmp_path, "edited")
    document = pybers.open(copy)
    document.cellSet("::Formats::B4", datetime.timedelta(minutes=95))
    document.save()
    assert readSavedCellChanges(golden, copy) == {
        ("Sheet 1", "Formats", "B4"): [
            "value '1h 30m' became '1h 35m'",
        ],
    }


def testAFormatEntryNamesOnlyTheFieldsThatChanged() -> None:
    before = readDuration({"format_type": "268", "duration_unit_largest": "8"})
    after = readDuration({"format_type": "268", "duration_unit_largest": "4"})
    assert listCellChanges(before, after) == [
        "format entry duration_unit_largest 8 became 4",
    ]


def testAFormulaResultNumbersRecalculatedIsNotAChange() -> None:
    before = SavedCell("none", "error", "=A1", "none", "none", frozendict())
    after = SavedCell("5", "number", "=A1", "number (automatic)", "none",
                      frozendict({"format_type": "256"}))
    assert listCellChanges(before, after) == []


def testASavedCopyNumbersLeftAloneIsOnePassedCheck(tmp_path: Path) -> None:
    golden = goldenDirectory / "13-formats-made-automatic-by-pybers.numbers"
    copy = copyGolden("13-formats-made-automatic-by-pybers", tmp_path)
    checks = report.checkSavedCells(golden, copy)
    assert [check.status for check in checks] == ["passed"]


def testEachChangedCellIsAFailedCheckNamingIt(tmp_path: Path) -> None:
    golden = goldenDirectory / "13-formats-made-automatic-by-pybers.numbers"
    copy = copyGolden("13-formats-made-automatic-by-pybers", tmp_path, "edited")
    document = pybers.open(copy)
    document.cellSet("::Table 1::B1", Decimal("0.5"))
    document.save()
    (check,) = report.checkSavedCells(golden, copy)
    assert (check.status, check.subject) == ("failed", "Sheet 1 / Table 1 / B1")
    assert check.detail == "Numbers changed it on saving: value '0.25' became '0.5'"


def testAFormatPybersChoseForAFormulaMustSurvive() -> None:
    before = SavedCell("none", "error", "=B1/10", "number", "none",
                       frozendict({"format_type": "256"}))
    after = SavedCell("0.5", "number", "=B1/10", "number (automatic)", "none",
                      frozendict({"format_type": "256"}))
    assert listCellChanges(before, after) == [
        "format 'number' became 'number (automatic)'",
    ]
