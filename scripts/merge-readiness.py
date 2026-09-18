#!/usr/bin/env python3
"""\
pybers merge-readiness report

Two commands for the two halves of the report. `collect` runs on the pull
request's branch where that code is allowed to run, and writes the facts it
gathers to a file. `report` runs this repository's own code, reads that file as
data, adds the checks only the GitHub API and the network can answer, and posts
one comment carrying one verdict.

Keeping them apart is what makes write access safe in the reporting half: it
executes nothing the branch carries. See .github/workflows/ for the two workflows
that call them.

Usage:
    python3 scripts/merge-readiness.py collect --pull-request 42 \
        --preflight-log preflight.log --output results.json
    python3 scripts/merge-readiness.py report --results results.json
    python3 scripts/merge-readiness.py report --results results.json --dry-run
    python3 scripts/merge-readiness.py dispatch --run-id 123 --ref my-branch

Requires rich, and a GitHub token for `report`, resolved by scripts/ticket.py.

UPDATES
2026-09-17  Written for PYB-76.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/17"
__usage__ = "python3 scripts/merge-readiness.py <command> [options]"

import argparse
import json
import os
import re
import subprocess
import sys
import time
import tomllib
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import merge_readiness_lib as checks
import merge_readiness_presenter as presenter
import pr
import ticket
from rich.console import Console

try:
    from rich_argparse import RichHelpFormatter
except ImportError:  # rich_argparse is optional, per scripts/README.md
    RichHelpFormatter = argparse.HelpFormatter  # type: ignore[assignment,misc]

console: Console = Console()

repositoryRoot: Path = Path(__file__).resolve().parent.parent
projectPath: Path = repositoryRoot / "pyproject.toml"
reportWorkflowFile: str = "merge-readiness.yml"
checkRunName: str = "merge readiness"
preflightWorkflowFile: str = "preflight.yml"
preflightCheckName: str = "preflight"
preflightAttempts: int = 40
preflightPauseSeconds: float = 15.0
failedExitCode: int = 1
errorExitCode: int = 2


def readDeclaredPackages() -> list[str]:
    """Return every package this project declares, runtime and development alike."""
    with projectPath.open("rb") as handle:
        project = tomllib.load(handle)["project"]
    declared = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        declared += extra
    return [
        re.split(r"[<>=!~\[; ]", entry, maxsplit=1)[0] for entry in declared if entry
    ]


def readResolvedPackages() -> list[list[str]]:
    """Return what a fresh install resolved, since this project pins nothing."""
    listed = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=json"],
        capture_output=True, text=True, check=False,
    )
    if listed.returncode != 0:
        return []
    return [[entry["name"], entry["version"]] for entry in json.loads(listed.stdout)]


def waitForPreflight(token: str, sha: str) -> str:
    """Return the preflight check's conclusion for a commit, waiting for it to finish.

    Read from GitHub rather than handed over, because the preflight is its own
    workflow and its own check. Waiting is what AC 3 asks for, and a preflight
    that never finishes leaves this reporting a wait rather than a verdict.
    """
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/{ticket.repositoryName}"
        f"/commits/{sha}/check-runs"
    )
    for attempt in range(preflightAttempts):
        runs = ticket.requestJson(url, token, apiVersion="2022-11-28")["check_runs"]
        # A commit carries its skipped draft run beside the real one, and taking
        # that as the answer reports a preflight that never ran while it is running.
        decided = [
            run for run in runs
            if run["name"] == preflightCheckName
            and run["status"] == "completed"
            and run["conclusion"] not in (None, "skipped")
        ]
        if decided:
            newest = max(decided, key=lambda run: str(run["started_at"]))
            return str(newest["conclusion"])
        if attempt < preflightAttempts - 1:
            time.sleep(preflightPauseSeconds)
    return ""


def readPullRequestFacts(token: str, number: int) -> dict[str, Any]:
    """Return the title, body, base and head a pull request carries."""
    url = f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/{ticket.repositoryName}"
    payload = ticket.requestJson(f"{url}/pulls/{number}", token)
    return {
        "title": payload.get("title", ""),
        "body": payload.get("body") or "",
        "base": payload.get("base", {}).get("ref", pr.defaultBaseBranch),
        "head": payload.get("head", {}).get("sha", ""),
        "draft": bool(payload.get("draft")),
    }


def readCommitsBehind(token: str, base: str, head: str) -> int:
    """Return how many commits the base holds that this head does not."""
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/{ticket.repositoryName}"
        f"/compare/{base}...{head}"
    )
    return int(ticket.requestJson(url, token).get("behind_by", 0))


def findReportComment(token: str, number: int) -> int | None:
    """Return the identifier of this report's own comment, found by its marker."""
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/{ticket.repositoryName}"
        f"/issues/{number}/comments?per_page=100"
    )
    for comment in ticket.requestJson(url, token):
        if presenter.commentMarker in (comment.get("body") or ""):
            return int(comment["id"])
    return None


def postReportComment(token: str, number: int, body: str) -> str:
    """Post the report, or replace the one an earlier run left, and say which."""
    root = f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/{ticket.repositoryName}"
    existing = findReportComment(token, number)
    if existing is None:
        ticket.requestJson(
            f"{root}/issues/{number}/comments", token, method="POST",
            payload={"body": body},
        )
        return "posted"
    ticket.requestJson(
        f"{root}/issues/comments/{existing}", token, method="PATCH",
        payload={"body": body},
    )
    return "replaced"


def checkPullRequest(facts: checks.BranchFacts, token: str) -> list[checks.CheckResult]:
    """Run every check, in the order the comment lists them."""
    pullRequest = readPullRequestFacts(token, facts.pullRequest)
    behind = readCommitsBehind(token, pullRequest["base"], facts.headSha)
    # The branch's template when it carried one, since the body was written against it.
    template = facts.template or pr.readTemplate()
    findings = pr.findBodyFindings(pullRequest["body"], template)
    return [
        checks.checkPreflight(waitForPreflight(token, facts.headSha)),
        checks.checkTemplate(findings),
        checks.checkChecklist(pullRequest["body"]),
        checks.checkChangelog(facts, pullRequest["body"]),
        checks.checkTicketAgreement(facts, pullRequest["title"]),
        checks.checkBranchCurrent(behind, pullRequest["base"]),
        checks.checkDependencies(facts),
        checks.checkGoldenConfirmations(facts),
    ]


def runCollect(arguments: argparse.Namespace) -> int:
    """Gather the branch's own facts into the file the reporting half reads."""
    facts = checks.collectBranchFacts(
        arguments.base, arguments.pull_request,
        branch=arguments.branch or "", headSha=arguments.head_sha or "",
    )
    facts.declaredPackages = readDeclaredPackages()
    facts.resolvedPackages = readResolvedPackages()
    Path(arguments.output).write_text(json.dumps(facts.toDictionary(), indent=1))
    console.print(f"[green]collected[/] this branch's facts into {arguments.output}")
    return 0


def runCheck(arguments: argparse.Namespace) -> int:
    """Check the pull request, write the comment for the posting half, and fail on red.

    This runs in the job Actions shows as its own check, so a red verdict fails
    that job and GitHub reports it like any other check. Nothing here writes to
    the pull request, which is why the job holds no write access.
    """
    stored = json.loads(Path(arguments.results).read_text())
    facts = checks.BranchFacts.fromDictionary(stored)
    token = ticket.resolveToken()
    results = checkPullRequest(facts, token)
    verdict = checks.readVerdict(results)
    body = presenter.renderComment(results, facts, datetime.now(UTC))
    Path(arguments.comment).write_text(body)
    presenter.reportResults(console, results, verdict)
    writeWorkflowOutput(results, body)
    console.print(f"wrote the report to {arguments.comment}")
    return failedExitCode if verdict == checks.failed else 0


def writeWorkflowOutput(results: list[checks.CheckResult], body: str) -> None:
    """Give GitHub the annotations and the summary page a run shows, when inside one."""
    for command in presenter.renderAnnotations(results):
        print(command)
    summaryPath = os.environ.get("GITHUB_STEP_SUMMARY")
    if summaryPath:
        # The same report the comment carries, so the two never disagree.
        Path(summaryPath).write_text(body)


def runReport(arguments: argparse.Namespace) -> int:
    """Post the comment the readiness check rendered, or replace the one already there.

    This half decides nothing and checks nothing: the readiness check is where a
    verdict comes from, and GitHub reports that check itself. Posting is the only
    write this repository's automation makes, and the token it holds allows no
    more than that.
    """
    stored = json.loads(Path(arguments.results).read_text())
    facts = checks.BranchFacts.fromDictionary(stored)
    body = Path(arguments.comment).read_text()
    if not facts.pullRequest:
        console.print("[red]the collected facts name no pull request[/]")
        return errorExitCode
    if arguments.dry_run:
        console.print(body, markup=False, highlight=False)
        return 0
    token = ticket.resolveToken()
    console.print(f"{postReportComment(token, facts.pullRequest, body)} the report on "
                  f"{pr.formatPullRequestRef(facts.pullRequest)}")
    return 0


def findLatestPreflightRun(token: str, ref: str) -> int:
    """Return the newest finished preflight run on a branch, which carries its facts."""
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/{ticket.repositoryName}"
        f"/actions/workflows/{preflightWorkflowFile}/runs"
        f"?branch={urllib.parse.quote(ref)}&status=completed&per_page=1"
    )
    runs = ticket.requestJson(url, token).get("workflow_runs", [])
    if not runs:
        raise RuntimeError(f"no finished preflight run on {ref}")
    return int(runs[0]["id"])


def runDispatch(arguments: argparse.Namespace) -> int:
    """Ask GitHub to run the reporting workflow from a branch, on one preflight run.

    The only way to exercise that workflow before it reaches the default branch,
    since `workflow_run` fires from the default branch's copy alone.
    """
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/{ticket.repositoryName}"
        f"/actions/workflows/{reportWorkflowFile}/dispatches"
    )
    token = ticket.resolveToken()
    runId = arguments.run_id or findLatestPreflightRun(token, arguments.ref)
    ticket.requestJson(
        url, token, method="POST",
        payload={"ref": arguments.ref, "inputs": {"run-id": str(runId)}},
    )
    console.print(f"[green]dispatched[/] {reportWorkflowFile} on {arguments.ref} "
                  f"for preflight run {runId}")
    return 0


def buildParser() -> argparse.ArgumentParser:
    """Describe the command line, one subcommand per half of the report."""
    parser = argparse.ArgumentParser(
        prog="merge-readiness.py",
        description="Report merge readiness as one comment on a pull request.",
        formatter_class=RichHelpFormatter,
    )
    commands = parser.add_subparsers(required=True)

    collect = commands.add_parser(
        "collect", help="gather the branch's facts for the reporting half",
        formatter_class=RichHelpFormatter,
    )
    collect.add_argument("--pull-request", type=int, required=True, help="its number")
    collect.add_argument("--base", default=pr.defaultBaseBranch, help="the base branch")
    collect.add_argument("--branch", help="its head branch, which a merge commit hides")
    collect.add_argument("--head-sha", help="its head commit, not the merge commit")
    collect.add_argument(
        "--output", default="merge-readiness.json", help="where to write"
    )
    collect.set_defaults(handler=runCollect)

    report = commands.add_parser(
        "report", help="check the pull request and post one comment",
        formatter_class=RichHelpFormatter,
    )
    report.add_argument("--results", required=True, help="the collected facts")
    report.add_argument("--comment", required=True, help="the rendered comment")
    report.add_argument("--dry-run", action="store_true", help="print, post nothing")
    report.set_defaults(handler=runReport)

    check = commands.add_parser(
        "check", help="check the pull request and write the comment, posting nothing",
        formatter_class=RichHelpFormatter,
    )
    check.add_argument("--results", required=True, help="the collected facts")
    check.add_argument("--comment", default="merge-readiness.md", help="where to write")
    check.set_defaults(handler=runCheck)

    dispatch = commands.add_parser(
        "dispatch", help="run the reporting workflow by hand, from a branch",
        formatter_class=RichHelpFormatter,
    )
    dispatch.add_argument("--run-id", type=int, help="a preflight run, or the newest")
    dispatch.add_argument("--ref", required=True, help="the branch to run it from")
    dispatch.set_defaults(handler=runDispatch)
    return parser


def main() -> int:
    """Parse the command line and dispatch, reporting failures without a traceback."""
    arguments = buildParser().parse_args()
    try:
        return int(arguments.handler(arguments))
    except Exception as exc:  # noqa: BLE001 - a report never shows a traceback
        console.print(f"[red]{exc}[/]")
        return errorExitCode


if __name__ == "__main__":
    sys.exit(main())
