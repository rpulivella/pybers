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
import re
import subprocess
import sys
import tomllib
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
    findings = pr.findBodyFindings(pullRequest["body"], pr.readTemplate())
    return [
        checks.checkPreflight(facts),
        checks.checkTemplate(findings),
        checks.checkChangelog(facts),
        checks.checkTicketAgreement(facts, pullRequest["title"]),
        checks.checkBranchCurrent(behind, pullRequest["base"]),
        checks.checkDependencies(facts),
        checks.checkGoldenConfirmations(facts),
    ]


def runCollect(arguments: argparse.Namespace) -> int:
    """Gather the branch's own facts into the file the reporting half reads."""
    log = Path(arguments.preflight_log).read_text() if arguments.preflight_log else ""
    facts = checks.collectBranchFacts(arguments.base, arguments.pull_request, log)
    facts.declaredPackages = readDeclaredPackages()
    facts.resolvedPackages = readResolvedPackages()
    Path(arguments.output).write_text(json.dumps(facts.toDictionary(), indent=1))
    console.print(f"[green]collected[/] {len(facts.preflightGates)} gates into "
                  f"{arguments.output}")
    return 0


def runReport(arguments: argparse.Namespace) -> int:
    """Check the pull request, render one comment, and fail loudly when red."""
    stored = json.loads(Path(arguments.results).read_text())
    facts = checks.BranchFacts(**stored)
    if not facts.pullRequest:
        console.print("[red]the collected facts name no pull request[/]")
        return errorExitCode
    token = ticket.resolveToken()
    if readPullRequestFacts(token, facts.pullRequest)["draft"]:
        console.print("[dim]a draft carries no report, and none was posted[/]")
        return 0
    results = checkPullRequest(facts, token)
    verdict = checks.readVerdict(results)
    body = presenter.renderComment(results, facts, verdict, datetime.now(UTC))
    presenter.reportResults(console, results, verdict)
    if arguments.dry_run:
        console.print(body, markup=False, highlight=False)
        return 0
    console.print(f"{postReportComment(token, facts.pullRequest, body)} the report on "
                  f"{pr.formatPullRequestRef(facts.pullRequest)}")
    return failedExitCode if verdict == checks.failed else 0


def runDispatch(arguments: argparse.Namespace) -> int:
    """Ask GitHub to run the reporting workflow from a branch, on one preflight run.

    The only way to exercise that workflow before it reaches the default branch,
    since `workflow_run` fires from the default branch's copy alone.
    """
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/{ticket.repositoryName}"
        f"/actions/workflows/{reportWorkflowFile}/dispatches"
    )
    ticket.requestJson(
        url, ticket.resolveToken(), method="POST",
        payload={"ref": arguments.ref, "inputs": {"run-id": str(arguments.run_id)}},
    )
    console.print(f"[green]dispatched[/] {reportWorkflowFile} on {arguments.ref}")
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
    collect.add_argument("--preflight-log", help="the log the preflight wrote")
    collect.add_argument(
        "--output", default="merge-readiness.json", help="where to write"
    )
    collect.set_defaults(handler=runCollect)

    report = commands.add_parser(
        "report", help="check the pull request and post one comment",
        formatter_class=RichHelpFormatter,
    )
    report.add_argument("--results", required=True, help="the collected facts")
    report.add_argument("--dry-run", action="store_true", help="render, post nothing")
    report.set_defaults(handler=runReport)

    dispatch = commands.add_parser(
        "dispatch", help="run the reporting workflow by hand, from a branch",
        formatter_class=RichHelpFormatter,
    )
    dispatch.add_argument("--run-id", type=int, required=True, help="the preflight run")
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
