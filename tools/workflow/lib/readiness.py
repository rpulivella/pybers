#!/usr/bin/env python3
"""\
The checks behind the merge-readiness report, and the facts a branch supplies them.

The facts and the checks both run in the pull request's own job, which holds no
write access, so a branch can make its own verdict read however it likes. What it
cannot do is reach the posting half: that half runs the default branch's code and
reads the stored results as data only, through `readStoredResults`.

Every function here returns a result and prints nothing, so a check is testable
without a token, a network or a pull request.

UPDATES
2026-10-13  Moved here from `scripts/merge_readiness_lib.py`, for PYB-204.
2026-10-13  The repository root and a branch's ticket number come from
            `lib/shared.py`, for PYB-204.
2026-10-03  Stored results are read back as data and refused when malformed, and a
            ticket disagrees only with a CHANGELOG line the branch added, for
            PYB-151.
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

import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from tools.workflow.lib.pull_request import templatePath
from tools.workflow.lib.shared import readTicketNumber, repositoryRoot

goldenDirectory: Path = repositoryRoot / "tests" / "golden"
changelogPath: Path = repositoryRoot / "CHANGELOG.md"
goldenReadmePath: Path = goldenDirectory / "README.md"

osvBatchUrl: str = "https://api.osv.dev/v1/querybatch"
pypiRoot: str = "https://pypi.org/pypi"
networkTimeoutSeconds: float = 30.0

templateCheckName: str = "PR Template"
changelogCheckName: str = "Changelog"
ticketCheckName: str = "Ticket Identifier"
baseCheckName: str = "Base Branch"

passed: str = "passed"
failed: str = "failed"
attention: str = "attention"
skipped: str = "skipped"
checkStatuses: frozenset[str] = frozenset({passed, failed, attention, skipped})
# A detail past this is cut, because the posting half renders text a branch wrote.
detailLimit: int = 2000


@dataclass(frozen=True)
class CheckResult:
    """One named check, its verdict, and the one line a reader needs.

    `attention` is a verdict of its own rather than a soft failure: it means a
    person has to decide something, which is what the yellow verdict reports.
    """

    name: str
    status: str
    detail: str


@dataclass
class BranchFacts:
    """What the branch itself supplies, collected where the branch code may run.

    Consumed as data by the checking half, which is why every field is a plain
    string, number or list rather than anything that could carry behavior.
    """

    ticket: str = ""
    branch: str = ""
    headSha: str = ""
    pullRequest: int = 0
    changelogTickets: list[str] = field(default_factory=list)
    changelogTicketsAdded: list[str] = field(default_factory=list)
    commitSubjects: list[str] = field(default_factory=list)
    goldensTouched: list[str] = field(default_factory=list)
    goldensConfirmed: list[str] = field(default_factory=list)
    resolvedPackages: list[list[str]] = field(default_factory=list)
    declaredPackages: list[str] = field(default_factory=list)
    template: str = ""

    def toDictionary(self) -> dict[str, Any]:
        """Return the facts as the plain dictionary the artifact carries."""
        return asdict(self)

    @classmethod
    def fromDictionary(cls, stored: dict[str, Any]) -> BranchFacts:
        """Build facts from a stored file, ignoring any field this code lacks.

        The two halves run different copies of this repository: the collecting
        half runs the branch's, and the checking half runs the default branch's.
        A branch that adds a field would otherwise crash the older reader, which
        is exactly how one run lost its check run entirely.
        """
        known = {field.name for field in fields(cls)}
        return cls(**{name: value for name, value in stored.items() if name in known})


def encodeResults(results: list[CheckResult]) -> list[dict[str, str]]:
    """Return results as the plain dictionaries the stored file carries."""
    return [asdict(result) for result in results]


def readStoredResults(stored: dict[str, Any]) -> list[CheckResult]:
    """Return the results a stored file carries, refusing any that is not one.

    The file comes from the pull request's own job, so every field is checked as
    text and every status against the four this code knows.
    """
    entries = stored.get("results")
    if not isinstance(entries, list) or not entries:
        raise ValueError("The stored report carries no check results.")
    results = []
    for entry in entries:
        values = [entry.get(key) if isinstance(entry, dict) else None
                  for key in ("name", "status", "detail")]
        name, status, detail = (value if isinstance(value, str) else None
                                for value in values)
        if name is None or detail is None or status not in checkStatuses:
            raise ValueError(
                f"The stored report carries an entry that is not a check result: "
                f"{entry!r:.80}"
            )
        results.append(CheckResult(name, str(status), detail[:detailLimit]))
    return results


def runGit(arguments: list[str]) -> str:
    """Run one git command in the repository and return its output.

    Git is the sanctioned shell-out: no Python library reads a branch's own log
    and diff, and the facts here come from both.
    """
    completed = subprocess.run(
        ["git", "-C", str(repositoryRoot), *arguments],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def readUnreleasedSection(text: str) -> str:
    """Return the CHANGELOG's Unreleased section, matched as a heading, not as text.

    The file explains itself above the list and names `## Unreleased` while doing so,
    so a plain search finds the sentence and reads the section as empty.
    """
    found = re.search(
        r"^## Unreleased\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    return found.group(1) if found else ""


def readChangelogTickets() -> list[str]:
    """Return every ticket key the CHANGELOG's Unreleased list names."""
    section = readUnreleasedSection(changelogPath.read_text())
    return re.findall(r"^- \[[A-Z]{3}-(\d+)\]", section, re.MULTILINE)


def readChangelogTicketsAdded(base: str) -> list[str]:
    """Return every ticket key in a CHANGELOG line this branch added."""
    diff = runGit(["diff", f"{base}...HEAD", "--", str(changelogPath)])
    return re.findall(r"^\+- \[[A-Z]{3}-(\d+)\]", diff, re.MULTILINE)


def readGoldenConfirmations() -> set[str]:
    """Return every golden the goldens README records a confirmation date for."""
    text = goldenReadmePath.read_text()
    confirmed: set[str] = set()
    for line in text.splitlines():
        named = re.findall(r"`([^`]+\.numbers)`", line)
        if named and re.search(r"\d{4}-\d{2}-\d{2}", line):
            confirmed.add(named[0])
    return confirmed


def collectBranchFacts(
    base: str, pullRequest: int, branch: str = "", headSha: str = "",
) -> BranchFacts:
    """Gather everything the checking half needs, from the branch it may not run.

    The branch and the head are passed in where a caller knows them, because a
    pull request is checked out as a detached merge commit: git there reports the
    branch as `HEAD` and the head as a commit no branch carries.
    """
    branch = branch or runGit(["rev-parse", "--abbrev-ref", "HEAD"])
    facts = BranchFacts(
        ticket=readTicketNumber(branch),
        branch=branch,
        headSha=headSha or runGit(["rev-parse", "HEAD"]),
        pullRequest=pullRequest,
        changelogTickets=readChangelogTickets(),
        changelogTicketsAdded=readChangelogTicketsAdded(base),
        commitSubjects=runGit(["log", f"{base}..HEAD", "--format=%s"]).splitlines(),
    )
    confirmed = readGoldenConfirmations()
    changed = runGit(["diff", f"{base}...HEAD", "--name-only"]).splitlines()
    facts.goldensTouched = [
        Path(path).name for path in changed
        if path.startswith("tests/golden/") and path.endswith(".numbers")
    ]
    facts.goldensConfirmed = [
        name for name in facts.goldensTouched if name in confirmed
    ]
    # The branch's own template, because a body is written against the template it
    # was given, and a change that edits the template would fail against the base's.
    if templatePath.is_file():
        facts.template = templatePath.read_text()
    return facts


def formatList(items: list[str]) -> str:
    """Join names as a sentence does, with a conjunction before the last."""
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def checkPreflight(conclusion: str) -> CheckResult:
    """Report what the preflight's own check concluded for this commit.

    Its gates are named in its own check, so repeating them here would be a copy
    that goes stale against a gate list this repository means to grow.
    """
    if conclusion == "success":
        return CheckResult("Preflight", passed, "The preflight passed")
    if conclusion in ("skipped", ""):
        return CheckResult("Preflight", skipped, "The preflight did not run")
    if conclusion == "failure":
        return CheckResult("Preflight", failed, "The preflight failed")
    return CheckResult("Preflight", failed, f"The preflight ended as {conclusion}")


def readChangelogException(body: str) -> str:
    """Return the reason a body records for carrying no CHANGELOG entry, if any."""
    found = re.search(r"^_No CHANGELOG entry[,:]? (.+?)_\s*$", body, re.MULTILINE)
    return found.group(1).strip() if found else ""


def checkChangelog(facts: BranchFacts, body: str = "") -> CheckResult:
    """Report whether an entry was added, or why an exception was made instead."""
    if not facts.ticket:
        return CheckResult(changelogCheckName, skipped, "This branch names no ticket")
    if facts.ticket in facts.changelogTickets:
        return CheckResult(
            changelogCheckName, passed,
            f"The Unreleased list names PYB-{facts.ticket}",
        )
    excepted = readChangelogException(body)
    if excepted:
        return CheckResult(
            changelogCheckName, attention,
            f"The Unreleased list names no entry, and the reason given is {excepted}",
        )
    return CheckResult(
        changelogCheckName, failed,
        f"The Unreleased list names no entry for PYB-{facts.ticket}, and this PR "
        "gives no reason",
    )


def checkTicketAgreement(facts: BranchFacts, title: str) -> CheckResult:
    """Report whether one ticket number runs through every place that names one."""
    if not facts.ticket:
        return CheckResult(
            ticketCheckName, skipped, "This branch names no ticket"
        )
    disagreeing: list[str] = []
    subjects = {
        match.group(1) for subject in facts.commitSubjects
        if (match := re.match(r"^\[(\d+)\]", subject)) is not None
    }
    strangers = sorted(subjects - {facts.ticket})
    if strangers:
        named = formatList([f"PYB-{number}" for number in strangers])
        disagreeing.append(f"the commits name {named}")
    # Only a line this branch added can disagree: the list accumulates every other
    # ticket, and an absent entry belongs to the Changelog check.
    others = sorted(set(facts.changelogTicketsAdded) - {facts.ticket})
    if others:
        named = formatList([f"PYB-{number}" for number in others])
        disagreeing.append(f"this branch adds a CHANGELOG line for {named}")
    titleMatch = re.match(r"^\[[A-Z]{3}-(\d+)\]", title)
    if titleMatch is None:
        disagreeing.append("the title names no ticket")
    elif titleMatch.group(1) != facts.ticket:
        disagreeing.append(f"the title names PYB-{titleMatch.group(1)}")
    if disagreeing:
        return CheckResult(
            ticketCheckName, failed,
            f"The branch names PYB-{facts.ticket}, but " + formatList(disagreeing),
        )
    return CheckResult(
        ticketCheckName, passed,
        f"PYB-{facts.ticket} names the branch, every commit subject and the title",
    )


def checkGoldenConfirmations(facts: BranchFacts) -> CheckResult:
    """Report whether every golden this change touches carries a confirmation date."""
    if not facts.goldensTouched:
        return CheckResult("Goldens", skipped, "This change touches no golden")
    missing = sorted(set(facts.goldensTouched) - set(facts.goldensConfirmed))
    if missing:
        return CheckResult(
            "Goldens", failed,
            f"{formatList(missing)} carries no confirmation date",
        )
    return CheckResult(
        "Goldens", passed,
        f"This change touches {len(set(facts.goldensTouched))} goldens, each "
        "confirmed in Numbers",
    )


def checkBranchCurrent(behind: int, base: str) -> CheckResult:
    """Report whether the branch has fallen behind the base it will merge into."""
    if behind == 0:
        current = f"This branch is up to date with {base}"
        return CheckResult(baseCheckName, passed, current)
    return CheckResult(
        baseCheckName, attention,
        f"This branch is {behind} commits behind {base}",
    )


def checkTemplate(findings: list[str]) -> CheckResult:
    """Report whether the body still matches .github/pull_request_template.md."""
    if not findings:
        return CheckResult(templateCheckName, passed, "This PR matches the template")
    return CheckResult(templateCheckName, failed, ". ".join(findings))


def checkChecklist(body: str) -> CheckResult:
    """Report any checklist line still waiting to be ticked or marked NA.

    An unticked box means not done, and the template says an item that cannot
    apply moves to the end of its list with `NA` in place of its checkbox. A box
    left blank at review time is therefore a question nobody answered.
    """
    waiting = [
        line.split("] ", 1)[-1].strip()
        for line in body.splitlines()
        if re.match(r"\s*- \[ \]", line)
    ]
    if waiting:
        subject = "checkbox is" if len(waiting) == 1 else "checkboxes are"
        return CheckResult(
            "Checklist", failed,
            f"{len(waiting)} {subject} neither checked nor NA: " + formatList(waiting),
        )
    return CheckResult("Checklist", passed, "Every checkbox is checked or NA")


def readVerdict(results: list[CheckResult]) -> str:
    """Return the one verdict a set of checks carries, worst first."""
    statuses = {result.status for result in results}
    if failed in statuses:
        return failed
    if attention in statuses:
        return attention
    return passed


def readAdvisories(packages: list[list[str]]) -> dict[str, list[str]]:
    """Ask OSV which of these exact versions carry a published advisory.

    One batch request, because a per-package request over a full dependency tree
    is dozens of round trips for the same answer. PYB-33 asks the same question on
    a schedule and calls this rather than growing a second implementation.
    """
    if not packages:
        return {}
    queries = [
        {"package": {"name": name, "ecosystem": "PyPI"}, "version": version}
        for name, version in packages
    ]
    request = urllib.request.Request(
        osvBatchUrl,
        data=json.dumps({"queries": queries}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=networkTimeoutSeconds) as response:
        payload = json.loads(response.read())
    found: dict[str, list[str]] = {}
    results = payload.get("results", [])
    for (name, version), result in zip(packages, results, strict=False):
        identifiers = [entry.get("id", "") for entry in result.get("vulns", [])]
        if identifiers:
            found[f"{name} {version}"] = identifiers
    return found


def readYankedPackages(packages: list[list[str]]) -> list[str]:
    """Return each resolved version PyPI has withdrawn, which a fresh install avoids."""
    yanked: list[str] = []
    for name, version in packages:
        quoted = f"{urllib.parse.quote(name)}/{urllib.parse.quote(version)}"
        url = f"{pypiRoot}/{quoted}/json"
        try:
            with urllib.request.urlopen(url, timeout=networkTimeoutSeconds) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError:
            continue
        if payload.get("info", {}).get("yanked"):
            yanked.append(f"{name} {version}")
    return yanked


def checkDependencies(facts: BranchFacts) -> CheckResult:
    """Report advisories and yanks against the versions a fresh install resolved."""
    watched = [
        [name, version] for name, version in facts.resolvedPackages
        if name.lower() in {package.lower() for package in facts.declaredPackages}
    ]
    if not watched:
        return CheckResult(
            "Dependencies", skipped, "This install resolved no declared dependency"
        )
    advisories = readAdvisories(watched)
    yanked = readYankedPackages(watched)
    if advisories or yanked:
        # One line per package, because a run of them in a sentence hides the second.
        lines = [
            f"- {package} has advisory {formatList(ids)}"
            for package, ids in sorted(advisories.items())
        ]
        lines += [f"- {package} is withdrawn from PyPI" for package in sorted(yanked)]
        return CheckResult("Dependencies", failed, "\n".join(lines))
    packages = "package" if len(watched) == 1 else "packages"
    return CheckResult(
        "Dependencies", passed,
        f"{len(watched)} resolved {packages}, no advisories, none withdrawn",
    )
