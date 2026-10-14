#!/usr/bin/env python3
"""\
A pull request's reference, its default base, and its body checked against the template.

Shared by `pr.py`, which writes bodies, and the readiness check, which reads them.

UPDATES
2026-10-14  Moved here from `pr.py`, so the readiness code imports a library rather
            than a command, for PYB-204.
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
from pathlib import Path

from tools.workflow.lib.shared import repositoryRoot

# The base a pull request targets by default. Library and app repositories cut from
# develop; a web-facing repository whose deploy tracks a different branch overrides
# this per invocation with --base.
defaultBaseBranch: str = "develop"


# The pull request template, and the authority on what a body may look like.
# Read here because nothing else in this repository reads it: `/pr-draft` tells
# an author to fill it, and GitHub applies it only to a body typed in the web
# interface, so a body posted through the API carries what it was given and
# nothing more.
templatePath: Path = repositoryRoot / ".github" / "pull_request_template.md"


# A body may run to twice the template's own length, comments excluded from both.
maximumBodyLengthMultiple: int = 2


def formatPullRequestRef(number: int) -> str:
    """Return a pull request reference in the house form, both parts always."""
    return f"PR #{number}"


def readTemplate() -> str:
    """Return the pull request template, refusing when it is absent.

    Missing means the checks below have nothing to compare a body against, and
    passing one because the authority went missing is the fallback cascade this
    repository refuses everywhere else.
    """
    if not templatePath.is_file():
        raise RuntimeError(
            f"No pull request template at {templatePath}. Every body is checked "
            "against it, so there is nothing left to check against."
        )
    return templatePath.read_text(encoding="utf-8")


def readHeadings(text: str) -> list[str]:
    """Return every `##` heading, in order."""
    return [line.strip() for line in text.splitlines() if line.startswith("## ")]


def readBoldRuns(text: str) -> list[str]:
    """Return every line that is nothing but bold text, which reads as a heading.

    Markdown makes `**Like this**` alone on a line look exactly like a section
    heading while staying invisible to a `## ` scan, which is how a body grows a
    section the template never had. The template uses bold inline under Breaking
    Changes, so only a line that is ENTIRELY bold counts.
    """
    return [
        line.strip()
        for line in text.splitlines()
        if re.fullmatch(r"\*\*[^*]+\*\*", line.strip())
    ]


def readCheckboxLabels(text: str) -> list[str]:
    """Return every checkbox's label, with its ticked state discarded.

    The state is what an author is meant to change and the label is what the
    template owns, so comparing labels catches a reworded line without
    complaining about a box legitimately ticked. `NA ` counts as a state,
    because the template says to mark an inapplicable item that way rather than
    delete it, which keeps its label under comparison.
    """
    labels: list[str] = []
    for line in text.splitlines():
        matched = re.match(r"\s*- (?:\[[ xX]\]\s*|NA\s+)(.+?)\s*$", line)
        if matched:
            labels.append(matched.group(1))
    return labels


def countProseWords(text: str) -> int:
    """Return the word count with HTML comments removed.

    The template is largely instructions inside comments, so counting those
    would raise the ceiling by the size of guidance no body ever publishes.
    """
    return len(re.findall(r"\S+", re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)))


def findBodyFindings(body: str, template: str) -> list[str]:
    """Return every way a body departs from its template.

    Pure by design: two strings in and complaints out, so the checks are
    testable without a token, a network or a repository. Headings are compared
    in BOTH directions, because the template asks for `None` under a heading a
    body does not need rather than for the heading to go. Checkboxes are
    compared in ONE, because it asks for the inapplicable ones to be deleted.
    """
    findings: list[str] = []
    templateHeadings = readHeadings(template)
    headings = readHeadings(body)

    invented = [heading for heading in headings if heading not in templateHeadings]
    if invented:
        findings.append(
            f"{len(invented)} heading(s) the template does not carry: "
            + ", ".join(invented)
        )
    missing = [heading for heading in templateHeadings if heading not in headings]
    if missing:
        findings.append(
            f"{len(missing)} template heading(s) missing: " + ", ".join(missing)
        )
    if not invented and not missing and headings != templateHeadings:
        findings.append(
            "headings are out of the template's order, expected "
            f"{templateHeadings} and got {headings}"
        )

    templateBold = set(readBoldRuns(template))
    inventedBold = [run for run in readBoldRuns(body) if run not in templateBold]
    if inventedBold:
        findings.append(
            f"{len(inventedBold)} bold line(s) reading as a heading: "
            + ", ".join(inventedBold)
        )

    templateLabels = set(readCheckboxLabels(template))
    reworded = [
        label for label in readCheckboxLabels(body) if label not in templateLabels
    ]
    if reworded:
        findings.append(
            f"this body carries {len(reworded)} checkbox the template does not: "
            + ", ".join(reworded)
        )

    templateWords = countProseWords(template)
    words = countProseWords(body)
    ceiling = templateWords * maximumBodyLengthMultiple
    if words > ceiling:
        findings.append(
            f"body is {words} words against a ceiling of {ceiling}, which is "
            f"{maximumBodyLengthMultiple} times the template's {templateWords}"
        )
    return findings
