#!/usr/bin/env python3
"""\
Printing what the failed jobs on a pull request logged, and nothing else.

GitHub is stood in for at the API boundary.

UPDATES
2026-10-13  Pull request summaries and check runs are dataclasses, for PYB-204.
2026-10-09  Written for PYB-181, after both checks on PR #191 failed with no comment.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/09"

import importlib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tools.workflow.lib import pull_request as pullRequest

repositoryRoot: Path = Path(__file__).resolve().parent.parent
setupLog: str = (
    "2026-10-09T18:00:01.0000000Z Extracted >=3.15 from pyproject.toml\n"
    "2026-10-09T18:00:02.0000000Z ##[error]The version '>=3.15.0' was not found.\n"
    "2026-10-09T18:00:03.0000000Z Post job cleanup.\n"
)


def loadPrScript() -> ModuleType:
    """Return the pull request tool, imported the way its own tests import it."""
    return importlib.import_module("tools.workflow.pr")


def buildApiStandIn(
    runs: list[dict[str, Any]], jobs: list[dict[str, Any]]
) -> Callable[..., dict[str, Any]]:
    """Return a stand-in for the API that knows one commit's runs and their jobs."""

    def requestStandIn(url: str, token: str, **options: Any) -> dict[str, Any]:
        return {"jobs": jobs} if "/jobs" in url else {"workflow_runs": runs}

    return requestStandIn


def runLogsOf(
    monkeypatch: pytest.MonkeyPatch,
    runs: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
) -> tuple[int, list[int]]:
    """Print a pull request's failed job logs with GitHub stood in for."""
    pr = loadPrScript()
    fetched: list[int] = []

    def readLogStandIn(token: str, jobId: int) -> str:
        fetched.append(jobId)
        return setupLog

    monkeypatch.setattr(pr.github, "resolveToken", lambda: "token")
    monkeypatch.setattr(
        pr, "readPullRequest",
        lambda token, number: pullRequest.PullRequestSummary(
            number=191, title="", url="", state="open", isDraft=False, head="",
            headRepository="", headSha="a" * 40, base="develop", nodeId="",
        ),
    )
    monkeypatch.setattr(pr.github, "requestJson", buildApiStandIn(runs, jobs))
    monkeypatch.setattr(pullRequest, "readJobLog", readLogStandIn)
    arguments = pr.buildParser().parse_args(["logs", "191"])
    return pr.runLogs(arguments), fetched


def readOutput(capsys: pytest.CaptureFixture[str]) -> str:
    """Return what the tool printed, with rich's line wrapping undone."""
    return " ".join(capsys.readouterr().out.split())


def buildJob(jobId: int, conclusion: str, failedStep: str) -> dict[str, Any]:
    """Return a job as GitHub's API describes one, with one step of each outcome."""
    return {
        "id": jobId,
        "name": "readiness",
        "conclusion": conclusion,
        "steps": [
            {"name": "Checkout", "conclusion": "success"},
            {"name": failedStep, "conclusion": conclusion},
        ],
    }


def testFailedJobPrintsItsFailedStepAndError(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runs = [{"id": 7, "name": "readiness", "conclusion": "failure",
             "created_at": "2026-10-09T18:00:00Z"}]
    code, fetched = runLogsOf(
        monkeypatch, runs, [buildJob(70, "failure", "Run actions/setup-python@v6")]
    )
    output = readOutput(capsys)

    assert (code, fetched) == (0, [70])
    assert "failed steps: Run actions/setup-python@v6" in output
    assert "##[error]The version '>=3.15.0' was not found." in output
    assert "Checkout" not in output
    assert "Post job cleanup." not in output


def testPassingRunsFetchNoLogAndReportNothingFailed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runs = [{"id": 7, "name": "readiness", "conclusion": "success",
             "created_at": "2026-10-09T18:00:00Z"}]
    code, fetched = runLogsOf(monkeypatch, runs, [])

    assert (code, fetched) == (1, [])
    assert "No failed job" in readOutput(capsys)


def testErrorExcerptsMergeWhenTheirContextOverlaps() -> None:
    pr = loadPrScript()
    lines = [
        "a", "b", "##[error]one", "c", "##[error]two", "d", "e", "f", "##[error]three"
    ]

    assert pr.findErrorExcerpts(lines, 2) == [
        ["a", "b", "##[error]one", "c", "##[error]two"],
        ["e", "f", "##[error]three"],
    ]


def testLogWithNoErrorLineFallsBackToItsEnd() -> None:
    pr = loadPrScript()

    assert pr.findErrorExcerpts(["a", "b", "c"], 2) == [["b", "c"]]
    assert pr.findErrorExcerpts([], 2) == []


def testRunnerTimestampIsDroppedAndOtherTextKept() -> None:
    pr = loadPrScript()

    assert pr.dropLogTimestamp("2026-10-09T18:00:01.0000000Z Post job cleanup.") == (
        "Post job cleanup."
    )
    assert pr.dropLogTimestamp("  File line 3") == "  File line 3"
