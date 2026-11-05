#!/usr/bin/env python3
"""\
The pull request client: reading, writing and merging pull requests, their checks and
runs, and a body checked against the template.

Shared by `pr.py` and the readiness check.

UPDATES
2026-10-23  `closePullRequest`, closing one without merging, for PYB-156.
2026-10-14  A summary carries its author, and `readApprovers` and
            `confirmMergeApproved` gate a merge on approval, for PYB-156.
2026-10-14  `findTicketPullRequest`, a ticket's open pull request by its branch,
            for PYB-211.
2026-10-14  The pull request client moved here from `pr.py`, which keeps its
            commands, for PYB-204.
2026-10-14  Moved here from `pr.py`, so the readiness code imports a library rather
            than a command, for PYB-204.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/14"

import argparse
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from typing import IO, Any

from tools.workflow.lib import github
from tools.workflow.lib.shared import readTicketNumber, repositoryRoot

# The base a pull request targets by default. Library and app repositories cut from
# develop; a web-facing repository whose deploy tracks a different branch overrides
# this per invocation with --base.
defaultBaseBranch: str = "develop"

# The pull request template, and the authority on what a body may look like.
# Read here because nothing else in this repository reads it: `/pr-draft` tells
# an author to fill it, and GitHub applies it only to a body typed in the web
# interface, so a body posted through the API carries what it was given and
# nothing more.
templatePath: Path = repositoryRoot / ".github" / "pull_request_template.md"


# A body may run to twice the template's own length, comments excluded from both.
maximumBodyLengthMultiple: int = 2


def formatPullRequestRef(number: int) -> str:
    """Return a pull request reference in the house form, both parts always."""
    return f"PR #{number}"


def readTemplate() -> str:
    """Return the pull request template, refusing when it is absent.

    Missing means the checks below have nothing to compare a body against, and
    passing one because the authority went missing is the fallback cascade this
    repository refuses everywhere else.
    """
    if not templatePath.is_file():
        raise RuntimeError(
            f"No pull request template at {templatePath}. Every body is checked "
            "against it, so there is nothing left to check against."
        )
    return templatePath.read_text(encoding="utf-8")


def readHeadings(text: str) -> list[str]:
    """Return every `##` heading, in order."""
    return [line.strip() for line in text.splitlines() if line.startswith("## ")]


def readBoldRuns(text: str) -> list[str]:
    """Return every line that is nothing but bold text, which reads as a heading.

    Markdown makes `**Like this**` alone on a line look exactly like a section
    heading while staying invisible to a `## ` scan, which is how a body grows a
    section the template never had. The template uses bold inline under Breaking
    Changes, so only a line that is ENTIRELY bold counts.
    """
    return [
        line.strip()
        for line in text.splitlines()
        if re.fullmatch(r"\*\*[^*]+\*\*", line.strip())
    ]


def readCheckboxLabels(text: str) -> list[str]:
    """Return every checkbox's label, with its ticked state discarded.

    The state is what an author is meant to change and the label is what the
    template owns, so comparing labels catches a reworded line without
    complaining about a box legitimately ticked. `NA ` counts as a state,
    because the template says to mark an inapplicable item that way rather than
    delete it, which keeps its label under comparison.
    """
    labels: list[str] = []
    for line in text.splitlines():
        matched = re.match(r"\s*- (?:\[[ xX]\]\s*|NA\s+)(.+?)\s*$", line)
        if matched:
            labels.append(matched.group(1))
    return labels


def countProseWords(text: str) -> int:
    """Return the word count with HTML comments removed.

    The template is largely instructions inside comments, so counting those
    would raise the ceiling by the size of guidance no body ever publishes.
    """
    return len(re.findall(r"\S+", re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)))


def findBodyFindings(body: str, template: str) -> list[str]:
    """Return every way a body departs from its template.

    Pure by design: two strings in and complaints out, so the checks are
    testable without a token, a network or a repository. Headings are compared
    in BOTH directions, because the template asks for `None` under a heading a
    body does not need rather than for the heading to go. Checkboxes are
    compared in ONE, because it asks for the inapplicable ones to be deleted.
    """
    findings: list[str] = []
    templateHeadings = readHeadings(template)
    headings = readHeadings(body)

    invented = [heading for heading in headings if heading not in templateHeadings]
    if invented:
        findings.append(
            f"{len(invented)} heading(s) the template does not carry: "
            + ", ".join(invented)
        )
    missing = [heading for heading in templateHeadings if heading not in headings]
    if missing:
        findings.append(
            f"{len(missing)} template heading(s) missing: " + ", ".join(missing)
        )
    if not invented and not missing and headings != templateHeadings:
        findings.append(
            "headings are out of the template's order, expected "
            f"{templateHeadings} and got {headings}"
        )

    templateBold = set(readBoldRuns(template))
    inventedBold = [run for run in readBoldRuns(body) if run not in templateBold]
    if inventedBold:
        findings.append(
            f"{len(inventedBold)} bold line(s) reading as a heading: "
            + ", ".join(inventedBold)
        )

    templateLabels = set(readCheckboxLabels(template))
    reworded = [
        label for label in readCheckboxLabels(body) if label not in templateLabels
    ]
    if reworded:
        findings.append(
            f"this body carries {len(reworded)} checkbox the template does not: "
            + ", ".join(reworded)
        )

    templateWords = countProseWords(template)
    words = countProseWords(body)
    ceiling = templateWords * maximumBodyLengthMultiple
    if words > ceiling:
        findings.append(
            f"body is {words} words against a ceiling of {ceiling}, which is "
            f"{maximumBodyLengthMultiple} times the template's {templateWords}"
        )
    return findings


# How long to watch for GitHub to act on the closing keyword, which it does
# seconds after the merge rather than with it.
ticketCloseAttempts: int = 10


ticketClosePauseSeconds: float = 3.0


errorLogMarker: str = "##[error]"


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
    author: str


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
        author=(payload.get("user") or {}).get("login", ""),
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


def findTicketPullRequest(token: str, number: int) -> PullRequestSummary | None:
    """Return the open pull request whose branch carries this ticket's number."""
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/pulls?state=open&per_page=100"
    )
    for payload in github.requestJson(url, token) or []:
        if readTicketNumber(payload.get("head", {}).get("ref", "")) == str(number):
            return summarizePullRequest(payload)
    return None


def readApprovers(token: str, number: int) -> list[str]:
    """Return who approved a pull request in their latest decisive review."""
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/pulls/{number}/reviews?per_page=100"
    )
    latest: dict[str, str] = {}
    for review in github.requestJson(url, token) or []:
        # A comment leaves a reviewer's verdict standing; a dismissal withdraws it.
        if review.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[(review.get("user") or {}).get("login", "")] = review["state"]
    return sorted(login for login, state in latest.items() if state == "APPROVED")


def confirmMergeApproved(
    approvers: list[str], author: str, merger: str, mergerIsAdmin: bool
) -> bool:
    """Return whether a merge may proceed: approved, or the administrator's own."""
    return bool(approvers) or (mergerIsAdmin and author != "" and author == merger)


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
            return str(response.read().decode(errors="replace"))
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
            return str(response.read().decode(errors="replace"))
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


def closePullRequest(token: str, number: int) -> PullRequestSummary:
    """Close an open pull request without merging it, and return what landed."""
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/"
        f"{github.repositoryName}/pulls/{number}"
    )
    return summarizePullRequest(
        github.requestJson(url, token, method="PATCH", payload={"state": "closed"})
    )


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
