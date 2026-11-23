#!/usr/bin/env python3
"""\
Each composer builds its shape of message in the order `docs/message-design.md` sets.

UPDATES
2026-11-23  Written for PYB-307.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/23"

from pathlib import Path

import pytest

import pybers
from pybers import errors


def testARefusalReadsPlaceCauseFixThenWhatWasNotDone() -> None:
    message = pybers.composeRefusal(
        "Sheet 1::Table 1::B4",
        "holds a formula, so a value written there would discard it",
        "Clear the formula first",
        errors.nothingWritten,
    )
    assert message == (
        "Sheet 1::Table 1::B4 holds a formula, so a value written there would discard "
        "it. Clear the formula first. Nothing was written."
    )


def testARefusalWithNoFixAndNothingWithheldEndsAtItsCause() -> None:
    assert pybers.composeRefusal("'x'", "is not a color") == "'x' is not a color."


def testARefusalLeavesOutAMissingFixAndKeepsWhatWasNotDone() -> None:
    message = pybers.composeRefusal(
        "B4", "is outside Table 1", None, errors.nothingWritten
    )
    assert message == "B4 is outside Table 1. Nothing was written."


@pytest.mark.parametrize("part", ["cause", "fix", "notDone"])
def testAPartArrivingWithItsOwnPeriodIsRefused(part: str) -> None:
    parts = {"cause": "is wrong", "fix": "Fix it", "notDone": errors.nothingWritten}
    parts[part] += "."
    with pytest.raises(ValueError, match="takes no period"):
        pybers.composeRefusal("B4", parts["cause"], parts["fix"], parts["notDone"])


def testMalformedTextNamesItsColumnCountedFromOne() -> None:
    message = errors.composeTextRefusal(
        "Budget::Q3::B0", 12, "is not an address, since rows count from one",
        "Write it as `B1`",
    )
    assert message == (
        "`Budget::Q3::B0`, column 13, is not an address, since rows count from one. "
        "Write it as `B1`."
    )


def testAnUnreadableDocumentNamesItsFileAndThatNothingWasRead() -> None:
    message = errors.composeReadRefusal(
        Path("/tmp/budget.numbers"), "is not a zip archive",
    )
    assert message == "/tmp/budget.numbers is not a zip archive. Nothing was read."


def testAFaultAsksForAReportAtTheIssuesAddress() -> None:
    message = errors.composeFault(
        "Sheet 1::Table 1", "holds a formula key past the end of its cell record",
        errors.nothingWritten,
    )
    assert message == (
        "Sheet 1::Table 1 holds a formula key past the end of its cell record. Report "
        f"this at {errors.issuesAddress}. Nothing was written."
    )


def testARefusedChoiceNamesTheClosestChoice() -> None:
    error = pybers.composeChoiceRefusal(
        pybers.PybersError, "outr", "a border position", ["outer", "between", "all"],
        errors.nothingWritten,
    )
    assert str(error) == (
        "'outr' is not a border position. The closest is outer. Nothing was written."
    )
    assert error.choices == ()


def testARefusedChoiceListsFiveChoicesOrFewerWhenNoneIsClose() -> None:
    error = pybers.composeChoiceRefusal(
        pybers.PybersError, "zzz", "a border style", ["solid", "dashed", "dotted"],
    )
    assert str(error) == (
        "'zzz' is not a border style. The choices are solid, dashed and dotted."
    )


def testARefusedChoiceCarriesMoreThanFiveChoicesItCannotName() -> None:
    choices = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]
    error = pybers.composeChoiceRefusal(pybers.PybersError, "zzz", "a letter", choices)
    assert str(error) == "'zzz' is not a letter."
    assert error.choices == tuple(choices)


def testARefusedChoiceIsTheErrorTypeAsked() -> None:
    error = pybers.composeChoiceRefusal(pybers.WriteError, "zzz", "a letter", ["a"])
    assert isinstance(error, pybers.WriteError)
