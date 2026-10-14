#!/usr/bin/env python3
"""\
The commands `ticket.py` and `pr.py` both offer, implemented once.

An issue and a pull request share one comment thread on GitHub, so commenting on
either is the same request with a different reference in what it prints.

UPDATES
2026-10-13  Moved here from `ticket.py`, so `pr.py` imports a library rather than
            another command, for PYB-204.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/13"

import argparse
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from tools.workflow.lib import github

console = Console()


def showComments(comments: list[github.CommentSummary]) -> None:
    """Print comments for a human reader, never for round-tripping.

    The id is printed because it is what `comment-edit` and `comment-delete` take,
    and it appears nowhere in GitHub's own interface without hunting for it.
    """
    if not comments:
        console.print("[dim]no comments[/]")
        return
    for comment in comments:
        console.print(
            f"[bold cyan]{comment.id}[/] "
            f"[bold]{escape(comment.author)}[/] "
            f"[dim]{comment.createdAt}[/]"
        )
        console.print(comment.body, markup=False, highlight=False)
        console.print(f"[dim]{comment.url}[/]\n")


def printTitleAsRawString(title: str) -> None:
    """Write a ticket or pull request title with nothing added but its newline.

    Deliberately bare: /changelog-add copies a title verbatim into CHANGELOG.md, and
    `find` prints `PR #<N> <title>`, which reused would carry a number it never had.
    """
    print(title)


def verifyCommentBody(token: str, comment: github.CommentSummary, sent: str) -> bool:
    """Read one comment back and report whether it matches what was sent.

    The same duty `edit` performs on a ticket body, and for the same reason: a
    write that did not land should fail loudly rather than report success.

    Returns a bool rather than an exit code because `pr.py` shares this and the
    two tools number their failures differently: 1 there means no open pull
    request, so returning it from here would report the wrong thing.
    """
    if github.readComment(token, comment.id).body == sent:
        console.print("[dim]verified against the filed comment[/]")
        console.print(comment.url)
        return True
    console.print(
        "[red]The comment did not land cleanly:[/] what GitHub holds differs from "
        "what was sent."
    )
    console.print(comment.url)
    return False


def postCommentFromFile(arguments: argparse.Namespace, reference: str) -> int:
    """Post a drafted comment on a ticket or a pull request, which share one thread."""
    bodyPath = Path(arguments.bodyFile)
    if not bodyPath.is_file():
        console.print(f"[red]Body file not found:[/] {escape(str(bodyPath))}")
        return 1
    posted = github.readBodyFile(bodyPath)
    if posted is None:
        return 1
    body = posted.text
    if arguments.dryRun:
        console.print(f"[yellow]Dry run[/] comment on {reference}:")
        console.print(body, markup=False, highlight=False)
        return 0
    token = github.resolveToken()
    comment = github.postComment(token, arguments.number, body)
    github.reportTidying(posted)
    console.print(
        f"[green]Commented on[/] [bold cyan]{reference}[/] "
        f"as comment [bold cyan]{comment.id}[/]"
    )
    return 0 if verifyCommentBody(token, comment, body) else 1


def runCommentExport(arguments: argparse.Namespace) -> int:
    """Emit one comment's body for editing, for a caller that will send it back.

    Separate from `comment-list` for the reason `export-as-source` is separate from
    `show`: displaying and round-tripping are different actions with incompatible
    contracts.
    """
    comment = github.readComment(github.resolveToken(), arguments.commentId)
    return 0 if github.writeBodyForEditing(comment.body) else 1


def runCommentEdit(arguments: argparse.Namespace) -> int:
    """Replace one comment's body, keeping its id and its place in the thread.

    What a re-running review needs: replacing its own summary costs neither the
    record that the first run happened nor the comment's position in the thread.
    """
    bodyPath = Path(arguments.bodyFile)
    if not bodyPath.is_file():
        console.print(f"[red]Body file not found:[/] {escape(str(bodyPath))}")
        return 1
    posted = github.readBodyFile(bodyPath)
    if posted is None:
        return 1
    body = posted.text
    if arguments.dryRun:
        console.print(f"[yellow]Dry run[/] rewrite of comment {arguments.commentId}:")
        console.print(body, markup=False, highlight=False)
        return 0
    token = github.resolveToken()
    comment = github.updateComment(token, arguments.commentId, body)
    github.reportTidying(posted)
    console.print(f"[green]Edited comment[/] [bold cyan]{comment.id}[/]")
    return 0 if verifyCommentBody(token, comment, body) else 1


def runCommentDelete(arguments: argparse.Namespace) -> int:
    """Remove one comment, after printing what is about to be lost.

    GitHub keeps no copy and offers no undo, so the body is shown first. A
    `--dry-run` shows it without removing anything.
    """
    token = github.resolveToken()
    comment = github.readComment(token, arguments.commentId)
    console.print(
        f"[yellow]GitHub keeps no copy of a deleted comment.[/] About to remove "
        f"comment [bold cyan]{comment.id}[/] by {escape(comment.author)}:"
    )
    console.print(comment.body, markup=False, highlight=False)
    if arguments.dryRun:
        console.print("[yellow]Dry run: nothing was removed.[/]")
        return 0
    github.deleteComment(token, arguments.commentId)
    console.print("[green]Deleted.[/]")
    return 0
