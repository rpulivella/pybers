#!/usr/bin/env python3
"""\
The step ledger: a skill's declared steps are owed until a hook records them run.

UPDATES
2026-11-14  Written for PYB-294.
"""

from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/14"

import io
import json
from pathlib import Path
from typing import Any

import pytest

from tools.workflow import steps as stepsCommand
from tools.workflow.lib import steps as stepsModule
from tools.workflow.lib.steps import (
    findBlockReason,
    parseFrontmatterSteps,
    readHookEvents,
)

skillText: str = """---
description: a skill
steps:
  - skill:standards
  - pause
  - tools.workflow.ticket create
---

# body
"""


@pytest.fixture(autouse=True)
def isolateLedger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Give each test its own ledger and skill folder."""
    (tmp_path / "file-ticket.md").write_text(skillText, encoding="utf-8")
    (tmp_path / "standards.md").write_text(
        "---\nsteps:\n  - tools.workflow.standards_check\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stepsModule, "ledgerFolder", tmp_path / "ledger")
    monkeypatch.setattr(stepsModule, "skillFolders", (tmp_path,))


def buildSkillEvent(name: str) -> dict[str, str]:
    """Return a ledger event for a skill invocation."""
    return {"kind": "skill", "name": name}


def buildCommandEvent(text: str) -> dict[str, str]:
    """Return a ledger event for a command that succeeded."""
    return {"kind": "command", "text": text}


prompt: dict[str, str] = {"kind": "prompt"}
proofread: list[dict[str, str]] = [
    buildSkillEvent("standards"),
    buildCommandEvent("tools.workflow.standards_check draft.md"),
]
filing: str = "tools.workflow.ticket create --label chore --title t --body-file d"


def testParsesDeclaredStepsInOrder() -> None:
    assert parseFrontmatterSteps(skillText) == [
        "skill:standards",
        "pause",
        "tools.workflow.ticket create",
    ]


def testSkillWithoutStepsOwesNothing() -> None:
    assert findBlockReason([buildSkillEvent("not-declared")]) == ""


def testBlocksWhileTheFirstSegmentIsOwed() -> None:
    reason = findBlockReason([buildSkillEvent("file-ticket")])
    assert "/file-ticket has not run: skill:standards" in reason
    assert "ticket create" not in reason


def testNestedSkillOwesItsOwnSteps() -> None:
    reason = findBlockReason(
        [buildSkillEvent("file-ticket"), buildSkillEvent("standards")]
    )
    assert "/standards has not run: tools.workflow.standards_check" in reason


def testAPauseEndsTheTurnOnceItsSegmentIsMet() -> None:
    assert findBlockReason([buildSkillEvent("file-ticket"), *proofread]) == ""


def testTheNextPromptOwesTheSegmentAfterThePause() -> None:
    reason = findBlockReason([buildSkillEvent("file-ticket"), *proofread, prompt])
    assert "tools.workflow.ticket create" in reason


def testAnMcpToolPerformsAToolStep(tmp_path: Path) -> None:
    (tmp_path / "launch.md").write_text(
        "---\nsteps:\n  - tool:RunProject\n---\n", encoding="utf-8"
    )
    events = [
        buildSkillEvent("launch"),
        {"kind": "tool", "name": "mcp__xcode__RunProject"},
    ]
    assert findBlockReason(events) == ""


def testEitherAlternativeMeetsAStep(tmp_path: Path) -> None:
    (tmp_path / "open.md").write_text(
        "---\nsteps:\n  - tools.workflow.pr create or tools.workflow.pr edit\n---\n",
        encoding="utf-8",
    )
    assert (
        findBlockReason(
            [
                buildSkillEvent("open"),
                buildCommandEvent("tools.workflow.pr edit 4"),
            ]
        )
        == ""
    )


def testCompletedSkillOwesNothing() -> None:
    events = [
        buildSkillEvent("file-ticket"),
        *proofread,
        prompt,
        buildCommandEvent(filing),
    ]
    assert findBlockReason(events) == ""


def testAPreviewDoesNotPerformAStep() -> None:
    events = [
        buildSkillEvent("file-ticket"),
        *proofread,
        prompt,
        buildCommandEvent(filing + " --preview"),
    ]
    assert "ticket create" in findBlockReason(events)


def testARecordedSkipMeetsTheStep() -> None:
    skip = {"kind": "skip", "target": "skill:standards", "reason": "no prose"}
    assert findBlockReason([buildSkillEvent("file-ticket"), skip]) == ""


def testAbandoningASkillReleasesEveryStep() -> None:
    abandon = {"kind": "abandon", "target": "file-ticket", "reason": "declined"}
    assert (
        findBlockReason([buildSkillEvent("file-ticket"), *proofread, prompt, abandon])
        == ""
    )


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"hook_event_name": "UserPromptSubmit"}, [{"kind": "prompt"}]),
        (
            {"hook_event_name": "UserPromptExpansion", "command_name": "/file-ticket"},
            [buildSkillEvent("file-ticket")],
        ),
        (
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Skill",
                "tool_input": {"skill": "standards"},
            },
            [buildSkillEvent("standards")],
        ),
        (
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            },
            [buildCommandEvent("ls")],
        ),
        (
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "tools.workflow.steps skip 'pause' --reason 'n/a'"
                },
            },
            [
                {"kind": "skip", "target": "pause", "reason": "n/a"},
                buildCommandEvent("tools.workflow.steps skip 'pause' --reason 'n/a'"),
            ],
        ),
        (
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "mcp__xcode__RunProject",
                "tool_input": {},
            },
            [{"kind": "tool", "name": "mcp__xcode__RunProject"}],
        ),
        ({"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {}}, []),
    ],
)
def testHookPayloadsBecomeLedgerEvents(
    payload: dict[str, Any], expected: list[dict[str, str]]
) -> None:
    assert readHookEvents(payload) == expected


def testStopHookBlocksWithTheOwedStep(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for payload in (
        {
            "session_id": "s",
            "hook_event_name": "PostToolUse",
            "tool_name": "Skill",
            "tool_input": {"skill": "file-ticket"},
        },
        {"session_id": "s", "hook_event_name": "Stop"},
    ):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        stepsCommand.runHook(stepsCommand.buildParser().parse_args(["hook"]))
    decision = json.loads(capsys.readouterr().out)
    assert decision["decision"] == "block"
    assert "skill:standards" in decision["reason"]


def testStatusReportsAnAbandonedSkillAsOwingNothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for event in (
        buildSkillEvent("file-ticket"),
        {"kind": "abandon", "target": "file-ticket", "reason": "declined"},
    ):
        stepsModule.recordEvent("s", event)
    stepsCommand.runStatus(stepsCommand.buildParser().parse_args(["status", "s"]))
    output = capsys.readouterr().out
    assert "/file-ticket: abandoned" in output
    assert "skill:standards" not in output


def testReinvokingAnOpenSkillContinuesIt() -> None:
    events = [
        buildSkillEvent("file-ticket"),
        *proofread,
        prompt,
        buildSkillEvent("file-ticket"),
        buildCommandEvent(filing),
    ]
    assert findBlockReason(events) == ""


def testOneSkipCommandRecordsEveryStepItNames() -> None:
    line = "tools.workflow.steps skip 'skill:a' 'tool:B' --reason 'n/a'"
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": line},
    }
    assert [event.get("target") for event in readHookEvents(payload)] == [
        "skill:a",
        "tool:B",
        None,
    ]


def testASkipChainedToAStepRecordsTheStepToo() -> None:
    line = "tools.workflow.steps skip 'skill:standards' --reason r && " + filing
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": line},
    }
    assert (
        findBlockReason(
            [buildSkillEvent("file-ticket"), prompt, *readHookEvents(payload)]
        )
        == ""
    )


def testUnreadableHookInputBlocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert (
        stepsCommand.runHook(stepsCommand.buildParser().parse_args(["hook"]))
        == stepsCommand.blockingExitCode
    )


def runHookWith(payload: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Feed one payload to the hook command."""
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    stepsCommand.runHook(stepsCommand.buildParser().parse_args(["hook"]))


def testALedgerFailureBlocksTheStop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "ledger").mkdir()
    (tmp_path / "ledger" / "s.jsonl").write_text("not json\n", encoding="utf-8")
    runHookWith({"session_id": "s", "hook_event_name": "Stop"}, monkeypatch)
    decision = json.loads(capsys.readouterr().out)
    assert decision["decision"] == "block"
    assert "step ledger failed" in decision["reason"]


def testAPromptIsRemindedOfStepsAnEarlierTurnLeftOwed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stepsModule.recordEvent("s", buildSkillEvent("file-ticket"))
    runHookWith(
        {"session_id": "s", "hook_event_name": "UserPromptSubmit", "prompt": "next"},
        monkeypatch,
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert "/file-ticket has not run: skill:standards" in context
