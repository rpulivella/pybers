#!/usr/bin/env python3
"""\
pybers pull request tool

The single sanctioned path to GitHub pull requests. `/pr-draft` and
`/pr-review-code` call this rather than `gh`, so that the workflow's invariants,
a PR is always opened as a draft and the merge commit carries the house subject,
hold in exactly one place. A merge deletes no branch unless asked to, and never one
a fork's pull request merely shares a name with.

**This tool exists to replace `gh`.** `gh` resolves its own identity from an OAuth
token in the system keyring, which can hold several accounts at once, so the
account a `gh pr create` acts as is ambient state no repository can control. This
tool authenticates with the explicit PAT that `github.py` already resolves, which
means every GitHub interaction in this repository runs on exactly two channels: a
PAT for the API, and SSH for git itself.

Talks to GitHub over urllib: REST for the pull request itself, GraphQL for the
one operation REST does not expose (marking a draft ready for review). Never
shells out, not to `gh`, not to `git`, not to `curl`. The current branch is read
by parsing `.git/HEAD` directly.

Authentication and the HTTP helpers are reused from `github.py` rather than
reimplemented, so this repository keeps exactly one auth story.

Usage:
    .venv/bin/python3 -m tools.workflow.pr create --title "[PYB-14] Add a thing" \
        --body-file draft.md
    .venv/bin/python3 -m tools.workflow.pr create --title "..." --body-file draft.md \
        --base main
    .venv/bin/python3 -m tools.workflow.pr find
    .venv/bin/python3 -m tools.workflow.pr find --number-only
    .venv/bin/python3 -m tools.workflow.pr export-as-source 8 --body
    .venv/bin/python3 -m tools.workflow.pr export-as-source 8 --title
    .venv/bin/python3 -m tools.workflow.pr ready 8
    .venv/bin/python3 -m tools.workflow.pr rerun 8
    .venv/bin/python3 -m tools.workflow.pr logs 8 --context 30
    .venv/bin/python3 -m tools.workflow.pr merge 8 --subject "[14] feat: add a thing"
    .venv/bin/python3 -m tools.workflow.pr merge 8 --subject "..." --delete-branch

Runs on the repository's venv.

UPDATES
2026-10-14  Moved here from `scripts/pr.py`, and run as a module, for PYB-204.
2026-10-13  The comment commands are `github.py`'s own, for PYB-204.
2026-10-13  The repository root comes from `lib/shared.py`, for PYB-204.
2026-10-09  Added `logs`, which prints each error a failed job logged, after both
            checks on PR #191 failed with no readiness comment, for PYB-181.
2026-10-06  A skipped run no longer hides another run of the same check, after a tie
            on the start time reported PR #174's readiness as skipped, for PYB-175.
2026-10-05  Added `rerun`, which restarts a pull request's canceled or failed workflow
            runs, after a runner outage canceled both checks on PR #167, for PYB-153.
2026-10-04  A merge deletes its head branch only with `--delete-branch`, which
            replaces `--keep-branch`, and only when that branch lives in this
            repository, so a fork's branch name never costs this repository a
            branch, for PYB-152.
2026-09-25  Bodies post and export through `github.py`'s shared handling, for
            PYB-134.
2026-09-01  Added `export-as-source`, matching github.py's command of the same name
            down to the flags and the handler name. `edit` replaces the WHOLE body
            and GitHub has no conflict detection, so a revision drafted from memory
            silently discards whatever changed in between. github.py has carried the
            remedy since 2026-08-13 and this tool carried only the hazard, which was
            hit twice in one day revising pull request 15. One divergence, forced by
            the data rather than chosen: PullRequestSummary omits the body, so the
            body emitter takes a string where github.py's takes a summary.
2026-08-31  Added `edit`, and fixed two calls that passed a `ticket` argument their
            signatures stopped taking when this module moved from injecting that
            dependency to importing it. Both were unreachable until now: the first
            blocked the first pull request this repository ever opened, and the
            second sat on the MERGE path inside a handler that reports "whether it
            landed is unknown", so a merge would have claimed an unknown outcome
            having sent nothing at all. `edit` exists because a body is a durable
            record that a branch outgrows, and because a waived preflight stage has
            to be written into the body to count.
2026-08-17  Round two of the same review. The merge PUT is now guarded as well as the
            branch delete: urllib lets a read-phase TimeoutError through as an OSError
            and a proxy error page makes json.loads raise ValueError, neither of which
            is a RuntimeError, so both escaped to exit 1, the code meaning "no pull
            request", after a merge that may have landed. main() is broadened for the
            same reason. A delete answering 404 or 422 is now success, because the ref
            is already gone whenever the repository deletes head branches automatically,
            and an alarm that fires on success stops being read. `squash` stays
            available: the tool serves repositories that permit it, and the prohibition
            belongs in /pr-review-code, but the usage example teaching it is gone, since
            permitting and advertising are different acts.
2026-08-16  Fixed the four defects a code review found on 2026-08-14, all of them in
            the half of this file that had never executed. A failed branch delete no
            longer reports the completed merge as a failure; `find` says which of
            three things happened instead of signalling "none" with silence; the
            unpushed-branch guard reads a status code rather than searching the error
            text for "404"; and `find` filters on base, refusing to choose when more
            than one pull request still matches.
2026-08-13  Written to take pull requests off `gh`. See the module docstring for
            why: `gh` acts as whichever account is active in its keyring, which
            no repository can pin.
"""
__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/13"
__usage__ = ".venv/bin/python3 -m tools.workflow.pr <command> [options]"

import argparse
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from typing import IO, Any

from rich.console import Console
from rich.markup import escape

# The one GitHub client, reused rather than reimplemented, so there is one auth story.
from tools.workflow.lib import github
from tools.workflow.lib import github_commands as commands
from tools.workflow.lib.pull_request import (
    defaultBaseBranch,
    findBodyFindings,
    formatPullRequestRef,
    readHeadings,
    readTemplate,
)
from tools.workflow.lib.shared import repositoryRoot

console = Console()


# GitHub also offers "rebase". It is deliberately absent: rebasing rewrites the
# branch's commits, and nothing in this workflow has ever asked for that.
validMergeMethods: tuple[str, ...] = (
    "merge",
    "squash",
)

# Where a ticket goes back to when a merge does not complete it. The closing
# keyword stays in every body, because it is what links a pull request to its
# ticket, so a ticket carried by more than one pull request is reopened instead.
inProgressStatus: str = "In Progress"

# How long to watch for GitHub to act on the closing keyword, which it does
# seconds after the merge rather than with it.
ticketCloseAttempts: int = 10
ticketClosePauseSeconds: float = 3.0

# Exit codes are distinguished because a skill reads them and acts. Collapsing
# "there is no pull request" into "something went wrong" made a missing token
# report as a missing pull request: /pr-review-code asks `find --number-only`
# whether a PR exists, and a 401 answered "no" just as convincingly as an empty
# list did. "I could not determine X" and "X is not there" are different claims,
# and only one of them is a fact this tool holds.
notFoundExitCode: int = 1
errorExitCode: int = 2

# Lines printed before each error a job logs. The runner's cleanup fills the end
# of every log, so the error lines locate the cause and the tail does not.
defaultLogContext: int = 12
errorLogMarker: str = "##[error]"


# The merge landed and only the cleanup did not. Distinct from both of the above
# because the recovery is neither "retry" nor "investigate": it is "finish the
# last step by hand, and on no account run merge again".
partialSuccessExitCode: int = 3

# What `find --number-only` prints when there is genuinely no pull request. A word
# rather than an empty line, because the caller is an agent reading stdout: it can
# tell this apart from a number and from an error message, whereas it cannot tell
# an empty stdout apart from a command that died before printing. Deliberately not
# a number and not a valid PR reference, so it can never be mistaken for one.
noOpenPullRequestMarker: str = "no-open-pull-request"


def parsePullRequestNumber(value: str) -> int:
    """Parse `PR #38`, `#38`, `38` or the pull request URL."""
    text = value.strip()
    if text.lower().startswith("pr"):
        text = text[2:].strip()
    elif "/pull/" in text:
        text = text.rsplit("/pull/", 1)[1]
    text = text.lstrip("#").strip()
    if not text.isdigit():
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a pull request. Use PR #38, #38, 38, or the URL."
        )
    return int(text)


# What `checks` prints as its verdict. Words rather than color alone, for the
# reason the marker above exists: the consumer is an agent reading stdout, and it
# must be able to tell an answer from a command that died before printing one.
checksPassedMarker: str = "checks-passed"
checksNotPassedMarker: str = "checks-not-passed"

# A conclusion that does not block a merge. `skipped` belongs here because #5's
# workflow skips its job on a draft, and that skipped run attaches to the SAME
# commit the real run does once the pull request is promoted, so treating it as a
# failure would leave every promoted pull request permanently red.
passingConclusions: frozenset[str] = frozenset({"success", "skipped"})

# A workflow run's conclusion that a re-run can change. GitHub spells it `cancelled`.
rerunConclusions: frozenset[str] = frozenset(
    {"cancelled", "failure", "timed_out", "startup_failure"}
)


@dataclass(frozen=True)
class PullRequestSummary:
    """An open or merged pull request, as the skills need to see it."""

    number: int
    title: str
    url: str
    state: str
    isDraft: bool
    head: str
    # The repository the head branch lives in, empty once a fork is deleted.
    headRepository: str
    headSha: str
    base: str
    nodeId: str


@dataclass(frozen=True)
class CheckRun:
    """One check run on a commit, reduced to what a merge decision needs."""

    name: str
    status: str
    conclusion: str


@dataclass(frozen=True)
class WorkflowRun:
    """One workflow run on a commit, reduced to what a re-run decision needs."""

    runId: int
    name: str
    conclusion: str


def readCurrentBranch() -> str:
    """Return the checked-out branch name by reading .git/HEAD.

    Parsed rather than shelled out to `git`, per the house rule. A worktree stores
    a `gitdir:` pointer in place of a directory, so both shapes are handled.
    """
    gitPath = repositoryRoot / ".git"
    if gitPath.is_file():
        pointer = gitPath.read_text(encoding="utf-8").strip()
        if not pointer.startswith("gitdir:"):
            raise RuntimeError(f"Unrecognized .git file contents: {pointer!r}")
        gitPath = Path(pointer.partition(":")[2].strip())

    headPath = gitPath / "HEAD"
    if not headPath.is_file():
        raise RuntimeError(f"No HEAD found at {headPath}.")

    head = headPath.read_text(encoding="utf-8").strip()
    if not head.startswith("ref: refs/heads/"):
        raise RuntimeError(
            "HEAD is detached, so there is no branch to open a pull request from. "
            "Check out a branch first."
        )
    return head[len("ref: refs/heads/") :]


def summarizePullRequest(payload: dict[str, Any]) -> PullRequestSummary:
    """Reduce GitHub's pull request payload to the fields this tool reports on."""
    return PullRequestSummary(
        number=int(payload["number"]),
        title=payload["title"],
        url=payload["html_url"],
        state=payload["state"],
        isDraft=bool(payload.get("draft", False)),
        head=payload["head"]["ref"],
        headRepository=(payload["head"].get("repo") or {}).get("full_name", ""),
        headSha=payload["head"]["sha"],
        base=payload["base"]["ref"],
        nodeId=payload["node_id"],
    )


def checkHeadIsOurs(summary: PullRequestSummary) -> bool:
    """Return whether a pull request's head branch lives in this repository.

    A fork's branch can carry any name, one of ours included, so its name alone
    never decides what a merge deletes here.
    """
    ours = f"{github.repositoryOwner}/{github.repositoryName}"
    return summary.headRepository.lower() == ours.lower()


def formatForkBranch(summary: PullRequestSummary) -> str:
    """Say whose a fork's head branch is, which a merge here never deletes."""
    owner = summary.headRepository or "a fork since deleted"
    return f"{summary.head} belongs to {owner}, so it is the fork's to remove"


def assertBranchIsPushed(token: str, branch: str) -> None:
    """Raise a clear error when the branch does not exist on the remote yet.

    GitHub refuses to open a pull request from an unpushed branch with a message
    about an invalid field, which reads as a bug in this tool rather than as the
    missing `git push` it actually is.

    The status is read from the exception's own `statusCode`, never by searching
    its message. Matching the string "404" conflated two very different causes:
    a **private** repository (which this one will be) answers 404 rather than
    403 to a token that has expired or lost `repo` scope, so an expired credential
    was reported as an unpushed branch and sent the user to run a `git push` that
    could not possibly help.
    """
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/branches/{urllib.parse.quote(branch)}"
    )
    try:
        github.requestJson(url, token)
    except github.GitHubHttpError as exc:
        if exc.statusCode == 404:
            raise RuntimeError(
                f"Branch {branch!r} was not found on the remote. Usually that means it "
                f"is unpushed, push it first:\n  git push -u origin {branch}\n"
                f"On a private repository a 404 can also mean the token cannot see the "
                f"repository at all, so check the credential if the branch is pushed."
            ) from exc
        raise


def createDraftPullRequest(
    token: str,
    title: str,
    body: str,
    head: str,
    base: str,
) -> PullRequestSummary:
    """Open a pull request as a draft and return it.

    Always a draft, with no option to open otherwise: draft-versus-ready is a real
    signal in this workflow, and only /pr-review-code may clear it.
    """
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/pulls"
    )
    payload = {
        "title": title,
        "body": body,
        "head": head,
        "base": base,
        "draft": True,
    }
    return summarizePullRequest(
        github.requestJson(url, token, method="POST", payload=payload)
    )


def findOpenPullRequest(
    token: str, head: str, base: str
) -> PullRequestSummary | None:
    """Return the open pull request for a branch and base, or None when there is none.

    Filtered by base as well as head, and it must be. GitHub permits several open
    pull requests from one head branch to different bases, and returns them newest
    first, so taking the first of an unfiltered list picks whichever was opened
    most recently rather than the one being asked about. `/pr-review-code` feeds
    that number straight into `ready` and `merge`, so guessing here would promote
    and merge the wrong pull request.

    More than one match after filtering is refused rather than resolved. There is
    no correct guess available, and choosing silently is how the wrong one gets
    merged.
    """
    query = urllib.parse.urlencode(
        {"head": f"{github.repositoryOwner}:{head}", "base": base, "state": "open"}
    )
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/pulls?{query}"
    )
    matches = github.requestJson(url, token)
    if not matches:
        return None
    if len(matches) > 1:
        numbers = ", ".join(
            f"{formatPullRequestRef(match['number'])}" for match in matches
        )
        raise RuntimeError(
            f"{len(matches)} open pull requests from {head!r} into {base!r}: "
            f"{numbers}. "
            "Refusing to choose one. Close the ones that do not belong, or name the "
            "number explicitly."
        )
    return summarizePullRequest(matches[0])


def readPullRequest(token: str, number: int) -> PullRequestSummary:
    """Fetch one pull request by number."""
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/pulls/{number}"
    )
    return summarizePullRequest(github.requestJson(url, token))


def readPullRequestBody(token: str, number: int) -> str:
    """Return a pull request's body text, which the summary deliberately omits.

    `PullRequestSummary` carries what the skills report on, and a whole description
    is not that. It is needed only to verify an edit landed.
    """
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/pulls/{number}"
    )
    return github.requestJson(url, token).get("body") or ""


def readCheckRuns(token: str, sha: str) -> list[CheckRun]:
    """Return every check run GitHub reports for one commit.

    The check-runs endpoint, never the legacy commit statuses one. Actions writes
    no legacy status, so `/commits/{sha}/status` answers an empty `success` for a
    repository whose only CI is Actions. That reads as green and is precisely the
    silent pass this command exists to prevent.
    """
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/commits/{sha}/check-runs"
    )
    payload = github.requestJson(url, token, apiVersion="2022-11-28")
    return chooseLatestRuns(payload.get("check_runs", []))


def chooseLatestRuns(runs: list[dict[str, Any]]) -> list[CheckRun]:
    """Return the newest run per name, since GitHub keeps every run a commit had.

    A pull request promoted out of draft carries the skipped draft run beside the
    real one, under the same name, and both can start in the same second. A skipped
    run therefore stands for its check only when the check has no other run, or a
    tie on the timestamp could report the skip and hide a failure behind it.
    """
    realNames = {run["name"] for run in runs if run.get("conclusion") != "skipped"}
    counted = [
        run for run in runs
        if run["name"] not in realNames or run.get("conclusion") != "skipped"
    ]
    latest: dict[str, CheckRun] = {}
    for run in sorted(counted, key=lambda run: str(run.get("started_at") or "")):
        latest[run["name"]] = CheckRun(
            name=run["name"],
            status=run["status"],
            # Null until a run completes, and "" reports better than "None".
            conclusion=run.get("conclusion") or "",
        )
    return list(latest.values())


def readWorkflowRuns(token: str, sha: str) -> list[WorkflowRun]:
    """Return the newest workflow run per workflow on one commit.

    Newest only, because a promoted pull request keeps its skipped draft run, and a
    re-run supersedes the run it restarted.
    """
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/actions/runs?head_sha={sha}&per_page=100"
    )
    payload = github.requestJson(url, token, apiVersion="2022-11-28")
    latest: dict[str, WorkflowRun] = {}
    runs = payload.get("workflow_runs", [])
    for run in sorted(runs, key=lambda run: str(run.get("created_at") or "")):
        latest[run["name"]] = WorkflowRun(
            runId=run["id"], name=run["name"], conclusion=run.get("conclusion") or ""
        )
    return list(latest.values())


@dataclass(frozen=True)
class JobFailure:
    """One job that did not succeed, with the steps that failed and its log."""

    workflow: str
    name: str
    conclusion: str
    failedSteps: tuple[str, ...]
    log: str


class RedirectRefusal(urllib.request.HTTPRedirectHandler):
    """Surface a redirect instead of following it with the token attached."""

    def redirect_request(
        self, req: urllib.request.Request, fp: IO[bytes], code: int, msg: str,
        headers: Message, newurl: str,
    ) -> None:
        """Decline every redirect, so urllib raises it as an HTTPError instead."""
        return None


def readJobLog(token: str, jobId: int) -> str:
    """Return one job's log as text.

    GitHub answers with a redirect to signed storage. Following it with urllib
    would forward the Authorization header to a host that has no business seeing
    the token, so the redirect is read and fetched again without it.
    """
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/actions/jobs/{jobId}/logs"
    )
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "pybers-ticket-tool")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    opener = urllib.request.build_opener(RedirectRefusal)
    try:
        with opener.open(request, timeout=30) as response:
            return response.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location") if exc.code in (301, 302, 307) else None
        if location is None:
            detail = exc.read().decode(errors="replace")
            raise github.GitHubHttpError(
                exc.code, f"GitHub returned HTTP {exc.code}: {detail}"
            ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach GitHub: {exc.reason}") from exc
    try:
        with urllib.request.urlopen(location, timeout=60) as response:
            return response.read().decode(errors="replace")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not download the job log: {exc}") from exc


def readJobFailures(token: str, sha: str) -> list[JobFailure]:
    """Return every job that did not succeed in the newest runs on one commit."""
    failures: list[JobFailure] = []
    for run in readWorkflowRuns(token, sha):
        if run.conclusion not in rerunConclusions:
            continue
        url = (
            f"{github.restRoot}/repos/{github.repositoryOwner}/"
            f"{github.repositoryName}/actions/runs/{run.runId}/jobs?per_page=100"
        )
        payload = github.requestJson(url, token, apiVersion="2022-11-28")
        for job in payload.get("jobs", []):
            conclusion = job.get("conclusion") or ""
            if conclusion not in rerunConclusions:
                continue
            failures.append(JobFailure(
                workflow=run.name,
                name=job["name"],
                conclusion=conclusion,
                failedSteps=tuple(
                    step["name"] for step in job.get("steps", [])
                    if step.get("conclusion") in rerunConclusions
                ),
                log=readJobLog(token, job["id"]),
            ))
    return failures


def dropLogTimestamp(line: str) -> str:
    """Drop the runner's leading timestamp, which every line carries."""
    stamp, _, rest = line.partition(" ")
    return rest if stamp[:4].isdigit() and stamp.endswith("Z") else line


def findErrorExcerpts(lines: list[str], context: int) -> list[list[str]]:
    """Return each error line with the lines before it, overlapping excerpts merged.

    A log with no error line returns its last `context` lines, so a job that died
    without one still shows something.
    """
    errors = [index for index, line in enumerate(lines) if errorLogMarker in line]
    if not errors:
        return [lines[-context:]] if lines else []
    excerpts: list[list[str]] = []
    start, end = max(errors[0] - context, 0), errors[0]
    for index in errors[1:]:
        if index - context <= end + 1:
            end = index
            continue
        excerpts.append(lines[start:end + 1])
        start, end = max(index - context, 0), index
    excerpts.append(lines[start:end + 1])
    return excerpts


def restartWorkflowRun(token: str, runId: int) -> None:
    """Re-run every job of one workflow run."""
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/actions/runs/{runId}/rerun"
    )
    github.requestJson(url, token, method="POST", apiVersion="2022-11-28")


def confirmChecksPassed(runs: list[CheckRun]) -> bool:
    """Return whether every check completed and at least one actually succeeded.

    Two conditions rather than one. An empty list is False, because no checks
    means CI has not started or the workflow failed to parse. `skipped` alone is
    False for the same reason wearing a different hat: a draft pull request
    carries nothing but a skipped run, and a commit whose only check was skipped
    has not been tested. Tolerating skipped is required, since the skipped draft
    run shares a commit with the real one after promotion; treating it as
    sufficient would call an untested commit green.
    """
    if not runs:
        return False
    if not all(
        run.status == "completed" and run.conclusion in passingConclusions
        for run in runs
    ):
        return False
    return any(run.conclusion == "success" for run in runs)


def editPullRequest(
    token: str, number: int, title: str | None, body: str | None
) -> PullRequestSummary:
    """Revise an open pull request's title or body and return what landed.

    Sends only the fields given, because a PATCH carrying `body: null` would erase
    the description rather than leave it alone.
    """
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/pulls/{number}"
    )
    payload: dict[str, str] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    return summarizePullRequest(
        github.requestJson(url, token, method="PATCH", payload=payload)
    )


def markReadyForReview(token: str, nodeId: str) -> bool:
    """Take a pull request out of draft and return whether it is now ready.

    REST does not expose this transition at all, so it is the one operation here
    that has to go through GraphQL, which is why the node id is carried around.
    The mutation already returns `isDraft`, so reading it costs nothing and closes
    the path where a 200 with no errors reports a promotion that did not happen.
    """
    mutation = """
    mutation($pullRequestId: ID!) {
      markPullRequestReadyForReview(input: {pullRequestId: $pullRequestId}) {
        pullRequest { number isDraft }
      }
    }
    """
    data = github.requestGraphql(token, mutation, {"pullRequestId": nodeId})
    return not data["markPullRequestReadyForReview"]["pullRequest"]["isDraft"]


def mergePullRequest(
    token: str,
    number: int,
    method: str,
    subject: str,
) -> str:
    """Merge a pull request and return the resulting commit SHA.

    The subject is passed explicitly so the merge commit follows the house format
    rather than GitHub's generated default.
    """
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/pulls/{number}/merge"
    )
    payload = {"merge_method": method, "commit_title": subject}
    result = github.requestJson(url, token, method="PUT", payload=payload)
    if not result or not result.get("merged"):
        raise RuntimeError(
            f"GitHub did not merge {formatPullRequestRef(number)}: {result}"
        )
    return str(result["sha"])


def deleteBranch(token: str, branch: str) -> None:
    """Delete a merged branch from the remote."""
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/{github.repositoryName}/"
        f"git/refs/heads/{urllib.parse.quote(branch)}"
    )
    github.requestJson(url, token, method="DELETE")


def showPullRequest(summary: PullRequestSummary) -> None:
    """Print one pull request, color-coded and unbordered."""
    state = "draft" if summary.isDraft else summary.state
    tint = "yellow" if summary.isDraft else "green"
    console.print(
        f"[bold cyan]{formatPullRequestRef(summary.number)}[/] "
        f"[bold]{escape(summary.title)}[/]"
    )
    console.print(f"[dim]{escape(summary.url)}[/]")
    console.print(
        f"state: [{tint}]{state}[/]   "
        f"[magenta]{escape(summary.head)}[/] -> [cyan]{escape(summary.base)}[/]"
    )


def refuseBody(body: str) -> bool:
    """Print what is wrong with a body and report whether to stop.

    Kept apart from `findBodyFindings` so the checks stay logic and the terminal
    stays here. The sanctioned headings print with the refusal, because an
    author told which heading is wrong still has to be told which are right.
    """
    template = readTemplate()
    findings = findBodyFindings(body, template)
    if not findings:
        return False

    console.print("[red]The body does not match the pull request template.[/]")
    for finding in findings:
        console.print(f"  {escape(finding)}", highlight=False)
    console.print("\n[dim]The template's headings, in order:[/]")
    for heading in readHeadings(template):
        console.print(f"  {escape(heading)}", highlight=False)
    return True


def runCreate(arguments: argparse.Namespace) -> int:
    """Open a draft pull request for the current branch."""
    bodyPath = Path(arguments.bodyFile)
    if not bodyPath.is_file():
        console.print(f"[red]Body file not found:[/] {escape(str(bodyPath))}")
        return errorExitCode
    posted = github.readBodyFile(bodyPath)
    if posted is None:
        return 1
    body = posted.text
    github.reportTidying(posted)
    if refuseBody(body):
        return errorExitCode

    head = arguments.head or readCurrentBranch()
    if head == arguments.base:
        console.print(
            f"[red]Refusing to open a pull request from {head!r} into itself.[/]"
        )
        return errorExitCode

    if arguments.dryRun:
        console.print("[yellow]Dry run, no pull request was opened.[/]")
        console.print(f"title: [bold]{escape(arguments.title)}[/]")
        console.print(
            f"[magenta]{escape(head)}[/] -> [cyan]{escape(arguments.base)}[/]"
        )
        console.print("state: [yellow]draft[/]")
        console.print()
        console.print(body, markup=False, highlight=False)
        return 0

    token = github.resolveToken()

    existing = findOpenPullRequest(token, head, arguments.base)
    if existing is not None:
        console.print(
            f"[yellow]An open pull request already exists for {head!r} "
            f"into {arguments.base!r}.[/]"
        )
        showPullRequest(existing)
        return errorExitCode

    assertBranchIsPushed(token, head)
    summary = createDraftPullRequest(
        token, arguments.title, body, head, arguments.base
    )
    console.print("[green]Opened as draft[/]")
    showPullRequest(summary)
    return 0


def runFind(arguments: argparse.Namespace) -> int:
    """Print the open pull request for a branch, if there is one.

    Three outcomes, and each one says which it is in what it prints: a number, the
    `no-open-pull-request` marker, or an error. The exit codes carry the same three
    for anything scripting this, but the printed output is the contract, because
    the consumer is an agent reading stdout rather than a shell reading `$?`.
    """
    head = arguments.head or readCurrentBranch()
    summary = findOpenPullRequest(
        github.resolveToken(), head, arguments.base
    )

    if summary is None:
        # Said out loud, never signalled by silence. An empty stdout is
        # indistinguishable from a command that failed before it printed anything,
        # which is how "your token expired" came to be reported as "there is no
        # pull request". The exit code below carries the same fact for scripts;
        # neither decides the outcome on its own.
        if arguments.numberOnly:
            console.print(noOpenPullRequestMarker)
        else:
            console.print(
                f"[yellow]No open pull request for {head!r} "
                f"into {arguments.base!r}.[/]"
            )
        return notFoundExitCode

    if arguments.numberOnly:
        console.print(summary.number)
        return 0

    showPullRequest(summary)
    return 0


def runChecks(arguments: argparse.Namespace) -> int:
    """Print every check on a pull request's head commit and whether all passed.

    Three outcomes, the contract `find` already carries: passed, not passed, and
    the question could not be asked, which main() turns into errorExitCode. Only
    the first means a merge is safe, and a pull request with no checks at all is
    the second rather than the first.
    """
    token = github.resolveToken()
    summary = readPullRequest(token, arguments.number)
    runs = readCheckRuns(token, summary.headSha)
    commit = summary.headSha[:12]

    for run in runs:
        if run.status != "completed":
            mark = "[yellow]WAIT[/]"
        elif run.conclusion == "success":
            mark = "[green]PASS[/]"
        elif run.conclusion in passingConclusions:
            # Tolerated, but never a pass on its own. PASS here would contradict
            # the verdict printed underneath it.
            mark = "[yellow]SKIP[/]"
        else:
            mark = "[red]FAIL[/]"
        state = run.conclusion or run.status
        console.print(f"{mark} [bold]{escape(run.name)}[/]  {escape(state)}")

    if confirmChecksPassed(runs):
        console.print(f"[green]{checksPassedMarker}[/] on {commit}")
        return 0

    if not runs:
        console.print(
            f"[yellow]{checksNotPassedMarker}[/] on {commit}: nothing has "
            "reported yet. A queued run looks identical to no run here, because "
            "a check suite creates no check run until a job starts, so this is "
            "as likely to be a busy runner as a workflow that failed to parse."
        )
    else:
        console.print(f"[red]{checksNotPassedMarker}[/] on {commit}")
    return notFoundExitCode


def runExportAsSource(arguments: argparse.Namespace) -> int:
    """Emit one field of a pull request for editing, for a skill that will send it back.

    Separate from `find` because displaying and round-tripping are different actions
    with incompatible contracts: `find` may decorate freely, and this changes nothing
    but a backslash ending each line GitHub shows as a break. `edit` replaces the
    WHOLE body and GitHub has no conflict detection, so a revision drafted from
    memory silently discards whatever changed in between. This is what makes
    drafting one against the current text possible.
    """
    token = github.resolveToken()
    if arguments.body:
        body = readPullRequestBody(token, arguments.number)
        return 0 if github.writeBodyForEditing(body) else 1
    else:
        commands.printTitleAsRawString(readPullRequest(token, arguments.number).title)
    return 0


def runComment(arguments: argparse.Namespace) -> int:
    """Add one comment to a pull request."""
    return commands.postCommentFromFile(
        arguments, formatPullRequestRef(arguments.number)
    )


def runCommentList(arguments: argparse.Namespace) -> int:
    """Print every comment on a pull request, rendered, with each one's id.

    A command of its own here where `github.py` puts the same thing behind
    `show --comments`, because `pr.py` has no `show`: it reads by branch through
    `find` and by number through `export-as-source`, and neither is a renderer a
    flag could hang on. Adding one for symmetry would cost more than the asymmetry.
    """
    commands.showComments(
        github.readComments(github.resolveToken(), arguments.number)
    )
    return 0


def runEdit(arguments: argparse.Namespace) -> int:
    """Revise an open pull request's title or body.

    Exists because the body is a durable record rather than a first draft: a branch
    grows commits after the pull request opens, and a waiver has to be written into
    the body to count at all. Without this the only ways to correct one were to hand
    run the GitHub API, which this repository forbids, or to leave it wrong.
    """
    if arguments.title is None and arguments.bodyFile is None:
        console.print("[red]Nothing to change.[/] Pass --title, --body-file, or both.")
        return errorExitCode

    body: str | None = None
    if arguments.bodyFile is not None:
        bodyPath = Path(arguments.bodyFile)
        if not bodyPath.is_file():
            console.print(f"[red]Body file not found:[/] {escape(str(bodyPath))}")
            return errorExitCode
        posted = github.readBodyFile(bodyPath)
        if posted is None:
            return 1
        body = posted.text
        github.reportTidying(posted)
        if refuseBody(body):
            return errorExitCode

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        if arguments.title is not None:
            console.print(f"would set title: [bold]{escape(arguments.title)}[/]")
        if body is not None:
            console.print("would replace the body with:")
            console.print(body, markup=False, highlight=False)
        return 0

    token = github.resolveToken()
    summary = editPullRequest(token, arguments.number, arguments.title, body)

    # Read it back rather than trusting the write's echo. A body edit replaces the
    # WHOLE description and GitHub offers no conflict detection, so a revision
    # drafted against a copy fetched earlier discards anything changed in between
    # with no error and no marker. Verifying does not prevent that, it makes it
    # visible to whoever caused it, which is the difference between losing the
    # record and failing a command.
    mismatches: list[str] = []
    if body is not None and readPullRequestBody(token, arguments.number) != body:
        mismatches.append("body")
    if arguments.title is not None and summary.title != arguments.title:
        mismatches.append("title")

    if mismatches:
        console.print(
            f"[red]Edit did not land cleanly:[/] {', '.join(mismatches)} differs "
            "from what was sent."
        )
        console.print(summary.url)
        return errorExitCode

    console.print(
        f"[green]Edited[/] [bold cyan]{formatPullRequestRef(summary.number)}[/]"
    )
    console.print("[dim]verified against the pull request[/]")
    console.print(summary.url)
    return 0


def runReady(arguments: argparse.Namespace) -> int:
    """Take a draft pull request out of draft."""
    token = github.resolveToken()
    summary = readPullRequest(token, arguments.number)

    if not summary.isDraft:
        console.print(
            f"[yellow]{formatPullRequestRef(summary.number)} is already out of "
            "draft.[/]"
        )
        return 0

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        console.print(
            f"would mark [bold cyan]{formatPullRequestRef(summary.number)}[/] "
            "ready for review"
        )
        return 0

    if not markReadyForReview(token, summary.nodeId):
        console.print(
            f"[red]{formatPullRequestRef(summary.number)} is still a draft "
            "after the mutation reported success.[/]"
        )
        return errorExitCode

    console.print(
        f"[green]Ready for review[/] "
        f"[bold cyan]{formatPullRequestRef(summary.number)}[/]"
    )
    console.print(summary.url)
    return 0


def runLogs(arguments: argparse.Namespace) -> int:
    """Print the failed steps and the end of the log of each failed job."""
    token = github.resolveToken()
    summary = readPullRequest(token, arguments.number)
    commit = summary.headSha[:12]
    failed = readJobFailures(token, summary.headSha)

    if not failed:
        console.print(f"[yellow]No failed job[/] on {commit}.")
        return notFoundExitCode

    for job in failed:
        steps = ", ".join(job.failedSteps) or "none reported"
        console.print(
            f"[red]FAIL[/] [bold]{escape(job.workflow)} / {escape(job.name)}[/]  "
            f"{escape(job.conclusion)}, failed steps: {escape(steps)}"
        )
        lines = [dropLogTimestamp(line) for line in job.log.splitlines()]
        for excerpt in findErrorExcerpts(lines, arguments.context):
            console.print("[dim]…[/]")
            for line in excerpt:
                console.print(escape(line), highlight=False, soft_wrap=True)
        console.print()
    return 0


def runRerun(arguments: argparse.Namespace) -> int:
    """Restart every canceled or failed workflow run on a pull request's head commit."""
    token = github.resolveToken()
    summary = readPullRequest(token, arguments.number)
    commit = summary.headSha[:12]
    stale = [
        run for run in readWorkflowRuns(token, summary.headSha)
        if run.conclusion in rerunConclusions
    ]

    if not stale:
        console.print(
            f"[yellow]Nothing to re-run[/] on {commit}: no workflow run there was "
            "canceled or failed."
        )
        return 0

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        for run in stale:
            console.print(
                f"would restart [bold]{escape(run.name)}[/]  {run.conclusion}"
            )
        return 0

    for run in stale:
        try:
            restartWorkflowRun(token, run.runId)
        except github.GitHubHttpError as exc:
            raise RuntimeError(f"Could not restart {run.name}: {exc}") from exc
        console.print(f"[green]Restarted[/] [bold]{escape(run.name)}[/] on {commit}")
    return 0


def readTicketFromSubject(subject: str) -> int | None:
    """Return the ticket number a merge subject carries, in the house `[34]` form."""
    matched = re.match(r"^\[(\d+)\]", subject)
    return int(matched.group(1)) if matched else None


def waitForTicketClosed(token: str, number: int) -> bool:
    """Wait for GitHub to act on the closing keyword, and say whether it did.

    GitHub closes the ticket some seconds after the merge, so reopening at once
    races it and loses: the reopen lands first and the close undoes it. Watching
    for the close is what makes the correction reliable.
    """
    for attempt in range(ticketCloseAttempts):
        if github.readTicket(token, number).state == "closed":
            return True
        if attempt < ticketCloseAttempts - 1:
            time.sleep(ticketClosePauseSeconds)
    return False


def reopenTicketAfterMerge(token: str, subject: str, status: str) -> bool:
    """Reopen the ticket this merge closed, and restore the Status the board moved.

    The closing keyword stays in every body because it is the link, so a merge that
    does not complete its ticket corrects the close rather than avoiding it. A
    failure here is loud: the merge landed and the ticket now reads as delivered.
    """
    number = readTicketFromSubject(subject)
    if number is None:
        console.print(
            "[red]The merge landed, but its subject names no ticket to reopen.[/] "
            "Reopen it by hand, and set its Status back."
        )
        return False
    if not waitForTicketClosed(token, number):
        console.print(
            f"[yellow]{github.formatTicketRef(number)} is still open[/], so the merge "
            "closed nothing and there was nothing to reopen"
        )
        return True
    try:
        github.reopenTicket(token, number)
        github.moveTicketStatus(token, number, status)
    except Exception as exc:
        console.print(
            f"[red]The merge landed, but {github.formatTicketRef(number)} could not be "
            "reopened, so it reads as delivered.[/]"
        )
        console.print(f"  [dim]{escape(str(exc))}[/]")
        return False
    console.print(
        f"[green]{github.formatTicketRef(number)}[/] stays open at [cyan]{status}[/], "
        "because this merge does not complete it"
    )
    return True


def runMerge(arguments: argparse.Namespace) -> int:
    """Merge a pull request, deleting its branch only when asked and only if ours."""
    if arguments.method not in validMergeMethods:
        console.print(f"[red]Unknown merge method {arguments.method!r}.[/]")
        console.print(f"Choose one of: {', '.join(validMergeMethods)}")
        return errorExitCode

    token = github.resolveToken()
    summary = readPullRequest(token, arguments.number)

    if summary.isDraft:
        console.print(
            f"[red]{formatPullRequestRef(summary.number)} is still a draft.[/] "
            "Run /pr-review-code, which owns the promotion out of draft."
        )
        return errorExitCode

    if not confirmChecksPassed(readCheckRuns(token, summary.headSha)):
        console.print(
            f"[red]CI has not passed on {formatPullRequestRef(summary.number)}.[/] "
            f"Run `.venv/bin/python3 -m tools.workflow.pr checks {summary.number}` "
            "for which."
        )
        return errorExitCode

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was merged.[/]")
        showPullRequest(summary)
        console.print(f"method:  [cyan]{arguments.method}[/]")
        console.print(f"subject: [bold]{escape(arguments.subject)}[/]")
        console.print(
            "branch:  "
            + (
                "[dim]kept[/] (`--delete-branch` deletes it)"
                if not arguments.removeBranch
                else f"would delete {summary.head}"
                if checkHeadIsOurs(summary)
                else f"deletes nothing: {escape(formatForkBranch(summary))}"
            )
        )
        number = readTicketFromSubject(arguments.subject)
        reference = github.formatTicketRef(number) if number else "the ticket"
        console.print(
            "ticket:  "
            + (
                f"would close {reference}, then reopen it at "
                f"[cyan]{arguments.ticketStatus}[/]"
                if arguments.ticketStaysOpen
                else f"would close {reference}, which the keyword does"
            )
        )
        return 0

    # `except Exception`, not `except RuntimeError`, and deliberately so. urllib does
    # not wrap every failure: a read-phase TimeoutError is an OSError it lets through
    # untouched, and a proxy's HTML error page makes json.loads raise ValueError.
    # Neither is a RuntimeError, so both escaped main()'s handler to a bare traceback
    # and exit 1, which is notFoundExitCode. A merge that may well have landed then
    # reported as "there is no pull request", and the warning below never printed.
    # The merge is the irreversible step, so an unknown outcome here must say so.
    try:
        sha = mergePullRequest(
            token, arguments.number, arguments.method, arguments.subject
        )
    except Exception as exc:
        console.print(
            f"[red]The merge request for {formatPullRequestRef(summary.number)} "
            "did not complete "
            "cleanly, and whether it landed is unknown.[/]"
        )
        console.print(f"  [dim]{escape(str(exc))}[/]")
        console.print(
            "[bold]Check the pull request on GitHub before doing anything else.[/] "
            "Do not re-run merge until you know: if it did land, a second attempt "
            "returns an opaque 405 that reads as though nothing ever worked."
        )
        return partialSuccessExitCode

    console.print(
        f"[green]Merged[/] [bold cyan]{formatPullRequestRef(summary.number)}[/] "
        f"by [cyan]{arguments.method}[/] as [dim]{sha[:12]}[/]"
    )

    if arguments.ticketStaysOpen and not reopenTicketAfterMerge(
        token, arguments.subject, arguments.ticketStatus
    ):
        return partialSuccessExitCode

    if not arguments.removeBranch:
        console.print(f"[dim]Kept branch[/] {escape(summary.head)}")
        return 0

    if not checkHeadIsOurs(summary):
        console.print(
            f"[green]Deleted nothing:[/] {escape(formatForkBranch(summary))}"
        )
        return 0

    # The merge is irreversible and the delete is a second call, so a failure here
    # must never read as a failure of the whole command. Left to propagate, it
    # printed a red error and returned non-zero *after* the merge had landed, and
    # the obvious response to that, re-running `merge`, sails past the draft guard
    # (the pull request is closed now, so isDraft is false), gets an opaque
    # "405 not mergeable" from GitHub, and reads as though nothing ever worked.
    # One handler on purpose. GitHubHttpError is a RuntimeError subclass, so catching it
    # separately and re-raising would escape this function entirely rather than fall
    # through to the sibling clause, which would regress the whole point of this block.
    try:
        deleteBranch(token, summary.head)
    except RuntimeError as exc:
        # 404 or 422 means the ref is already gone, which is the NORMAL outcome when the
        # repository has "automatically delete head branches" enabled. Reporting that as
        # a failed cleanup printed a bold "Do not re-run merge", exited non-zero, and
        # sent the user to run a `git push --delete` that also fails. An alarm that
        # fires on success is an alarm that stops being read.
        alreadyGone = getattr(exc, "statusCode", None) in (404, 422)
        if alreadyGone:
            console.print(
                f"[green]Branch[/] {escape(summary.head)} "
                "[green]was already deleted.[/]"
            )
            return 0
        console.print("[yellow]The merge succeeded. Only the branch delete failed.[/]")
        console.print(f"  [dim]{escape(str(exc))}[/]")
        console.print(
            f"[bold]Do not re-run merge[/], "
            f"{formatPullRequestRef(summary.number)} is already merged. "
            f"Finish by hand:\n  git push origin --delete {summary.head}"
        )
        return partialSuccessExitCode
    console.print(f"[green]Deleted branch[/] {escape(summary.head)}")
    return 0


def buildParser() -> argparse.ArgumentParser:
    """Assemble the command line, one subcommand per cmd-prefixed handler."""
    parser = argparse.ArgumentParser(
        prog="pr.py",
        description="Open, inspect, promote and merge pybers pull requests over "
        "the GitHub API.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    createParser = subparsers.add_parser("create", help="open a draft pull request")
    createParser.add_argument(
        "--title", required=True, help="pull request title, verbatim"
    )
    createParser.add_argument(
        "--body-file", dest="bodyFile", required=True, help="drafted body"
    )
    createParser.add_argument(
        "--head", default=None, help="source branch (default: the checked-out branch)"
    )
    createParser.add_argument(
        "--base",
        default=defaultBaseBranch,
        help=f"target branch (default: {defaultBaseBranch})",
    )
    createParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    createParser.set_defaults(handler=runCreate)

    findParser = subparsers.add_parser(
        "find", help="print the open pull request for a branch"
    )
    findParser.add_argument(
        "--head", default=None, help="source branch (default: the checked-out branch)"
    )
    findParser.add_argument(
        "--base",
        default=defaultBaseBranch,
        help=f"target branch to match on (default: {defaultBaseBranch})",
    )
    findParser.add_argument(
        "--number-only",
        dest="numberOnly",
        action="store_true",
        help="print just the number, for a skill that only needs to resolve it",
    )
    findParser.set_defaults(handler=runFind)

    exportParser = subparsers.add_parser(
        "export-as-source",
        help="The SOURCE, nothing rendered, each line GitHub shows as a break ending "
        "in a backslash: the form to edit and send back to `edit`. Contrast "
        "`find`, which renders.",
    )
    exportParser.add_argument("number", type=parsePullRequestNumber)
    # Mutually exclusive and required, because these never compose: each is a whole
    # output, not a modifier on a shared one. Same shape as github.py's.
    fieldGroup = exportParser.add_mutually_exclusive_group(required=True)
    fieldGroup.add_argument(
        "--body", action="store_true",
        help="the body, as a file means it, nothing rendered",
    )
    fieldGroup.add_argument(
        "--title", action="store_true", help="the title, with nothing added"
    )
    exportParser.set_defaults(handler=runExportAsSource)

    editParser = subparsers.add_parser(
        "edit", help="revise a pull request's title or body"
    )
    editParser.add_argument("number", type=parsePullRequestNumber)
    editParser.add_argument("--title", help="replacement title, verbatim")
    editParser.add_argument(
        "--body-file", dest="bodyFile", help="file holding the replacement body"
    )
    editParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    editParser.set_defaults(handler=runEdit)

    commentParser = subparsers.add_parser(
        "comment", help="add a comment to a pull request"
    )
    commentParser.add_argument("number", type=parsePullRequestNumber)
    commentParser.add_argument(
        "--body-file", dest="bodyFile", required=True,
        help="drafted comment body, a file so lists and code fences survive",
    )
    commentParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    commentParser.set_defaults(handler=runComment)

    commentListParser = subparsers.add_parser(
        "comment-list",
        help="RENDERED for reading: every comment on a pull request, with its id.",
    )
    commentListParser.add_argument("number", type=parsePullRequestNumber)
    commentListParser.set_defaults(handler=runCommentList)

    commentExportParser = subparsers.add_parser(
        "comment-export",
        help="The SOURCE of one comment, as `export-as-source` gives a body: the "
        "form to revise and send back to `comment-edit`.",
    )
    commentExportParser.add_argument("commentId", type=int)
    commentExportParser.set_defaults(handler=commands.runCommentExport)

    commentEditParser = subparsers.add_parser(
        "comment-edit", help="replace a comment's body in place"
    )
    commentEditParser.add_argument("commentId", type=int)
    commentEditParser.add_argument(
        "--body-file", dest="bodyFile", required=True, help="revised comment body"
    )
    commentEditParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    commentEditParser.set_defaults(handler=commands.runCommentEdit)

    commentDeleteParser = subparsers.add_parser(
        "comment-delete", help="delete a comment (permanent, no GitHub undo)"
    )
    commentDeleteParser.add_argument("commentId", type=int)
    commentDeleteParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    commentDeleteParser.set_defaults(handler=commands.runCommentDelete)

    checksParser = subparsers.add_parser(
        "checks", help="report whether every check on a pull request has passed"
    )
    checksParser.add_argument("number", type=parsePullRequestNumber)
    checksParser.set_defaults(handler=runChecks)

    rerunParser = subparsers.add_parser(
        "rerun", help="restart a pull request's canceled or failed workflow runs"
    )
    rerunParser.add_argument("number", type=parsePullRequestNumber)
    rerunParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    rerunParser.set_defaults(handler=runRerun)

    logsParser = subparsers.add_parser(
        "logs", help="print each error the failed jobs on a pull request logged"
    )
    logsParser.add_argument("number", type=parsePullRequestNumber)
    logsParser.add_argument(
        "--context", type=int, default=defaultLogContext,
        help=f"lines to print before each error (default {defaultLogContext})",
    )
    logsParser.set_defaults(handler=runLogs)

    readyParser = subparsers.add_parser("ready", help="take a draft out of draft")
    readyParser.add_argument("number", type=parsePullRequestNumber)
    readyParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    readyParser.set_defaults(handler=runReady)

    mergeParser = subparsers.add_parser("merge", help="merge a pull request")
    mergeParser.add_argument("number", type=parsePullRequestNumber)
    mergeParser.add_argument(
        "--subject",
        required=True,
        help="merge commit subject in the house format, rather than GitHub's default",
    )
    mergeParser.add_argument(
        "--method",
        default="merge",
        choices=validMergeMethods,
        help="merge keeps every commit (the default); squash collapses them to one",
    )
    mergeParser.add_argument(
        "--delete-branch",
        dest="removeBranch",
        action="store_true",
        help="delete the source branch once merged, when it lives in this repository",
    )
    mergeParser.add_argument(
        "--ticket-stays-open",
        dest="ticketStaysOpen",
        action="store_true",
        help="this merge does not complete the ticket, so reopen it and restore "
             "the Status it held",
    )
    mergeParser.add_argument(
        "--ticket-status",
        dest="ticketStatus",
        default=inProgressStatus,
        help="the Status to restore with --ticket-stays-open, "
             f"default {inProgressStatus}",
    )
    mergeParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    mergeParser.set_defaults(handler=runMerge)

    return parser


def main() -> int:
    """Parse the command line and dispatch, reporting failures without a traceback.

    Returns ``errorExitCode`` rather than 1, so that "the question could not be
    asked" stays distinguishable from a command's own considered negative answer.
    """
    arguments = buildParser().parse_args()
    try:
        return int(arguments.handler(arguments))
    except Exception as exc:
        # Broader than RuntimeError deliberately. urllib lets a read-phase TimeoutError
        # through as a bare OSError, and a proxy error page makes json.loads raise
        # ValueError. Anything escaping to Python's own handler would exit 1, and 1 is
        # notFoundExitCode, so an unhandled crash would announce itself as "there is no
        # pull request". No path may reach exit 1 except a considered negative answer.
        console.print(f"[red]{escape(str(exc))}[/]")
        return errorExitCode


if __name__ == "__main__":
    sys.exit(main())
