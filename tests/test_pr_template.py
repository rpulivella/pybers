#!/usr/bin/env python3
"""\
The pull request body checks, exercised against the repository's own template.

`findBodyFindings` is pure, two strings in and complaints out, so none of this needs
a token, a network or an open pull request. The template is read from the
repository rather than invented here, because a check that passes against a
made-up template proves nothing about the one bodies are actually filled from.

UPDATES
2026-10-14  The body checks are tested in `lib/pull_request.py`, where they moved,
            for PYB-204.
2026-10-13  Pull request summaries and check runs are dataclasses, for PYB-204.
2026-09-05  Written for #50.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/05"

import importlib
from pathlib import Path
from types import ModuleType

import pytest

from tools.workflow.lib import pull_request as pullRequest

repositoryRoot: Path = Path(__file__).resolve().parent.parent


def loadPrTool() -> ModuleType:
    """Return tools/workflow/pr.py as a module, which is where the checks live."""
    return importlib.import_module("tools.workflow.pr")


@pytest.fixture
def template() -> str:
    """The repository's own pull request template."""
    return pullRequest.readTemplate()


def testAMissingTemplateRefusesRatherThanSkipping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Passing a body because the authority went missing is a silent yes.

    Deleting the template makes every pull request refuse to open, which is the
    intended consequence: there is nothing left to check a body against, and a
    check that disappears with its rule is worse than no check.
    """
    monkeypatch.setattr(pullRequest, "templatePath", tmp_path / "absent.md")
    with pytest.raises(RuntimeError, match="No pull request template"):
        pullRequest.readTemplate()


# ── AC 1 and 3: headings, checked in both directions ─────────────────────────


def testTheTemplatePassesItsOwnCheck(template: str) -> None:
    """A body that is the template unchanged has departed from nothing."""
    assert pullRequest.findBodyFindings(template, template) == []


def testAnInventedHeadingIsRefusedAndNamed(template: str) -> None:
    """The failure that prompted this ticket: a section nobody sanctioned."""
    findings = pullRequest.findBodyFindings(
        template + "\n## What a reviewer should push on\n\nSomething.\n", template
    )
    assert len(findings) == 1
    assert "What a reviewer should push on" in findings[0]


def testAMissingHeadingIsRefused(template: str) -> None:
    """The template asks for `None` under a heading rather than for it to go."""
    body = template.replace("## Breaking Changes", "Breaking Changes")
    findings = pullRequest.findBodyFindings(body, template)
    assert any("missing" in finding for finding in findings)
    assert any("Breaking Changes" in finding for finding in findings)


# ── AC 6: order ──────────────────────────────────────────────────────────────


def testHeadingsOutOfOrderAreRefused(template: str) -> None:
    """A record reads back the same way only if every body orders it alike."""
    headings = pullRequest.readHeadings(template)
    body = template.replace(headings[0], "PLACEHOLDER")
    body = body.replace(headings[1], headings[0]).replace("PLACEHOLDER", headings[1])
    findings = pullRequest.findBodyFindings(body, template)
    assert any("out of the template's order" in finding for finding in findings)


# ── AC 7: a bold line reads as a heading ─────────────────────────────────────


def testABoldLineAloneIsTreatedAsAHeading(template: str) -> None:
    """`**Like this**` on its own line looks like a section and hides from `##`."""
    findings = pullRequest.findBodyFindings(
        template + "\n**A section in disguise**\n\nSomething.\n", template
    )
    assert len(findings) == 1
    assert "bold line(s) reading as a heading" in findings[0]


def testBoldInsideALineIsNotAHeading(template: str) -> None:
    """The template itself opens Breaking Changes entries with inline bold, so
    only a line that is entirely bold counts."""
    findings = pullRequest.findBodyFindings(
        template + "\n**Emphasis** inside a sentence is ordinary prose.\n", template
    )
    assert findings == []


# ── AC 8: checkboxes, checked in one direction ───────────────────────────────


def testARewordedCheckboxLabelIsRefused(template: str) -> None:
    """The label belongs to the template even when the state belongs to the author."""
    label = pullRequest.readCheckboxLabels(template)[0]
    body = template.replace(label, f"{label} probably")
    findings = pullRequest.findBodyFindings(body, template)
    assert any("checkbox the template does not" in finding for finding in findings)


def testTickingABoxIsNotARewording(template: str) -> None:
    """The state is exactly what an author is supposed to change."""
    ticked = template.replace("- [ ]", "- [x]")
    assert pullRequest.findBodyFindings(ticked, template) == []


def testRemovingACheckboxIsAccepted(template: str) -> None:
    """`/pr-draft` tells an author to delete the boxes that do not apply."""
    label = pullRequest.readCheckboxLabels(template)[0]
    body = "\n".join(
        line for line in template.splitlines() if label not in line
    )
    assert not any(
        "checkbox the template does not" in finding
        for finding in pullRequest.findBodyFindings(body, template)
    )


def testAnItemMarkedNotApplicableKeepsItsLabelUnderComparison(template: str) -> None:
    """`NA` is a state, so an item moved to the end stays compared rather than
    escaping the way a deleted line would."""
    label = pullRequest.readCheckboxLabels(template)[0]
    assert label in pullRequest.readCheckboxLabels(f"- NA {label}\n")


# ── AC 2: length, with comments excluded from both ───────────────────────────


def testHtmlCommentsAreNotCountedAsProse(template: str) -> None:
    """The template is largely instructions inside comments, and counting them
    raises the ceiling by guidance no body ever publishes."""
    assert pullRequest.countProseWords("<!-- a b c d e -->") == 0
    assert pullRequest.countProseWords(template) < len(template.split())


def testABodyOverTheCeilingIsRefusedWithBothCounts(template: str) -> None:
    """Reporting one number leaves an author guessing what to cut to."""
    multiple = pullRequest.maximumBodyLengthMultiple
    ceiling = pullRequest.countProseWords(template) * multiple
    findings = pullRequest.findBodyFindings(template + " word" * ceiling, template)
    assert any(str(ceiling) in finding for finding in findings)


def testABodyUnderTheCeilingIsAccepted(template: str) -> None:
    """A body may say twice what the template does before it is too long."""
    body = template + "\nOne short sentence.\n"
    assert pullRequest.findBodyFindings(body, template) == []


# ── The ticket a merge subject names, for the merge that does not complete it ──


def testAMergeSubjectNamesItsTicket() -> None:
    assert loadPrTool().readTicketFromSubject("[76] feat: a thing") == 76


def testAHotfixSubjectNamesNoTicketToReopen() -> None:
    assert loadPrTool().readTicketFromSubject("[hotfix] docs: a fix") is None


# ── One entry per check, whatever history a commit carries ──────────────────


def testOnlyTheNewestRunOfEachCheckIsReported() -> None:
    runs = [
        {"name": "preflight", "status": "completed", "conclusion": "skipped",
         "started_at": "2026-09-18T01:00:00Z"},
        {"name": "preflight", "status": "completed", "conclusion": "success",
         "started_at": "2026-09-18T02:00:00Z"},
        {"name": "merge readiness", "status": "completed", "conclusion": "failure",
         "started_at": "2026-09-18T02:05:00Z"},
    ]

    reported = pullRequest.chooseLatestRuns(runs)

    assert [(run.name, run.conclusion) for run in reported] == [
        ("preflight", "success"),
        ("merge readiness", "failure"),
    ]
