#!/usr/bin/env python3
"""\
Every golden rebuilt from its builder and compared, archive by archive, with its file.

`--golden-write` writes each selected golden from its builder instead, the one way a
golden is made. Narrow it with `-k`.

UPDATES
2026-11-02  A golden starting from a fixture or measurement must state why, for PYB-261.
2026-10-23  Every label beneath a cell pybers changed is checked against the cell,
            for PYB-255.
2026-10-22  Written for PYB-255, replacing the comparison each golden's test held.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/22"

import dataclasses
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from golden.builders import (
    GoldenBuilder,
    buildGolden,
    findBuilder,
    findFirstTable,
    formatGoldenLabel,
    goldens,
    readMeasuredCells,
)
from test_writer import listArchiveDifferences

import pybers
from conftest import findDocumentPath
from pybers._persistence import readPackage
from tools.local.lib.golden_expected import buildExpectedValues

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"


def testEveryGoldenHasExactlyOneBuilder() -> None:
    names = [builder.name for builder in goldens]
    assert len(names) == len(set(names))
    assert sorted(names) == sorted(
        path.stem for path in goldenDirectory.glob("*.numbers")
    )


@pytest.mark.parametrize("builder", goldens, ids=lambda builder: builder.name)
def testEachGoldenIsWhatItsBuilderWrites(
    builder: GoldenBuilder, tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    built = buildGolden(builder, tmp_path)
    if request.config.getoption("--golden-write"):
        shutil.copyfile(built, goldenDirectory / f"{builder.name}.numbers")
        pytest.skip(f"wrote {builder.name}.numbers")
    golden = readPackage(goldenDirectory / f"{builder.name}.numbers")
    differences = listArchiveDifferences(golden, readPackage(built))
    assert not differences, "\n  ".join(differences)


def listUnexplainedGoldens(builders: tuple[GoldenBuilder, ...]) -> list[str]:
    """Return each golden whose start and stated reason disagree.

    One from a fixture or measurement names a ticket or a reason, and a created one
    names neither.
    """
    return [
        builder.name for builder in builders
        if (builder.source is None) == bool(builder.sourceReason)
    ]


def testEveryGoldenFromANumbersDocumentStatesWhy() -> None:
    assert listUnexplainedGoldens(goldens) == []


def testAGoldenFromAMeasurementNamingNoReasonIsCaught() -> None:
    unexplained = GoldenBuilder("99-unexplained", "00-baseline", lambda document: None)
    explained = dataclasses.replace(
        unexplained, name="99-explained", sourceReason="PYB-1"
    )

    assert listUnexplainedGoldens((unexplained, explained)) == ["99-unexplained"]


def testACreatedGoldenNamingAReasonIsCaught() -> None:
    created = GoldenBuilder(
        "99-created", None, lambda document: None, sourceReason="PYB-1"
    )

    assert listUnexplainedGoldens((created,)) == ["99-created"]


def listStaleLabels(builder: GoldenBuilder, golden: Path) -> list[str]:
    """Return each measured cell whose label no longer says what it holds."""
    assert builder.source is not None, f"{builder.name} is labeled but has no source"
    sourceTable = findFirstTable(pybers.open(findDocumentPath(builder.source)))
    source = readMeasuredCells(sourceTable)
    built = readMeasuredCells(findFirstTable(pybers.open(golden)))
    stale = []
    for address, (shown, label) in built.items():
        sourceShown, sourceLabel = source[address]
        wanted = (sourceLabel if shown == sourceShown
                  else formatGoldenLabel(shown, sourceLabel))
        if label != wanted:
            stale.append(str(address))
    return stale


@pytest.mark.parametrize(
    "builder", [builder for builder in goldens if builder.labeled],
    ids=lambda builder: builder.name,
)
def testEveryLabelDescribesItsCell(builder: GoldenBuilder) -> None:
    golden = goldenDirectory / f"{builder.name}.numbers"
    assert listStaleLabels(builder, golden) == []


def testALabelLeftBehindByAnEditIsCaught(tmp_path: Path) -> None:
    builder = findBuilder("12-currency-written-by-pybers")
    working = tmp_path / "stale.numbers"
    shutil.copyfile(goldenDirectory / f"{builder.name}.numbers", working)
    document = pybers.open(working)
    findFirstTable(document).cell("A1").value = Decimal(5)
    document.save()
    assert listStaleLabels(builder, working) == ["A1"]


def testTheExpectationsFindLabelsInExactlyTheLabeledGoldens() -> None:
    found = {
        builder.name for builder in goldens
        if any(cell.label for table in buildExpectedValues(
            goldenDirectory / f"{builder.name}.numbers").tables for cell in table.cells)
    }
    assert found == {builder.name for builder in goldens if builder.labeled}
