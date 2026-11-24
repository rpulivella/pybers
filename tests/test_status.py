#!/usr/bin/env python3
"""\
Status messages through `import pybers`: each step a long call reports, and each part
a call skipped.

UPDATES
2026-11-24  Written for PYB-319.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"

from pathlib import Path

import pytest
from fontbuilders import buildFont, saveFont

import pybers
from conftest import copyDocument
from pybers.status import composeProgressCount, composeProgressStep


def listMessages(heard: list[pybers.ProgressStep]) -> list[str]:
    """Return each message heard, once, in the order it was first heard."""
    return list(dict.fromkeys(step.message for step in heard))


def listCounts(heard: list[pybers.ProgressStep], message: str) -> list[int | None]:
    """Return each count a message reported, in order."""
    return [step.completed for step in heard if step.message == message]


def testAStepEndsInAnEllipsisAndHasNoTotal() -> None:
    step = composeProgressStep("reading the document")
    assert step == pybers.ProgressStep("reading the document…")
    assert str(step) == "reading the document…"


def testACountCarriesItsTotal() -> None:
    step = composeProgressCount("reading the tables", 2, 5)
    assert (step.message, step.completed, step.total) == ("reading the tables…", 2, 5)
    assert str(step) == "reading the tables… 2/5"


@pytest.mark.parametrize("phrase", [
    "Reading the document", "reading the document.", "reading the document…", "",
    " reading",
])
def testAMalformedPhraseIsRefused(phrase: str) -> None:
    with pytest.raises(ValueError, match="status phrase"):
        composeProgressStep(phrase)


@pytest.mark.parametrize(("completed", "total"), [(-1, 3), (4, 3)])
def testACountOutsideItsTotalIsRefused(completed: int, total: int) -> None:
    with pytest.raises(ValueError, match="out of its range"):
        composeProgressCount("reading the tables", completed, total)


@pytest.mark.parametrize("reason", ["Holds a formula", "holds a formula."])
def testASkippedPartsReasonIsAPhrase(reason: str) -> None:
    with pytest.raises(ValueError, match="status phrase"):
        pybers.PartSkip("Sheet 1::Table 1::A11", reason)


def testOpeningCountsEachMemberAndTableToItsTotal(tmp_path: Path) -> None:
    heard: list[pybers.ProgressStep] = []
    document = pybers.open(
        copyDocument("20-formula-shapes", tmp_path), onProgress=heard.append
    )
    assert listMessages(heard) == ["unpacking the document…", "reading the tables…"]
    tables = sum(len(sheet.tables) for sheet in document.sheets)
    assert listCounts(heard, "reading the tables…") == list(range(1, tables + 1))
    members = [step for step in heard if step.message == "unpacking the document…"]
    assert members[-1].completed == members[-1].total


def testSavingCountsEachTableAndMemberToItsTotal(tmp_path: Path) -> None:
    document = pybers.open(copyDocument("20-formula-shapes", tmp_path))
    heard: list[pybers.ProgressStep] = []
    document.save(tmp_path / "saved.numbers", onProgress=heard.append)
    assert listMessages(heard) == ["writing the tables…", "saving the document…"]
    for message in listMessages(heard):
        last = [step for step in heard if step.message == message][-1]
        assert last.completed == last.total


def testOpeningTypefacesCountsEveryMachineFontFile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = tuple(
        saveFont(buildFont("Brand Sans", name, f"BrandSans-{name}"),
                 tmp_path / f"{name}.ttf")
        for name in ("Regular", "Bold")
    )
    monkeypatch.setattr(
        "pybers.typeface.typefaces.findMachineFontFiles", lambda: files
    )
    heard: list[pybers.ProgressStep] = []
    pybers.openTypefaces(onProgress=heard.append)
    assert listMessages(heard) == [
        "reading the catalog…", "finding the fonts on this machine…",
        "reading the fonts on this machine…",
    ]
    assert listCounts(heard, "reading the fonts on this machine…") == [0, 1, 2]


def testOpeningAFontFileIsOneStep(tmp_path: Path) -> None:
    path = saveFont(buildFont("Brand Sans", "Regular", "BrandSans-Regular"),
                    tmp_path / "brand.ttf")
    heard: list[pybers.ProgressStep] = []
    pybers.openTypefaces(path, onProgress=heard.append)
    assert heard == [pybers.ProgressStep("reading the font file…")]
