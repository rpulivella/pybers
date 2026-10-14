#!/usr/bin/env python3
"""\
Restarting a pull request's canceled or failed workflow runs, and nothing else.

GitHub is stood in for at the API boundary, and the restarts recorded.

UPDATES
2026-10-13  Pull request summaries and check runs are dataclasses, for PYB-204.
2026-10-05  Written for PYB-153, after a runner outage canceled both checks on PR #167.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/05"

import importlib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

repositoryRoot: Path = Path(__file__).resolve().parent.parent

def loadPrScript() -> ModuleType:
    """Return the pull request tool, imported the way its own tests import it."""
    return importlib.import_module("tools.workflow.pr")


def buildRun(
    runId: int, name: str, conclusion: str | None, created: str
) -> dict[str, Any]:
    """Return a workflow run as GitHub's API describes one."""
    return {"id": runId, "name": name, "conclusion": conclusion, "created_at": created}


def runRerunOf(
    monkeypatch: pytest.MonkeyPatch, runs: list[dict[str, Any]], *extra: str,
    failure: Exception | None = None,
) -> tuple[int, list[int]]:
    """Re-run a pull request's runs with GitHub stood in for, returning the restarts."""
    pr = loadPrScript()
    restarted: list[int] = []

    def restartStandIn(token: str, runId: int) -> None:
        if failure is not None:
            raise failure
        restarted.append(runId)

    monkeypatch.setattr(pr.github, "resolveToken", lambda: "token")
    monkeypatch.setattr(
        pr, "readPullRequest",
        lambda token, number: pr.PullRequestSummary(
            number=167, title="", url="", state="open", isDraft=False, head="",
            headRepository="", headSha="a" * 40, base="develop", nodeId="",
        ),
    )
    monkeypatch.setattr(
        pr.github, "requestJson",
        lambda url, token, **options: {"workflow_runs": runs},
    )
    monkeypatch.setattr(pr, "restartWorkflowRun", restartStandIn)
    arguments = pr.buildParser().parse_args(["rerun", "167", *extra])
    return pr.runRerun(arguments), restarted


def readOutput(capsys: pytest.CaptureFixture[str]) -> str:
    """Return what the tool printed, with rich's line wrapping undone."""
    return " ".join(capsys.readouterr().out.split())


def testCanceledAndFailedRunsRestartAndPassingOnesDoNot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = [
        buildRun(1, "preflight", "cancelled", "2026-10-05T01:00:00Z"),
        buildRun(2, "readiness", "failure", "2026-10-05T01:00:00Z"),
        buildRun(3, "merge-readiness", "success", "2026-10-05T01:00:00Z"),
    ]
    code, restarted = runRerunOf(monkeypatch, runs)
    assert code == 0
    assert restarted == [1, 2]


def testOnlyTheNewestRunOfAWorkflowCounts(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [
        buildRun(2, "preflight", "success", "2026-10-05T02:00:00Z"),
        buildRun(1, "preflight", "cancelled", "2026-10-05T01:00:00Z"),
    ]
    _, restarted = runRerunOf(monkeypatch, runs)
    assert restarted == []


def testNothingToRerunSaysSoAndRestartsNothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runs = [buildRun(1, "preflight", "success", "2026-10-05T01:00:00Z")]
    code, restarted = runRerunOf(monkeypatch, runs)
    assert (code, restarted) == (0, [])
    assert "Nothing to re-run" in readOutput(capsys)


def testARunStillInProgressIsNotRestarted(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [buildRun(1, "preflight", None, "2026-10-05T01:00:00Z")]
    _, restarted = runRerunOf(monkeypatch, runs)
    assert restarted == []


def testADryRunNamesTheRunsAndRestartsNone(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runs = [buildRun(1, "preflight", "cancelled", "2026-10-05T01:00:00Z")]
    code, restarted = runRerunOf(monkeypatch, runs, "--dry-run")
    assert (code, restarted) == (0, [])
    assert "would restart preflight" in readOutput(capsys)


def testARefusedRestartFailsNamingTheRunAndTheReason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pr = loadPrScript()
    refusal = pr.github.GitHubHttpError(403, "GitHub returned HTTP 403: not accessible")
    runs = [buildRun(1, "preflight", "cancelled", "2026-10-05T01:00:00Z")]
    with pytest.raises(RuntimeError, match="Could not restart preflight.*403"):
        runRerunOf(monkeypatch, runs, failure=refusal)
