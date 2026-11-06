#!/usr/bin/env python3
"""\
The published coverage files, and the worker count that measures them.

UPDATES
2026-11-05  Written for PYB-277.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/05"

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import pytest_xdist_auto_num_workers
from tools.local.coverage_report import (
    chooseBadgeColor,
    renderBadge,
    renderReport,
)
from tools.local.coverage_report import main as coverageReportMain
from tools.local.lib.readiness import coverageNoticeTitle


@pytest.mark.parametrize(
    ("cores", "workers"),
    [(10, 9), (4, 3), (3, 2), (2, 2), (1, 2), (None, 2)],
)
def testWorkersLeaveOneCoreFreeAndNeverFallBelowTwo(
    monkeypatch: pytest.MonkeyPatch, cores: int | None, workers: int,
) -> None:
    monkeypatch.setattr("os.process_cpu_count", lambda: cores)
    assert pytest_xdist_auto_num_workers(SimpleNamespace()) == workers  # type: ignore[arg-type]


def testTheBadgeIsWhatAShieldsEndpointReads() -> None:
    assert json.loads(renderBadge(95.04)) == {
        "schemaVersion": 1,
        "label": "coverage",
        "message": "95.0%",
        "color": "brightgreen",
    }


@pytest.mark.parametrize(
    ("percent", "color"),
    [(100.0, "brightgreen"), (90.0, "brightgreen"), (89.9, "yellow"), (75.0, "yellow"),
     (74.9, "red"), (0.0, "red")],
)
def testTheBadgeColorChangesAtEachBoundary(percent: float, color: str) -> None:
    assert chooseBadgeColor(percent) == color


def testTheReportNamesTheCommitAndCarriesTheTable() -> None:
    report = renderReport("| Name | Cover |\n", "abc1234")
    assert "`develop` at abc1234" in report
    assert report.endswith("| Name | Cover |\n")


def testMainWritesBothFilesAndAnnotatesTheRun(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    class MeasuredStandIn:
        def load(self) -> None:
            pass

        def report(self, file: io.StringIO, output_format: str) -> float:
            assert output_format == "markdown"
            file.write("| Name | Cover |\n")
            return 95.54

    monkeypatch.setattr("coverage.Coverage", MeasuredStandIn)
    output = tmp_path / "published"
    arguments = ["coverage_report", "--output", str(output), "--commit", "abc1234"]
    monkeypatch.setattr("sys.argv", arguments)
    assert coverageReportMain() == 0
    assert json.loads((output / "badge.json").read_text())["message"] == "95.5%"
    assert (output / "README.md").read_text().endswith("| Name | Cover |\n")
    assert f"::notice title={coverageNoticeTitle}::95.5" in capsys.readouterr().out
