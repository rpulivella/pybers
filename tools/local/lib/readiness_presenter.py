#!/usr/bin/env python3
"""\
The one place the merge-readiness comment takes its shape.

The comment is rendered from results here rather than assembled where it is
posted, so a failing check produces a report that still reads as a report. Its
marker is what later runs find it by, which is why it is the first line and never
moves.

The verdict says a change is ready for a person to test. It never says a change is
ready to merge, because no automated check can know that.

UPDATES
2026-10-14  Moved to `tools/local/`, since no other repository uses it, for PYB-204.
2026-10-13  Moved here from `scripts/merge_readiness_presenter.py`, for PYB-204.
2026-09-17  Written for PYB-76.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/17"

from datetime import UTC, datetime

from rich.console import Console
from rich.markup import escape

from tools.local.lib.readiness import (
    BranchFacts,
    CheckResult,
    attention,
    failed,
    passed,
    readVerdict,
    skipped,
)

commentMarker: str = "<!-- pybers-merge-readiness -->"
commentHeading: str = "Merge Readiness"
checkHeadingLevel: str = "###"

verdictSymbols: dict[str, str] = {
    passed: "✅", failed: "❌", attention: "⚠️", skipped: "➖",
}
# The check run carries these, not the comment: a reader of the comment wants the
# checks themselves rather than a sentence restating their worst verdict.
verdictTitles: dict[str, str] = {
    passed: "Every check passed",
    attention: "A decision is required",
    failed: "A check failed",
}
# A check GitHub should surface above the log, and the color it gives that check.
annotationKinds: dict[str, str] = {failed: "error", attention: "warning"}

consoleColors: dict[str, str] = {
    passed: "green", failed: "red", attention: "yellow", skipped: "dim",
}


def formatTimestamp(moment: datetime) -> str:
    """Spell the moment a run happened, since an advisory is true only on a date."""
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def renderComment(
    results: list[CheckResult], facts: BranchFacts, moment: datetime
) -> str:
    """Render the whole comment, marker first, from results and nothing else."""
    # The heading carries the verdict, because it is the line a reader lands on.
    # A skipped check never decides it: only a failure or a decision can.
    verdict = readVerdict(results)
    lines = [
        commentMarker,
        f"## {verdictSymbols[verdict]} {commentHeading}",
        "",
        renderSummary(results),
        "",
    ]
    # A list rather than a table, because a table reads badly in a narrow window
    # and in an email, which is where a notification of this comment arrives.
    for result in results:
        symbol = verdictSymbols.get(result.status, verdictSymbols[skipped])
        lines += [f"{checkHeadingLevel} {symbol} {result.name}", "", result.detail, ""]
    commit = facts.headSha[:12] or "an unknown commit"
    lines += [f"_Checked {formatTimestamp(moment)} against commit {commit}_"]
    return "\n".join(lines) + "\n"


def renderSummary(results: list[CheckResult]) -> str:
    """Count the checks in one line, which is what a reader takes from the top."""
    counts = {status: sum(1 for r in results if r.status == status) for status in
              (passed, failed, attention, skipped)}
    skips = counts[skipped]
    trailing = "" if not skips else f" with {skips} skip" + ("" if skips == 1 else "s")
    if not counts[failed] and not counts[attention]:
        return f"All checks passed{trailing}"
    parts = []
    if counts[passed]:
        checkWord = "check" if counts[passed] == 1 else "checks"
        parts.append(f"{counts[passed]} {checkWord} passed")
    if counts[failed]:
        parts.append(f"{counts[failed]} failed")
    if counts[attention]:
        needs = "needs" if counts[attention] == 1 else "need"
        parts.append(f"{counts[attention]} {needs} a decision")
    if skips:
        parts.append(f"{skips} skip" + ("" if skips == 1 else "s"))
    return ", ".join(parts)


def renderAnnotations(results: list[CheckResult]) -> list[str]:
    """Render one workflow command per check, which GitHub shows in its Checks view.

    A failed check becomes an error and a decision becomes a warning, so the names
    a reader needs sit above the log rather than inside it.
    """
    commands: list[str] = []
    for result in results:
        if result.status not in annotationKinds:
            continue
        kind = annotationKinds[result.status]
        commands.append(f"::{kind} title={result.name}::{result.detail}")
    return commands


def reportResults(console: Console, results: list[CheckResult], verdict: str) -> None:
    """Print the same checks to a terminal, for a run made by hand."""
    for result in results:
        color = consoleColors.get(result.status, "dim")
        name, detail = escape(result.name), escape(result.detail)
        console.print(f"[{color}]{result.status:9}[/] {name}: {detail}")
    console.print(f"[{consoleColors[verdict]}]verdict: {verdict}[/]")
