#!/usr/bin/env python3
"""\
The posting half of the merge-readiness report, and the workflows around it.

A pull request from a fork chooses what its own job uploads, so these establish
that nothing it uploads runs, that the comment is rendered by this repository's
code, that it lands only on the pull request the run checked, and that no
workflow hands a branch's values to a shell or keeps its token in a checkout.

UPDATES
2026-10-13  Imports `lib/readiness_posting.py` rather than the command, for
            PYB-204.
2026-10-03  Written for PYB-151.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/03"

import json
import re
from pathlib import Path
from typing import Any

import pytest

repositoryRoot: Path = Path(__file__).resolve().parent.parent
from tools.workflow.lib import readiness as checks  # noqa: E402
from tools.workflow.lib import readiness_posting as posting  # noqa: E402
from tools.workflow.lib import readiness_presenter as presenter  # noqa: E402

workflowDirectory: Path = repositoryRoot / ".github" / "workflows"
checkedHead: str = "0123456789abcdef0123456789abcdef01234567"
workflowNames: list[str] = sorted(path.name for path in workflowDirectory.glob("*.yml"))


def buildStoredReport(**overrides: Any) -> dict[str, Any]:
    """Return a stored report as the checking job writes it, with any field replaced."""
    stored: dict[str, Any] = {
        "ticket": "151", "branch": "bugfix/151-a", "headSha": checkedHead,
        "pullRequest": 160,
        "results": [{"name": "preflight", "status": "passed", "detail": "It passed"}],
        "checkedAt": "2026-10-03T12:00:00+00:00",
    }
    stored.update(overrides)
    return stored


def readWorkflow(name: str) -> str:
    """Return one workflow's text."""
    return (workflowDirectory / name).read_text()


def listRunBlocks(text: str) -> list[str]:
    """Return every `run:` step's script in a workflow, read without a YAML parser."""
    blocks: list[str] = []
    lines = text.splitlines()
    for at, line in enumerate(lines):
        match = re.match(r"^(\s*)run:\s*(.*)$", line)
        if not match:
            continue
        indent, inline = len(match.group(1)), match.group(2)
        if inline not in ("|", ">", "|-", ">-"):
            blocks.append(inline)
            continue
        body = []
        for following in lines[at + 1:]:
            if following.strip() and len(following) - len(following.lstrip()) <= indent:
                break
            body.append(following)
        blocks.append("\n".join(body))
    return blocks


def testTheRenderedCommentComesFromStoredResultsNotFromAnyBodyTheBranchWrote(
    tmp_path: Path,
) -> None:
    stored = buildStoredReport()
    (tmp_path / "merge-readiness.md").write_text("Anything a fork wanted to say")

    number, body = posting.renderStoredReport(stored, checkedHead)

    assert number == 160
    assert body.startswith(presenter.commentMarker)
    assert "### ✅ preflight" in body
    assert "Anything a fork wanted to say" not in body


def testTheCommentNamesTheCommitTheRunCheckedNotTheOneTheFileClaims() -> None:
    stored = buildStoredReport(headSha="ffffffffffff")

    _, body = posting.renderStoredReport(stored, checkedHead)

    assert checkedHead[:12] in body
    assert "ffffffffffff" not in body


@pytest.mark.parametrize(
    "results",
    [
        [],
        [{"name": "preflight", "status": "excellent", "detail": "x"}],
        [{"name": "preflight", "status": "passed", "detail": ["not", "text"]}],
        ["not an object"],
    ],
)
def testAStoredReportWithoutValidResultsIsRefused(results: list[Any]) -> None:
    with pytest.raises(ValueError):
        posting.renderStoredReport(
            buildStoredReport(results=results), checkedHead
        )


@pytest.mark.parametrize("pullRequest", [0, -3, "160"])
def testAStoredReportNamingNoValidPullRequestIsRefused(pullRequest: object) -> None:
    with pytest.raises(ValueError):
        posting.renderStoredReport(
            buildStoredReport(pullRequest=pullRequest), checkedHead
        )


def testALongDetailIsCutRatherThanPostedWhole() -> None:
    stored = buildStoredReport(
        results=[{"name": "preflight", "status": "passed", "detail": "x" * 9000}]
    )

    assert len(checks.readStoredResults(stored)[0].detail) == checks.detailLimit


def testNothingIsPostedToAPullRequestWhoseHeadIsNotTheCheckedCommit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        posting.github, "requestJson",
        lambda url, token, **kwargs: {"head": {"sha": "f" * 40}, "base": {"ref": "x"}},
    )

    with pytest.raises(RuntimeError, match="nothing was posted"):
        posting.confirmCheckedPullRequest("token", 160, checkedHead)


def testAPullRequestWhoseHeadIsTheCheckedCommitIsConfirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        posting.github, "requestJson",
        lambda url, token, **kwargs: {
            "head": {"sha": checkedHead}, "base": {"ref": "x"}
        },
    )

    posting.confirmCheckedPullRequest("token", 160, checkedHead)


def buildComment(identifier: int, login: str, body: str) -> dict[str, Any]:
    """Return one comment as the issues API lists it."""
    return {"id": identifier, "user": {"login": login}, "body": body}


def testAnotherAccountsCommentCarryingTheMarkerIsNeverTakenForTheReport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = [
        buildComment(1, "someone", f"{presenter.commentMarker} imitation"),
        buildComment(2, posting.reportAuthor, f"{presenter.commentMarker} real"),
    ]
    monkeypatch.setattr(
        posting.github, "requestJson", lambda url, token, **kwargs: page
    )

    assert posting.findReportComment("token", 160) == 2


def testOnlyAnImitationMeansThereIsNoEarlierReport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = [buildComment(1, "someone", f"{presenter.commentMarker} imitation")]
    monkeypatch.setattr(
        posting.github, "requestJson", lambda url, token, **kwargs: page
    )

    assert posting.findReportComment("token", 160) is None


def testTheReportIsFoundPastTheFirstHundredComments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filler = [buildComment(n, "someone", "chatter") for n in range(100)]
    report = buildComment(500, posting.reportAuthor, presenter.commentMarker)
    pages = {1: filler, 2: [report]}
    requested: list[int] = []

    def answerPage(url: str, token: str, **kwargs: object) -> list[dict[str, Any]]:
        number = int(re.search(r"[?&]page=(\d+)", url).group(1))  # type: ignore[union-attr]
        requested.append(number)
        return pages.get(number, [])

    monkeypatch.setattr(posting.github, "requestJson", answerPage)

    assert posting.findReportComment("token", 160) == 500
    assert requested == [1, 2]


def testThePostingWorkflowUnpacksTheArtifactOutsideItsCheckout() -> None:
    text = readWorkflow("merge-readiness.yml")
    download = text.split("actions/download-artifact", 1)[1].split("- name:", 1)[0]

    assert "path: ${{ runner.temp }}/readiness" in download


def testThePostingWorkflowRunsItsOwnScriptAgainstTheUnpackedData() -> None:
    (script,) = [
        block for block in listRunBlocks(readWorkflow("merge-readiness.yml"))
        if "tools.workflow.merge_readiness" in block
    ]

    assert script.split()[:4] == [
        "python", "-m", "tools.workflow.merge_readiness", "report",
    ]
    assert '--results "$RUNNER_TEMP/readiness/merge-readiness.json"' in script
    assert '--head-sha "$HEAD_SHA"' in script
    assert "--comment" not in script


def testTheCheckingWorkflowHandsOnDataAndNoRenderedComment() -> None:
    upload = readWorkflow("readiness.yml").split("actions/upload-artifact", 1)[1]

    assert "path: merge-readiness.json" in upload
    assert "merge-readiness.md" not in upload


@pytest.mark.parametrize("name", workflowNames)
def testEveryCheckoutKeepsNoToken(name: str) -> None:
    text = readWorkflow(name)
    checkouts = text.split("uses: actions/checkout@")[1:]

    for checkout in checkouts:
        step = checkout.split("\n      - ", 1)[0]
        assert "persist-credentials: false" in step, name


@pytest.mark.parametrize("name", workflowNames)
def testNoRunStepReadsAnExpressionAsShell(name: str) -> None:
    for block in listRunBlocks(readWorkflow(name)):
        assert "${{" not in block, f"{name}: {block.strip()[:60]}"


def testTheStoredResultsSurviveTheRoundTripTheTwoJobsMake() -> None:
    results = [
        checks.CheckResult("preflight", checks.passed, "It passed"),
        checks.CheckResult("Changelog", checks.attention, "A reason was recorded"),
    ]
    stored = json.loads(json.dumps({"results": checks.encodeResults(results)}))

    assert checks.readStoredResults(stored) == results
