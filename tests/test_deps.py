#!/usr/bin/env python3
"""\
What to bump is reported and never blocks, and an unreadable answer is never "none".

GitHub and pip are stood in for at their boundaries, with an alert shaped as
Dependabot returned one on 2026-11-16.

UPDATES
2026-11-16  Written for PYB-295.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/16"

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tools.workflow import deps
from tools.workflow.lib import dependencies, github

repositoryRoot: Path = Path(__file__).resolve().parent.parent

rawAlert: dict[str, Any] = {
    "number": 50,
    "html_url": "https://github.com/rpulivella/pybers/security/dependabot/50",
    "dependency": {
        "package": {"ecosystem": "pip", "name": "soupsieve"},
        "manifest_path": "uv.lock",
    },
    "security_advisory": {"severity": "high"},
    "security_vulnerability": {"first_patched_version": {"identifier": "3.0.2"}},
}


def patchGitHub(monkeypatch: pytest.MonkeyPatch, answer: Any) -> None:
    """Answer every GitHub request with a value, or raise it when it is an error."""
    def requestJson(url: str, token: str, **_: Any) -> Any:
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(github, "requestJson", requestJson)
    monkeypatch.setattr(github, "resolveToken", lambda: "token")


def patchPip(monkeypatch: pytest.MonkeyPatch, entries: list[dict[str, str]]) -> None:
    """Answer `pip list --outdated` with these entries."""
    def run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, json.dumps(entries), "")

    monkeypatch.setattr(dependencies.subprocess, "run", run)


def testAnAlertReportsItsPackageFixedReleaseAndLink() -> None:
    assert dependencies.summarizeAlert(rawAlert) == dependencies.DependencyAlert(
        50, "soupsieve", "high", "3.0.2", "uv.lock", rawAlert["html_url"]
    )


def testAnAlertWithNoFixedReleaseSaysSo(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    unpatched = {**rawAlert, "security_vulnerability": {"first_patched_version": None}}
    patchGitHub(monkeypatch, [unpatched])
    assert deps.reportAlerts()
    assert "no fixed release yet" in capsys.readouterr().out


@pytest.mark.parametrize("statusCode", [403, 404])
def testARefusedTokenIsUnreadableNeverEmpty(
    monkeypatch: pytest.MonkeyPatch, statusCode: int
) -> None:
    patchGitHub(monkeypatch, github.GitHubHttpError(statusCode, "refused"))
    with pytest.raises(dependencies.AlertsUnreadableError, match="security_events"):
        dependencies.readOpenAlerts("token")


def testOnlyDeclaredPackagesAreReportedOutdated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patchPip(monkeypatch, [
        {"name": "Typer", "version": "0.27.3", "latest_version": "0.29.1"},
        {"name": "pluggy", "version": "1.6.0", "latest_version": "1.7.0"},
    ])
    assert dependencies.readOutdatedPackages() == [
        dependencies.OutdatedPackage("Typer", "0.27.3", "0.29.1")
    ]


def testDeclaredNamesCompareInTheirNormalSpelling() -> None:
    assert dependencies.normalizePackageName("rich_argparse") == "rich-argparse"
    assert "rich_argparse" in dependencies.readDeclaredPackages()


def testFindingsStillExitZero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    patchGitHub(monkeypatch, [rawAlert])
    patchPip(monkeypatch, [
        {"name": "ruff", "version": "0.16.10", "latest_version": "0.17.5"}
    ])
    assert deps.runReport(deps.buildParser().parse_args(["report"])) == 0
    out = capsys.readouterr().out
    assert "1 open Dependabot alert" in out
    assert "ruff 0.16.10 → 0.17.5" in out


def testNothingToBumpSaysSo(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    patchGitHub(monkeypatch, [])
    patchPip(monkeypatch, [])
    assert deps.runReport(deps.buildParser().parse_args(["report"])) == 0
    out = capsys.readouterr().out
    assert "No open Dependabot alerts" in out
    assert "Every declared package is at its newest release" in out


def testUnreadableAlertsStillReportOutdatedAndExitTwo(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    patchGitHub(monkeypatch, github.GitHubHttpError(403, "refused"))
    patchPip(monkeypatch, [])
    exitCode = deps.runReport(deps.buildParser().parse_args(["report"]))
    out = capsys.readouterr().out
    assert exitCode == deps.errorExitCode
    assert "Dependabot alerts unread" in out
    assert "Every declared package is at its newest release" in out


def testDependabotIsGivenNoUpdateSchedule() -> None:
    assert not (repositoryRoot / ".github" / "dependabot.yml").exists()
    assert not (repositoryRoot / ".github" / "dependabot.yaml").exists()
