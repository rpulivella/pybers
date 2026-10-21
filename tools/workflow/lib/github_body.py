#!/usr/bin/env python3
"""\
A ticket, pull request or comment body, carried between GitHub and a file on disk.

**One newline means two things.** GitHub renders a single newline inside a body as
a line break, and a `.md` file renders it as a space, so the same text meant a
wrap to whoever drafted it and a break to whoever typed it on GitHub. Guessing
which, line by line, is what broke the bottom of PR #133.

A file on disk therefore follows the `.md` rule alone. Exporting writes each break
GitHub shows as a trailing backslash, changing no other byte, and posting formats
the file with `mdformat`, which joins every wrap and keeps every break. Both are
checked by rendering before and after, and a change GitHub would show is refused.
Measured 2026-09-25: all 134 bodies filed up to then survived the round trip.

UPDATES
2026-10-13  Moved here from `scripts/github_body.py`, for PYB-204.
2026-09-25  Written for PYB-134.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/25"

import difflib
import re
from dataclasses import dataclass

import mdformat
from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin

# The `.md` rule on the page. Consecutive list numbers are kept, so an author who
# wrote 2. and 3. still reads 2. and 3. in the file the next export gives back.
formatOptions: dict[str, object] = {"wrap": "no", "number": True}
formatExtensions: tuple[str, ...] = ("gfm",)

# How many changed lines a refusal names before it stops listing them.
refusalLineLimit: int = 8


class BodyRenderingError(RuntimeError):
    """A body whose posting would change what GitHub renders from it."""


@dataclass(frozen=True, slots=True)
class PostedBody:
    """A body as it will be posted, and how many of its lines formatting changed."""

    text: str
    tidied: int


def buildParser(breaks: bool) -> MarkdownIt:
    """Return a parser for GitHub's markdown, reading a newline as a break or a wrap.

    Independent of the one `mdformat` formats with, so a fault in the formatter
    cannot hide itself from the check that follows it.
    """
    parser = MarkdownIt("commonmark", {"breaks": breaks, "html": True})
    parser.enable(["table", "strikethrough"])
    parser.use(tasklists_plugin)
    return parser


def renderHtml(text: str, breaks: bool) -> str:
    """Return the HTML a body renders to, with whitespace a browser ignores evened out.

    Inside `<pre>` whitespace is content and is kept exactly.
    """
    html = buildParser(breaks).render(text)
    parts = re.split(r"(<pre[\s>].*?</pre>)", html, flags=re.S)
    return "".join(
        part if part.startswith("<pre") else re.sub(r"\s+", " ", part)
        for part in parts
    ).strip()


def findRenderingChanges(before: str, after: str) -> list[str]:
    """Return each rendered line that differs, prefixed as a diff prints it."""
    return [
        line for line in difflib.unified_diff(
            before.splitlines(), after.splitlines(), lineterm="", n=0
        )
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]


def refuseRenderingChange(before: str, after: str, action: str) -> None:
    """Raise, naming the lines, when two renderings of one body disagree."""
    changes = findRenderingChanges(before, after)
    if not changes:
        return
    shown = "\n".join(changes[:refusalLineLimit])
    more = len(changes) - refusalLineLimit
    tail = f"\n... and {more} more" if more > 0 else ""
    raise BodyRenderingError(
        f"{action} would change what GitHub renders, in these lines:\n{shown}{tail}"
    )


def listBreakLines(text: str) -> list[int]:
    """Return every line, counted from zero, whose newline GitHub shows as a break.

    Those are the lines of a paragraph, a list item or a quote but the last, since
    a paragraph is the only place a newline inside running text survives parsing.
    """
    lines: list[int] = []
    for token in buildParser(False).parse(text):
        if token.type == "inline" and token.map is not None:
            lines.extend(range(token.map[0], token.map[1] - 1))
    return lines


def convertBodyForEditing(body: str) -> str:
    """Return a GitHub body as a file means it, with each break GitHub shows kept.

    A line already ending in a backslash or two spaces is a break in both, and is
    left alone, and so is every other byte, which is what keeps a body holding no
    break inside a paragraph exactly as `export-as-source` always printed it.
    """
    lines = body.splitlines(keepends=True)
    for number in listBreakLines(body):
        line = lines[number]
        content = line.rstrip("\r\n")
        if content.endswith(("\\", "  ")):
            continue
        lines[number] = content + "\\" + line[len(content):]
    converted = "".join(lines)
    refuseRenderingChange(
        renderHtml(body, breaks=True), renderHtml(converted, breaks=False),
        "Exporting this body",
    )
    return converted


def formatBodyForPosting(text: str) -> PostedBody:
    """Return a file's body as GitHub has to receive it to render what the file means.

    Every wrap is joined, every break is kept, runs of blank lines become one, and
    the body ends with a single newline. Refused, naming the lines, when GitHub
    would render the result differently from the file.
    """
    formatted = mdformat.text(
        text, options=formatOptions, extensions=formatExtensions
    )
    refuseRenderingChange(
        renderHtml(text, breaks=False), renderHtml(formatted, breaks=True),
        "Posting this body",
    )
    tidied = sum(
        1 for line in difflib.ndiff(text.splitlines(), formatted.splitlines())
        if line.startswith("- ")
    )
    return PostedBody(formatted, tidied)


__all__ = [
    "BodyRenderingError",
    "PostedBody",
    "convertBodyForEditing",
    "formatBodyForPosting",
    "renderHtml",
]
