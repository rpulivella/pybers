#!/usr/bin/env python3
"""\
Closing a pull request without merging it, checked against what GitHub reports back.

GitHub is stood in for at the API boundary, and each request recorded.

UPDATES
2026-10-23  Written for PYB-156, to close a fork's test pull request.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/23"

import importlib
from types import ModuleType
from typing import Any

import pytest


def loadPrScript() -> ModuleType:
    """Return the pull request tool, imported the way its own tests import it."""
    return importlib.import_module("tools.workflow.pr")


def buildPullRequest(state: str) -> dict[str, Any]:
    """Return a pull request as GitHub's API describes one."""
    return {
        "number": 258, "title": "Update README.md", "html_url": "https://example/258",
        "state": state, "draft": False, "node_id": "PR_1",
        "head": {"ref": "develop", "sha": "a" * 40, "repo": {"full_name": "m/pybers"}},
        "base": {"ref": "develop"}, "user": {"login": "markus"},
    }


def runCloseOf(
    monkeypatch: pytest.MonkeyPatch, state: str, *extra: str, after: str = "closed"
) -> tuple[int, list[dict[str, Any]]]:
    """Close pull request 258 with GitHub stood in for, returning what was sent."""
    pr = loadPrScript()
    sent: list[dict[str, Any]] = []

    def requestStandIn(url: str, token: str, **options: Any) -> dict[str, Any]:
        if options.get("method") == "PATCH":
            sent.append(options["payload"])
            return buildPullRequest(after)
        return buildPullRequest(state)

    monkeypatch.setattr(pr.github, "resolveToken", lambda: "token")
    monkeypatch.setattr(pr.github, "requestJson", requestStandIn)
    arguments = pr.buildParser().parse_args(["close", "258", *extra])
    return pr.runClose(arguments), sent


def readOutput(capsys: pytest.CaptureFixture[str]) -> str:
    """Return what the tool printed, with rich's line wrapping undone."""
    return " ".join(capsys.readouterr().out.split())


def testAnOpenPullRequestIsClosedWithoutMerging(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, sent = runCloseOf(monkeypatch, "open")
    assert (code, sent) == (0, [{"state": "closed"}])
    assert "Closed PR #258 without merging" in readOutput(capsys)


def testAClosedPullRequestIsANoOpThatSendsNothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, sent = runCloseOf(monkeypatch, "closed")
    assert (code, sent) == (0, [])
    assert "PR #258 is already closed" in readOutput(capsys)


def testADryRunSendsNothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, sent = runCloseOf(monkeypatch, "open", "--dry-run")
    assert (code, sent) == (0, [])
    assert "would close PR #258 without merging" in readOutput(capsys)


def testAPullRequestStillOpenAfterTheCloseFailsLoudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _ = runCloseOf(monkeypatch, "open", after="open")
    assert code != 0
    stillOpen = "PR #258 is still open after the close reported success"
    assert stillOpen in readOutput(capsys)
