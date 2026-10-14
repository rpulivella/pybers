#!/usr/bin/env python3
"""\
Each check judged by its real run, never by a skipped draft run beside it.

A promoted pull request keeps its skipped draft run on the same commit as the real
run, and both can start in the same second. GitHub is stood in for at the API
boundary, with the runs PR #174 carried on 7057e55.

UPDATES
2026-10-13  Pull request summaries and check runs are dataclasses, for PYB-204.
2026-10-06  Written for PYB-175.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/06"

import importlib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tools.workflow.lib import pull_request as pullRequest

repositoryRoot: Path = Path(__file__).resolve().parent.parent
sameSecond: str = "2026-10-06T17:18:19Z"


def loadPrScript() -> ModuleType:
    """Return the pull request tool, imported the way its own tests import it."""
    return importlib.import_module("tools.workflow.pr")


def buildRun(
    name: str, conclusion: str | None, started: str = sameSecond
) -> dict[str, Any]:
    """Return one check run as GitHub's check-runs endpoint describes it."""
    status = "completed" if conclusion else "in_progress"
    return {
        "name": name, "status": status, "conclusion": conclusion,
        "started_at": started,
    }


def buildPr174Runs(readiness: str) -> list[dict[str, Any]]:
    """Return the runs on 7057e55, the real readiness run concluding as given."""
    return [
        buildRun("readiness", "skipped"),
        buildRun("preflight", "success"),
        buildRun("readiness", readiness),
        buildRun("preflight", "skipped", "2026-10-06T17:18:18Z"),
        buildRun("readiness", "skipped", "2026-10-06T17:18:18Z"),
    ]


def readVerdicts(runs: list[dict[str, Any]]) -> dict[str, str]:
    """Return each check's reported conclusion, or its status while it runs."""
    return {
        run.name: run.conclusion or run.status
        for run in pullRequest.chooseLatestRuns(runs)
    }


@pytest.mark.parametrize("ordering", [list, lambda runs: list(reversed(runs))])
def testTheRunsOnPr174ReportReadinessAsItsSuccess(ordering: Any) -> None:
    assert readVerdicts(ordering(buildPr174Runs("success"))) == {
        "readiness": "success", "preflight": "success",
    }


def testASkippedTwinNeverHidesAFailureInEitherOrder() -> None:
    runs = buildPr174Runs("failure")
    assert readVerdicts(runs)["readiness"] == "failure"
    assert readVerdicts(list(reversed(runs)))["readiness"] == "failure"


def testALaterSkippedRunNeverHidesAnEarlierFailure() -> None:
    runs = [
        buildRun("readiness", "failure", "2026-10-06T17:00:00Z"),
        buildRun("readiness", "skipped", "2026-10-06T18:00:00Z"),
    ]
    assert readVerdicts(runs) == {"readiness": "failure"}


def testARealRunStillInProgressIsReportedOverItsSkippedTwin() -> None:
    runs = [buildRun("readiness", "skipped"), buildRun("readiness", None)]
    assert readVerdicts(runs) == {"readiness": "in_progress"}


def testALoneSkippedRunReportsSkippedAndIsNoPass() -> None:
    pr = loadPrScript()
    runs = pullRequest.chooseLatestRuns([buildRun("readiness", "skipped")])
    assert [run.conclusion for run in runs] == ["skipped"]
    assert pr.confirmChecksPassed(runs) is False


@pytest.mark.parametrize("ordering", [list, lambda runs: list(reversed(runs))])
def testAMergeRefusesAFailureTiedWithASkippedRun(
    monkeypatch: pytest.MonkeyPatch, ordering: Any,
) -> None:
    pr = loadPrScript()
    merged: list[int] = []
    payload = {
        "number": 174, "title": "[PYB-155] A change", "html_url": "https://x/174",
        "state": "open", "draft": False, "node_id": "PR_1",
        "head": {"ref": "docs/155-a-change", "sha": "a" * 40,
                 "repo": {"full_name": "rpulivella/pybers"}},
        "base": {"ref": "develop"},
    }
    monkeypatch.setattr(pr.github, "resolveToken", lambda: "token")
    monkeypatch.setattr(
        pr, "readPullRequest",
        lambda token, number: pullRequest.summarizePullRequest(payload),
    )
    monkeypatch.setattr(
        pr.github, "requestJson",
        lambda url, token, **options: {
            "check_runs": ordering(buildPr174Runs("failure")),
        },
    )
    monkeypatch.setattr(pr, "mergePullRequest", lambda *args: merged.append(174))
    arguments = pr.buildParser().parse_args(
        ["merge", "174", "--subject", "[155] docs: a change"]
    )
    assert pr.runMerge(arguments) == pr.errorExitCode
    assert merged == []
