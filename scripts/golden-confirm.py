#!/usr/bin/env python3
"""\
pybers golden confirmation tool

Opens a temporary copy of a golden in running Numbers, checks the cells a golden's
expected-values file names, and writes a report a developer reads in place of a manual
session in Numbers. Backs the /golden-confirm skill (PYB-94).

Everything that needs Accessibility, Screen Recording or control of Numbers happens in
pybersdev-golden-confirm.app, built from scripts/golden-confirm-helper/ by the
`helper-build` command, so that Terminal holds none of those permissions.

Shells out to `security`, `swiftc`, `codesign` and `open`, the external toolchain the
house rules allow: no Python library signs an app or starts one under its own grants.

Usage:
    python3 scripts/golden-confirm.py run 11-text-written-and-retyped.numbers
    python3 scripts/golden-confirm.py run 11-text-written-and-retyped.numbers --dry-run
    python3 scripts/golden-confirm.py helper-build
    python3 scripts/golden-confirm.py helper-build --identity <SHA-1> --dry-run
    python3 scripts/golden-confirm.py permissions

Requires rich, and the Xcode command line tools for `helper-build`.

UPDATES
2026-09-17  Written for PYB-94.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/17"
__usage__ = "python3 scripts/golden-confirm.py <command> [options]"

import argparse
import hashlib
import json
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape

try:
    from rich_argparse import RichHelpFormatter
except ImportError:  # rich_argparse is optional, per scripts/README.md
    RichHelpFormatter = argparse.HelpFormatter  # type: ignore[assignment,misc]

console: Console = Console()

repositoryRoot: Path = Path(__file__).resolve().parent.parent
helperSourceDirectory: Path = repositoryRoot / "scripts" / "golden-confirm-helper"
helperSourceFiles: tuple[str, ...] = ("Info.plist", "helper.entitlements", "main.swift")
helperName: str = "pybersdev-golden-confirm"
helperInstallDirectory: Path = Path.home() / "Library/Application Support/pybers"
helperBundle: Path = helperInstallDirectory / f"{helperName}.app"
helperSourceHashKey: str = "PybersSourceHash"
logDirectory: Path = repositoryRoot / "workarea" / "logs"
goldenDirectory: Path = repositoryRoot / "tests" / "golden"
reportRoot: Path = repositoryRoot / "workarea" / "golden-confirm"
expectedSuffix: str = ".expected.toml"
expectedKeys: frozenset[str] = frozenset({
    "sheet", "table", "cell", "value", "formula", "format", "dataFormat", "human",
})
maxCaptures: int = 40
numbersOperators: dict[int, str] = str.maketrans({"×": "*", "÷": "/", "−": "-"})
inspectDeadlineSeconds: float = 300.0

# Slack beyond the helper's own deadline, for `open` to start it and write the result.
helperLaunchSlackSeconds: float = 30.0


class GoldenConfirmError(RuntimeError):
    """A run that cannot continue, with a message naming what to do about it."""


@dataclass(frozen=True)
class HelperProblem:
    """One reason the helper refused or failed, and where a developer fixes it."""

    kind: str
    detail: str
    remedy: str


@dataclass(frozen=True)
class ExpectedCell:
    """One cell an expected-values file names, and what Numbers should show for it."""

    sheet: str
    table: str
    cell: str
    value: object
    formula: str | None
    formatKind: str | None
    dataFormat: dict[str, str]
    human: tuple[str, ...]


@dataclass(frozen=True)
class Check:
    """One check of a run: passed, failed, or left for a human, with its screenshot."""

    status: str
    subject: str
    detail: str
    evidence: str = ""


@dataclass
class GoldenRun:
    """Everything one run found, which the report and the console both present."""

    golden: Path
    ticket: str
    outputDirectory: Path
    captureCount: int
    checks: list[Check]
    problems: list[HelperProblem] = field(default_factory=list)
    archiveDifferences: list[str] = field(default_factory=list)
    numbersVersion: str | None = None


@dataclass(frozen=True)
class HelperBuild:
    """What `helper-build` produced, or would produce under `--dry-run`."""

    identity: str
    sourceHash: str
    bundle: Path
    installed: bool


def runTool(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one external toolchain command, raising with its output when it fails."""
    try:
        completed = subprocess.run(
            arguments, capture_output=True, text=True, check=False
        )
    except FileNotFoundError as exc:
        raise GoldenConfirmError(f"{arguments[0]} is not installed") from exc
    if completed.returncode != 0:
        raise GoldenConfirmError(
            f"{arguments[0]} exited {completed.returncode}: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed


def readHelperSourceHash() -> str:
    """Hash the helper's source in the repository, the value a current build carries."""
    digest = hashlib.sha256()
    for name in helperSourceFiles:
        digest.update(name.encode())
        digest.update((helperSourceDirectory / name).read_bytes())
    return digest.hexdigest()


def readInstalledHelperHash() -> str | None:
    """Return the source hash stamped into the installed helper, or None when absent."""
    infoPath = helperBundle / "Contents" / "Info.plist"
    if not infoPath.is_file():
        return None
    with infoPath.open("rb") as handle:
        value = plistlib.load(handle).get(helperSourceHashKey)
    return value if isinstance(value, str) else None


def findSigningIdentity(requested: str | None) -> str:
    """Resolve the one Apple Development identity to sign with, refusing ambiguity."""
    listing = runTool(["security", "find-identity", "-v", "-p", "codesigning"]).stdout
    identities: list[tuple[str, str]] = re.findall(
        r'^\s*\d+\)\s+([0-9A-F]{40})\s+"(.+)"$', listing, re.MULTILINE
    )
    if requested is not None:
        for fingerprint, label in identities:
            if requested in (fingerprint, label):
                return fingerprint
        raise GoldenConfirmError(f"no valid signing identity matches {requested}")
    development = [
        pair for pair in identities if pair[1].startswith("Apple Development:")
    ]
    if len(development) != 1:
        raise GoldenConfirmError(
            f"found {len(development)} Apple Development identities; pass --identity "
            "with one fingerprint from `security find-identity -v -p codesigning`. "
            "Xcode, Settings, Accounts creates one when there is none"
        )
    return development[0][0]


def buildHelper(identity: str, dryRun: bool) -> HelperBuild:
    """Compile, sign and install the helper, replacing any installed build."""
    sourceHash = readHelperSourceHash()
    if dryRun:
        return HelperBuild(identity, sourceHash, helperBundle, installed=False)
    helperInstallDirectory.mkdir(parents=True, exist_ok=True)
    # Staged beside the install so the final move is a rename on one volume.
    with tempfile.TemporaryDirectory(dir=helperInstallDirectory) as staging:
        bundle = Path(staging) / f"{helperName}.app"
        executableDirectory = bundle / "Contents" / "MacOS"
        executableDirectory.mkdir(parents=True)
        with (helperSourceDirectory / "Info.plist").open("rb") as handle:
            info = plistlib.load(handle)
        info[helperSourceHashKey] = sourceHash
        with (bundle / "Contents" / "Info.plist").open("wb") as handle:
            plistlib.dump(info, handle)
        runTool([
            "swiftc", "-O", "-module-cache-path", str(Path(staging) / "module-cache"),
            "-o", str(executableDirectory / helperName),
            str(helperSourceDirectory / "main.swift"),
        ])
        runTool([
            "codesign", "--force", "--options", "runtime", "--timestamp=none",
            "--entitlements", str(helperSourceDirectory / "helper.entitlements"),
            "--sign", identity, str(bundle),
        ])
        runTool(["codesign", "--verify", "--strict", str(bundle)])
        if helperBundle.exists():
            shutil.rmtree(helperBundle)
        bundle.rename(helperBundle)
    return HelperBuild(identity, sourceHash, helperBundle, installed=True)


def checkHelperCurrent() -> None:
    """Refuse a run whose helper is missing or was built from other source (AC 14)."""
    installed = readInstalledHelperHash()
    if installed is None:
        raise GoldenConfirmError(
            f"{helperBundle} is not installed; run "
            "`python3 scripts/golden-confirm.py helper-build`"
        )
    if installed != readHelperSourceHash():
        raise GoldenConfirmError(
            "the installed helper was built from different source than this checkout; "
            "run `python3 scripts/golden-confirm.py helper-build`"
        )


def requestHelper(request: dict[str, Any], deadlineSeconds: float) -> dict[str, Any]:
    """Start the helper on one request and return its result, failing without one."""
    checkHelperCurrent()
    logDirectory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dt%H-%M-%S")
    logPath = logDirectory / f"golden-confirm-helper-{stamp}.log"
    with tempfile.TemporaryDirectory(prefix="pybers-golden-confirm-") as exchange:
        requestPath = Path(exchange) / "request.json"
        resultPath = Path(exchange) / "result.json"
        body = {
            **request,
            "resultPath": str(resultPath),
            "deadlineSeconds": deadlineSeconds,
        }
        requestPath.write_text(json.dumps(body))
        try:
            subprocess.run(
                [
                    "open", "-n", "-W", "-g", "--stdout", str(logPath),
                    "--stderr", str(logPath), "-a", str(helperBundle),
                    "--args", str(requestPath),
                ],
                check=True, capture_output=True, text=True,
                timeout=deadlineSeconds + helperLaunchSlackSeconds,
            )
        except subprocess.CalledProcessError as exc:
            raise GoldenConfirmError(
                f"open could not start the helper: {exc.stderr}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise GoldenConfirmError(
                f"the helper ran past its deadline and wrote no result; see {logPath}"
            ) from exc
        if not resultPath.is_file():
            raise GoldenConfirmError(f"the helper wrote no result; see {logPath}")
        result: dict[str, Any] = json.loads(resultPath.read_text())
    if result.get("sourceHash") != readHelperSourceHash():
        raise GoldenConfirmError(
            "the helper that answered is not the build this checkout expects"
        )
    return result


def readProblems(result: dict[str, Any]) -> list[HelperProblem]:
    """Return the problems a helper result reports, in the order it found them."""
    return [HelperProblem(**problem) for problem in result.get("problems", [])]


def checkPermissions() -> list[HelperProblem]:
    """Ask the helper for every session and permission problem it can see (AC 9)."""
    result = requestHelper({"operation": "permissionsCheck"}, deadlineSeconds=20.0)
    return readProblems(result)


def findGolden(argument: str) -> Path:
    """Resolve a golden named on the command line, refusing one outside tests/golden."""
    candidate = Path(argument)
    if not candidate.is_absolute():
        inFolder = goldenDirectory / candidate.name
        candidate = inFolder if inFolder.exists() else repositoryRoot / candidate
    golden = candidate.resolve()
    if golden.parent != goldenDirectory or golden.suffix != ".numbers":
        raise GoldenConfirmError(f"{argument} is not a .numbers file in tests/golden/")
    if not golden.is_file():
        raise GoldenConfirmError(f"{golden} does not exist")
    return golden


def readTicketKey() -> str:
    """Return the ticket key the current branch names, such as PYB-94 (AC 18)."""
    branch = runTool(["git", "-C", str(repositoryRoot), "branch", "--show-current"])
    match = re.match(r"^[a-z]+/(\d+)-", branch.stdout.strip())
    if match is None:
        raise GoldenConfirmError(
            f"branch {branch.stdout.strip() or '(detached)'} names no ticket, so the "
            "report has no folder; switch to a <type>/<N>-<title> branch"
        )
    return f"PYB-{match.group(1)}"


def readExpectedCells(golden: Path) -> list[ExpectedCell]:
    """Read the cells to check and what each should show, from beside the golden."""
    path = golden.with_name(f"{golden.stem}{expectedSuffix}")
    if not path.is_file():
        raise GoldenConfirmError(f"{path.name} does not exist beside {golden.name}")
    try:
        with path.open("rb") as handle:
            entries = tomllib.load(handle).get("cell", [])
    except tomllib.TOMLDecodeError as exc:
        raise GoldenConfirmError(f"{path.name} is not valid TOML: {exc}") from exc
    cells: list[ExpectedCell] = []
    for position, entry in enumerate(entries, start=1):
        unknown = set(entry) - expectedKeys
        missing = {"sheet", "table", "cell"} - set(entry)
        if unknown or missing:
            raise GoldenConfirmError(
                f"{path.name} cell {position}: unknown keys {sorted(unknown)}, "
                f"missing keys {sorted(missing)}"
            )
        cells.append(ExpectedCell(
            sheet=entry["sheet"], table=entry["table"], cell=entry["cell"],
            value=entry.get("value"), formula=entry.get("formula"),
            formatKind=entry.get("format"),
            dataFormat={str(key): str(value) for key, value in
                        entry.get("dataFormat", {}).items()},
            human=tuple(entry.get("human", ())),
        ))
    if not cells:
        raise GoldenConfirmError(f"{path.name} names no [[cell]] to check")
    addresses = [(cell.sheet, cell.table, cell.cell) for cell in cells]
    if len(set(addresses)) != len(addresses):
        raise GoldenConfirmError(f"{path.name} names the same cell twice")
    return cells


def readFileHash(path: Path) -> str:
    """Return a file's SHA-256, the proof a golden left a run unchanged (AC 2)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def readDataFormatSettings(elements: list[dict[str, str]]) -> dict[str, str]:
    """Name each Data Format control by the label Numbers shows beside it."""
    settings: dict[str, str] = {}
    items: list[str] = []
    pendingLabel: str | None = None
    unlabeled = 0
    for position, element in enumerate(elements):
        role, value = element["role"], element["value"]
        following = elements[position + 1] if position + 1 < len(elements) else None
        if role == "AXStaticText":
            if value.endswith(":"):
                pendingLabel = value[:-1]
            continue
        if role == "AXPopUpButton" and "Data Format" not in settings:
            settings["Data Format"] = value
        elif role == "AXCheckBox":
            settings[(element["title"] or element["label"]).strip()] = value
        elif pendingLabel is not None:
            settings[pendingLabel] = value
        elif (role == "AXTextField" and following is not None
              and following["role"] == "AXStaticText"
              and not following["value"].endswith(":") and following["value"] != "–"):
            settings[following["value"]] = value
        elif role == "AXTextField":
            items.append(value)
        else:
            unlabeled += 1
            settings[f"Unlabeled {role[2:]} {unlabeled}"] = value
        pendingLabel = None
    if items:
        settings["Items"] = ", ".join(items)
    return settings


def readFormulaText(shown: str) -> str:
    """Spell a formula as pybers does, from the typographic operators Numbers shows."""
    # Numbers ends some formulas it saved itself with a newline outside the formula.
    return shown.translate(numbersOperators).rstrip()


def checkValue(expected: object, reading: dict[str, str]) -> bool:
    """Compare an expected TOML value with what Numbers reads, region-free (AC 4)."""
    kind, text = reading["kind"], reading["text"]
    if isinstance(expected, bool):
        return kind == "boolean" and text == str(expected).lower()
    if isinstance(expected, int | float):
        return kind == "number" and float(text) == float(expected)
    if isinstance(expected, datetime):
        return kind == "date" and text == expected.strftime("%Y-%m-%dT%H:%M:%S")
    if expected == "":
        return kind in ("empty", "text") and text == ""
    return kind == "text" and text == expected


def checkCell(expected: ExpectedCell, reading: dict[str, Any]) -> list[Check]:
    """Compare everything expected of one cell with what Numbers read (AC 4, AC 8)."""
    subject = f"{expected.sheet} / {expected.table} / {expected.cell}"
    evidence = Path(reading.get("inspectorCapture") or "").name
    checks: list[Check] = []

    def record(name: str, passed: bool, wanted: object, found: object) -> None:
        """Add one comparison, showing both sides when it fails."""
        detail = f"{name} {found}"
        if not passed:
            detail += f", expected {wanted!r}"
        status = "passed" if passed else "failed"
        checks.append(Check(status, subject, detail, evidence))

    if expected.value is not None:
        value = reading.get("value") or {"kind": "missing", "text": ""}
        # The formatted value follows region settings, so it is shown, never compared.
        shown = f"{value['kind']} {value['text']!r}, shown as "
        record("value", checkValue(expected.value, value), expected.value,
               shown + repr(reading.get("formattedValue")))
    if expected.formula is not None:
        found = readFormulaText(reading.get("formula") or "")
        record("formula", found == expected.formula, expected.formula, repr(found))
    if expected.formatKind is not None:
        found = reading.get("formatKind") or ""
        record("format", found == expected.formatKind, expected.formatKind, repr(found))
    settings = readDataFormatSettings(reading.get("dataFormat", []))
    for label, wanted in expected.dataFormat.items():
        name = label if label == "Data Format" else f"Data Format {label}"
        record(name, settings.get(label) == wanted, wanted, repr(settings.get(label)))
    for question in expected.human:
        checks.append(Check("human", subject, question, evidence))
    return checks


def renderQuickLook(golden: Path, outputDirectory: Path) -> Path:
    """Render the golden's Quick Look image, whose values Numbers never recalculated."""
    runTool(["qlmanage", "-t", "-s", "2400", "-o", str(outputDirectory), str(golden)])
    rendered = outputDirectory / f"{golden.name}.png"
    if not rendered.is_file():
        raise GoldenConfirmError(f"Quick Look rendered nothing for {golden.name}")
    target = outputDirectory / "quick-look.png"
    rendered.rename(target)
    return target


def readSavedCopyDifferences(golden: Path, saved: Path) -> list[str]:
    """Name every member and archive the Numbers-saved copy holds differently (AC 7)."""
    # Internal on purpose: pybers exposes no archives, and round-trip tests share this.
    from pybers._persistence import readPackage
    from pybers._persistence.difference import listPackageDifferences

    before, after = readPackage(golden), readPackage(saved)
    return [str(difference) for difference in listPackageDifferences(before, after)]


def runGoldenConfirm(golden: Path, dryRun: bool) -> GoldenRun:
    """Confirm one golden in running Numbers and return every check it made."""
    ticket = readTicketKey()
    expectedCells = readExpectedCells(golden)
    sheets = list(dict.fromkeys(cell.sheet for cell in expectedCells))
    captureCount = len(sheets) + len(expectedCells)
    if captureCount > maxCaptures:
        raise GoldenConfirmError(
            f"checking these cells takes {captureCount} screenshots, over the limit of "
            f"{maxCaptures}; split the expected-values file"
        )
    outputDirectory = reportRoot / ticket / golden.stem
    run = GoldenRun(golden, ticket, outputDirectory, captureCount, [])
    if dryRun:
        return run

    problems = checkPermissions()
    if problems:
        raise GoldenConfirmError("the helper cannot run:\n" + "\n".join(
            f"  {p.kind}: {p.detail}. {p.remedy}" for p in problems
        ))
    if outputDirectory.exists():
        shutil.rmtree(outputDirectory)
    outputDirectory.mkdir(parents=True)
    goldenHash = readFileHash(golden)
    with tempfile.TemporaryDirectory(prefix="pybers-golden-copy-") as work:
        copy = Path(work) / golden.name
        saved = Path(work) / f"{golden.stem}-saved-by-numbers.numbers"
        shutil.copyfile(golden, copy)
        result = requestHelper({
            "operation": "documentInspect",
            "documentPath": str(copy),
            "savedCopyPath": str(saved),
            "captureDirectory": str(outputDirectory),
            "cells": [{"sheet": c.sheet, "table": c.table, "cell": c.cell}
                      for c in expectedCells],
            "maxCaptures": maxCaptures,
        }, deadlineSeconds=inspectDeadlineSeconds)
        run.numbersVersion = result.get("numbersVersion")
        run.problems.extend(readProblems(result))
        opened = result.get("openOutcome")
        if opened is None and run.problems:
            shutil.rmtree(outputDirectory)
            raise GoldenConfirmError("the helper refused before opening:\n" + "\n".join(
                f"  {p.kind}: {p.detail}. {p.remedy}" for p in run.problems
            ))
        if opened is not None:
            alert = " ".join(result.get("alertText", []))
            run.checks.append(Check(
                "passed" if opened == "opened" else "failed", "document",
                f"Numbers {opened} the copy" + (f": {alert}" if alert else ""),
            ))
        readings = {
            (r["address"]["sheet"], r["address"]["table"], r["address"]["cell"]): r
            for r in result.get("cells", [])
        }
        for expected in expectedCells:
            reading = readings.get((expected.sheet, expected.table, expected.cell))
            if reading is None:
                if opened == "opened":
                    subject = f"{expected.sheet} / {expected.table} / {expected.cell}"
                    run.checks.append(Check(
                        "failed", subject, "the helper returned no reading for it"))
                continue
            run.checks.extend(checkCell(expected, reading))
        for capture in result.get("sheetCaptures", []):
            run.checks.append(Check(
                "human", capture["sheet"], "the sheet as Numbers displays it",
                Path(capture["path"]).name))
        if result.get("savedCopy") and saved.is_file():
            differences = readSavedCopyDifferences(golden, saved)
            run.archiveDifferences.extend(differences)
            run.checks.append(Check(
                "human", "saved copy",
                f"{len(differences)} members or archives differ once Numbers saves it",
                "report.md"))
    run.checks.append(Check(
        "human", "Quick Look", "what pybers stored, before Numbers recalculates",
        renderQuickLook(golden, outputDirectory).name))
    unchanged = readFileHash(golden) == goldenHash
    run.checks.append(Check(
        "passed" if unchanged else "failed", "golden",
        "byte-identical after the run" if unchanged else "CHANGED during the run"))
    writeReport(run)
    return run


def writeReport(run: GoldenRun) -> Path:
    """Write the Markdown report beside its screenshots, images linked relatively."""
    lines = [
        f"# {run.golden.name}",
        "",
        f"{run.ticket}, {datetime.now().strftime('%Y-%m-%d %H:%M')}, "
        f"Numbers {run.numbersVersion or 'unknown'}",
        "",
    ]
    for problem in run.problems:
        lines += [f"- **{problem.kind}**: {problem.detail}. {problem.remedy}"]
    for status in ("failed", "human", "passed"):
        chosen = [check for check in run.checks if check.status == status]
        if not chosen:
            continue
        lines += ["", f"## {status.capitalize()} ({len(chosen)})", ""]
        for check in chosen:
            link = f" [{check.evidence}]({check.evidence})" if check.evidence else ""
            lines.append(f"- {check.subject}: {check.detail}{link}")
    images = sorted(path.name for path in run.outputDirectory.glob("*.png"))
    if images:
        lines += ["", "## Screenshots", ""]
        lines += [f"### {name}\n\n![{name}]({name})\n" for name in images]
    if run.archiveDifferences:
        lines += ["", "## Archives the Numbers-saved copy holds differently", ""]
        lines += [f"- {difference}" for difference in run.archiveDifferences]
    reportPath = run.outputDirectory / "report.md"
    reportPath.write_text("\n".join(lines) + "\n")
    return reportPath


def reportProblems(problems: list[HelperProblem]) -> None:
    """Print each problem with the place a developer fixes it."""
    for problem in problems:
        console.print(f"[red]{escape(problem.kind)}[/]: {escape(problem.detail)}")
        console.print(f"  [dim]{escape(problem.remedy)}[/]")


def runHelperBuild(arguments: argparse.Namespace) -> int:
    """Build, sign and install the helper, or preview that under --dry-run."""
    identity = findSigningIdentity(arguments.identity)
    build = buildHelper(identity, arguments.dry_run)
    verb = "installed" if build.installed else "would install"
    console.print(f"[green]{verb}[/] {escape(str(build.bundle))}")
    console.print(f"  signed by {escape(build.identity)}")
    console.print(f"  source hash {escape(build.sourceHash)}")
    return 0


def runPermissions(arguments: argparse.Namespace) -> int:
    """Report whether the helper can run, and what to grant when it cannot."""
    problems = checkPermissions()
    if not problems:
        console.print("[green]the helper holds every permission it needs[/]")
        return 0
    reportProblems(problems)
    return 1


def runRun(arguments: argparse.Namespace) -> int:
    """Confirm a golden in running Numbers and summarize the report it wrote."""
    golden = findGolden(arguments.golden)
    run = runGoldenConfirm(golden, arguments.dry_run)
    if arguments.dry_run:
        console.print(f"[green]would confirm[/] {escape(golden.name)} for {run.ticket}")
        console.print(f"  {run.captureCount} screenshots into "
                      f"{escape(str(run.outputDirectory))}")
        return 0
    reportProblems(run.problems)
    counts = {status: sum(1 for c in run.checks if c.status == status)
              for status in ("passed", "failed", "human")}
    for check in run.checks:
        if check.status == "failed":
            console.print(
                f"[red]failed[/] {escape(check.subject)}: {escape(check.detail)}"
            )
    console.print(
        f"[green]{counts['passed']} passed[/], [red]{counts['failed']} failed[/], "
        f"[yellow]{counts['human']} left for a human[/]"
    )
    console.print(f"report: {escape(str(run.outputDirectory / 'report.md'))}")
    return 1 if counts["failed"] or run.problems else 0


def buildParser() -> argparse.ArgumentParser:
    """Describe the command line, one subcommand per handler."""
    parser = argparse.ArgumentParser(
        prog="golden-confirm.py", description="Confirm a golden in running Numbers.",
        formatter_class=RichHelpFormatter,
    )
    commands = parser.add_subparsers(required=True)

    build = commands.add_parser(
        "helper-build", help="build, sign and install pybersdev-golden-confirm.app",
        formatter_class=RichHelpFormatter,
    )
    build.add_argument("--identity", help="signing identity fingerprint or name")
    build.add_argument("--dry-run", action="store_true", help="resolve and report only")
    build.set_defaults(handler=runHelperBuild)

    permissions = commands.add_parser(
        "permissions", help="report what the helper still needs granted",
        formatter_class=RichHelpFormatter,
    )
    permissions.set_defaults(handler=runPermissions)

    confirm = commands.add_parser(
        "run", help="confirm one golden in running Numbers and write its report",
        formatter_class=RichHelpFormatter,
    )
    confirm.add_argument("golden", help="a .numbers file in tests/golden/")
    confirm.add_argument("--dry-run", action="store_true",
                         help="check the golden and its expected values, open nothing")
    confirm.set_defaults(handler=runRun)
    return parser


def main() -> int:
    """Parse the command line and dispatch, reporting failures without a traceback."""
    arguments = buildParser().parse_args()
    try:
        return int(arguments.handler(arguments))
    except GoldenConfirmError as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return 2


if __name__ == "__main__":
    sys.exit(main())
