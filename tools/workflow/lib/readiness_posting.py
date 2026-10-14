#!/usr/bin/env python3
"""\
The posting half of the merge-readiness report, which `merge-readiness.py report` runs.

It runs on the default branch's code in its own workflow, holding the one write this
automation makes, and reads the stored results the pull request's job wrote as data
only. Kept apart from `lib/readiness.py`, which never reaches this half.

UPDATES
2026-10-13  Moved here from `merge-readiness.py`, for PYB-204.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/03"

from datetime import datetime
from typing import Any

from tools.workflow.lib import github
from tools.workflow.lib import readiness as checks
from tools.workflow.lib import readiness_presenter as presenter
from tools.workflow.lib.pull_request import (
    defaultBaseBranch,
    formatPullRequestRef,
)

# The account a workflow's own token posts as, so a copied marker is never mistaken
# for this report.
reportAuthor: str = "github-actions[bot]"
commentsPerPage: int = 100


def readPullRequestFacts(token: str, number: int) -> dict[str, Any]:
    """Return the title, body, base and head a pull request carries."""
    url = f"{github.restRoot}/repos/{github.repositoryOwner}/{github.repositoryName}"
    payload = github.requestJson(f"{url}/pulls/{number}", token)
    return {
        "title": payload.get("title", ""),
        "body": payload.get("body") or "",
        "base": payload.get("base", {}).get("ref", defaultBaseBranch),
        "head": payload.get("head", {}).get("sha", ""),
        "draft": bool(payload.get("draft")),
    }


def findReportComment(token: str, number: int) -> int | None:
    """Return this report's earlier comment: its marker, posted by its own account."""
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/{github.repositoryName}"
        f"/issues/{number}/comments?per_page={commentsPerPage}"
    )
    page = 1
    while True:
        batch = github.requestJson(f"{url}&page={page}", token)
        for comment in batch:
            author = (comment.get("user") or {}).get("login")
            if author == reportAuthor and presenter.commentMarker in (
                comment.get("body") or ""
            ):
                return int(comment["id"])
        if len(batch) < commentsPerPage:
            return None
        page += 1


def confirmCheckedPullRequest(token: str, number: int, headSha: str) -> None:
    """Refuse to post unless the pull request's head is the commit this run checked.

    The number arrives in a file the pull request's own job wrote, so it is held
    against the run's head commit, which GitHub supplies and no branch can set.
    """
    head = readPullRequestFacts(token, number)["head"]
    if head != headSha:
        raise RuntimeError(
            f"{formatPullRequestRef(number)} has head {head[:12] or 'none'}, "
            f"not {headSha[:12]}, the commit this run checked, so nothing was posted."
        )


def postReportComment(token: str, number: int, body: str) -> str:
    """Post the report, or replace the one an earlier run left, and say which."""
    root = f"{github.restRoot}/repos/{github.repositoryOwner}/{github.repositoryName}"
    existing = findReportComment(token, number)
    if existing is None:
        github.requestJson(
            f"{root}/issues/{number}/comments", token, method="POST",
            payload={"body": body},
        )
        return "posted"
    github.requestJson(
        f"{root}/issues/comments/{existing}", token, method="PATCH",
        payload={"body": body},
    )
    return "replaced"


def renderStoredReport(stored: dict[str, Any], headSha: str) -> tuple[int, str]:
    """Return the pull request a stored report names and the comment this code renders.

    Nothing of the stored file is posted as written: its results are read as data
    and the comment is built here, against the head commit the run supplies.
    """
    facts = checks.BranchFacts.fromDictionary(stored)
    if not isinstance(facts.pullRequest, int) or facts.pullRequest <= 0:
        raise ValueError("The stored report names no pull request.")
    results = checks.readStoredResults(stored)
    moment = datetime.fromisoformat(str(stored.get("checkedAt", "")))
    facts.headSha = headSha
    return facts.pullRequest, presenter.renderComment(results, facts, moment)
