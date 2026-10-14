#!/usr/bin/env python3
"""\
The session dashboard, `workarea/dashboard.md`, read and written in its one shape.

A first line giving the active ticket's stage and title, then its tasks in state
order, the queue of tickets after it, and the tickets that recently merged.

UPDATES
2026-10-14  Written for PYB-211.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/14"

import re
from dataclasses import dataclass, field

from tools.workflow.lib import github
from tools.workflow.lib.pull_request import findTicketPullRequest, readCurrentBranch
from tools.workflow.lib.shared import readTicketNumber, repositoryRoot

dashboardPath = repositoryRoot / "workarea" / "dashboard.md"
tasksHeading: str = "## Tasks"
queueHeading: str = "## Tickets Queue"
completedHeading: str = "## Tickets Recently Completed"
recentLimit: int = 20
noTicket: str = "None"
# A ticket's stage, three characters each so every title lines up.
workCode: str = "WiP"
draftCode: str = "dPR"
reviewCode: str = "REV"
otherCode: str = "---"
noteSeparator: str = " › "
blockedNote: str = "blocked by "

# A task's state is its first character, and this is the order the section keeps.
stateOrder: tuple[str, ...] = ("◼", "◻", "✔")
ticketKeyPattern: re.Pattern[str] = re.compile(r"\b[A-Z]{3,4}-\d+\b")


class DashboardError(RuntimeError):
    """The dashboard is not in the shape this module reads and writes."""


@dataclass
class Dashboard:
    """The dashboard's four parts, each section a list of its lines."""

    status: str = noTicket
    tasks: list[str] = field(default_factory=list)
    queue: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)


def parseBoard(text: str) -> Dashboard:
    """Read a dashboard, refusing one with no status line or with an unknown section."""
    lines = [line.rstrip() for line in text.splitlines()]
    if not lines or not lines[0] or lines[0].startswith("## "):
        raise DashboardError("the dashboard does not open with its status line")
    board = Dashboard(status=lines[0])
    sections = {
        tasksHeading: board.tasks, queueHeading: board.queue,
        completedHeading: board.completed,
    }
    current: list[str] | None = None
    for line in lines[1:]:
        if line.startswith("## "):
            if line not in sections:
                raise DashboardError(f"the dashboard has an unknown section {line!r}")
            current = sections[line]
        elif line and current is not None:
            current.append(line)
        elif line:
            raise DashboardError(f"a line sits outside every section: {line!r}")
    return board


def sortTasks(tasks: list[str]) -> list[str]:
    """Return tasks in state order, keeping each state's own order."""
    def rank(task: str) -> int:
        return stateOrder.index(task[0]) if task[:1] in stateOrder else len(stateOrder)
    return sorted(tasks, key=rank)


def formatStage(openPullRequest: bool, draft: bool, boardStatus: str) -> str:
    """Return a ticket's stage: its pull request's state, else in progress or other."""
    if openPullRequest:
        return draftCode if draft else reviewCode
    return workCode if boardStatus == "In Progress" else otherCode


def formatStatusLine(key: str, title: str, stage: str) -> str:
    """Return the status line for an active ticket, or for none when `key` is empty."""
    return f"{stage} · {key}: {title}" if key else noTicket


def readStatusKey(status: str) -> str:
    """Return the ticket key a status line names, or an empty string."""
    found = ticketKeyPattern.search(status)
    return found.group() if found else ""


def setBlockers(line: str, blockers: list[str]) -> str:
    """Return a line whose `› blocked by` note names these blockers alone."""
    head, *notes = line.split(noteSeparator)
    kept = [note for note in notes if not note.startswith(blockedNote)]
    if blockers:
        kept.insert(0, blockedNote + ", ".join(blockers))
    return noteSeparator.join([head, *kept])


def readBlockers(line: str) -> list[str]:
    """Return the blockers a line's `› blocked by` note names."""
    for note in line.split(noteSeparator)[1:]:
        if note.startswith(blockedNote):
            return note.removeprefix(blockedNote).split(", ")
    return []


def recordMerge(board: Dashboard, key: str, pullRequest: int) -> None:
    """Move a merged ticket into the recent list, clear it as a blocker and as focus."""
    if readStatusKey(board.status) == key:
        board.status = noTicket
    def clear(line: str) -> str:
        return setBlockers(line, [name for name in readBlockers(line) if name != key])
    board.tasks = [
        clear(line) for line in board.tasks if key not in line.split(noteSeparator)[0]
    ]
    board.queue = [clear(line) for line in board.queue if readStatusKey(line) != key]
    entry = f"{key} merged as PR #{pullRequest}"
    if entry not in board.completed:
        board.completed = [entry, *board.completed][:recentLimit]


def renderBoard(board: Dashboard) -> str:
    """Return the dashboard's text, tasks in state order and the recent list trimmed."""
    parts = [board.status]
    for heading, lines in (
        (tasksHeading, sortTasks(board.tasks)), (queueHeading, board.queue),
        (completedHeading, board.completed[:recentLimit]),
    ):
        parts += ["", heading, *lines]
    return "\n".join(parts) + "\n"


def readDashboard() -> Dashboard:
    """Return the dashboard, or an empty one when the file does not exist yet."""
    if not dashboardPath.is_file():
        return Dashboard()
    return parseBoard(dashboardPath.read_text(encoding="utf-8"))


def writeDashboard(board: Dashboard) -> bool:
    """Write the dashboard in its one shape, returning False when nothing changed."""
    text = renderBoard(board)
    if dashboardPath.is_file() and dashboardPath.read_text(encoding="utf-8") == text:
        return False
    dashboardPath.parent.mkdir(parents=True, exist_ok=True)
    dashboardPath.write_text(text, encoding="utf-8")
    return True


def findFocusKey(board: Dashboard, focus: str | None) -> str:
    """Return the ticket in focus: the one named, else the branch's, else the line's."""
    if focus is not None:
        return focus
    try:
        number = readTicketNumber(readCurrentBranch())
    except RuntimeError:
        number = ""
    if number:
        return github.formatTicketRef(int(number))
    return readStatusKey(board.status)


def updateDashboard(token: str, board: Dashboard, focus: str | None = None) -> None:
    """Rewrite the status line for the ticket in focus and its queue's blocker notes."""
    key = findFocusKey(board, focus)
    if key:
        number = github.parseTicketNumber(key)
        found = findTicketPullRequest(token, number)
        stage = formatStage(
            found is not None, bool(found and found.isDraft),
            github.readBoardStatus(token, number),
        )
        title = github.readTicket(token, number).title
        board.status = formatStatusLine(key, title, stage)
        board.queue = [line for line in board.queue if readStatusKey(line) != key]
    else:
        board.status = noTicket
    board.queue = [updateBlockerNote(token, line) for line in board.queue]


def updateBlockerNote(token: str, line: str) -> str:
    """Return a queue line whose `› blocked by` note names its open blockers alone."""
    key = readStatusKey(line)
    if not key:
        return line
    blockers = github.readOpenBlockers(token, github.parseTicketNumber(key))
    return setBlockers(line, [github.formatTicketRef(number) for number in blockers])


def saveStageChange(token: str, focus: str | None = None) -> str:
    """Save the dashboard after a stage changed, returning a warning or ''."""
    try:
        board = readDashboard()
        updateDashboard(token, board, focus)
        writeDashboard(board)
    except (DashboardError, RuntimeError, OSError) as exc:
        return f"The dashboard was not updated: {exc}"
    return ""


def saveMerge(key: str, pullRequest: int) -> str:
    """Record a merge on the dashboard, returning a warning or ''."""
    try:
        board = readDashboard()
        recordMerge(board, key, pullRequest)
        writeDashboard(board)
    except (DashboardError, OSError) as exc:
        return f"The dashboard was not updated: {exc}"
    return ""
