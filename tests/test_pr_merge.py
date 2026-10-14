#!/usr/bin/env python3
"""\
What a merge deletes, decided by where the head branch lives rather than its name.

A fork's branch can carry the name of one of this repository's branches, so a
merge that deleted by name alone could cost this repository a branch it never
merged. GitHub is stood in for at the API boundary, and the deletes recorded.

UPDATES
2026-10-13  Pull request summaries and check runs are dataclasses, for PYB-204.
2026-10-04  Written for PYB-152.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/04"

import importlib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tools.workflow.lib import pull_request as pullRequest

repositoryRoot: Path = Path(__file__).resolve().parent.parent
sharedName: str = "feature/136-copy-a-block-of-cells"


def loadPrScript() -> ModuleType:
    """Return the pull request tool, imported the way its own tests import it."""
    return importlib.import_module("tools.workflow.pr")


def buildPayload(repository: str | None, branch: str = sharedName) -> dict[str, Any]:
    """Return a pull request as GitHub's API describes one, its head in `repository`."""
    return {
        "number": 160, "title": "[PYB-152] A change", "html_url": "https://x/160",
        "state": "open", "draft": False, "node_id": "PR_1",
        "head": {
            "ref": branch, "sha": "a" * 40,
            "repo": None if repository is None else {"full_name": repository},
        },
        "base": {"ref": "develop"},
    }


def runMergeOf(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any], *extra: str,
    asked: bool = True,
) -> tuple[int, list[str]]:
    """Merge one pull request with GitHub stood in for, and return what was deleted."""
    pr = loadPrScript()
    deleted: list[str] = []
    monkeypatch.setattr(pr.github, "resolveToken", lambda: "token")
    monkeypatch.setattr(
        pr, "readPullRequest",
        lambda token, number: pullRequest.summarizePullRequest(payload),
    )
    monkeypatch.setattr(
        pr, "readCheckRuns",
        lambda token, sha: [
            pullRequest.CheckRun(
                name="preflight", status="completed", conclusion="success"
            )
        ],
    )
    monkeypatch.setattr(pr, "mergePullRequest", lambda *args: "b" * 40)
    monkeypatch.setattr(
        pr, "deleteBranch", lambda token, branch: deleted.append(branch)
    )
    flags = ["--delete-branch"] if asked else []
    arguments = pr.buildParser().parse_args(
        ["merge", "160", "--subject", "[152] fix: a change", *flags, *extra]
    )
    return pr.runMerge(arguments), deleted


def readOutput(capsys: pytest.CaptureFixture[str]) -> str:
    """Return what the tool printed, with rich's line wrapping undone."""
    return " ".join(capsys.readouterr().out.split())


def testAMergeDeletesNoBranchUnlessAsked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pr = loadPrScript()
    ours = f"{pr.github.repositoryOwner}/{pr.github.repositoryName}"

    code, deleted = runMergeOf(monkeypatch, buildPayload(ours), asked=False)

    assert (code, deleted) == (0, [])
    assert f"Kept branch {sharedName}" in readOutput(capsys)


def testOurOwnBranchIsDeletedAfterItsMerge(monkeypatch: pytest.MonkeyPatch) -> None:
    pr = loadPrScript()
    ours = f"{pr.github.repositoryOwner}/{pr.github.repositoryName}"

    code, deleted = runMergeOf(monkeypatch, buildPayload(ours))

    assert (code, deleted) == (0, [sharedName])


def testAForksBranchNamedLikeOneOfOursIsNeverDeletedHere(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, deleted = runMergeOf(monkeypatch, buildPayload("stranger/pybers"))

    assert (code, deleted) == (0, [])
    assert "the fork's to remove" in readOutput(capsys)


def testAPullRequestWhoseForkWasDeletedDeletesNothingHere(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, deleted = runMergeOf(monkeypatch, buildPayload(None))

    assert (code, deleted) == (0, [])
    assert "a fork since deleted" in readOutput(capsys)


def testTheRepositoryNameIsComparedWhateverItsCase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pr = loadPrScript()
    ours = f"{pr.github.repositoryOwner}/{pr.github.repositoryName}".upper()

    _, deleted = runMergeOf(monkeypatch, buildPayload(ours))

    assert deleted == [sharedName]


def testADryRunOfAForksMergeSaysItDeletesNothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, deleted = runMergeOf(
        monkeypatch, buildPayload("stranger/pybers"), "--dry-run"
    )

    output = readOutput(capsys)
    assert (code, deleted) == (0, [])
    assert "deletes nothing" in output
    assert "would delete" not in output
