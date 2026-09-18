#!/usr/bin/env python3
"""\
The checks behind the merge-readiness report, and the facts a branch supplies them.

Split in two on purpose, because the two halves run with different trust. The
collecting half runs on the pull request's own branch with no write access and
writes facts to a file. The checking half runs this repository's code, reads that
file as data, and never executes anything the branch carries.

Every function here returns a result and prints nothing, so a check is testable
without a token, a network or a pull request.

UPDATES
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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

repositoryRoot: Path = Path(__file__).resolve().parent.parent
goldenDirectory: Path = repositoryRoot / "tests" / "golden"
changelogPath: Path = repositoryRoot / "CHANGELOG.md"
goldenReadmePath: Path = goldenDirectory / "README.md"

osvBatchUrl: str = "https://api.osv.dev/v1/querybatch"
pypiRoot: str = "https://pypi.org/pypi"
networkTimeoutSeconds: float = 30.0

passed: str = "passed"
failed: str = "failed"
attention: str = "attention"
skipped: str = "skipped"


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
    preflightGates: list[list[str]] = field(default_factory=list)
    preflightPassed: bool = False
    changelogTickets: list[str] = field(default_factory=list)
    commitSubjects: list[str] = field(default_factory=list)
    goldensTouched: list[str] = field(default_factory=list)
    goldensConfirmed: list[str] = field(default_factory=list)
    resolvedPackages: list[list[str]] = field(default_factory=list)
    declaredPackages: list[str] = field(default_factory=list)

    def toDictionary(self) -> dict[str, Any]:
        """Return the facts as the plain dictionary the artifact carries."""
        return asdict(self)


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


def readTicketNumber(branch: str) -> str:
    """Return the ticket number a branch name carries, or an empty string."""
    match = re.match(r"^[a-z]+/(\d+)-", branch)
    return match.group(1) if match else ""


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
    base: str, pullRequest: int, preflightLog: str,
    branch: str = "", headSha: str = "",
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
        commitSubjects=runGit(["log", f"{base}..HEAD", "--format=%s"]).splitlines(),
    )
    facts.preflightGates = readPreflightGates(preflightLog)
    facts.preflightPassed = bool(facts.preflightGates) and all(
        gate[1] == passed for gate in facts.preflightGates
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
    return facts


def readPreflightGates(log: str) -> list[list[str]]:
    """Return each gate the preflight reported, as a name and a verdict."""
    gates: list[list[str]] = []
    for line in log.splitlines():
        match = re.match(r"^(PASS|FAIL) (\S+)\s\s+(.*)$", line)
        if match is not None:
            verdict = passed if match.group(1) == "PASS" else failed
            gates.append([match.group(2), verdict, match.group(3).strip()])
    return gates


def checkPreflight(facts: BranchFacts) -> CheckResult:
    """Report the gates the first half ran, which is where a code failure shows."""
    if not facts.preflightGates:
        return CheckResult("preflight", failed, "the preflight reported no gates")
    broken = [gate[0] for gate in facts.preflightGates if gate[1] != passed]
    if broken:
        return CheckResult("preflight", failed, f"{', '.join(broken)} failed")
    names = ", ".join(gate[0] for gate in facts.preflightGates)
    return CheckResult("preflight", passed, f"{names} passed")


def checkChangelog(facts: BranchFacts) -> CheckResult:
    """Report whether the CHANGELOG's Unreleased list names this ticket."""
    if not facts.ticket:
        return CheckResult("changelog", skipped, "the branch names no ticket")
    if facts.ticket in facts.changelogTickets:
        return CheckResult("changelog", passed, f"Unreleased names PYB-{facts.ticket}")
    return CheckResult(
        "changelog", failed,
        f"Unreleased names no PYB-{facts.ticket} entry; run /changelog-add",
    )


def checkTicketAgreement(facts: BranchFacts, title: str) -> CheckResult:
    """Report whether one ticket number runs through every place that names one."""
    if not facts.ticket:
        return CheckResult("ticket number", skipped, "the branch names no ticket")
    disagreeing: list[str] = []
    subjects = {
        match.group(1) for subject in facts.commitSubjects
        if (match := re.match(r"^\[(\d+)\]", subject)) is not None
    }
    if subjects - {facts.ticket}:
        disagreeing.append(f"commit subjects name {', '.join(sorted(subjects))}")
    # An absent entry belongs to the CHANGELOG check, so only a different one disagrees.
    others = set(facts.changelogTickets) - {facts.ticket}
    if others and facts.ticket not in facts.changelogTickets:
        disagreeing.append(f"the CHANGELOG's newest entry names {sorted(others)[0]}")
    titleMatch = re.match(r"^\[[A-Z]{3}-(\d+)\]", title)
    if titleMatch is None or titleMatch.group(1) != facts.ticket:
        disagreeing.append(f"the title reads {title.split(']')[0] + ']'}")
    if disagreeing:
        return CheckResult(
            "ticket number", failed,
            f"the branch names PYB-{facts.ticket}, but " + "; ".join(disagreeing),
        )
    return CheckResult(
        "ticket number", passed,
        f"PYB-{facts.ticket} in the branch, the commits and the title",
    )


def checkGoldenConfirmations(facts: BranchFacts) -> CheckResult:
    """Report whether every golden this change touches carries a confirmation date."""
    if not facts.goldensTouched:
        return CheckResult("goldens", skipped, "the change touches no golden")
    missing = sorted(set(facts.goldensTouched) - set(facts.goldensConfirmed))
    if missing:
        return CheckResult(
            "goldens", failed,
            f"{', '.join(missing)} carry no confirmation date in the goldens README",
        )
    return CheckResult(
        "goldens", passed,
        f"{len(set(facts.goldensTouched))} touched, each confirmed in Numbers",
    )


def checkBranchCurrent(behind: int, base: str) -> CheckResult:
    """Report whether the branch has fallen behind the base it will merge into."""
    if behind == 0:
        return CheckResult("branch currency", passed, f"current with {base}")
    return CheckResult(
        "branch currency", attention,
        f"{behind} commits behind {base}; merge {base} in and let the checks rerun",
    )


def checkTemplate(findings: list[str]) -> CheckResult:
    """Report whether the pull request body still matches its template."""
    if not findings:
        return CheckResult("body template", passed, "the body matches the template")
    return CheckResult("body template", failed, "; ".join(findings))


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
    """Return each resolved version PyPI has yanked, which no install should keep."""
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
        return CheckResult("dependencies", skipped, "no declared dependency resolved")
    advisories = readAdvisories(watched)
    yanked = readYankedPackages(watched)
    if advisories or yanked:
        parts = [f"{package}: {', '.join(ids)}" for package, ids in advisories.items()]
        parts += [f"{package}: yanked" for package in yanked]
        return CheckResult("dependencies", failed, "; ".join(parts))
    names = ", ".join(f"{name} {version}" for name, version in watched)
    return CheckResult("dependencies", passed, f"no advisory against {names}")
