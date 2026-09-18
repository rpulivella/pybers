#!/usr/bin/env python3
"""\
The merge-readiness checks and the comment they render.

Every check here is pure, so the suite exercises them without a token, a network
or a pull request. What needs GitHub is the half that gathers the facts, and it is
the workflows that prove that.

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

import sys
from datetime import UTC, datetime
from pathlib import Path

repositoryRoot: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repositoryRoot / "scripts"))

import merge_readiness_lib as checks  # noqa: E402
import merge_readiness_presenter as presenter  # noqa: E402


def buildFacts(**overrides: object) -> checks.BranchFacts:
    """Return facts for one branch, with only what a test cares about set."""
    facts = checks.BranchFacts(
        ticket="76", branch="chore/76-a-thing", headSha="abc123def456"
    )
    for name, value in overrides.items():
        setattr(facts, name, value)
    return facts


def testAPreflightLogYieldsOneEntryPerGate() -> None:
    gates = checks.readPreflightGates(
        "PASS pytest  1618 passed\nFAIL ruff  2 errors\nnoise\n"
    )

    assert gates == [
        ["pytest", checks.passed, "1618 passed"],
        ["ruff", checks.failed, "2 errors"],
    ]


def testTheUnreleasedListIsReadPastTheFilesOwnMentionOfTheHeading() -> None:
    text = (
        "# Changelog\n\nMaintained by `/changelog-add`, one bullet under "
        "`## Unreleased`.\n\n## Unreleased\n\n- [PYB-76] A thing\n- [PYB-94] Another"
        "\n\n## 0.1.0\n\n- [PYB-1] Older\n"
    )

    assert checks.readUnreleasedSection(text).strip().startswith("- [PYB-76]")
    assert "PYB-1] Older" not in checks.readUnreleasedSection(text)


def testTheRepositorysOwnChangelogNamesItsOpenTickets() -> None:
    assert checks.readChangelogTickets(), "the Unreleased list parsed as empty"


def testAFailedGateFailsThePreflightCheckAndNamesIt() -> None:
    facts = buildFacts(preflightGates=[["pytest", checks.passed, ""],
                                       ["mypy", checks.failed, "3 errors"]])

    result = checks.checkPreflight(facts)

    assert result.status == checks.failed
    assert "mypy" in result.detail


def testAPreflightThatReportedNothingFailsRatherThanPasses() -> None:
    assert checks.checkPreflight(buildFacts()).status == checks.failed


def testAChangelogNamingThisTicketPasses() -> None:
    facts = buildFacts(changelogTickets=["94", "76"])

    assert checks.checkChangelog(facts).status == checks.passed


def testAMissingEntryWithARecordedReasonAsksForADecision() -> None:
    facts = buildFacts(changelogTickets=["94"])
    body = "Some prose.\n\n_No CHANGELOG entry, because this ticket ships nothing._\n"

    result = checks.checkChangelog(facts, body)

    assert result.status == checks.attention
    assert "this ticket ships nothing" in result.detail


def testAnUntickedChecklistItemFailsAndNamesIt() -> None:
    body = (
        "## Checklist\n- [x] I performed a self-review\n"
        "- [ ] I added or updated pytest tests covering the change\n"
        "- NA Round-trip tests pass\n"
    )

    result = checks.checkChecklist(body)

    assert result.status == checks.failed
    assert "I added or updated pytest tests covering the change" in result.detail


def testAChecklistOfTickedAndNAItemsPasses() -> None:
    body = "- [x] I performed a self-review\n- NA Round-trip tests pass\n"

    assert checks.checkChecklist(body).status == checks.passed


def testAChangelogMissingThisTicketWithNoReasonFails() -> None:
    result = checks.checkChangelog(buildFacts(changelogTickets=["94"]))

    assert result.status == checks.failed
    assert "names no entry for PYB-76" in result.detail


def testABranchNamingNoTicketSkipsRatherThanFails() -> None:
    assert checks.checkChangelog(buildFacts(ticket="")).status == checks.skipped


def testOneTicketNumberThroughoutAgrees() -> None:
    facts = buildFacts(
        commitSubjects=["[76] feat: a thing", "[76] docs: another"],
        changelogTickets=["76"],
    )

    result = checks.checkTicketAgreement(facts, "[PYB-76] A thing")

    assert result.status == checks.passed


def testACommitNamingAnotherTicketDisagrees() -> None:
    facts = buildFacts(commitSubjects=["[76] feat: a thing", "[94] fix: elsewhere"])

    result = checks.checkTicketAgreement(facts, "[PYB-76] A thing")

    assert result.status == checks.failed
    assert "94" in result.detail


def testATitleNamingAnotherTicketDisagrees() -> None:
    facts = buildFacts(commitSubjects=["[76] feat: a thing"])

    result = checks.checkTicketAgreement(facts, "[PYB-94] Something else")

    assert result.status == checks.failed
    assert "the title names PYB-94" in result.detail


def testATouchedGoldenWithNoConfirmationDateFails() -> None:
    facts = buildFacts(goldensTouched=["20-sheets-added.numbers"], goldensConfirmed=[])

    result = checks.checkGoldenConfirmations(facts)

    assert result.status == checks.failed
    assert "20-sheets-added.numbers" in result.detail


def testATouchedGoldenThatIsConfirmedPasses() -> None:
    facts = buildFacts(goldensTouched=["20-sheets-added.numbers"],
                       goldensConfirmed=["20-sheets-added.numbers"])

    assert checks.checkGoldenConfirmations(facts).status == checks.passed


def testABranchBehindItsBaseAsksForADecisionRatherThanFailing() -> None:
    result = checks.checkBranchCurrent(3, "develop")

    assert result.status == checks.attention
    assert "3 commits behind develop" in result.detail


def testTheWorstStatusDecidesTheVerdict() -> None:
    green = [checks.CheckResult("a", checks.passed, ""),
             checks.CheckResult("b", checks.skipped, "")]
    yellow = [*green, checks.CheckResult("c", checks.attention, "")]
    red = [*yellow, checks.CheckResult("d", checks.failed, "")]

    assert checks.readVerdict(green) == checks.passed
    assert checks.readVerdict(yellow) == checks.attention
    assert checks.readVerdict(red) == checks.failed


def testTheCommentOpensWithItsMarkerSoALaterRunFindsIt() -> None:
    body = presenter.renderComment(
        [checks.CheckResult("Preflight", checks.passed, "four gates")],
        buildFacts(), datetime(2026, 9, 17, 18, 54, tzinfo=UTC),
    )

    assert body.splitlines()[0] == presenter.commentMarker


def testTheCommentCarriesEveryCheckItsVerdictAndTheMomentItRan() -> None:
    results = [
        checks.CheckResult("Preflight", checks.passed, "four gates"),
        checks.CheckResult("Goldens", checks.skipped, "none touched"),
        checks.CheckResult("Changelog", checks.failed, "no entry"),
    ]

    body = presenter.renderComment(
        results, buildFacts(), datetime(2026, 9, 17, 18, 54, tzinfo=UTC)
    )

    assert "### ✅ Preflight\n\nfour gates" in body
    assert "### ➖ Goldens\n\nnone touched" in body
    assert "### ❌ Changelog\n\nno entry" in body
    assert "2026-09-17 18:54 UTC" in body
    assert "abc123def456" in body


def testTheCommentCarriesTheChecksRatherThanASentenceAboutThem() -> None:
    body = presenter.renderComment(
        [checks.CheckResult("Preflight", checks.passed, "four gates")],
        buildFacts(), datetime.now(UTC),
    )

    assert body.splitlines()[1] == presenter.commentHeading
    assert "### ✅ Preflight" in body
    assert "ready to merge" not in body.lower()


def testADetailReachesTheCommentWhateverPunctuationItCarries() -> None:
    body = presenter.renderComment(
        [checks.CheckResult("Dependencies", checks.failed, "rich 1.0 | yanked")],
        buildFacts(), datetime.now(UTC),
    )

    assert "rich 1.0 | yanked" in body
