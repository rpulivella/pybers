#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
pybers pull request tool

The single sanctioned path to GitHub pull requests. `/pr-draft` and
`/pr-review-code` call this rather than `gh`, so that the workflow's invariants,
a PR is always opened as a draft, the merge commit carries the house subject, the
branch is deleted on merge, hold in exactly one place.

**This tool exists to replace `gh`.** `gh` resolves its own identity from an OAuth
token in the system keyring, which can hold several accounts at once, so the
account a `gh pr create` acts as is ambient state no repository can control. This
tool authenticates with the explicit PAT that `ticket.py` already resolves, which
means every GitHub interaction in this repository runs on exactly two channels: a
PAT for the API, and SSH for git itself.

Talks to GitHub over urllib: REST for the pull request itself, GraphQL for the
one operation REST does not expose (marking a draft ready for review). Never
shells out, not to `gh`, not to `git`, not to `curl`. The current branch is read
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
    python3 scripts/pr.py merge 8 --subject "..." --keep-branch

Requires rich:
    /usr/bin/env python3 -m pip install --upgrade rich

UPDATES
2026-08-17  Round two of the same review. The merge PUT is now guarded as well as the
            branch delete: urllib lets a read-phase TimeoutError through as an OSError
            and a proxy error page makes json.loads raise ValueError, neither of which is
            a RuntimeError, so both escaped to exit 1, the code meaning "no pull
            request", after a merge that may have landed. main() is broadened for the
            same reason. A delete answering 404 or 422 is now success, because the ref is
            already gone whenever the repository deletes head branches automatically, and
            an alarm that fires on success stops being read. `squash` stays available:
            the tool serves repositories that permit it, and the prohibition belongs in
            /pr-review-code, but the usage example teaching it is gone, since permitting
            and advertising are different acts.
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
__email__ = "rpulivella@icloud.com"
__status__ = "Development"
__date__ = "2026/08/13"
__usage__ = "python3 scripts/pr.py <command> [options]"

import argparse
import sys
import urllib.parse
from pathlib import Path
from typing import Any, TypedDict

from rich.console import Console
from rich.markup import escape

# scripts/ is not a package, but Python puts a script's OWN directory at the
# front of sys.path, so this resolves to scripts/ticket.py and takes precedence
# over any installed package of the same name. Reused rather than
# reimplemented so this repository keeps exactly one auth story.
import ticket

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

# Exit codes are distinguished because a skill reads them and acts. Collapsing
# "there is no pull request" into "something went wrong" made a missing token
# report as a missing pull request: /pr-review-code asks `find --number-only`
# whether a PR exists, and a 401 answered "no" just as convincingly as an empty
# list did. "I could not determine X" and "X is not there" are different claims,
# and only one of them is a fact this tool holds.
notFoundExitCode: int = 1
errorExitCode: int = 2

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
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/"
        f"{ticket.repositoryName}/branches/{urllib.parse.quote(branch)}"
    )
    try:
        ticket.requestJson(url, token)
    except ticket.GitHubHttpError as exc:
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
        {"head": f"{ticket.repositoryOwner}:{head}", "base": base, "state": "open"}
    )
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/"
        f"{ticket.repositoryName}/pulls?{query}"
    )
    matches = ticket.requestJson(url, token)
    if not matches:
        return None
    if len(matches) > 1:
        numbers = ", ".join(f"#{match['number']}" for match in matches)
        raise RuntimeError(
            f"{len(matches)} open pull requests from {head!r} into {base!r}: {numbers}. "
            "Refusing to choose one. Close the ones that do not belong, or name the "
            "number explicitly."
        )
    return summarizePullRequest(matches[0])


def readPullRequest(token: str, number: int) -> PullRequestSummary:
    """Fetch one pull request by number."""
    url = (
        f"{ticket.restRoot}/repos/{ticket.repositoryOwner}/"
        f"{ticket.repositoryName}/pulls/{number}"
    )
    return summarizePullRequest(ticket.requestJson(url, token))


def markReadyForReview(token: str, nodeId: str) -> None:
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


def deleteBranch(token: str, branch: str) -> None:
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
        console.print(f"[red]Body file not found:[/] {escape(str(bodyPath))}")
        return errorExitCode
    body = bodyPath.read_text(encoding="utf-8")

    head = arguments.head or readCurrentBranch()
    if head == arguments.base:
        console.print(
            f"[red]Refusing to open a pull request from {head!r} into itself.[/]"
        )
        return errorExitCode

    if arguments.dryRun:
        console.print("[yellow]Dry run, no pull request was opened.[/]")
        console.print(f"title: [bold]{escape(arguments.title)}[/]")
        console.print(f"[magenta]{escape(head)}[/] -> [cyan]{escape(arguments.base)}[/]")
        console.print("state: [yellow]draft[/]")
        console.print()
        console.print(body, markup=False, highlight=False)
        return 0

    token = ticket.resolveToken()

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
        ticket, token, arguments.title, body, head, arguments.base
    )
    console.print("[green]Opened as draft[/]")
    showPullRequest(summary)
    return 0


def cmdFind(arguments: argparse.Namespace) -> int:
    """Print the open pull request for a branch, if there is one.

    Three outcomes, and each one says which it is in what it prints: a number, the
    `no-open-pull-request` marker, or an error. The exit codes carry the same three
    for anything scripting this, but the printed output is the contract, because
    the consumer is an agent reading stdout rather than a shell reading `$?`.
    """
    head = arguments.head or readCurrentBranch()
    summary = findOpenPullRequest(
        ticket.resolveToken(), head, arguments.base
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
        console.print(summary["number"])
        return 0

    showPullRequest(summary)
    return 0


def cmdReady(arguments: argparse.Namespace) -> int:
    """Take a draft pull request out of draft."""
    token = ticket.resolveToken()
    summary = readPullRequest(token, arguments.number)

    if not summary["isDraft"]:
        console.print(f"[yellow]#{summary['number']} is already out of draft.[/]")
        return 0

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        console.print(f"would mark [bold cyan]#{summary['number']}[/] ready for review")
        return 0

    markReadyForReview(token, summary["nodeId"])
    console.print(f"[green]Ready for review[/] [bold cyan]#{summary['number']}[/]")
    console.print(summary["url"])
    return 0


def cmdMerge(arguments: argparse.Namespace) -> int:
    """Merge a pull request and delete its branch."""
    if arguments.method not in validMergeMethods:
        console.print(f"[red]Unknown merge method {arguments.method!r}.[/]")
        console.print(f"Choose one of: {', '.join(validMergeMethods)}")
        return errorExitCode

    token = ticket.resolveToken()
    summary = readPullRequest(token, arguments.number)

    if summary["isDraft"]:
        console.print(
            f"[red]#{summary['number']} is still a draft.[/] "
            "Run /pr-review-code, which owns the promotion out of draft."
        )
        return errorExitCode

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was merged.[/]")
        showPullRequest(summary)
        console.print(f"method:  [cyan]{arguments.method}[/]")
        console.print(f"subject: [bold]{escape(arguments.subject)}[/]")
        console.print(
            "branch:  "
            + ("[dim]kept[/]" if arguments.keepBranch else f"would delete {summary['head']}")
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
            ticket, token, arguments.number, arguments.method, arguments.subject
        )
    except Exception as exc:
        console.print(
            f"[red]The merge request for #{summary['number']} did not complete "
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
        f"[green]Merged[/] [bold cyan]#{summary['number']}[/] "
        f"by [cyan]{arguments.method}[/] as [dim]{sha[:12]}[/]"
    )

    if arguments.keepBranch:
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
        deleteBranch(token, summary["head"])
    except RuntimeError as exc:
        # 404 or 422 means the ref is already gone, which is the NORMAL outcome when the
        # repository has "automatically delete head branches" enabled. Reporting that as
        # a failed cleanup printed a bold "Do not re-run merge", exited non-zero, and
        # sent the user to run a `git push --delete` that also fails. An alarm that
        # fires on success is an alarm that stops being read.
        alreadyGone = getattr(exc, "statusCode", None) in (404, 422)
        if alreadyGone:
            console.print(
                f"[green]Branch[/] {escape(summary['head'])} "
                "[green]was already deleted.[/]"
            )
            return 0
        console.print("[yellow]The merge succeeded. Only the branch delete failed.[/]")
        console.print(f"  [dim]{escape(str(exc))}[/]")
        console.print(
            f"[bold]Do not re-run merge[/], #{summary['number']} is already merged. "
            f"Finish by hand:\n  git push origin --delete {summary['head']}"
        )
        return partialSuccessExitCode
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
