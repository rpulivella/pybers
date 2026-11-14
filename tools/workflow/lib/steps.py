#!/usr/bin/env python3
"""\
The step ledger: what a session ran, and which declared skill steps it still owes.

A skill declares its required steps in its frontmatter under `steps:`. An entry is
text a command contains, `skill:<name>` for another skill, `tool:<name>` for an MCP
tool, `a or b` for either, or `pause` where a person answers before the next steps are
owed. Claude Code's hooks append what actually ran to a per-session ledger, and the
Stop hook keeps a turn going while a step is owed.

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

import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.workflow.lib.shared import repositoryRoot

ledgerFolder: Path = repositoryRoot / "workarea" / "steps"
skillFolders: tuple[Path, ...] = (
    repositoryRoot / ".claude" / "commands",
    repositoryRoot / ".claude" / "skills",
)
pauseStep: str = "pause"
skillPrefix: str = "skill:"
toolPrefix: str = "tool:"
alternative: str = " or "
stepsCommand: str = "tools.workflow.steps"


@dataclass
class Obligation:
    """One invocation of a skill, and the steps it still owes."""

    skill: str
    segments: list[list[str]]
    segment: int = 0
    met: set[str] = field(default_factory=set)
    skipped: dict[str, str] = field(default_factory=dict)
    abandoned: bool = False

    def owed(self) -> list[str]:
        """Return the steps due by now and not yet met, in declared order."""
        due = [step for part in self.segments[: self.segment + 1] for step in part]
        return [step for step in due if step not in self.met]

    def complete(self) -> bool:
        """Return whether every step in every segment is met."""
        return self.abandoned or (
            self.segment >= len(self.segments) - 1 and not self.owed()
        )


def readDeclaredSteps(skill: str) -> list[str]:
    """Return a skill's declared steps from its frontmatter, or [] when it has none."""
    name = skill.split(":")[-1]
    for folder in skillFolders:
        for path in (folder / f"{name}.md", folder / name / "SKILL.md"):
            if path.is_file():
                return parseFrontmatterSteps(path.read_text(encoding="utf-8"))
    return []


def parseFrontmatterSteps(text: str) -> list[str]:
    """Return the `steps:` list from a Markdown file's frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    steps: list[str] = []
    inSteps = False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line.startswith((" ", "\t")):
            inSteps = line.strip() == "steps:"
            continue
        item = line.strip()
        if inSteps and item.startswith("- "):
            steps.append(item[2:].strip().strip("\"'"))
    return steps


def splitSegments(steps: list[str]) -> list[list[str]]:
    """Return the steps split at each pause, so each segment is owed in its own turn."""
    segments: list[list[str]] = [[]]
    for step in steps:
        if step == pauseStep:
            segments.append([])
        else:
            segments[-1].append(step)
    return segments


def findLedgerPath(sessionId: str) -> Path:
    """Return the ledger file for one session."""
    return ledgerFolder / f"{sessionId}.jsonl"


def recordEvent(sessionId: str, event: dict[str, str]) -> None:
    """Append one event to the session's ledger."""
    ledgerFolder.mkdir(parents=True, exist_ok=True)
    with findLedgerPath(sessionId).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def readEvents(sessionId: str) -> list[dict[str, str]]:
    """Return the session's ledger events, oldest first."""
    path = findLedgerPath(sessionId)
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def parseStepsCommand(command: str) -> list[dict[str, str]]:
    """Return the skip or abandon events a `steps` command records, one per target."""
    try:
        words = shlex.split(command)
    except ValueError:
        return []
    if stepsCommand not in words:
        return []
    rest = words[words.index(stepsCommand) + 1 :]
    if not rest or rest[0] not in ("skip", "abandon") or "--reason" not in rest[:-1]:
        return []
    reasonAt = rest.index("--reason")
    return [
        {"kind": rest[0], "target": target, "reason": rest[reasonAt + 1]}
        for target in rest[1:reasonAt]
    ]


def readHookEvents(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Return the ledger events one hook payload records."""
    event = payload.get("hook_event_name", "")
    if event == "UserPromptSubmit":
        return [{"kind": "prompt"}]
    if event == "UserPromptExpansion" and payload.get("command_name"):
        return [{"kind": "skill", "name": str(payload["command_name"]).lstrip("/")}]
    if event != "PostToolUse":
        return []
    toolInput = payload.get("tool_input") or {}
    if payload.get("tool_name") == "Skill" and toolInput.get("skill"):
        return [{"kind": "skill", "name": str(toolInput["skill"])}]
    if payload.get("tool_name") == "Bash" and toolInput.get("command"):
        command = str(toolInput["command"])
        return [*parseStepsCommand(command), {"kind": "command", "text": command}]
    if str(payload.get("tool_name", "")).startswith("mcp__"):
        return [{"kind": "tool", "name": str(payload["tool_name"])}]
    return []


def matchStep(event: dict[str, str], step: str) -> bool:
    """Return whether a ledger event performs a declared step or one of its choices."""
    if alternative in step:
        return any(matchStep(event, choice) for choice in step.split(alternative))
    if step.startswith(skillPrefix):
        return (
            event["kind"] == "skill"
            and event["name"].split(":")[-1] == step[len(skillPrefix) :]
        )
    if step.startswith(toolPrefix):
        return (
            event["kind"] == "tool"
            and event["name"].split("__")[-1] == step[len(toolPrefix) :]
        )
    return (
        event["kind"] == "command"
        and step in event["text"]
        and "--preview" not in event["text"]
    )


def replayObligations(events: list[dict[str, str]]) -> list[Obligation]:
    """Return every skill invocation in the ledger, with what each still owes."""
    obligations: list[Obligation] = []
    for event in events:
        kind = event["kind"]
        if kind == "prompt":
            for obligation in obligations:
                if (
                    not obligation.owed()
                    and obligation.segment < len(obligation.segments) - 1
                ):
                    obligation.segment += 1
            continue
        open_ = [item for item in obligations if not item.complete()]
        if kind in ("skill", "command", "tool"):
            for obligation in open_:
                for part in obligation.segments:
                    obligation.met.update(
                        step for step in part if matchStep(event, step)
                    )
        if kind == "skill" and not any(item.skill == event["name"] for item in open_):
            steps = readDeclaredSteps(event["name"])
            if steps:
                obligations.append(Obligation(event["name"], splitSegments(steps)))
        elif kind == "abandon":
            for obligation in reversed(open_):
                if obligation.skill.split(":")[-1] == event["target"]:
                    obligation.abandoned = True
                    obligation.skipped["*"] = event["reason"]
                    break
        elif kind == "skip":
            for obligation in reversed(open_):
                if event["target"] in obligation.owed():
                    obligation.met.add(event["target"])
                    obligation.skipped[event["target"]] = event["reason"]
                    break
    return obligations


def findOwedSteps(events: list[dict[str, str]]) -> list[str]:
    """Return one line per invoked skill that still owes a due step."""
    return [
        f"/{item.skill} has not run: " + ", ".join(item.owed())
        for item in replayObligations(events)
        if item.owed() and not item.abandoned
    ]


# The model reads this, so unlike a console message it names the remedy.
skipAdvice: str = (
    "Run each step now. A step that does not apply is skipped with "
    '`.venv/bin/python3 -m tools.workflow.steps skip "<step>" --reason "<why>"`, '
    "and a skill a person declined is released with "
    '`.venv/bin/python3 -m tools.workflow.steps abandon <skill> --reason "<why>"`.'
)


def findBlockReason(events: list[dict[str, str]]) -> str:
    """Return why the turn may not end, or '' when nothing is owed."""
    lines = findOwedSteps(events)
    return "\n".join([*lines, skipAdvice]) if lines else ""
