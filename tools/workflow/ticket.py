#!/usr/bin/env python3
"""\
pybers ticket tool

The single sanctioned path to GitHub Issues and the pybers Project board.
The /ticket-create, /ticket-startwork, /changelog-add and /pr-draft skills all
call this rather than driving the API by hand, so that the board's invariants,
one classification label, a Status that always moves forward, an issue that is
always on the board, hold in exactly one place.

Talks to GitHub through `lib/github.py`, which holds the client and how a token is
resolved, and shares its comment commands with `pr.py` through
`lib/github_commands.py`.

Usage:
    .venv/bin/python3 -m tools.workflow.ticket create --label feat \
        --title "Add a thing" --body-file draft.md
    .venv/bin/python3 -m tools.workflow.ticket show 14
    .venv/bin/python3 -m tools.workflow.ticket export-as-source 14 --title
    .venv/bin/python3 -m tools.workflow.ticket export-as-source 14 --body
    .venv/bin/python3 -m tools.workflow.ticket start 14
    .venv/bin/python3 -m tools.workflow.ticket edit 14 --body-file revised.md
    .venv/bin/python3 -m tools.workflow.ticket status 14 --set "Code Review"
    .venv/bin/python3 -m tools.workflow.ticket close 14
    .venv/bin/python3 -m tools.workflow.ticket close 14 --reason not-planned
    .venv/bin/python3 -m tools.workflow.ticket block 25 --by 6 17
    .venv/bin/python3 -m tools.workflow.ticket block 25 --unblock 17
    .venv/bin/python3 -m tools.workflow.ticket list --status Todo

Runs on the repository's venv.

UPDATES
2026-10-15  `start` no longer touches the session dashboard, for PYB-156.
2026-10-14  `start` puts the ticket in focus on the dashboard, for PYB-211.
2026-10-14  Moved here from `scripts/ticket.py`, and run as a module, for PYB-204.
2026-10-13  The GitHub client moved to `lib/github.py` and the comment commands to
            `lib/github_commands.py`, leaving this file its own commands, for
            PYB-204.
2026-10-13  `lib/github_body.py` is a lazy import at the top rather than an import in
            each function that formats a body, for PYB-204.
2026-10-13  Posting a comment takes the reference it names, so `pr.py` shares
            every comment command rather than copying them, for PYB-204.
2026-09-25  Bodies are formatted by `github_body` on the way out and marked for editing
            on the way back, replacing the unwrapper, for PYB-134.
2026-09-24  A comment and a wholly italic line keep their own lines, found on
            PR #133, where both were joined onto the line below.
2026-09-14  A bold label keeps its own line, and a title carrying square
            brackets prints as filed rather than being eaten by rich.
2026-08-27  Set projectNumber to the real board (3), and corrected the 404 story, which
            had been carried in from an early revision of the upstream notes and was
            wrong. A later revision corrected it and the upstream tooling carries that
            correction; this repo did not. An expired or revoked token is 401, not 404.
            What answers 404 on a private repository is a VALID token lacking `repo`
            scope, or a wrong owner/name, so the old wording sent a reader hunting a
            dead credential when the fault was a scope or a typo. requestJson now adds a
            404 hint naming the two real causes. Also fixed an indentation bug in
            `edit --dry-run`: the body preview sat OUTSIDE its `if body is not None`
            guard, so `edit --title X --dry-run` printed a bare `None`. Introduced
            here while applying the markup fix; the predecessor never had it.
2026-08-17  Fixed two credential bugs. readTokenFromSecretsFile returned the first line
            matching GITHUB_TOKEN *or* GH_TOKEN, so a stale GH_TOKEN above the real one
            silently decided the identity; GITHUB_TOKEN now wins by name, and two
            different values refuse rather than picking. resolveToken tested the
            environment variable for truth before stripping it, so a whitespace-only
            value sent `Authorization: Bearer `, it now strips first and raises on
            set-but-empty rather than falling through to another source.
2026-08-17  `edit` now reads the ticket back and compares body, title and label against
            what was sent. `edit` replaces the WHOLE body and GitHub has no conflict
            detection, so a revision drafted against a copy exported minutes earlier
            silently discarded whatever changed in between. This cannot prevent a lost
            update; it makes one visible immediately, and it is what makes deleting the
            local draft safe.
2026-08-16  Added GitHubHttpError so requestJson carries the HTTP status as a number.
            pr.py's unpushed-branch guard was recovering it by searching the message
            for "404", which reported an expired token as an unpushed branch: a
            private repository answers 404, not 403, to a credential that cannot see
            it. A RuntimeError subclass, so every existing handler keeps working.
2026-08-13  Split `export-as-source` out of `show`. Displaying and round-tripping are
            separate actions: `show` renders through rich and may reformat freely,
            `export-as-source` emits bytes and must never transform any. Named for what
            each returns, not for the verb, because both of them read. /ticket-edit was
            reading the rendered view and writing part of it back, silently reflowing
            bodies.
2026-08-13  Removed the system-keyring fallback from resolveToken. `gh` can hold several
            accounts at once, so the keyring was a silent path to the wrong identity. A
            missing token now fails loudly.
2026-08-12  Adapted from the author's existing tooling. projectNumber is a placeholder
            until the pybers GitHub repo and Project board exist.
"""
__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/12"
__usage__ = ".venv/bin/python3 -m tools.workflow.ticket <command> [options]"

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from tools.workflow.lib import github
from tools.workflow.lib import github_commands as commands

console = Console()


def showTicket(summary: github.TicketSummary) -> None:
    """Print a ticket for a human reader.

    Everything coming back from GitHub is escaped, and the body is printed with
    markup off entirely. Square brackets are rich's own syntax, so a body carrying
    `- [init] <title>` or `[#14]` would otherwise render with the bracket silently
    swallowed.
    """
    labelText = ", ".join(summary.labels) or "none"
    console.print(
        f"[bold cyan]{github.formatTicketRef(summary.number)}[/] "
        f"[bold]{escape(summary.title)}[/]"
    )
    console.print(f"[dim]{escape(summary.url)}[/]")
    console.print(
        f"label: [magenta]{escape(labelText)}[/]   state: [yellow]{summary.state}[/]"
    )
    if summary.assignees:
        console.print(f"assigned: [green]{escape(', '.join(summary.assignees))}[/]")
    for related, label, tint in (
        (summary.blockedBy, "blocked by", "red"),
        (summary.blocking, "blocking", "yellow"),
    ):
        if related:
            listed = ", ".join(
                f"{github.formatTicketRef(number)} {title}" for number, title in related
            )
            console.print(f"{label}: [{tint}]{escape(listed)}[/]")
    if summary.body:
        console.print()
        # markup=False because rich reads square brackets as style tags, and a body
        # carrying [bold], [red] or [hotfix] would lose those words silently.
        # highlight=False stops it recoloring numbers and URLs inside prose it does
        # not own. Wrapping stays ON: this is the human-reading path and
        # terminal-width wrapping is wanted here. It is also why this cannot
        # round-trip, for that use github.writeBodyForEditing().
        console.print(summary.body, markup=False, highlight=False)


def runCreate(arguments: argparse.Namespace) -> int:
    """File a ticket, place it on the board, and set its Status to Todo."""
    if arguments.label not in github.validLabels:
        console.print(f"[red]Unknown label {arguments.label!r}.[/]")
        console.print(f"Choose exactly one of: {', '.join(github.validLabels)}")
        return 1

    bodyPath = Path(arguments.bodyFile)
    if not bodyPath.is_file():
        console.print(f"[red]Body file not found:[/] {escape(str(bodyPath))}")
        return 1
    posted = github.readBodyFile(bodyPath)
    if posted is None:
        return 1
    body = posted.text
    github.reportTidying(posted)

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was filed.[/]")
        console.print(f"label:  [magenta]{arguments.label}[/]")
        console.print(f"title:  [bold]{escape(arguments.title)}[/]")
        console.print(f"status: [cyan]{arguments.status}[/]")
        console.print()
        # markup=False because this is a PREVIEW of bytes about to be written:
        # rich reads square brackets as style tags, so a body carrying [hotfix]
        # or a path like /work/[slug] would display with those words missing.
        # A dry run whose whole purpose is showing what will be written must not
        # be the one place the text is altered.
        console.print(body, markup=False, highlight=False)
        return 0

    token = github.resolveToken()
    coordinates = github.readBoardCoordinates(token)

    summary = github.createTicket(token, arguments.label, arguments.title, body)
    console.print(
        f"[green]Filed[/] [bold cyan]{github.formatTicketRef(summary.number)}[/] "
        f"{escape(summary.title)}"
    )

    nodeId = github.readIssueNodeId(token, summary.number)
    itemId = github.placeOnBoard(token, coordinates, nodeId)
    github.setBoardStatus(token, coordinates, itemId, arguments.status)
    console.print(f"[green]On the board[/] with Status [cyan]{arguments.status}[/]")
    console.print(summary.url)
    return 0


def runShow(arguments: argparse.Namespace) -> int:
    """Print one ticket for a human reader.

    `show` renders; `export-as-source` does not. That is the whole distinction, and the
    names are meant to carry it without anyone having to read this file. This one is
    free to change its formatting at any time, which is exactly why its output must
    never be sent back, use `export-as-source` for that.
    """
    token = github.resolveToken()
    showTicket(github.readTicket(token, arguments.number))
    if arguments.comments:
        console.print()
        commands.showComments(github.readComments(token, arguments.number))
    return 0


def runExportAsSource(arguments: argparse.Namespace) -> int:
    """Emit one field of a ticket for editing, for a skill that will send it back.

    Separate from `show` because displaying and round-tripping are different actions
    with incompatible contracts: `show` may reformat freely, and `export-as-source`
    changes nothing but a backslash ending each line GitHub shows as a break. Both of
    them "read" a ticket, which is why neither is called that.
    """
    summary = github.readTicket(github.resolveToken(), arguments.number)
    if arguments.body:
        return 0 if github.writeBodyForEditing(summary.body) else 1
    else:
        commands.printTitleAsRawString(summary.title)
    return 0


def runStart(arguments: argparse.Namespace) -> int:
    """Assign a ticket and move it to In Progress."""
    token = github.resolveToken()
    summary = github.readTicket(token, arguments.number)

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        console.print(
            f"would assign {github.formatTicketRef(summary.number)} "
            f"to {arguments.assignee}"
        )
        console.print("would set Status to [cyan]In Progress[/]")
        return 0

    github.assignTicket(token, arguments.number, arguments.assignee)
    coordinates = github.readBoardCoordinates(token)
    itemId = github.findBoardItem(token, coordinates, arguments.number)
    if itemId is None:
        itemId = github.placeOnBoard(
            token, coordinates, github.readIssueNodeId(token, arguments.number)
        )
        console.print("[yellow]Ticket was not on the board; added it.[/]")
    github.setBoardStatus(token, coordinates, itemId, "In Progress")

    console.print(
        f"[green]Started[/] [bold cyan]{github.formatTicketRef(summary.number)}[/] "
        f"{escape(summary.title)}"
    )
    console.print(
        f"assigned to [green]{escape(arguments.assignee)}[/], "
        "Status [cyan]In Progress[/]"
    )
    return 0


def runEdit(arguments: argparse.Namespace) -> int:
    """Revise a filed ticket in place."""
    if arguments.label is not None and arguments.label not in github.validLabels:
        console.print(f"[red]Unknown label {arguments.label!r}.[/]")
        console.print(f"Choose exactly one of: {', '.join(github.validLabels)}")
        return 1

    body: str | None = None
    if arguments.bodyFile is not None:
        bodyPath = Path(arguments.bodyFile)
        if not bodyPath.is_file():
            console.print(f"[red]Body file not found:[/] {escape(str(bodyPath))}")
            return 1
        posted = github.readBodyFile(bodyPath)
        if posted is None:
            return 1
        body = posted.text
        github.reportTidying(posted)

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        if arguments.title:
            console.print(f"would set title: [bold]{escape(arguments.title)}[/]")
        if arguments.label:
            console.print(f"would set label: [magenta]{arguments.label}[/]")
        if body is not None:
            console.print("would replace the body with:")
            # markup=False because this is a PREVIEW of bytes about to be written:
            # rich reads square brackets as style tags, so a body carrying [hotfix]
            # or a path like /work/[slug] would display with those words missing.
            # A dry run whose whole purpose is showing what will be written must not
            # be the one place the text is altered.
            console.print(body, markup=False, highlight=False)
        return 0

    token = github.resolveToken()
    github.editTicket(token, arguments.number, arguments.title, body, arguments.label)

    # Read the ticket back and confirm what landed. `edit` replaces the WHOLE body
    # and GitHub offers no conflict detection, so a revision drafted against a copy
    # exported even minutes earlier silently discards whatever changed in between,
    # no error, no conflict marker, the other edit simply gone. Verifying cannot
    # prevent that, but it makes it visible immediately to whoever caused it, which
    # is the difference between losing data and failing a command. It is also what
    # makes deleting the local draft safe: once this passes, the copy is provably
    # redundant, and a lingering export is the thing a later revision gets drafted
    # against by mistake.
    summary = github.readTicket(token, arguments.number)
    mismatches: list[str] = []
    if body is not None and summary.body != body:
        mismatches.append("body")
    if arguments.title is not None and summary.title != arguments.title:
        mismatches.append("title")
    if arguments.label is not None and arguments.label not in summary.labels:
        mismatches.append("label")

    if mismatches:
        console.print(
            f"[red]Edit did not land cleanly:[/] {', '.join(mismatches)} differs from "
            "what was sent."
        )
        console.print(
            "The ticket may have changed between your export and this write. Re-export "
            "it, re-apply your revision, and check that nothing was lost."
        )
        console.print(summary.url)
        return 1

    console.print(
        f"[green]Edited[/] [bold cyan]{github.formatTicketRef(summary.number)}[/] "
        f"{escape(summary.title)}"
    )
    console.print("[dim]verified against the filed ticket[/]")
    console.print(summary.url)
    return 0


def runComment(arguments: argparse.Namespace) -> int:
    """Add one comment to a ticket."""
    return commands.postCommentFromFile(
        arguments, github.formatTicketRef(arguments.number)
    )


def runClose(arguments: argparse.Namespace) -> int:
    """Close a ticket and move it to Done.

    Merging a pull request whose body carries `Closes #N` already closes the
    issue, which leaves the board behind, an already-closed issue is the normal
    case after a merge, not an error, so this command still sets the Status and
    only skips the close itself.
    """
    reason = "completed" if arguments.reason == "completed" else "not_planned"
    token = github.resolveToken()
    summary = github.readTicket(token, arguments.number)
    alreadyClosed = summary.state == "closed"

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        if alreadyClosed:
            console.print(
                f"{github.formatTicketRef(summary.number)} is already closed; "
                "would leave the issue alone"
            )
        else:
            console.print(
                f"would close {github.formatTicketRef(summary.number)} "
                f"as [cyan]{reason}[/]"
            )
        console.print("would set Status to [cyan]Done[/]")
        return 0

    if alreadyClosed:
        console.print(
            f"[yellow]{github.formatTicketRef(arguments.number)} is already closed[/], "
            "setting Status only."
        )
    else:
        github.closeTicket(token, arguments.number, reason)
    coordinates = github.readBoardCoordinates(token)
    itemId = github.findBoardItem(token, coordinates, arguments.number)
    if itemId is not None:
        github.setBoardStatus(token, coordinates, itemId, "Done")
    else:
        console.print(
            "[yellow]Ticket was not on the board; only the issue was closed.[/]"
        )

    verb = "Completed" if reason == "completed" else "Abandoned"
    console.print(
        f"[green]{verb}[/] [bold cyan]{github.formatTicketRef(summary.number)}[/] "
        f"{escape(summary.title)}"
    )
    return 0


def runStatus(arguments: argparse.Namespace) -> int:
    """Move a ticket to a named Status on the board."""
    token = github.resolveToken()
    coordinates = github.readBoardCoordinates(token)

    if arguments.setStatus not in coordinates.statusOptionIds:
        console.print(f"[red]Unknown Status {arguments.setStatus!r}.[/]")
        console.print(f"The board offers: {', '.join(coordinates.statusOptionIds)}")
        return 1

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        console.print(
            f"would set {github.formatTicketRef(arguments.number)} "
            f"to [cyan]{arguments.setStatus}[/]"
        )
        return 0

    itemId = github.findBoardItem(token, coordinates, arguments.number)
    if itemId is None:
        console.print(
            f"[red]{github.formatTicketRef(arguments.number)} "
            "is not on the board.[/]"
        )
        return 1

    github.setBoardStatus(token, coordinates, itemId, arguments.setStatus)
    console.print(
        f"[green]{github.formatTicketRef(arguments.number)}[/] "
        f"is now [cyan]{arguments.setStatus}[/]"
    )
    return 0


def runList(arguments: argparse.Namespace) -> int:
    """List open tickets, optionally narrowed to one Status."""
    token = github.resolveToken()
    query = """
    query($projectId: ID!, $cursor: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              fieldValueByName(name: "Status") {
                ... on ProjectV2ItemFieldSingleSelectValue { name }
              }
              content {
                __typename
                ... on Issue { number title state labels(first: 5) { nodes { name } } }
                ... on DraftIssue { title }
                ... on PullRequest { title }
              }
            }
          }
        }
      }
    }
    """
    coordinates = github.readBoardCoordinates(token)
    cursor: str | None = None
    rows: list[tuple[str, int, str, str]] = []
    nonTickets: list[tuple[str, str]] = []
    unreadableCount = 0

    while True:
        data = github.requestGraphql(
            token, query, {"projectId": coordinates.projectId, "cursor": cursor}
        )
        page = data["node"]["items"]
        for item in page["nodes"]:
            content = item.get("content") or {}
            typeName = content.get("__typename")
            if typeName and typeName != "Issue":
                nonTickets.append((typeName, content.get("title") or "untitled"))
                continue
            if not content.get("number"):
                unreadableCount += 1
                continue
            statusValue = item.get("fieldValueByName") or {}
            statusName = statusValue.get("name") or ", "
            if arguments.status and statusName != arguments.status:
                continue
            labelNames = [entry["name"] for entry in content["labels"]["nodes"]]
            rows.append(
                (statusName, content["number"], content["title"], ", ".join(labelNames))
            )
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    if unreadableCount:
        console.print(
            f"[red]{unreadableCount} board item(s) could not be read.[/] "
            "The token reaches the board but not the issues behind it, "
            "check that it carries the full [bold]repo[/] scope, not only repo:status."
        )

    for typeName, title in nonTickets:
        kind = "draft" if typeName == "DraftIssue" else typeName.lower()
        console.print(
            f"[yellow]{kind:<12}[/] [dim], [/]    {escape(title)}  "
            "[dim](on the board but not a ticket)[/]"
        )

    if not rows:
        console.print("[dim]No tickets match.[/]")
        return 1 if unreadableCount else 0

    rows.sort(
        key=lambda row: (
            github.statusOrder.index(row[0]) if row[0] in github.statusOrder else 99,
            row[1],
        )
    )
    for statusName, number, title, labelText in rows:
        # Escaped because rich reads square brackets as style tags, so a title
        # carrying `[hotfix]` printed without the word. `[PYB-99]` survives and
        # `[hotfix]` does not, so one example never reveals it.
        console.print(
            f"[cyan]{statusName:<12}[/] [bold]{github.formatTicketRef(number):<8}[/] "
            f"{escape(title)}  [magenta]{escape(labelText)}[/]"
        )
    return 0


def runBlock(arguments: argparse.Namespace) -> int:
    """Record, drop, or list what a ticket is waiting on."""
    token = github.resolveToken()
    number = arguments.number

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        for blocker in arguments.blockedBy:
            console.print(
                f"would mark {github.formatTicketRef(number)} "
                f"blocked by {github.formatTicketRef(blocker)}"
            )
        for blocker in arguments.unblock:
            console.print(
                f"would clear {github.formatTicketRef(blocker)} as a blocker of "
                f"{github.formatTicketRef(number)}"
            )
        return 0

    for blocker in arguments.blockedBy:
        if blocker == number:
            console.print("[red]A ticket cannot block itself.[/]")
            return 1
        github.addBlockedBy(token, number, blocker)
        console.print(
            f"[green]{github.formatTicketRef(number)}[/] is now blocked by "
            f"[bold cyan]{github.formatTicketRef(blocker)}[/]"
        )

    for blocker in arguments.unblock:
        github.removeBlockedBy(token, number, blocker)
        console.print(
            f"[green]{github.formatTicketRef(number)}[/] no longer blocked by "
            f"[bold cyan]{github.formatTicketRef(blocker)}[/]"
        )

    blockedBy = github.readDependencies(token, number, "blocked_by")
    blocking = github.readDependencies(token, number, "blocking")
    if not blockedBy and not blocking:
        console.print(f"[dim]{github.formatTicketRef(number)} has no dependencies.[/]")
        return 0

    for label, related, tint in (
        ("blocked by", blockedBy, "red"),
        ("blocking", blocking, "yellow"),
    ):
        for relatedNumber, title in related:
            console.print(
                f"{label}: [{tint}]{github.formatTicketRef(relatedNumber)}[/] "
                f"{escape(title)}"
            )
    return 0


def buildParser() -> argparse.ArgumentParser:
    """Assemble the command line, one subcommand per cmd-prefixed handler."""
    parser = argparse.ArgumentParser(
        description="File and move pybers tickets on GitHub Issues and the "
        "Project board.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    createParser = subparsers.add_parser("create", help="file a new ticket")
    createParser.add_argument(
        "--label", required=True, help=f"one of: {', '.join(github.validLabels)}"
    )
    createParser.add_argument("--title", required=True, help="issue title, verbatim")
    createParser.add_argument(
        "--body-file", dest="bodyFile", required=True, help="drafted body"
    )
    createParser.add_argument(
        "--status", default="Todo", help="starting Status (default: Todo)"
    )
    createParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    createParser.set_defaults(handler=runCreate)

    showParser = subparsers.add_parser(
        "show",
        help="RENDERED for reading: colored, wrapped to your terminal. "
        "Never copy from it.",
    )
    showParser.add_argument("number", type=github.parseTicketNumber)
    showParser.add_argument(
        "--comments", action="store_true",
        help="also print the ticket's comments, with the id each is reached by",
    )
    showParser.set_defaults(handler=runShow)

    exportParser = subparsers.add_parser(
        "export-as-source",
        help="The SOURCE, nothing rendered, each line GitHub shows as a break ending "
        "in a backslash: the form to edit and send back to `edit`. Contrast "
        "`show`, which renders.",
    )
    exportParser.add_argument("number", type=github.parseTicketNumber)
    # Mutually exclusive and required, because these never compose: each is a whole
    # output, not a modifier on a shared one.
    fieldGroup = exportParser.add_mutually_exclusive_group(required=True)
    fieldGroup.add_argument(
        "--body", action="store_true",
        help="the body, as a file means it, nothing rendered",
    )
    fieldGroup.add_argument(
        "--title", action="store_true", help="the title, with nothing added"
    )
    exportParser.set_defaults(handler=runExportAsSource)

    startParser = subparsers.add_parser("start", help="assign and move to In Progress")
    startParser.add_argument("number", type=github.parseTicketNumber)
    startParser.add_argument("--assignee", default=github.repositoryOwner)
    startParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    startParser.set_defaults(handler=runStart)

    editParser = subparsers.add_parser("edit", help="revise a filed ticket")
    editParser.add_argument("number", type=github.parseTicketNumber)
    editParser.add_argument("--title", default=None, help="replace the title")
    editParser.add_argument(
        "--body-file", dest="bodyFile", default=None, help="replace the body"
    )
    editParser.add_argument(
        "--label", default=None, help=f"one of: {', '.join(github.validLabels)}"
    )
    editParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    editParser.set_defaults(handler=runEdit)

    commentParser = subparsers.add_parser(
        "comment", help="add a comment to a ticket"
    )
    commentParser.add_argument("number", type=github.parseTicketNumber)
    commentParser.add_argument(
        "--body-file", dest="bodyFile", required=True,
        help="drafted comment body, a file so lists and code fences survive",
    )
    commentParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    commentParser.set_defaults(handler=runComment)

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

    closeParser = subparsers.add_parser(
        "close", help="close a ticket and set Status to Done"
    )
    closeParser.add_argument("number", type=github.parseTicketNumber)
    closeParser.add_argument(
        "--reason",
        choices=("completed", "not-planned"),
        default="completed",
        help="completed for delivered work, not-planned for an abandoned ticket",
    )
    closeParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    closeParser.set_defaults(handler=runClose)

    statusParser = subparsers.add_parser("status", help="move a ticket to a Status")
    statusParser.add_argument("number", type=github.parseTicketNumber)
    statusParser.add_argument("--set", dest="setStatus", required=True)
    statusParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    statusParser.set_defaults(handler=runStatus)

    listParser = subparsers.add_parser("list", help="list tickets on the board")
    listParser.add_argument("--status", default=None, help="narrow to one Status")
    listParser.set_defaults(handler=runList)

    blockParser = subparsers.add_parser(
        "block", help="record or list what a ticket is waiting on"
    )
    blockParser.add_argument("number", type=github.parseTicketNumber)
    blockParser.add_argument(
        "--by",
        dest="blockedBy",
        type=github.parseTicketNumber,
        nargs="+",
        default=[],
        metavar="N",
        help="issue numbers that must finish first",
    )
    blockParser.add_argument(
        "--unblock",
        type=github.parseTicketNumber,
        nargs="+",
        default=[],
        metavar="N",
        help="issue numbers that no longer block this one",
    )
    blockParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    blockParser.set_defaults(handler=runBlock)

    return parser


def main() -> int:
    """Parse the command line and dispatch, reporting failures without a traceback."""
    arguments = buildParser().parse_args()
    try:
        return int(arguments.handler(arguments))
    except RuntimeError as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
