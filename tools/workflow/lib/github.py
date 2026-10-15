#!/usr/bin/env python3
"""\
The GitHub client every tooling script shares: issues, pull request comments and the
pybers Project board.

Talks to GitHub over urllib: REST for issues, GraphQL for the Project board. Never
shells out to `gh` or `jq`, per the house rules in tools/workflow/README.md.

Authentication resolves in this order, and there is deliberately no third fallback, so
a missing token is a loud failure, never a guess:
    1. GITHUB_TOKEN or GH_TOKEN in the environment
    2. a GITHUB_TOKEN= line in the git-ignored .dev.vars at the repository root

UPDATES
2026-10-14  `readAuthenticatedLogin` and `readPermission`, for a merge's approval
            gate, for PYB-156.
2026-10-14  `readBoardStatus`, a ticket's Status for the dashboard, for PYB-211.
2026-10-14  `readOpenBlockers`, for the dashboard's blocked-by notes, for PYB-211.
2026-10-13  Split from `ticket.py`, which keeps its commands, for PYB-204. The history
            of this code before the split is in that file's UPDATES.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/12"

import argparse
import json
import os
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape

from tools.workflow.lib.shared import repositoryRoot

# Lazy, since the job posting the readiness comment installs rich alone and imports
# this module without ever formatting a body.
lazy from tools.workflow.lib import github_body

console = Console()

repositoryOwner: str = "rpulivella"
repositoryName: str = "pybers"
projectNumber: int = 3


def readTicketPrefix() -> str:
    """Return the ticket key `pyproject.toml` declares, so it has one home."""
    config = repositoryRoot / "pyproject.toml"
    with config.open("rb") as handle:
        return str(tomllib.load(handle)["tool"]["pybers"]["ticketPrefix"])


ticketPrefix: str = readTicketPrefix()


def parseTicketNumber(value: str) -> int:
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


def formatTicketRef(number: int) -> str:
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


@dataclass(frozen=True)
class TicketSummary:
    """A filed issue, as the skills need to see it."""

    number: int
    title: str
    body: str
    labels: list[str]
    state: str
    assignees: list[str]
    url: str
    blockedBy: list[tuple[int, str]]
    blocking: list[tuple[int, str]]


@dataclass(frozen=True)
class CommentSummary:
    """One comment on a filed issue or pull request, as a caller needs to see it."""

    id: int
    author: str
    createdAt: str
    body: str
    url: str


@dataclass(frozen=True)
class BoardCoordinates:
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


def isFormatterPresent() -> bool:
    """Report whether this interpreter can format a body, saying what it lacks."""
    try:
        github_body.PostedBody  # noqa: B018  # touching a name is what loads it
    except ModuleNotFoundError as exc:
        console.print(
            f"[red]{escape(sys.executable)} lacks {exc.name}, which carrying a body "
            "to or from GitHub needs. It is one of this repository's dev extras.[/]"
        )
        return False
    return True


def readBodyFile(path: Path) -> github_body.PostedBody | None:
    """Read a drafted body and format it for GitHub, or say why it cannot be posted.

    Read with `newline=""`, so a line ending the author chose reaches the formatter
    untranslated. None after printing the refusal, which names the lines whose
    rendering would change.
    """
    if not isFormatterPresent():
        return None
    try:
        return github_body.formatBodyForPosting(
            path.read_text(encoding="utf-8", newline="")
        )
    except github_body.BodyRenderingError as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return None


def reportTidying(posted: github_body.PostedBody) -> None:
    """Say how many lines formatting changed, so it is never a silent rewrite."""
    if posted.tidied:
        console.print(
            f"[dim]tidied {posted.tidied} line(s) for GitHub, "
            "which renders them as the file reads[/]"
        )


def writeBodyForEditing(body: str) -> bool:
    """Write a body to stdout as a file means it, or say why it cannot be exported.

    Never through rich, which hard-wraps, expands tabs, substitutes emoji shortcodes
    and reads square brackets as markup, so `[hotfix]` would vanish silently.
    """
    if not isFormatterPresent():
        return False
    try:
        sys.stdout.write(github_body.convertBodyForEditing(body))
    except github_body.BodyRenderingError as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return False
    return True


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
    secretsPath = repositoryRoot / ".dev.vars"
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
        blockedBy=readDependencies(token, number, "blocked_by"),
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


def readBoardStatus(token: str, number: int) -> str:
    """Return a ticket's Status on this repository's board, or '' when absent."""
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) {
        issue(number: $number) {
          projectItems(first: 20) {
            nodes {
              project { number }
              fieldValueByName(name: "Status") {
                ... on ProjectV2ItemFieldSingleSelectValue { name }
              }
            }
          }
        }
      }
    }
    """
    data = requestGraphql(
        token, query,
        {"owner": repositoryOwner, "name": repositoryName, "number": number},
    )
    issue = data["repository"]["issue"] or {}
    for item in (issue.get("projectItems") or {}).get("nodes") or []:
        if item["project"]["number"] == projectNumber:
            return str((item.get("fieldValueByName") or {}).get("name") or "")
    return ""


def readAuthenticatedLogin(token: str) -> str:
    """Return the login the token acts as."""
    return str((requestJson(f"{restRoot}/user", token) or {}).get("login", ""))


def readPermission(token: str, login: str) -> str:
    """Return a user's permission on this repository: admin, write, read or none."""
    url = (
        f"{restRoot}/repos/{repositoryOwner}/{repositoryName}"
        f"/collaborators/{login}/permission"
    )
    return str((requestJson(url, token) or {}).get("permission", "none"))


def readOpenBlockers(token: str, number: int) -> list[int]:
    """Return the issues still open that block this one, by number."""
    url = (
        f"{restRoot}/repos/{repositoryOwner}/{repositoryName}"
        f"/issues/{number}/dependencies/blocked_by"
    )
    issues = requestJson(url, token, apiVersion=dependencyApiVersion) or []
    return [int(issue["number"]) for issue in issues if issue.get("state") == "open"]


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
        blockedBy=[],
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
        {"projectId": coordinates.projectId, "contentId": issueNodeId},
    )
    return str(data["addProjectV2ItemById"]["item"]["id"])


def setBoardStatus(
    token: str,
    coordinates: BoardCoordinates,
    itemId: str,
    status: str,
) -> None:
    """Set a board item's Status to one of the pipeline's named options."""
    optionId = coordinates.statusOptionIds.get(status)
    if optionId is None:
        known = ", ".join(coordinates.statusOptionIds)
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
            "projectId": coordinates.projectId,
            "itemId": itemId,
            "fieldId": coordinates.statusFieldId,
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
            token, query, {"projectId": coordinates.projectId, "cursor": cursor}
        )
        page = data["node"]["items"]
        for item in page["nodes"]:
            content = item.get("content") or {}
            if content.get("number") == number:
                return str(item["id"])
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
        raise RuntimeError(f"Issue {formatTicketRef(number)} was not found.")
    return str(issue["id"])


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
        blockedBy=readDependencies(token, number, "blocked_by"),
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


def reopenTicket(token: str, number: int) -> None:
    """Reopen an issue a merge closed, for a ticket more than one pull request carries.

    The closing keyword is what links a pull request to its ticket, so the link is
    worth the close even when the work continues. Reopening is the correction, and
    the caller restores the Status the board moved.
    """
    url = f"{restRoot}/repos/{repositoryOwner}/{repositoryName}/issues/{number}"
    requestJson(url, token, method="PATCH", payload={"state": "open"})


def moveTicketStatus(token: str, number: int, status: str) -> None:
    """Set one ticket's board Status, for a caller that is not the status command."""
    coordinates = readBoardCoordinates(token)
    itemId = findBoardItem(token, coordinates, number)
    if itemId is None:
        raise RuntimeError(f"Issue #{number} is not on the board.")
    setBoardStatus(token, coordinates, itemId, status)


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
