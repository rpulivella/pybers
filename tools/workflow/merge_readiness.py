#!/usr/bin/env python3
"""\
pybers merge-readiness report

`collect` and `check` run in the pull request's own job, with no write access:
one gathers the branch's facts, the other runs the checks and stores their results
beside the facts. `report` runs in a separate workflow on the default branch's
code, holding the one write this automation makes. It reads the stored file as
data only, renders the comment itself, and posts it to the pull request whose head
is the commit that run checked.

A branch can make its own stored results say anything, so the report is only as
honest as the branch. What a branch cannot do is run code in the posting half or
aim a comment at another pull request. See .github/workflows/.

Usage:
    .venv/bin/python3 -m tools.workflow.merge_readiness collect --pull-request 42 \
        --output results.json
    .venv/bin/python3 -m tools.workflow.merge_readiness check --results results.json
    .venv/bin/python3 -m tools.workflow.merge_readiness report --results results.json \
        --head-sha abc123

Runs on the repository's venv, though the posting workflow installs rich alone, and
needs a GitHub token for `check` and `report`, resolved by tools/workflow/lib/github.py.

UPDATES
2026-10-14  Moved here from `scripts/merge-readiness.py`, and run as a module,
            for PYB-204.
2026-10-13  The posting half moved to `lib/readiness_posting.py`, so its tests
            import a library rather than this command, for PYB-204.
2026-10-06  Removed `dispatch`, which sent an event no workflow listens for, for
            PYB-155.
2026-10-03  The posting half renders the comment from stored results, aims it at
            the pull request its run checked, and replaces only its own earlier
            comment, for PYB-151.
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
__usage__ = ".venv/bin/python3 -m tools.workflow.merge_readiness <command> [options]"

import argparse
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from tools.workflow.lib import github
from tools.workflow.lib import readiness as checks
from tools.workflow.lib import readiness_posting as posting
from tools.workflow.lib import readiness_presenter as presenter
from tools.workflow.lib.pull_request import (
    defaultBaseBranch,
    findBodyFindings,
    formatPullRequestRef,
    readTemplate,
)
from tools.workflow.lib.shared import RichHelpFormatter, repositoryRoot

console: Console = Console()

projectPath: Path = repositoryRoot / "pyproject.toml"
checkRunName: str = "merge readiness"
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
        f"{github.restRoot}/repos/{github.repositoryOwner}/{github.repositoryName}"
        f"/commits/{sha}/check-runs"
    )
    for attempt in range(preflightAttempts):
        runs = github.requestJson(url, token, apiVersion="2022-11-28")["check_runs"]
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


def readCommitsBehind(token: str, base: str, head: str) -> int:
    """Return how many commits the base holds that this head does not."""
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/{github.repositoryName}"
        f"/compare/{base}...{head}"
    )
    return int(github.requestJson(url, token).get("behind_by", 0))


def checkPullRequest(facts: checks.BranchFacts, token: str) -> list[checks.CheckResult]:
    """Run every check, in the order the comment lists them."""
    pullRequest = posting.readPullRequestFacts(token, facts.pullRequest)
    behind = readCommitsBehind(token, pullRequest["base"], facts.headSha)
    # The branch's template when it carried one, since the body was written against it.
    template = facts.template or readTemplate()
    findings = findBodyFindings(pullRequest["body"], template)
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
    token = github.resolveToken()
    results = checkPullRequest(facts, token)
    verdict = checks.readVerdict(results)
    moment = datetime.now(UTC)
    body = presenter.renderComment(results, facts, moment)
    Path(arguments.comment).write_text(body)
    # The posting half renders its own comment from these, never from the body above.
    stored["results"] = checks.encodeResults(results)
    stored["checkedAt"] = moment.isoformat()
    Path(arguments.results).write_text(json.dumps(stored, indent=1))
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
    """Post the comment for a checked pull request, or replace the one already there.

    This half decides nothing and checks nothing: the readiness check is where a
    verdict comes from, and GitHub reports that check itself. Posting is the only
    write this repository's automation makes, and the token it holds allows no
    more than that.
    """
    stored = json.loads(Path(arguments.results).read_text())
    number, body = posting.renderStoredReport(stored, arguments.head_sha)
    if arguments.dry_run:
        console.print(body, markup=False, highlight=False)
        return 0
    token = github.resolveToken()
    posting.confirmCheckedPullRequest(token, number, arguments.head_sha)
    console.print(f"{posting.postReportComment(token, number, body)} the report on "
                  f"{formatPullRequestRef(number)}")
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
    collect.add_argument("--base", default=defaultBaseBranch, help="the base branch")
    collect.add_argument("--branch", help="its head branch, which a merge commit hides")
    collect.add_argument("--head-sha", help="its head commit, not the merge commit")
    collect.add_argument(
        "--output", default="merge-readiness.json", help="where to write"
    )
    collect.set_defaults(handler=runCollect)

    report = commands.add_parser(
        "report", help="render the stored results and post one comment",
        formatter_class=RichHelpFormatter,
    )
    report.add_argument("--results", required=True, help="the stored facts and results")
    report.add_argument(
        "--head-sha", required=True, help="the head commit the checking run checked"
    )
    report.add_argument("--dry-run", action="store_true", help="print, post nothing")
    report.set_defaults(handler=runReport)

    check = commands.add_parser(
        "check", help="check the pull request and write the comment, posting nothing",
        formatter_class=RichHelpFormatter,
    )
    check.add_argument("--results", required=True, help="the collected facts")
    check.add_argument("--comment", default="merge-readiness.md", help="where to write")
    check.set_defaults(handler=runCheck)

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
