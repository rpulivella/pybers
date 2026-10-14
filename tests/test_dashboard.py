#!/usr/bin/env python3
"""\
The session dashboard's shape: its status line, sections and state order.

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

import pytest

from tools.workflow.lib import dashboard as dashboardModule
from tools.workflow.lib.dashboard import (
    Dashboard,
    DashboardError,
    findFocusKey,
    formatStage,
    formatStatusLine,
    parseBoard,
    readStatusKey,
    recentLimit,
    recordMerge,
    renderBoard,
    saveMerge,
    setBlockers,
)

dashboard: str = """WiP · PYB-211: Give session tasks a status line
\n## Tasks
✔ PYB-211 AC 1 status line
◻ PYB-211 AC 3 queue › blocked by PYB-157
◼ PYB-211 AC 2 state order
\n## Tickets Queue
PYB-156 make the repository public
PYB-164 accept pull requests from anyone › blocked by PYB-156
\n## Tickets Recently Completed
PYB-193 merged as PR #210
"""


def testADashboardReadsBackAsWritten() -> None:
    written = renderBoard(parseBoard(dashboard))
    assert renderBoard(parseBoard(written)) == written


def testTasksRunInProgressThenPendingThenDone() -> None:
    tasks = parseBoard(renderBoard(parseBoard(dashboard))).tasks
    assert [task[0] for task in tasks] == ["◼", "◻", "✔"]


@pytest.mark.parametrize(("open", "draft", "status", "stage"), [
    (True, True, "In Progress", "dPR"),
    (True, False, "Code Review", "REV"),
    (False, False, "In Progress", "WiP"),
    (False, False, "Todo", "---"),
    (False, False, "Done", "---"),
    (False, False, "", "---"),
])
def testTheStageFollowsThePullRequestThenTheBoard(
    open: bool, draft: bool, status: str, stage: str
) -> None:
    assert formatStage(open, draft, status) == stage


def testTheStatusLineGivesTheStageThenTheTicket() -> None:
    assert formatStatusLine("PYB-211", "A title", "WiP") == "WiP · PYB-211: A title"
    assert formatStatusLine("", "", "") == "None"


def testTheStatusLineGivesItsKeyOrNone() -> None:
    assert readStatusKey("dPR · PYB-211: A title") == "PYB-211"
    assert readStatusKey("None") == ""


def testAMergeLeavesTheTasksAndQueueForTheRecentList() -> None:
    board = parseBoard(dashboard)
    recordMerge(board, "PYB-156", 212)
    assert board.completed[0] == "PYB-156 merged as PR #212"
    assert board.queue == ["PYB-164 accept pull requests from anyone"]


def testTheRecentListKeepsOnlyTheNewest() -> None:
    merged = [f"PYB-{n} merged as PR #{n}" for n in range(recentLimit)]
    board = Dashboard(completed=merged)
    recordMerge(board, "PYB-999", 999)
    assert len(board.completed) == recentLimit
    assert board.completed[0] == "PYB-999 merged as PR #999"


@pytest.mark.parametrize("text", [
    "## Tasks\n◼ a task\n",
    "None\n\n## Notes\nsomething\n",
    "None\nstray line\n",
])
def testADashboardOutOfShapeIsRefused(text: str) -> None:
    with pytest.raises(DashboardError):
        parseBoard(text)


@pytest.mark.parametrize(("line", "blockers", "rebuilt"), [
    ("A-1 x › blocked by A-2", ["A-2"], "A-1 x › blocked by A-2"),
    ("A-1 x › blocked by A-2, 168", ["A-2"], "A-1 x › blocked by A-2"),
    ("A-1 x", ["A-2"], "A-1 x › blocked by A-2"),
    ("A-1 x › blocked by A-2", [], "A-1 x"),
    ("A-1 x › deferred", ["A-2"], "A-1 x › blocked by A-2 › deferred"),
])
def testABlockedByNoteNamesTheOpenBlockersAlone(
    line: str, blockers: list[str], rebuilt: str
) -> None:
    assert setBlockers(line, blockers) == rebuilt


def testAMergeOfTheTicketInFocusClearsTheFocus() -> None:
    board = parseBoard(dashboard)
    recordMerge(board, "PYB-211", 212)
    assert board.status == "None"


def testANamedFocusBeatsTheBranch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tools.workflow.lib.dashboard.readCurrentBranch", lambda: "chore/211-a-title"
    )
    assert findFocusKey(parseBoard(dashboard), "PYB-156") == "PYB-156"


def testAnEmptyFocusClearsItOnATicketBranch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tools.workflow.lib.dashboard.readCurrentBranch", lambda: "chore/211-a-title"
    )
    assert findFocusKey(parseBoard(dashboard), "") == ""


def testWithNoFocusNamedTheBranchDecides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tools.workflow.lib.dashboard.readCurrentBranch", lambda: "chore/156-a-title"
    )
    assert findFocusKey(parseBoard(dashboard), None) == "PYB-156"


def testOffATicketBranchTheStatusLineDecides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tools.workflow.lib.dashboard.readCurrentBranch", lambda: "develop"
    )
    assert findFocusKey(parseBoard(dashboard), None) == "PYB-211"


def testAMalformedDashboardWarnsRatherThanFailingTheMerge() -> None:
    dashboardModule.dashboardPath.write_text("## Tasks\n", encoding="utf-8")
    warning = saveMerge("PYB-211", 212)
    assert warning.startswith("The dashboard was not updated:")

