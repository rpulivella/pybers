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

import base64
import json
from types import SimpleNamespace

import pytest

from conftest import pytest_xdist_auto_num_workers
from tools.local.coverage_report import chooseBadgeColor, renderBadge, renderReport
from tools.local.lib import readiness as checks
from tools.workflow import preflight


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


@pytest.mark.parametrize(
    ("percent", "published", "status", "detail"),
    [
        ("95.6", "95.5", checks.passed, "95.6%, increased from 95.5% on develop"),
        ("95.5", "95.5", checks.passed, "95.5%"),
        ("95.5", "95.50", checks.passed, "95.5%"),
        ("94.6", "95.5", checks.passed, "94.6%, down from 95.5% on develop"),
        ("94.5", "95.5", checks.attention, "94.5%, down from 95.5% on develop"),
        ("90.0", "95.5", checks.attention, "90.0%, down from 95.5% on develop"),
        ("95.5", "", checks.passed, "95.5%, with no develop figure to compare"),
        ("", "95.5", checks.skipped, "Coverage was not measured"),
        ("", "", checks.skipped, "Coverage was not measured"),
    ],
)
def testCoverageReadsAgainstDevelopAndOnlyALargeDropAsksADecision(
    percent: str, published: str, status: str, detail: str,
) -> None:
    result = checks.checkCoverage(percent, published)
    assert (result.status, result.detail) == (status, detail)


def testThePublishedFigureIsReadFromTheBadge(monkeypatch: pytest.MonkeyPatch) -> None:
    content = base64.b64encode(renderBadge(95.5).encode()).decode()
    monkeypatch.setattr(
        checks.github, "requestJson", lambda *args, **kwargs: {"content": content},
    )
    assert checks.readPublishedCoverage("token") == "95.5"


def testNoCoverageBranchYetReadsAsNothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise checks.github.GitHubHttpError(404, "Not Found")

    monkeypatch.setattr(checks.github, "requestJson", refuse)
    assert checks.readPublishedCoverage("token") == ""


def testAnyOtherFailureReadingTheFigureIsRaised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise checks.github.GitHubHttpError(500, "Server Error")

    monkeypatch.setattr(checks.github, "requestJson", refuse)
    with pytest.raises(checks.github.GitHubHttpError):
        checks.readPublishedCoverage("token")


def testTheNoticeIsReadFromAmongAnnotations(monkeypatch: pytest.MonkeyPatch) -> None:
    annotations = [
        {"title": "", "message": "Node.js 20 is deprecated."},
        {"title": checks.coverageNoticeTitle, "message": "95.0"},
    ]
    monkeypatch.setattr(
        checks.github, "requestJson", lambda *args, **kwargs: annotations,
    )
    assert checks.readCoverageNotice("token", 1) == "95.0"


def testARunWithNoNoticeReadsAsNothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checks.github, "requestJson", lambda *args, **kwargs: [])
    assert checks.readCoverageNotice("token", 1) == ""


def testEveryGateIsTimedEvenWhenItCannotRun(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse() -> preflight.GateResult:
        raise preflight.PreflightError("no binary")

    monkeypatch.setitem(preflight.gates, "ruff", refuse)
    result = preflight.runGates(["ruff"])[0]
    assert not result.passed
    assert result.seconds >= 0
