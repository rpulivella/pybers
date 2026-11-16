#!/usr/bin/env python3
"""\
What a project declares, which of it has a newer release, and what Dependabot flags.

Both reports only inform. Readiness keeps its own advisory check, which blocks.

UPDATES
2026-11-16  Written for PYB-295, taking `readDeclaredPackages` from readiness.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/16"

import importlib.metadata
import json
import re
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Lazy, since the job posting the readiness comment installs rich alone.
lazy from packaging.version import Version

from tools.workflow.lib import github
from tools.workflow.lib.shared import repositoryRoot

projectPath: Path = repositoryRoot / "pyproject.toml"
alertsPageSize: int = 100
pypiRoot: str = "https://pypi.org/pypi"
networkTimeoutSeconds: float = 30.0


@dataclass(frozen=True)
class DependencyAlert:
    """One open Dependabot alert."""

    number: int
    package: str
    severity: str
    fixedIn: str
    manifest: str
    url: str


@dataclass(frozen=True)
class OutdatedPackage:
    """A declared package whose installed version trails its newest release."""

    name: str
    installed: str
    newest: str


class AlertsUnreadableError(RuntimeError):
    """GitHub refused the alerts, so whether any are open is unknown."""


def normalizePackageName(name: str) -> str:
    """Return a package name in the one spelling PyPI compares, per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def readDeclaredPackages() -> list[str]:
    """Return every package this project declares, runtime and development alike."""
    with projectPath.open("rb") as handle:
        project = tomllib.load(handle)["project"]
    declared = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        declared += extra
    return [
        re.split(r"[<>=!~\[; ]", entry, maxsplit=1)[0] for entry in declared if entry
    ]


def summarizeAlert(raw: dict[str, Any]) -> DependencyAlert:
    """Return the fields of one alert a review reports."""
    patched = raw["security_vulnerability"].get("first_patched_version") or {}
    return DependencyAlert(
        number=int(raw["number"]),
        package=str(raw["dependency"]["package"]["name"]),
        severity=str(raw["security_advisory"]["severity"]),
        fixedIn=str(patched.get("identifier") or ""),
        manifest=str(raw["dependency"].get("manifest_path") or ""),
        url=str(raw["html_url"]),
    )


def readOpenAlerts(token: str) -> list[DependencyAlert]:
    """Return the open Dependabot alerts on the repository, oldest first, one page.

    A 403 or 404 means the token lacks a scope that reads alerts, or alerts are off,
    and never that none are open, so it raises rather than returning [].
    """
    url = (
        f"{github.restRoot}/repos/{github.repositoryOwner}/{github.repositoryName}"
        f"/dependabot/alerts?state=open&per_page={alertsPageSize}&direction=asc"
    )
    try:
        raw = github.requestJson(url, token)
    except github.GitHubHttpError as exc:
        if exc.statusCode in (403, 404):
            raise AlertsUnreadableError(
                "Dependabot alerts could not be read: the token lacks the "
                "security_events scope, or public_repo on a public repository, "
                f"or alerts are off. {exc}"
            ) from exc
        raise
    return [summarizeAlert(item) for item in raw]


def readNewestRelease(name: str) -> str:
    """Return a package's newest release on PyPI, raising when PyPI cannot answer."""
    url = f"{pypiRoot}/{urllib.parse.quote(name)}/json"
    try:
        with urllib.request.urlopen(url, timeout=networkTimeoutSeconds) as response:
            return str(json.loads(response.read())["info"]["version"])
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        raise RuntimeError(f"PyPI could not say the newest {name}: {exc}") from exc


def readOutdatedPackages() -> list[OutdatedPackage]:
    """Return each declared package installed here at less than its newest release.

    Asks PyPI directly, because `pip list --outdated` answers [] when the index is
    unreachable, which would read as every package being current.
    """
    with projectPath.open("rb") as handle:
        projectName = normalizePackageName(tomllib.load(handle)["project"]["name"])
    names = sorted(
        {normalizePackageName(name) for name in readDeclaredPackages()} - {projectName}
    )
    outdated: list[OutdatedPackage] = []
    for name in names:
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        newest = readNewestRelease(name)
        if Version(installed) < Version(newest):
            outdated.append(OutdatedPackage(name, installed, newest))
    return outdated
