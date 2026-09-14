#!/usr/bin/env python3
"""\
pybers ticket tool

The single sanctioned path to GitHub Issues and the pybers Project board.
The /ticket-create, /ticket-startwork, /changelog-add and /pr-draft skills all
call this rather than driving the API by hand, so that the board's invariants,
one classification label, a Status that always moves forward, an issue that is
always on the board, hold in exactly one place.

Adapted from the same author's tooling in another repository and carried further
here; this copy holds credential and markup fixes that predecessor does not.

Talks to GitHub over urllib: REST for issues, GraphQL for the Project board.
Never shells out to `gh` or `jq`, per the house rules in scripts/README.md.

Authentication resolves in this order, and there is deliberately no third
fallback, a missing token is a loud failure, never a guess:
    1. GITHUB_TOKEN or GH_TOKEN in the environment
    2. a GITHUB_TOKEN= line in the git-ignored .dev.vars at the repository root

Usage:
    python3 scripts/ticket.py create --label feat --title "Add a thing" \
        --body-file draft.md
    python3 scripts/ticket.py show 14
    python3 scripts/ticket.py export-as-source 14 --title
    python3 scripts/ticket.py export-as-source 14 --body
    python3 scripts/ticket.py start 14
    python3 scripts/ticket.py edit 14 --body-file revised.md
    python3 scripts/ticket.py status 14 --set "Code Review"
    python3 scripts/ticket.py close 14
    python3 scripts/ticket.py close 14 --reason not-planned
    python3 scripts/ticket.py block 25 --by 6 17
    python3 scripts/ticket.py block 25 --unblock 17
    python3 scripts/ticket.py list --status Todo

Requires rich:
    /usr/bin/env python3 -m pip install --upgrade rich

UPDATES
2026-09-14  A bold label keeps its own line, found on PR #77.
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
__usage__ = "python3 scripts/ticket.py <command> [options]"

import argparse
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

from rich.console import Console
from rich.markup import escape

console = Console()

repositoryOwner: str = "rpulivella"
repositoryName: str = "pybers"
projectNumber: int = 3


def readTicketPrefix() -> str:
    """Return the ticket key `pyproject.toml` declares, so it has one home."""
    config = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with config.open("rb") as handle:
        return str(tomllib.load(handle)["tool"]["pybers"]["ticketPrefix"])


ticketPrefix: str = readTicketPrefix()


def ticketNumber(value: str) -> int:
    """Parse `PYB-39`, `39`, `#39` or the issue URL, which cannot differ here.

    ArgumentTypeError rather than ValueError, so argparse prints usage.
    """
    text = value.strip()
    if text.lower().startswith(f"{ticketPrefix.lower()}-"):
        text = text[len(ticketPrefix) + 1:]
    elif "/issues/" in text:
        text = text.rsplit("/issues/", 1)[1]
    text = text.lstrip("#")
    if not text.isdigit():
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a ticket. Use {ticketPrefix}-39, 39, #39, or the URL."
        )
    return int(text)


def ticketRef(number: int) -> str:
    """Return a ticket reference in the house form, never a bare number.

    GitHub numbers issues and pull requests from one counter, so `#34` names two.
    """
    return f"{ticketPrefix}-{number}"


restRoot: str = "https://api.github.com"
graphqlRoot: str = "https://api.github.com/graphql"
# Issue dependencies arrived after the unversioned endpoints and require this
# explicitly.
dependencyApiVersion: str = "2026-03-10"


# "style" is absent because a library with no interface to restyle gives it nothing to
# label. It survives as a commit prefix, which CONTRIBUTING.md keeps separate.
validLabels: tuple[str, ...] = (
    "feat",
    "fix",
    "perf",
    "refactor",
    "docs",
    "chore",
)

# The board's Status options, in pipeline order. Concept is the only state that
# means "a human still has to think"; Todo asserts the ticket is specified well
# enough to drive autonomously.
statusOrder: tuple[str, ...] = (
    "Concept",
    "Todo",
    "In Progress",
    "Code Review",
    "Done",
)


class TicketSummary(TypedDict):
    """A filed issue, as the skills need to see it."""

    number: int
    title: str
    body: str
    labels: list[str]
    state: str
    assignees: list[str]
    url: str
    blocked_by: list[tuple[int, str]]
    blocking: list[tuple[int, str]]


class CommentSummary(TypedDict):
    """One comment on a filed issue or pull request, as a caller needs to see it."""

    id: int
    author: str
    createdAt: str
    body: str
    url: str


class BoardCoordinates(TypedDict):
    """The identifiers required to move an item on the Project board."""

    projectId: str
    statusFieldId: str
    statusOptionIds: dict[str, str]


class GitHubHttpError(RuntimeError):
    """A refusal from GitHub, carrying its status code as a number.

    A `RuntimeError` subclass on purpose: every existing `except RuntimeError`
    keeps catching it unchanged, so this adds a capability without moving any
    caller onto a new failure path.

    The status has to survive as an integer because the alternative, recovering
    it from the formatted message, silently conflates causes. On a PRIVATE
    repository GitHub answers **404** to a VALID token that lacks `repo` scope, and
    to a wrong owner or name, exactly as it does to a branch that is genuinely
    absent. An expired or revoked token is **401**, not 404. So a guard matching on
    the string "404" reports "no such thing" when the truth is "your token cannot
    see it", and sends someone off fixing the wrong problem. A message is prose and
    will be reworded; a status code is a value, so carry the value.
    """

    def __init__(self, statusCode: int, message: str) -> None:
        super().__init__(message)
        self.statusCode = statusCode


# A markdown block opens only when a space follows its marker, so `**bold**:` is
# ordinary prose rather than a bullet. Getting this wrong splits a bolded paragraph
# across two lines, which is the exact defect this whole mechanism exists to stop.
#
# A LABEL is the exception, and it earned its place on PR #77: a line that is only
# `**Something**:` and its value is a heading in prose clothing, and the pull
# request template puts three of them on consecutive lines under Breaking Changes.
# Joining those gave one run-on paragraph. Matched only when the bold run opens the
# line, so `see **this**: here` inside a sentence is still prose.
blockOpener = re.compile(r"^(#{1,6} |> |\||```|~~~|:{3}|\*\*[^*]+\*\*:)")

# A list item is the one block whose wrapped continuation belongs to it rather than
# standing alone, so it is matched separately from the openers above.
#
# The third alternative is the SUPERSEDED sub-criterion form, `1.a` and `4.b`, which
# carries no space after the period and so is invisible to the ordinary list patterns.
# Sub-criteria are an indented ordered list now, matched by the second alternative, but
# tickets filed before 2026-09-02 still carry the old form and it stays matched here.
# Without it a sub-criterion is read as prose and joined onto its parent, which silently
# collapses a nested acceptance criterion into the one above it.
listOpener = re.compile(r"^([-*+] |\d+[.)] |\d+\.[a-z] )")

# The two lines of a ticket body that GitHub links, kept on their own lines because
# each is a statement rather than part of a paragraph.
standaloneLines: tuple[str, ...] = ("Link:", "Closes ")

# Every separator `str.splitlines` breaks on, verified against it rather than listed
# from memory. `\r\n` comes first because a line ending in one also ends in `\n`, so
# the shorter match would strand a `\r` on the content for `strip` to delete. Named
# because splitting on these and rejoining with `\n` rewrites a line ending the author
# chose, and inside a fenced code block that is their code rather than their formatting.
lineSeparators: tuple[str, ...] = (
    "\r\n", "\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e",
    "\x85", "\u2028", "\u2029",
)


def lineEnding(line: str) -> str:
    """Return the separator one line from `splitlines(keepends=True)` carries.

    The empty string for the last line of a body that does not end in one.
    """
    for separator in lineSeparators:
        if line.endswith(separator):
            return separator
    return ""


# CommonMark makes four columns of indentation a code block needing no fence, a tab
# advancing to the next stop. A construct identified by its indentation is invisible
# to a pattern matched against the stripped line, which is how a pasted block arrived
# at GitHub as a sentence. See #74.
codeIndent: int = 4


def leadingWidth(content: str) -> int:
    """Return how many columns a line is indented before its first other character."""
    width = 0
    for character in content:
        if character == " ":
            width += 1
        elif character == "\t":
            width += codeIndent - (width % codeIndent)
        else:
            break
    return width


@dataclass(frozen=True, slots=True)
class BodyChanges:
    """A drafted body as it will be posted, and every change made on the way there.

    A dataclass rather than a `TypedDict` like its neighbors, which each mirror a
    GitHub payload. This is computed here and never parsed from one.
    """

    text: str
    joined: int
    trimmed: int


def unwrapParagraphs(body: str) -> BodyChanges:
    """Join every hard-wrapped paragraph onto one line, and say how many were joined.

    **GitHub renders an issue, pull request or comment body with GFM hard line breaks
    turned on**, so a single newline inside a paragraph becomes a `<br>` rather than
    reflowing. Text wrapped at eighty-eight columns therefore reproduces its own wrap
    points on screen, at any window width, and a wrapped continuation under a list
    item breaks the item apart. A `.md` file committed to the repository has the
    opposite behavior, which is why the same habit is right in `CLAUDE.md` and wrong
    the moment the text is posted. Both are markdown and both end in `.md`, and that
    is why this went unnoticed for eighteen tickets.

    Only prose is joined. Headings, list items, tables, block quotes and fenced code
    are emitted exactly as given, because a newline is meaningful in every one of
    them. Returning the count keeps the transformation visible: a caller reports it
    rather than rewriting the author's text in silence.
    """
    lines = body.splitlines(keepends=True)
    out: list[str] = []
    paragraph: list[str] = []
    paragraphEnding = ""
    paragraphTrims = 0
    joined = 0
    trimmed = 0
    inFence = False
    inCode = False
    inList = False

    def flush() -> None:
        # A joined paragraph already reports the whitespace it destroyed, so only a
        # paragraph of one line has a trim left to report on its own.
        nonlocal joined, trimmed, paragraphTrims
        if paragraph:
            if len(paragraph) > 1:
                joined += len(paragraph) - 1
            else:
                trimmed += paragraphTrims
            out.append(" ".join(paragraph) + paragraphEnding)
            paragraph.clear()
        paragraphTrims = 0

    for line in lines:
        ending = lineEnding(line)
        content = line[: len(line) - len(ending)]
        stripped = content.strip()
        indent = leadingWidth(content)

        if stripped.startswith(("```", "~~~")):
            flush()
            inFence = not inFence
            inList = False
            out.append(line)
            continue
        if inFence:
            out.append(line)
            continue

        if inCode:
            # A blank line belongs to the block; a non-blank one inside the margin
            # closes it and is then dispatched normally below.
            if not stripped or indent >= codeIndent:
                out.append(line)
                continue
            inCode = False
        elif stripped and indent >= codeIndent and not inList and not paragraph:
            # Indented code cannot interrupt a paragraph, and inside a list the same
            # indentation is a continuation rather than a block.
            inCode = True
            out.append(line)
            continue

        if not stripped or stripped.startswith(standaloneLines):
            flush()
            out.append(line)
            continue

        if listOpener.match(stripped):
            # A list item opens a paragraph of its own, so its wrapped continuation
            # joins the item rather than becoming a stray line outside the list.
            flush()
            item = content.rstrip()
            if item != content:
                paragraphTrims += 1
            paragraph.append(item)
            paragraphEnding = ending
            inList = True
            continue

        if indent == 0:
            inList = False

        if blockOpener.match(stripped):
            flush()
            out.append(line)
            continue

        if stripped != content:
            paragraphTrims += 1
        paragraph.append(stripped)
        paragraphEnding = ending
    flush()

    return BodyChanges(text="".join(out), joined=joined, trimmed=trimmed)


def readBodyFile(path: Path) -> BodyChanges:
    """Read a drafted body and unwrap it, because it is bound for GitHub.

    Every body this tool posts is destined for GitHub and nowhere else, so it is
    normalized on the way out rather than left to whoever drafted it to remember.

    **Read with `newline=""`, which turns universal newlines OFF.** The default
    translates `\r\n` and a bare `\r` to `\n` before any of this code sees the
    text, so a carriage return inside a fenced code block was gone before
    `unwrapParagraphs` could preserve it, and nothing reported the change.
    """
    return unwrapParagraphs(path.read_text(encoding="utf-8", newline=""))


def reportUnwrapping(changes: BodyChanges) -> None:
    """Say what was changed, so the normalization is never a silent rewrite."""
    if changes.joined:
        console.print(
            f"[dim]unwrapped {changes.joined} hard-wrapped line(s); GitHub renders a "
            f"newline inside a paragraph as a line break[/]"
        )
    if changes.trimmed:
        console.print(
            f"[dim]trimmed the indent or the trailing spaces from "
            f"{changes.trimmed} line(s)[/]"
        )


def readTokenFromSecretsFile() -> str | None:
    """Return a token from the repository's git-ignored .dev.vars, if one is there.

    This file is the sanctioned home for the token. It is git-ignored, scoped to
    this repository, and read explicitly, so the identity in use is never
    inherited from ambient machine state.

    `GITHUB_TOKEN` wins over `GH_TOKEN` **by name, not by position**. Returning the
    first line matching either name meant a stale `GH_TOKEN=` sitting above the real
    one silently decided the identity, and on a machine with two GitHub accounts
    that means every issue filed and every commit authored as the wrong person,
    with nothing to show for it but the wrong name in the history.

    Two different values for the two names is a misconfiguration rather than a
    preference, so it raises instead of picking. Whichever this function chose,
    roughly half the time it would be the one the user did not mean.
    """
    secretsPath = Path(__file__).resolve().parent.parent / ".dev.vars"
    if not secretsPath.is_file():
        return None

    found: dict[str, str] = {}
    for line in secretsPath.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        name = name.strip()
        if name in ("GITHUB_TOKEN", "GH_TOKEN"):
            # Last occurrence of a given name wins, matching how a shell would
            # source the file. Only the cross-name conflict is an error.
            found[name] = value.strip().strip('"').strip("'")

    primary = found.get("GITHUB_TOKEN")
    secondary = found.get("GH_TOKEN")
    if primary and secondary and primary != secondary:
        raise RuntimeError(
            f"{secretsPath} sets GITHUB_TOKEN and GH_TOKEN to different values. "
            "Refusing to guess which account you meant, delete whichever is stale. "
            "Picking one silently is how work gets filed under the wrong identity."
        )
    return primary or secondary or None


def resolveToken() -> str:
    """Return a GitHub token from the environment or the git-ignored secrets file.

    There is deliberately no third fallback. The system keyring holds `gh`'s own
    token, and `gh` can be signed into several accounts at once, so reading it
    would silently pick an identity this tool never chose. An explicit token or a
    loud failure is the only safe pair of outcomes.

    A variable that is **set but empty or whitespace** raises rather than falling
    through to the next source. Testing the raw value for truth before stripping it
    sent `Authorization: Bearer ` to GitHub, whose refusal explains nothing; and
    falling through would be worse still, because it would quietly authenticate as
    whatever `.dev.vars` holds while the user believed the environment was in
    charge. Someone who exported the variable meant to use it.
    """
    for variableName in ("GITHUB_TOKEN", "GH_TOKEN"):
        fromEnvironment = os.environ.get(variableName)
        if fromEnvironment is None:
            continue
        cleaned = fromEnvironment.strip()
        if not cleaned:
            raise RuntimeError(
                f"{variableName} is set but empty. That is a misconfiguration, not a "
                "request to look elsewhere, unset it to fall back to .dev.vars, or "
                "give it a real value."
            )
        return cleaned

    fromFile = readTokenFromSecretsFile()
    if fromFile:
        return fromFile

    raise RuntimeError(
        "No GitHub token found. Set GITHUB_TOKEN in the environment, or add a "
        "GITHUB_TOKEN= line to the git-ignored .dev.vars at the repository root. "
        "The system keyring is never consulted: it belongs to `gh`, which may hold "
        "several accounts, and guessing one is how the wrong identity gets used."
    )


def requestJson(
    url: str,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    apiVersion: str | None = None,
) -> Any:
    """Perform one authenticated JSON request and return the decoded body.

    Raises ``GitHubHttpError`` carrying GitHub's own message, because the API
    explains its refusals far better than a status code does, and carrying the
    status *as a number* alongside it, because a caller that needs to branch on
    one must not go looking for it in the prose. A guard that recovered the status
    by searching the message for "404" told a user to push an already-pushed
    branch, because a private repository answers 404 rather than 403 to a valid
    token that cannot see the resource. An expired or revoked token is 401.
    """
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Content-Type", "application/json")
    request.add_header("User-Agent", "pybers-ticket-tool")
    if apiVersion:
        # Only the newer endpoints ask for this, and pinning it globally would opt every
        # other call into a version they were not written against.
        request.add_header("X-GitHub-Api-Version", apiVersion)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        hint = ""
        if exc.code == 404:
            # A private repo answers 404 to a VALID token lacking `repo` scope, and
            # to a wrong owner/name. An expired or revoked token is 401, not 404,
            # do not send anyone hunting an expired credential from here.
            hint = (", on a private repository this is also what a valid token "
                    "without `repo` scope looks like, or a wrong owner/name")
        raise GitHubHttpError(
            exc.code, f"GitHub returned HTTP {exc.code}{hint}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach GitHub: {exc.reason}") from exc


def requestGraphql(token: str, query: str, variables: dict[str, Any]) -> Any:
    """Perform one GraphQL request, raising on transport or query errors.

    GraphQL answers with HTTP 200 even when the query failed, so the errors
    array has to be inspected explicitly or failures pass silently.
    """
    result = requestJson(
        graphqlRoot,
        token,
        method="POST",
        payload={"query": query, "variables": variables},
    )
    if isinstance(result, dict) and result.get("errors"):
        messages = "; ".join(error.get("message", "?") for error in result["errors"])
        raise RuntimeError(f"GraphQL error: {messages}")
    return result["data"]


def readBoardCoordinates(token: str) -> BoardCoordinates:
    """Look up the Project board identifiers needed to place and move an item."""
    query = """
    query($owner: String!, $number: Int!) {
      user(login: $owner) {
        projectV2(number: $number) {
          id
          field(name: "Status") {
            ... on ProjectV2SingleSelectField { id options { id name } }
          }
        }
      }
    }
    """
    data = requestGraphql(
        token, query, {"owner": repositoryOwner, "number": projectNumber}
    )
    project = data["user"]["projectV2"]
    if project is None:
        raise RuntimeError(
            f"Project #{projectNumber} was not found for {repositoryOwner}."
        )

    field = project["field"]
    if field is None:
        raise RuntimeError("The Project board has no Status field.")

    return BoardCoordinates(
        projectId=project["id"],
        statusFieldId=field["id"],
        statusOptionIds={option["name"]: option["id"] for option in field["options"]},
    )


def readTicket(token: str, number: int) -> TicketSummary:
    """Fetch one issue and reduce it to the fields the skills consume."""
    url = f"{restRoot}/repos/{repositoryOwner}/{repositoryName}/issues/{number}"
    issue = requestJson(url, token)
    return TicketSummary(
        number=issue["number"],
        title=issue["title"],
        body=issue.get("body") or "",
        labels=[label["name"] for label in issue.get("labels", [])],
        state=issue["state"],
        assignees=[user["login"] for user in issue.get("assignees", [])],
        url=issue["html_url"],
        blocked_by=readDependencies(token, number, "blocked_by"),
        blocking=readDependencies(token, number, "blocking"),
    )


def readIssueDatabaseId(token: str, number: int) -> int:
    """Return an issue's numeric database id, which is not its issue number.

    The dependency endpoints identify the other side of a relationship by database id
    rather than by the number people actually use, so every call has to resolve one.
    """
    url = f"{restRoot}/repos/{repositoryOwner}/{repositoryName}/issues/{number}"
    return int(requestJson(url, token)["id"])


def readDependencies(token: str, number: int, direction: str) -> list[tuple[int, str]]:
    """List the issues on one side of a dependency, as (number, title) pairs.

    `direction` is GitHub's own vocabulary: `blocked_by` for what must finish first,
    `blocking` for what is waiting on this.
    """
    url = (
        f"{restRoot}/repos/{repositoryOwner}/{repositoryName}"
        f"/issues/{number}/dependencies/{direction}"
    )
    issues = requestJson(url, token, apiVersion=dependencyApiVersion) or []
    return [(issue["number"], issue["title"]) for issue in issues]


def addBlockedBy(token: str, number: int, blockerNumber: int) -> None:
    """Record that `number` cannot proceed until `blockerNumber` is done."""
    url = (
        f"{restRoot}/repos/{repositoryOwner}/{repositoryName}"
        f"/issues/{number}/dependencies/blocked_by"
    )
    requestJson(
        url,
        token,
        method="POST",
        payload={"issue_id": readIssueDatabaseId(token, blockerNumber)},
        apiVersion=dependencyApiVersion,
    )


def removeBlockedBy(token: str, number: int, blockerNumber: int) -> None:
    """Drop a blocker that no longer applies."""
    blockerId = readIssueDatabaseId(token, blockerNumber)
    url = (
        f"{restRoot}/repos/{repositoryOwner}/{repositoryName}"
        f"/issues/{number}/dependencies/blocked_by/{blockerId}"
    )
    requestJson(url, token, method="DELETE", apiVersion=dependencyApiVersion)


def createTicket(token: str, label: str, title: str, body: str) -> TicketSummary:
    """File a new issue carrying exactly one classification label."""
    url = f"{restRoot}/repos/{repositoryOwner}/{repositoryName}/issues"
    issue = requestJson(
        url,
        token,
        method="POST",
        payload={"title": title, "body": body, "labels": [label]},
    )
    return TicketSummary(
        number=issue["number"],
        title=issue["title"],
        body=issue.get("body") or "",
        labels=[entry["name"] for entry in issue.get("labels", [])],
        state=issue["state"],
        assignees=[],
        url=issue["html_url"],
        blocked_by=[],
        blocking=[],
    )


def placeOnBoard(token: str, coordinates: BoardCoordinates, issueNodeId: str) -> str:
    """Add an issue to the Project board and return its item identifier.

    The identifier comes from this mutation's own response rather than from a
    follow-up query. Listing the board immediately after adding races: the item
    is not yet queryable and the lookup comes back empty.
    """
    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item { id }
      }
    }
    """
    data = requestGraphql(
        token,
        mutation,
        {"projectId": coordinates["projectId"], "contentId": issueNodeId},
    )
    return data["addProjectV2ItemById"]["item"]["id"]


def setBoardStatus(
    token: str,
    coordinates: BoardCoordinates,
    itemId: str,
    status: str,
) -> None:
    """Set a board item's Status to one of the pipeline's named options."""
    optionId = coordinates["statusOptionIds"].get(status)
    if optionId is None:
        known = ", ".join(coordinates["statusOptionIds"])
        raise RuntimeError(f"Unknown Status {status!r}. The board offers: {known}.")

    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $projectId, itemId: $itemId, fieldId: $fieldId,
        value: {singleSelectOptionId: $optionId}
      }) { projectV2Item { id } }
    }
    """
    requestGraphql(
        token,
        mutation,
        {
            "projectId": coordinates["projectId"],
            "itemId": itemId,
            "fieldId": coordinates["statusFieldId"],
            "optionId": optionId,
        },
    )


def findBoardItem(token: str, coordinates: BoardCoordinates, number: int) -> str | None:
    """Return the board item identifier for an issue, or None if it is not on the
    board."""
    query = """
    query($projectId: ID!, $cursor: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes { id content { ... on Issue { number } } }
          }
        }
      }
    }
    """
    cursor: str | None = None
    while True:
        data = requestGraphql(
            token, query, {"projectId": coordinates["projectId"], "cursor": cursor}
        )
        page = data["node"]["items"]
        for item in page["nodes"]:
            content = item.get("content") or {}
            if content.get("number") == number:
                return item["id"]
        if not page["pageInfo"]["hasNextPage"]:
            return None
        cursor = page["pageInfo"]["endCursor"]


def readIssueNodeId(token: str, number: int) -> str:
    """Return an issue's GraphQL node identifier, which the board mutations require."""
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) { issue(number: $number) { id } }
    }
    """
    data = requestGraphql(
        token,
        query,
        {"owner": repositoryOwner, "name": repositoryName, "number": number},
    )
    issue = data["repository"]["issue"]
    if issue is None:
        raise RuntimeError(f"Issue {ticketRef(number)} was not found.")
    return issue["id"]


def editTicket(
    token: str,
    number: int,
    title: str | None,
    body: str | None,
    label: str | None,
) -> TicketSummary:
    """Revise an issue's title, body, or classification label.

    Only the fields supplied are sent, so editing a body cannot silently discard
    a title. The label is replaced rather than appended to, because exactly one
    classification label is the rule this repository holds to.
    """
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if label is not None:
        payload["labels"] = [label]
    if not payload:
        raise RuntimeError("Nothing to edit. Supply --title, --body-file, or --label.")

    url = f"{restRoot}/repos/{repositoryOwner}/{repositoryName}/issues/{number}"
    issue = requestJson(url, token, method="PATCH", payload=payload)
    return TicketSummary(
        number=issue["number"],
        title=issue["title"],
        body=issue.get("body") or "",
        labels=[entry["name"] for entry in issue.get("labels", [])],
        state=issue["state"],
        assignees=[user["login"] for user in issue.get("assignees", [])],
        url=issue["html_url"],
        blocked_by=readDependencies(token, number, "blocked_by"),
        blocking=readDependencies(token, number, "blocking"),
    )


def closeTicket(token: str, number: int, reason: str) -> None:
    """Close an issue, recording whether it was completed or abandoned.

    GitHub's own state_reason is the differentiator rather than a board Status:
    an abandoned ticket is `not_planned`, a delivered one is `completed`.
    """
    url = f"{restRoot}/repos/{repositoryOwner}/{repositoryName}/issues/{number}"
    requestJson(
        url, token, method="PATCH",
        payload={"state": "closed", "state_reason": reason},
    )


def assignTicket(token: str, number: int, assignee: str) -> None:
    """Assign an issue. Assignment marks the moment work actually begins."""
    url = (
        f"{restRoot}/repos/{repositoryOwner}/{repositoryName}/issues/{number}"
        "/assignees"
    )
    requestJson(url, token, method="POST", payload={"assignees": [assignee]})


def summarizeComment(raw: dict[str, Any]) -> CommentSummary:
    """Narrow GitHub's comment payload to the fields a caller actually uses."""
    return CommentSummary(
        id=raw["id"],
        author=(raw.get("user") or {}).get("login", "unknown"),
        createdAt=raw["created_at"],
        body=raw.get("body") or "",
        url=raw["html_url"],
    )


def readComments(token: str, number: int) -> list[CommentSummary]:
    """Every comment on one issue or pull request, oldest first as GitHub orders."""
    url = (
        f"{restRoot}/repos/{repositoryOwner}/{repositoryName}"
        f"/issues/{number}/comments?per_page=100"
    )
    return [summarizeComment(raw) for raw in requestJson(url, token)]


def readComment(token: str, commentId: int) -> CommentSummary:
    """Return one comment by its own id.

    **GitHub scopes a comment id to the repository, not to the issue it sits on**,
    so this takes no issue number. Accepting one would imply a check that is not
    happening: a mismatched pair would be ignored rather than refused.
    """
    url = (
        f"{restRoot}/repos/{repositoryOwner}/{repositoryName}"
        f"/issues/comments/{commentId}"
    )
    return summarizeComment(requestJson(url, token))


def postComment(token: str, number: int, body: str) -> CommentSummary:
    """Add one comment to an issue or a pull request, which are one endpoint here."""
    url = (
        f"{restRoot}/repos/{repositoryOwner}/{repositoryName}"
        f"/issues/{number}/comments"
    )
    return summarizeComment(
        requestJson(url, token, method="POST", payload={"body": body})
    )


def updateComment(token: str, commentId: int, body: str) -> CommentSummary:
    """Replace one comment's body in place, keeping its id and its place in the thread.

    Editing rather than deleting and re-posting is what lets a review that runs
    twice correct itself without losing the record that the first run happened.
    """
    url = (
        f"{restRoot}/repos/{repositoryOwner}/{repositoryName}"
        f"/issues/comments/{commentId}"
    )
    return summarizeComment(
        requestJson(url, token, method="PATCH", payload={"body": body})
    )


def deleteComment(token: str, commentId: int) -> None:
    """Remove one comment. GitHub keeps no copy, so the caller warns before calling."""
    url = (
        f"{restRoot}/repos/{repositoryOwner}/{repositoryName}"
        f"/issues/comments/{commentId}"
    )
    requestJson(url, token, method="DELETE")


def printCommentAsRawString(comment: CommentSummary) -> None:
    """Write one comment's body to stdout byte for byte, for revising and sending back.

    Same contract and same reason as `printBodyAsRawString`: rich hard-wraps,
    expands tabs and reads square brackets as markup, so anything that passes
    through it is unusable for round-tripping.
    """
    sys.stdout.write(comment["body"])


def showComments(comments: list[CommentSummary]) -> None:
    """Print comments for a human reader, never for round-tripping.

    The id is printed because it is what `comment-edit` and `comment-delete` take,
    and it appears nowhere in GitHub's own interface without hunting for it.
    """
    if not comments:
        console.print("[dim]no comments[/]")
        return
    for comment in comments:
        console.print(
            f"[bold cyan]{comment['id']}[/] "
            f"[bold]{escape(comment['author'])}[/] "
            f"[dim]{comment['createdAt']}[/]"
        )
        console.print(comment["body"], markup=False, highlight=False)
        console.print(f"[dim]{comment['url']}[/]\n")


def printBodyAsRawString(summary: TicketSummary) -> None:
    """Write a ticket body to stdout byte for byte, so it can be edited and sent back.

    Anything that passes through rich is unusable for that. rich hard-wraps to the
    terminal width, expands tabs to spaces, substitutes emoji shortcodes (`:warning:`
    becomes a glyph), and reads square brackets as style markup, a body containing
    `[bold]`, `[red]` or `[hotfix]` loses those words SILENTLY, with no error.
    Measured 2026-08-13: "use [bold] tags and [red] markers, plus [88] and [hotfix]"
    renders as "use  tags and  markers, plus [88] and ". Passing markup=False,
    highlight=False and soft_wrap=True narrows this but never eliminates it; tab
    expansion and emoji substitution survive every flag.

    Without this, the only way to fetch an editable body is to curl the API directly,
    which is forbidden. If a future operation is not covered here, add a subcommand
    rather than reaching around the tool.
    """
    sys.stdout.write(summary["body"])


def printTitleAsRawString(summary: TicketSummary) -> None:
    """Write a ticket title to stdout with nothing added but its own newline.

    Deliberately bare: /changelog-add copies this verbatim into CHANGELOG.md, so
    any decoration would end up committed.
    """
    print(summary["title"])


def showTicket(summary: TicketSummary) -> None:
    """Print a ticket for a human reader.

    Everything coming back from GitHub is escaped, and the body is printed with
    markup off entirely. Square brackets are rich's own syntax, so a body carrying
    `- [init] <title>` or `[#14]` would otherwise render with the bracket silently
    swallowed.
    """
    labelText = ", ".join(summary["labels"]) or "none"
    console.print(
        f"[bold cyan]{ticketRef(summary['number'])}[/] "
        f"[bold]{escape(summary['title'])}[/]"
    )
    console.print(f"[dim]{escape(summary['url'])}[/]")
    console.print(
        f"label: [magenta]{escape(labelText)}[/]   state: [yellow]{summary['state']}[/]"
    )
    if summary["assignees"]:
        console.print(f"assigned: [green]{escape(', '.join(summary['assignees']))}[/]")
    # Indexed directly rather than through a variable key: `TicketSummary` is a
    # TypedDict, so a non-literal key gives back `object` and the tuple unpacking
    # below stops being checkable.
    for related, label, tint in (
        (summary["blocked_by"], "blocked by", "red"),
        (summary["blocking"], "blocking", "yellow"),
    ):
        if related:
            listed = ", ".join(
                f"{ticketRef(number)} {title}" for number, title in related
            )
            console.print(f"{label}: [{tint}]{escape(listed)}[/]")
    if summary["body"]:
        console.print()
        # markup=False because rich reads square brackets as style tags, and a body
        # carrying [bold], [red] or [hotfix] would lose those words silently.
        # highlight=False stops it recoloring numbers and URLs inside prose it does
        # not own. Wrapping stays ON: this is the human-reading path and
        # terminal-width wrapping is wanted here. It is also why this cannot
        # round-trip, for that use printBodyAsRawString(), which touches nothing.
        console.print(summary["body"], markup=False, highlight=False)


def cmdCreate(arguments: argparse.Namespace) -> int:
    """File a ticket, place it on the board, and set its Status to Todo."""
    if arguments.label not in validLabels:
        console.print(f"[red]Unknown label {arguments.label!r}.[/]")
        console.print(f"Choose exactly one of: {', '.join(validLabels)}")
        return 1

    bodyPath = Path(arguments.bodyFile)
    if not bodyPath.is_file():
        console.print(f"[red]Body file not found:[/] {escape(str(bodyPath))}")
        return 1
    changes = readBodyFile(bodyPath)
    body = changes.text
    reportUnwrapping(changes)

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

    token = resolveToken()
    coordinates = readBoardCoordinates(token)

    summary = createTicket(token, arguments.label, arguments.title, body)
    console.print(
        f"[green]Filed[/] [bold cyan]{ticketRef(summary['number'])}[/] "
        f"{escape(summary['title'])}"
    )

    nodeId = readIssueNodeId(token, summary["number"])
    itemId = placeOnBoard(token, coordinates, nodeId)
    setBoardStatus(token, coordinates, itemId, arguments.status)
    console.print(f"[green]On the board[/] with Status [cyan]{arguments.status}[/]")
    console.print(summary["url"])
    return 0


def cmdShow(arguments: argparse.Namespace) -> int:
    """Print one ticket for a human reader.

    `show` renders; `export-as-source` does not. That is the whole distinction, and the
    names are meant to carry it without anyone having to read this file. This one is
    free to change its formatting at any time, which is exactly why its output must
    never be sent back, use `export-as-source` for that.
    """
    token = resolveToken()
    showTicket(readTicket(token, arguments.number))
    if arguments.comments:
        console.print()
        showComments(readComments(token, arguments.number))
    return 0


def cmdExportAsSource(arguments: argparse.Namespace) -> int:
    """Emit one field of a ticket verbatim, for a skill that will send it back.

    Separate from `show` because displaying and round-tripping are different actions
    with incompatible contracts: `show` may reformat freely, `export-as-source` must
    never transform a single byte. Both of them "read" a ticket, which is why neither is
    called that, the name has to say what comes out.
    """
    summary = readTicket(resolveToken(), arguments.number)
    if arguments.body:
        printBodyAsRawString(summary)
    else:
        printTitleAsRawString(summary)
    return 0


def cmdStart(arguments: argparse.Namespace) -> int:
    """Assign a ticket and move it to In Progress."""
    token = resolveToken()
    summary = readTicket(token, arguments.number)

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        console.print(
            f"would assign {ticketRef(summary['number'])} to {arguments.assignee}"
        )
        console.print("would set Status to [cyan]In Progress[/]")
        return 0

    assignTicket(token, arguments.number, arguments.assignee)
    coordinates = readBoardCoordinates(token)
    itemId = findBoardItem(token, coordinates, arguments.number)
    if itemId is None:
        itemId = placeOnBoard(
            token, coordinates, readIssueNodeId(token, arguments.number)
        )
        console.print("[yellow]Ticket was not on the board; added it.[/]")
    setBoardStatus(token, coordinates, itemId, "In Progress")

    console.print(
        f"[green]Started[/] [bold cyan]{ticketRef(summary['number'])}[/] "
        f"{summary['title']}"
    )
    console.print(
        f"assigned to [green]{arguments.assignee}[/], "
        "Status [cyan]In Progress[/]"
    )
    return 0


def cmdEdit(arguments: argparse.Namespace) -> int:
    """Revise a filed ticket in place."""
    if arguments.label is not None and arguments.label not in validLabels:
        console.print(f"[red]Unknown label {arguments.label!r}.[/]")
        console.print(f"Choose exactly one of: {', '.join(validLabels)}")
        return 1

    body: str | None = None
    if arguments.bodyFile is not None:
        bodyPath = Path(arguments.bodyFile)
        if not bodyPath.is_file():
            console.print(f"[red]Body file not found:[/] {escape(str(bodyPath))}")
            return 1
        changes = readBodyFile(bodyPath)
        body = changes.text
        reportUnwrapping(changes)

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

    token = resolveToken()
    editTicket(token, arguments.number, arguments.title, body, arguments.label)

    # Read the ticket back and confirm what landed. `edit` replaces the WHOLE body
    # and GitHub offers no conflict detection, so a revision drafted against a copy
    # exported even minutes earlier silently discards whatever changed in between,
    # no error, no conflict marker, the other edit simply gone. Verifying cannot
    # prevent that, but it makes it visible immediately to whoever caused it, which
    # is the difference between losing data and failing a command. It is also what
    # makes deleting the local draft safe: once this passes, the copy is provably
    # redundant, and a lingering export is the thing a later revision gets drafted
    # against by mistake.
    summary = readTicket(token, arguments.number)
    mismatches: list[str] = []
    if body is not None and summary["body"] != body:
        mismatches.append("body")
    if arguments.title is not None and summary["title"] != arguments.title:
        mismatches.append("title")
    if arguments.label is not None and arguments.label not in summary["labels"]:
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
        console.print(summary["url"])
        return 1

    console.print(
        f"[green]Edited[/] [bold cyan]{ticketRef(summary['number'])}[/] "
        f"{escape(summary['title'])}"
    )
    console.print("[dim]verified against the filed ticket[/]")
    console.print(summary["url"])
    return 0


def verifyCommentBody(token: str, comment: CommentSummary, sent: str) -> bool:
    """Read one comment back and report whether it matches what was sent.

    The same duty `edit` performs on a ticket body, and for the same reason: a
    write that did not land should fail loudly rather than report success.

    Returns a bool rather than an exit code because `pr.py` shares this and the
    two tools number their failures differently: 1 there means no open pull
    request, so returning it from here would report the wrong thing.
    """
    if readComment(token, comment["id"])["body"] == sent:
        console.print("[dim]verified against the filed comment[/]")
        console.print(comment["url"])
        return True
    console.print(
        "[red]The comment did not land cleanly:[/] what GitHub holds differs from "
        "what was sent."
    )
    console.print(comment["url"])
    return False


def cmdComment(arguments: argparse.Namespace) -> int:
    """Add one comment to a ticket."""
    bodyPath = Path(arguments.bodyFile)
    if not bodyPath.is_file():
        console.print(f"[red]Body file not found:[/] {escape(str(bodyPath))}")
        return 1
    changes = readBodyFile(bodyPath)
    body = changes.text
    if arguments.dryRun:
        console.print(f"[yellow]Dry run[/] comment on {ticketRef(arguments.number)}:")
        console.print(body, markup=False, highlight=False)
        return 0
    token = resolveToken()
    comment = postComment(token, arguments.number, body)
    reportUnwrapping(changes)
    console.print(
        f"[green]Commented on[/] [bold cyan]{ticketRef(arguments.number)}[/] "
        f"as comment [bold cyan]{comment['id']}[/]"
    )
    return 0 if verifyCommentBody(token, comment, body) else 1


def cmdCommentExport(arguments: argparse.Namespace) -> int:
    """Emit one comment's body verbatim, for a caller that will send it back.

    Separate from `comment-list` for the reason `export-as-source` is separate from
    `show`: displaying and round-tripping are different actions with incompatible
    contracts.
    """
    printCommentAsRawString(readComment(resolveToken(), arguments.commentId))
    return 0


def cmdCommentEdit(arguments: argparse.Namespace) -> int:
    """Replace one comment's body, keeping its id and its place in the thread."""
    bodyPath = Path(arguments.bodyFile)
    if not bodyPath.is_file():
        console.print(f"[red]Body file not found:[/] {escape(str(bodyPath))}")
        return 1
    changes = readBodyFile(bodyPath)
    body = changes.text
    if arguments.dryRun:
        console.print(f"[yellow]Dry run[/] rewrite of comment {arguments.commentId}:")
        console.print(body, markup=False, highlight=False)
        return 0
    token = resolveToken()
    comment = updateComment(token, arguments.commentId, body)
    reportUnwrapping(changes)
    console.print(f"[green]Edited comment[/] [bold cyan]{comment['id']}[/]")
    return 0 if verifyCommentBody(token, comment, body) else 1


def cmdCommentDelete(arguments: argparse.Namespace) -> int:
    """Remove one comment, after printing what is about to be lost.

    GitHub keeps no copy and offers no undo, so the body is shown first. A
    `--dry-run` shows it without removing anything.
    """
    token = resolveToken()
    comment = readComment(token, arguments.commentId)
    console.print(
        f"[yellow]GitHub keeps no copy of a deleted comment.[/] About to remove "
        f"comment [bold cyan]{comment['id']}[/] by {escape(comment['author'])}:"
    )
    console.print(comment["body"], markup=False, highlight=False)
    if arguments.dryRun:
        console.print("[yellow]Dry run: nothing was removed.[/]")
        return 0
    deleteComment(token, arguments.commentId)
    console.print("[green]Deleted.[/]")
    return 0


def cmdClose(arguments: argparse.Namespace) -> int:
    """Close a ticket and move it to Done.

    Merging a pull request whose body carries `Closes #N` already closes the
    issue, which leaves the board behind, an already-closed issue is the normal
    case after a merge, not an error, so this command still sets the Status and
    only skips the close itself.
    """
    reason = "completed" if arguments.reason == "completed" else "not_planned"
    token = resolveToken()
    summary = readTicket(token, arguments.number)
    alreadyClosed = summary["state"] == "closed"

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        if alreadyClosed:
            console.print(
                f"{ticketRef(summary['number'])} is already closed; "
                "would leave the issue alone"
            )
        else:
            console.print(
                f"would close {ticketRef(summary['number'])} as [cyan]{reason}[/]"
            )
        console.print("would set Status to [cyan]Done[/]")
        return 0

    if alreadyClosed:
        console.print(
            f"[yellow]{ticketRef(arguments.number)} is already closed[/], "
            "setting Status only."
        )
    else:
        closeTicket(token, arguments.number, reason)
    coordinates = readBoardCoordinates(token)
    itemId = findBoardItem(token, coordinates, arguments.number)
    if itemId is not None:
        setBoardStatus(token, coordinates, itemId, "Done")
    else:
        console.print(
            "[yellow]Ticket was not on the board; only the issue was closed.[/]"
        )

    verb = "Completed" if reason == "completed" else "Abandoned"
    console.print(
        f"[green]{verb}[/] [bold cyan]{ticketRef(summary['number'])}[/] "
        f"{escape(summary['title'])}"
    )
    return 0


def cmdStatus(arguments: argparse.Namespace) -> int:
    """Move a ticket to a named Status on the board."""
    token = resolveToken()
    coordinates = readBoardCoordinates(token)

    if arguments.setStatus not in coordinates["statusOptionIds"]:
        console.print(f"[red]Unknown Status {arguments.setStatus!r}.[/]")
        console.print(f"The board offers: {', '.join(coordinates['statusOptionIds'])}")
        return 1

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        console.print(
            f"would set {ticketRef(arguments.number)} to [cyan]{arguments.setStatus}[/]"
        )
        return 0

    itemId = findBoardItem(token, coordinates, arguments.number)
    if itemId is None:
        console.print(
            f"[red]Issue {ticketRef(arguments.number)} is not on the board.[/]"
        )
        return 1

    setBoardStatus(token, coordinates, itemId, arguments.setStatus)
    console.print(
        f"[green]{ticketRef(arguments.number)}[/] is now [cyan]{arguments.setStatus}[/]"
    )
    return 0


def cmdList(arguments: argparse.Namespace) -> int:
    """List open tickets, optionally narrowed to one Status."""
    token = resolveToken()
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
    coordinates = readBoardCoordinates(token)
    cursor: str | None = None
    rows: list[tuple[str, int, str, str]] = []
    nonTickets: list[tuple[str, str]] = []
    unreadableCount = 0

    while True:
        data = requestGraphql(
            token, query, {"projectId": coordinates["projectId"], "cursor": cursor}
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
            statusOrder.index(row[0]) if row[0] in statusOrder else 99,
            row[1],
        )
    )
    for statusName, number, title, labelText in rows:
        console.print(
            f"[cyan]{statusName:<12}[/] [bold]{ticketRef(number):<8}[/] {title}  "
            f"[magenta]{labelText}[/]"
        )
    return 0


def cmdBlock(arguments: argparse.Namespace) -> int:
    """Record, drop, or list what a ticket is waiting on."""
    token = resolveToken()
    number = arguments.number

    if arguments.dryRun:
        console.print("[yellow]Dry run. Nothing was changed.[/]")
        for blocker in arguments.blockedBy:
            console.print(
                f"would mark {ticketRef(number)} blocked by {ticketRef(blocker)}"
            )
        for blocker in arguments.unblock:
            console.print(
                f"would clear {ticketRef(blocker)} as a blocker of "
                f"{ticketRef(number)}"
            )
        return 0

    for blocker in arguments.blockedBy:
        if blocker == number:
            console.print("[red]A ticket cannot block itself.[/]")
            return 1
        addBlockedBy(token, number, blocker)
        console.print(
            f"[green]{ticketRef(number)}[/] is now blocked by "
            f"[bold cyan]{ticketRef(blocker)}[/]"
        )

    for blocker in arguments.unblock:
        removeBlockedBy(token, number, blocker)
        console.print(
            f"[green]{ticketRef(number)}[/] no longer blocked by "
            f"[bold cyan]{ticketRef(blocker)}[/]"
        )

    blockedBy = readDependencies(token, number, "blocked_by")
    blocking = readDependencies(token, number, "blocking")
    if not blockedBy and not blocking:
        console.print(f"[dim]{ticketRef(number)} has no dependencies.[/]")
        return 0

    for label, related, tint in (
        ("blocked by", blockedBy, "red"),
        ("blocking", blocking, "yellow"),
    ):
        for relatedNumber, title in related:
            console.print(
                f"{label}: [{tint}]{ticketRef(relatedNumber)}[/] {escape(title)}"
            )
    return 0


def buildParser() -> argparse.ArgumentParser:
    """Assemble the command line, one subcommand per cmd-prefixed handler."""
    parser = argparse.ArgumentParser(
        prog="ticket.py",
        description="File and move pybers tickets on GitHub Issues and the "
        "Project board.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    createParser = subparsers.add_parser("create", help="file a new ticket")
    createParser.add_argument(
        "--label", required=True, help=f"one of: {', '.join(validLabels)}"
    )
    createParser.add_argument("--title", required=True, help="issue title, verbatim")
    createParser.add_argument(
        "--body-file", dest="bodyFile", required=True, help="drafted body"
    )
    createParser.add_argument(
        "--status", default="Todo", help="starting Status (default: Todo)"
    )
    createParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    createParser.set_defaults(handler=cmdCreate)

    showParser = subparsers.add_parser(
        "show",
        help="RENDERED for reading: colored, wrapped to your terminal. "
        "Never copy from it.",
    )
    showParser.add_argument("number", type=ticketNumber)
    showParser.add_argument(
        "--comments", action="store_true",
        help="also print the ticket's comments, with the id each is reached by",
    )
    showParser.set_defaults(handler=cmdShow)

    exportParser = subparsers.add_parser(
        "export-as-source",
        help="The SOURCE, byte for byte, nothing rendered: the form to edit and send "
        "back to `edit`. Contrast `show`, which renders.",
    )
    exportParser.add_argument("number", type=ticketNumber)
    # Mutually exclusive and required, because these never compose: each is a whole
    # output, not a modifier on a shared one.
    fieldGroup = exportParser.add_mutually_exclusive_group(required=True)
    fieldGroup.add_argument(
        "--body", action="store_true", help="the body, byte for byte, nothing rendered"
    )
    fieldGroup.add_argument(
        "--title", action="store_true", help="the title, with nothing added"
    )
    exportParser.set_defaults(handler=cmdExportAsSource)

    startParser = subparsers.add_parser("start", help="assign and move to In Progress")
    startParser.add_argument("number", type=ticketNumber)
    startParser.add_argument("--assignee", default=repositoryOwner)
    startParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    startParser.set_defaults(handler=cmdStart)

    editParser = subparsers.add_parser("edit", help="revise a filed ticket")
    editParser.add_argument("number", type=ticketNumber)
    editParser.add_argument("--title", default=None, help="replace the title")
    editParser.add_argument(
        "--body-file", dest="bodyFile", default=None, help="replace the body"
    )
    editParser.add_argument(
        "--label", default=None, help=f"one of: {', '.join(validLabels)}"
    )
    editParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    editParser.set_defaults(handler=cmdEdit)

    commentParser = subparsers.add_parser(
        "comment", help="add a comment to a ticket"
    )
    commentParser.add_argument("number", type=ticketNumber)
    commentParser.add_argument(
        "--body-file", dest="bodyFile", required=True,
        help="drafted comment body, a file so lists and code fences survive",
    )
    commentParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    commentParser.set_defaults(handler=cmdComment)

    commentExportParser = subparsers.add_parser(
        "comment-export",
        help="The SOURCE of one comment, byte for byte: the form to revise and "
        "send back to `comment-edit`.",
    )
    commentExportParser.add_argument("commentId", type=int)
    commentExportParser.set_defaults(handler=cmdCommentExport)

    commentEditParser = subparsers.add_parser(
        "comment-edit", help="replace a comment's body in place"
    )
    commentEditParser.add_argument("commentId", type=int)
    commentEditParser.add_argument(
        "--body-file", dest="bodyFile", required=True, help="revised comment body"
    )
    commentEditParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    commentEditParser.set_defaults(handler=cmdCommentEdit)

    commentDeleteParser = subparsers.add_parser(
        "comment-delete", help="delete a comment (permanent, no GitHub undo)"
    )
    commentDeleteParser.add_argument("commentId", type=int)
    commentDeleteParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    commentDeleteParser.set_defaults(handler=cmdCommentDelete)

    closeParser = subparsers.add_parser(
        "close", help="close a ticket and set Status to Done"
    )
    closeParser.add_argument("number", type=ticketNumber)
    closeParser.add_argument(
        "--reason",
        choices=("completed", "not-planned"),
        default="completed",
        help="completed for delivered work, not-planned for an abandoned ticket",
    )
    closeParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    closeParser.set_defaults(handler=cmdClose)

    statusParser = subparsers.add_parser("status", help="move a ticket to a Status")
    statusParser.add_argument("number", type=ticketNumber)
    statusParser.add_argument("--set", dest="setStatus", required=True)
    statusParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    statusParser.set_defaults(handler=cmdStatus)

    listParser = subparsers.add_parser("list", help="list tickets on the board")
    listParser.add_argument("--status", default=None, help="narrow to one Status")
    listParser.set_defaults(handler=cmdList)

    blockParser = subparsers.add_parser(
        "block", help="record or list what a ticket is waiting on"
    )
    blockParser.add_argument("number", type=ticketNumber)
    blockParser.add_argument(
        "--by",
        dest="blockedBy",
        type=ticketNumber,
        nargs="+",
        default=[],
        metavar="N",
        help="issue numbers that must finish first",
    )
    blockParser.add_argument(
        "--unblock",
        type=ticketNumber,
        nargs="+",
        default=[],
        metavar="N",
        help="issue numbers that no longer block this one",
    )
    blockParser.add_argument("--dry-run", dest="dryRun", action="store_true")
    blockParser.set_defaults(handler=cmdBlock)

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
