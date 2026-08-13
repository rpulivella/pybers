#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
pybers pull request tool

The single sanctioned path to GitHub pull requests. `/pr-draft` and
`/pr-review-code` call this rather than `gh`, so that the workflow's invariants —
a PR is always opened as a draft, the merge commit carries the house subject, the
branch is deleted on merge — hold in exactly one place.

**This tool exists to replace `gh`.** `gh` resolves its own identity from an OAuth
token in the system keyring, which can hold several accounts at once, so the
account a `gh pr create` acts as is ambient state no repository can control. This
tool authenticates with the explicit PAT that `ticket.py` already resolves, which
means every GitHub interaction in this repository runs on exactly two channels: a
PAT for the API, and SSH for git itself.

Talks to GitHub over urllib: REST for the pull request itself, GraphQL for the
one operation REST does not expose (marking a draft ready for review). Never
shells out — not to `gh`, not to `git`, not to `curl`. The current branch is read
by parsing `.git/HEAD` directly.

Authentication and the HTTP helpers are reused from `ticket.py` rather than
reimplemented, so this repository keeps exactly one auth story.

Usage:
    python3 scripts/pr.py create --title "[#14] Add a thing" --body-file draft.md
    python3 scripts/pr.py create --title "..." --body-file draft.md --base main
    python3 scripts/pr.py find
    python3 scripts/pr.py find --number-only
    python3 scripts/pr.py ready 8
    python3 scripts/pr.py merge 8 --subject "[14] feat: add a thing"
    python3 scripts/pr.py merge 8 --subject "..." --method squash
    python3 scripts/pr.py merge 8 --subject "..." --keep-branch

Requires rich:
    /usr/bin/env python3 -m pip install --upgrade rich

UPDATES
2026-08-13  Written to take pull requests off `gh`. See the module docstring for
            why: `gh` acts as whichever account is active in its keyring, which
            no repository can pin.
"""
__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "TBD"
__version__ = "0.1.0"
__email__ = "rpulivella@icloud.com"
__status__ = "Development"
__date__ = "2026/08/13"
__usage__ = "python3 scripts/pr.py <command> [options]"

import argparse
import importlib.util
import sys
import urllib.parse
from pathlib import Path
from types import ModuleType
from typing import Any, TypedDict

from rich.console import Console
from rich.markup import escape

console = Console()

repositoryRoot: Path = Path(__file__).resolve().parent.parent

# The base a pull request targets by default. Library and app repositories cut from
# develop; a web-facing repository whose deploy tracks a different branch overrides
# this per invocation with --base.
defaultBaseBranch: str = "develop"

# GitHub also offers "rebase". It is deliberately absent: rebasing rewrites the
# branch's commits, and nothing in this workflow has ever asked for that.
validMergeMethods: tuple[str, ...] = (
    "merge",
    "squash",
)


class PullRequestSummary(TypedDict):
    """An open or merged pull request, as the skills need to see it."""

    number: int
    title: str
    url: str
    state: str
    isDraft: bool
    head: str
    base: str
    nodeId: str


def loadTicketModule() -> ModuleType:
    """Load scripts/ticket.py as a module for its auth and HTTP helpers.

    Reused rather than reimplemented so this repository keeps exactly one auth
    story. ticket.py guards its entry point, so importing runs no commands.
    """
    spec = importlib.util.spec_from_file_location(
        "ticketForPullRequests", repositoryRoot / "scripts" / "ticket.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load scripts/ticket.py.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        base=payload["base"]["ref"],
        nodeId=payload["node_id"],
    )


def assertBranchIsPushed(ticket: ModuleType, token: str, branch: str) -> None:
    """Raise a clear error when the branch does not exist on the remote yet.

    GitHub refuses to open a pull request from an unpushed branch with a message
    about an invalid field, which reads as a bug in this tool rather than as the
    missing `git push` it actually is.
    """
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/"
        f"{ticket.repositoryName}/branches/{urllib.parse.quote(branch)}"
    )
    try:
        ticket.requestJson(url, token)
    except RuntimeError as exc:
        if "404" in str(exc):
            raise RuntimeError(
                f"Branch {branch!r} does not exist on the remote. Push it first: "
                f"git push -u origin {branch}"
            ) from exc
        raise


def createDraftPullRequest(
    ticket: ModuleType,
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
    url = f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/{ticket.repositoryName}/pulls"
    payload = {
        "title": title,
        "body": body,
        "head": head,
        "base": base,
        "draft": True,
    }
    return summarizePullRequest(ticket.requestJson(url, token, method="POST", payload=payload))


def findOpenPullRequest(
    ticket: ModuleType, token: str, head: str
) -> PullRequestSummary | None:
    """Return the open pull request for a branch, or None when there is none."""
    query = urllib.parse.urlencode(
        {"head": f"{ticket.repositoryOwner}:{head}", "state": "open"}
    )
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/"
        f"{ticket.repositoryName}/pulls?{query}"
    )
    matches = ticket.requestJson(url, token)
    if not matches:
        return None
    return summarizePullRequest(matches[0])


def readPullRequest(ticket: ModuleType, token: str, number: int) -> PullRequestSummary:
    """Fetch one pull request by number."""
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/"
        f"{ticket.repositoryName}/pulls/{number}"
    )
    return summarizePullRequest(ticket.requestJson(url, token))


def markReadyForReview(ticket: ModuleType, token: str, nodeId: str) -> None:
    """Take a pull request out of draft.

    REST does not expose this transition at all, so it is the one operation here
    that has to go through GraphQL, which is why the node id is carried around.
    """
    mutation = """
    mutation($pullRequestId: ID!) {
      markPullRequestReadyForReview(input: {pullRequestId: $pullRequestId}) {
        pullRequest { number isDraft }
      }
    }
    """
    ticket.requestGraphql(token, mutation, {"pullRequestId": nodeId})


def mergePullRequest(
    ticket: ModuleType,
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
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/"
        f"{ticket.repositoryName}/pulls/{number}/merge"
    )
    payload = {"merge_method": method, "commit_title": subject}
    result = ticket.requestJson(url, token, method="PUT", payload=payload)
    if not result or not result.get("merged"):
        raise RuntimeError(f"GitHub did not merge #{number}: {result}")
    return str(result["sha"])


def deleteBranch(ticket: ModuleType, token: str, branch: str) -> None:
    """Delete a merged branch from the remote."""
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/{ticket.repositoryName}/"
        f"git/refs/heads/{urllib.parse.quote(branch)}"
    )
    ticket.requestJson(url, token, method="DELETE")


def showPullRequest(summary: PullRequestSummary) -> None:
    """Print one pull request, color-coded and unbordered."""
    state = "draft" if summary["isDraft"] else summary["state"]
    tint = "yellow" if summary["isDraft"] else "green"
    console.print(f"[bold cyan]#{summary['number']}[/] [bold]{escape(summary['title'])}[/]")
    console.print(f"[dim]{escape(summary['url'])}[/]")
    console.print(
        f"state: [{tint}]{state}[/]   "
        f"[magenta]{escape(summary['head'])}[/] -> [cyan]{escape(summary['base'])}[/]"
    )


def cmdCreate(arguments: argparse.Namespace) -> int:
    """Open a draft pull request for the current branch."""
    bodyPath = Path(arguments.bodyFile)
    if not bodyPath.is_file():
        console.print(f"[red]Body file not found:[/] {bodyPath}")
        return 1
    body = bodyPath.read_text(encoding="utf-8")

    head = arguments.head or readCurrentBranch()
    if head == arguments.base:
        console.print(
            f"[red]Refusing to open a pull request from {head!r} into itself.[/]"
        )
        return 1

    if arguments.dryRun:
        console.print("[yellow]Dry run — no pull request was opened.[/]")
        console.print(f"title: [bold]{escape(arguments.title)}[/]")
        console.print(f"[magenta]{escape(head)}[/] -> [cyan]{escape(arguments.base)}[/]")
        console.print("state: [yellow]draft[/]")
        console.print()
        console.print(body, markup=False, highlight=False)
        return 0

    ticket = loadTicketModule()
    token = ticket.resolveToken()

    existing = findOpenPullRequest(ticket, token, head)
    if existing is not None:
        console.print(f"[yellow]An open pull request already exists for {head!r}.[/]")
        showPullRequest(existing)
        return 1

    assertBranchIsPushed(ticket, token, head)
    summary = createDraftPullRequest(
        ticket, token, arguments.title, body, head, arguments.base
    )
    console.print("[green]Opened as draft[/]")
    showPullRequest(summary)
    return 0


def cmdFind(arguments: argparse.Namespace) -> int:
    """Print the open pull request for a branch, if there is one."""
    head = arguments.head or readCurrentBranch()
    ticket = loadTicketModule()
    summary = findOpenPullRequest(ticket, ticket.resolveToken(), head)

    if summary is None:
        if arguments.numberOnly:
            return 1
        console.print(f"[yellow]No open pull request for {head!r}.[/]")
        return 1

    if arguments.numberOnly:
        console.print(summary["number"])
        return 0

    showPullRequest(summary)
    return 0


def cmdReady(arguments: argparse.Namespace) -> int:
    """Take a draft pull request out of draft."""
    ticket = loadTicketModule()
    token = ticket.resolveToken()
    summary = readPullRequest(ticket, token, arguments.number)

    if not summary["isDraft"]:
        console.print(f"[yellow]#{summary['number']} is already out of draft.[/]")
        return 0

    if arguments.dryRun:
        console.print("[yellow]Dry run — nothing was changed.[/]")
        console.print(f"would mark [bold cyan]#{summary['number']}[/] ready for review")
        return 0

    markReadyForReview(ticket, token, summary["nodeId"])
    console.print(f"[green]Ready for review[/] [bold cyan]#{summary['number']}[/]")
    console.print(summary["url"])
    return 0


def cmdMerge(arguments: argparse.Namespace) -> int:
    """Merge a pull request and delete its branch."""
    if arguments.method not in validMergeMethods:
        console.print(f"[red]Unknown merge method {arguments.method!r}.[/]")
        console.print(f"Choose one of: {', '.join(validMergeMethods)}")
        return 1

    ticket = loadTicketModule()
    token = ticket.resolveToken()
    summary = readPullRequest(ticket, token, arguments.number)

    if summary["isDraft"]:
        console.print(
            f"[red]#{summary['number']} is still a draft.[/] "
            "Run /pr-review-code, which owns the promotion out of draft."
        )
        return 1

    if arguments.dryRun:
        console.print("[yellow]Dry run — nothing was merged.[/]")
        showPullRequest(summary)
        console.print(f"method:  [cyan]{arguments.method}[/]")
        console.print(f"subject: [bold]{escape(arguments.subject)}[/]")
        console.print(
            "branch:  "
            + ("[dim]kept[/]" if arguments.keepBranch else f"would delete {summary['head']}")
        )
        return 0

    sha = mergePullRequest(ticket, token, arguments.number, arguments.method, arguments.subject)
    console.print(
        f"[green]Merged[/] [bold cyan]#{summary['number']}[/] "
        f"by [cyan]{arguments.method}[/] as [dim]{sha[:12]}[/]"
    )

    if not arguments.keepBranch:
        deleteBranch(ticket, token, summary["head"])
        console.print(f"[green]Deleted branch[/] {escape(summary['head'])}")
    return 0


def buildParser() -> argparse.ArgumentParser:
    """Assemble the command line, one subcommand per cmd-prefixed handler."""
    parser = argparse.ArgumentParser(
        prog="pr.py",
        description="Open, inspect, promote and merge pybers pull requests over the GitHub API.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    createParser = subparsers.add_parser("create", help="open a draft pull request")
    createParser.add_argument("--title", required=True, help="pull request title, verbatim")
    createParser.add_argument("--body-file", dest="bodyFile", required=True, help="drafted body")
    createParser.add_argument(
        "--head", default=None, help="source branch (default: the checked-out branch)"
    )
    createParser.add_argument(
        "--base",
        default=defaultBaseBranch,
        help=f"target branch (default: {defaultBaseBranch})",
    )
    createParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    createParser.set_defaults(handler=cmdCreate)

    findParser = subparsers.add_parser("find", help="print the open pull request for a branch")
    findParser.add_argument(
        "--head", default=None, help="source branch (default: the checked-out branch)"
    )
    findParser.add_argument(
        "--number-only",
        dest="numberOnly",
        action="store_true",
        help="print just the number, for a skill that only needs to resolve it",
    )
    findParser.set_defaults(handler=cmdFind)

    readyParser = subparsers.add_parser("ready", help="take a draft out of draft")
    readyParser.add_argument("number", type=int)
    readyParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    readyParser.set_defaults(handler=cmdReady)

    mergeParser = subparsers.add_parser("merge", help="merge a pull request")
    mergeParser.add_argument("number", type=int)
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
        "--keep-branch",
        dest="keepBranch",
        action="store_true",
        help="leave the source branch in place instead of deleting it",
    )
    mergeParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    mergeParser.set_defaults(handler=cmdMerge)

    return parser


def main() -> int:
    """Parse the command line and dispatch, reporting failures without a traceback."""
    arguments = buildParser().parse_args()
    try:
        return int(arguments.handler(arguments))
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
