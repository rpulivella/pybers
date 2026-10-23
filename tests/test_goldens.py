#!/usr/bin/env python3
"""\
Every golden rebuilt from its builder and compared, archive by archive, with its file.

`--golden-write` writes each selected golden from its builder instead, the one way a
golden is made. Narrow it with `-k`.

UPDATES
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


def listStaleLabels(builder: GoldenBuilder, golden: Path) -> list[str]:
    """Return each measured cell whose label no longer says what it holds."""
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
