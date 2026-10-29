#!/usr/bin/env python3
"""\
The golden confirmation's logic: building and checking the helper, reading what a golden
expects, comparing it with what Numbers read, and writing the report.

`golden_confirm.py` keeps only its command line, and the report's text functions run
without Numbers, the helper or a logged-in Mac.

UPDATES
2026-10-29  A formula is compared as Numbers saved it, its shown text in the
            document's language left for a person, for PYB-272.
2026-10-24  The expectations' machine form is the golden's JSON form, for PYB-259.
2026-10-23  `--preview` names what was `--dry-run`, as the command-line design does,
            for PYB-156.
2026-10-22  Every cell of every table is checked against what pybers reads from the
            golden, and the inspector only where a setting needs it, for PYB-255.
2026-10-22  A golden's expected values are generated from the golden, for PYB-220.
2026-10-22  A run's folder holds a copy of the golden to open and its expectations
            as headed Markdown, for PYB-220.
2026-10-21  The helper names each Data Format control, and a recipe step sets one,
            for PYB-219.
2026-10-14  A missing or stale helper states the miss and stops, as house rule 11
            asks, for PYB-204.
2026-10-14  The confirmation's logic moved here from `golden_confirm.py`, for
            PYB-204.
2026-10-13  Moved here from `scripts/golden_confirm_lib.py`, for PYB-204.
2026-10-13  Written for PYB-201.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/13"

import hashlib
import json
import plistlib
import re
import shutil
import subprocess
import tempfile
import tomllib
import zipfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, assert_never

import pybers
from pybers import (
    CellControl,
    CellControlCheckbox,
    CellControlPopUpMenu,
    CellControlSlider,
    CellControlStarRating,
    CellControlStepper,
    CellControlUnknown,
    CellFormat,
    CellRange,
    CellReference,
    CurrencyAmount,
    PybersError,
)
from pybers._persistence import readPackage
from pybers._persistence.difference import listPackageDifferences
from pybers.formula.syntax import (
    FormulaSyntaxError,
    formulaMarker,
    percentSymbol,
    tokenize,
)
from tools.local.lib.golden_expected import (
    ExpectedCell,
    ExpectedTable,
    ExpectedValues,
    buildExpectedValues,
    formatValue,
    writeExpectations,
    writeExpectationsJson,
)
from tools.workflow.lib.shared import readTicketNumber, repositoryRoot


def formatCodeSpan(value: object) -> str:
    """Quote one reported value as a Markdown code span, fenced past its backticks."""
    if value is None:
        return "nothing"
    text = str(value).lower() if isinstance(value, bool) else str(value)
    if text == "":
        return "empty text"
    fence = "`" * (max((len(run) for run in re.findall("`+", text)), default=0) + 1)
    padding = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{padding}{text}{padding}{fence}"


def formatSpacedFormula(text: str) -> str:
    """Return a formula with one space each side of every binary operator, for reading.

    Only the report reads this; every check compares the exact text Numbers read.
    """
    body = text.removeprefix(formulaMarker)
    try:
        tokens = tokenize(body)
    except FormulaSyntaxError:
        return text
    pieces: list[str] = []
    expectsOperand = True
    for token in tokens[:-1]:
        piece = body[token.position:token.position + token.width]
        isOperator = token.kind == "operator" and token.text != percentSymbol
        pieces.append(f" {piece} " if isOperator and not expectsOperand else piece)
        expectsOperand = token.kind in ("open", "comma") or isOperator
    return text[:len(text) - len(body)] + "".join(pieces)


helperSourceDirectory: Path = Path(__file__).parent / "golden-confirm-helper"


helperSourceFiles: tuple[str, ...] = ("Info.plist", "helper.entitlements", "main.swift")


helperName: str = "pybersdev-golden-confirm"


helperInstallDirectory: Path = Path.home() / "Library/Application Support/pybers"


helperBundle: Path = helperInstallDirectory / f"{helperName}.app"


helperSourceHashKey: str = "PybersSourceHash"


goldenDirectory: Path = repositoryRoot / "tests" / "golden"


documentDirectories: tuple[Path, ...] = (
    repositoryRoot / "tests" / "fixtures", repositoryRoot / "tests" / "measurements",
    goldenDirectory,
)


measurementDirectory: Path = repositoryRoot / "tests" / "measurements"


recipeSuffix: str = ".recipe.toml"


recipeDefaultKeys: tuple[str, ...] = ("document", "sheet", "table")


recipeStepKeys: frozenset[str] = frozenset({
    "action", "document", "sheet", "table", "range", "menuItem", "format", "value",
    "setting",
})


reportRoot: Path = repositoryRoot / "workarea" / "golden-confirm"


# A run launches a closed Numbers itself, so its permissions check does not refuse one.
numbersNotRunningKind: str = "numbersNotRunning"


maxCaptures: int = 40


quickLookScale: float = 3.0


numbersOperators: dict[int, str] = str.maketrans({"×": "*", "÷": "/", "−": "-"})


inspectDeadlineSeconds: float = 300.0


# What reading one more grid cell adds to a run's deadline, AppleScript asking per cell.
gridSecondsPerCell: float = 0.1


# Slack beyond the helper's own deadline, for `open` to start it and write the result.
helperLaunchSlackSeconds: float = 30.0


openAttempts: int = 2


class GoldenConfirmError(RuntimeError):
    """A run that cannot continue, with a message naming what to do about it."""


@dataclass(frozen=True)
class HelperProblem:
    """One reason the helper refused or failed, and where a developer fixes it."""

    kind: str
    detail: str
    remedy: str


@dataclass(frozen=True)
class Check:
    """One check of a run: passed, failed, or left for QA, with its screenshot."""

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
class MeasurementRecipe:
    """How Numbers makes one measurement: the documents it opens and its steps."""

    base: str
    documents: list[str]
    steps: list[dict[str, Any]]


@dataclass(frozen=True)
class HelperBuild:
    """What `helper-build` produced, or would produce under `--preview`."""

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


def buildHelper(identity: str, preview: bool) -> HelperBuild:
    """Compile, sign and install the helper, replacing any installed build."""
    sourceHash = readHelperSourceHash()
    if preview:
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
        raise GoldenConfirmError(f"{helperBundle} is not installed")
    if installed != readHelperSourceHash():
        raise GoldenConfirmError(
            "the installed helper was built from different source than this checkout"
        )


@contextmanager
def holdDisplayAwake() -> Iterator[None]:
    """Keep the display awake, since the lock that follows its sleep stops a run."""
    awake = subprocess.Popen(["caffeinate", "-d", "-i"])
    try:
        yield
    finally:
        awake.terminate()
        awake.wait(timeout=5)


def requestHelper(
    request: dict[str, Any], deadlineSeconds: float, logPath: Path = Path("/dev/null")
) -> dict[str, Any]:
    """Start the helper on one request and return its result, failing without one."""
    checkHelperCurrent()
    with tempfile.TemporaryDirectory(prefix="pybers-golden-confirm-") as exchange:
        requestPath = Path(exchange) / "request.json"
        resultPath = Path(exchange) / "result.json"
        body = {
            **request,
            "resultPath": str(resultPath),
            "deadlineSeconds": deadlineSeconds,
        }
        requestPath.write_text(json.dumps(body))
        command = [
            "open", "-n", "-W", "-g", "--stdout", str(logPath), "--stderr",
            str(logPath), "-a", str(helperBundle), "--args", str(requestPath),
        ]
        try:
            for attempt in range(openAttempts):
                opened = subprocess.run(
                    command, check=False, capture_output=True, text=True,
                    timeout=deadlineSeconds + helperLaunchSlackSeconds,
                )
                # `open` can fail to start waiting, which leaves the helper never run.
                if opened.returncode == 0 or resultPath.is_file():
                    break
                if attempt == openAttempts - 1 or checkHelperRunning():
                    raise GoldenConfirmError(
                        f"open could not start the helper: {opened.stderr.strip()}"
                    )
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


def checkHelperRunning() -> bool:
    """Report whether a helper is still running, which a retried launch would double."""
    executable = str(helperBundle / "Contents" / "MacOS" / helperName)
    found = subprocess.run(["pgrep", "-f", executable], capture_output=True)
    return found.returncode == 0


def readProblems(result: dict[str, Any]) -> list[HelperProblem]:
    """Return the problems a helper result reports, in the order it found them."""
    return [HelperProblem(**problem) for problem in result.get("problems", [])]


def checkPermissions() -> list[HelperProblem]:
    """Ask the helper for every session and permission problem it can see (AC 9)."""
    result = requestHelper(
        {"operation": "permissionsCheck"}, deadlineSeconds=20.0
    )
    return readProblems(result)


def checkHelperCanRun() -> None:
    """Refuse a run the helper cannot make, allowing a closed Numbers it launches."""
    problems = [p for p in checkPermissions() if p.kind != numbersNotRunningKind]
    if problems:
        raise GoldenConfirmError("the helper cannot run:\n" + "\n".join(
            f"  {p.kind}: {p.detail}. {p.remedy}" for p in problems
        ))


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


def findDocument(stem: str) -> Path:
    """Return the one document named `stem`, refusing none or two."""
    found = [
        directory / f"{stem}.numbers" for directory in documentDirectories
        if (directory / f"{stem}.numbers").is_file()
    ]
    if len(found) != 1:
        raise GoldenConfirmError(
            f"{stem}.numbers is in {len(found)} of tests/fixtures, "
            "tests/measurements and tests/golden"
        )
    return found[0]


def readMeasurementRecipe(name: str) -> MeasurementRecipe:
    """Read the recipe a measurement is made from, refusing a key the helper lacks."""
    path = measurementDirectory / f"{name}{recipeSuffix}"
    if not path.is_file():
        raise GoldenConfirmError(f"{path.relative_to(repositoryRoot)} does not exist")
    with path.open("rb") as handle:
        recipe = tomllib.load(handle)
    # A recipe may name its document, sheet and table once, for every step.
    defaults = {key: recipe[key] for key in recipeDefaultKeys if key in recipe}
    steps = [defaults | step for step in recipe.get("step", [])]
    for position, step in enumerate(steps, start=1):
        unknown = set(step) - recipeStepKeys
        if unknown:
            raise GoldenConfirmError(
                f"step {position} of {path.name} holds {', '.join(sorted(unknown))}, "
                "which no step takes"
            )
    return MeasurementRecipe(recipe["base"], recipe.get("documents", []), steps)


def readTicketKey() -> str:
    """Return the ticket key the current branch names, such as PYB-94 (AC 18)."""
    with (repositoryRoot / "pyproject.toml").open("rb") as handle:
        prefix = tomllib.load(handle)["tool"]["pybers"]["ticketPrefix"]
    branch = runTool(["git", "-C", str(repositoryRoot), "branch", "--show-current"])
    number = readTicketNumber(branch.stdout.strip())
    if not number:
        raise GoldenConfirmError(
            f"branch {branch.stdout.strip() or '(detached)'} names no ticket, so the "
            "report has no folder; switch to a <type>/<N>-<title> branch"
        )
    return f"{prefix}-{number}"


def readFileHash(path: Path) -> str:
    """Return a file's SHA-256, the proof a golden left a run unchanged (AC 2)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def readDataFormatSettings(elements: list[dict[str, str]]) -> dict[str, str]:
    """Return each Data Format control's value under the name the helper gave it."""
    settings: dict[str, str] = {}
    items: list[str] = []
    for element in elements:
        name, value = element["setting"], element["value"]
        if name == "Items":
            items.append(value)
        elif name:
            settings[name] = value
    if items:
        settings["Items"] = ", ".join(items)
    return settings


def readFormulaText(shown: str) -> str:
    """Spell a formula as pybers does, from the typographic operators Numbers shows."""
    # Numbers ends some formulas it saved itself with a newline outside the formula.
    return shown.translate(numbersOperators).rstrip()


def readMerges(subject: str, cellNames: list[list[str]]) -> list[str]:
    """Find each merge in Numbers' cell names, where a covered cell names its anchor."""
    corners: dict[str, tuple[int, int]] = {}
    for row, names in enumerate(cellNames, start=1):
        for column, name in enumerate(names, start=1):
            if name != CellReference(row, column).asReference():
                lastRow, lastColumn = corners.get(name, (row, column))
                corners[name] = (max(lastRow, row), max(lastColumn, column))
    try:
        merges = [CellRange.fromReferences(CellReference.parse(anchor),
                                           CellReference(*corner))
                  for anchor, corner in corners.items()]
    except PybersError as exc:
        raise GoldenConfirmError(
            f"{subject}: Numbers named a cell in a way that is not a cell reference: "
            f"{exc}") from exc
    return sorted((str(merge) for merge in merges), key=readMergeOrder)


def readMergeOrder(merge: str) -> tuple[int | None, ...]:
    """Order a merge by its rows, then its columns, rather than as text."""
    extent = CellRange.parse(merge)
    return (extent.startRow, extent.startCol, extent.endRow, extent.endCol)


# A format as AppleScript's `format of cell` names it, once a person chose it.
numbersFormatNames: dict[CellFormat, str] = {
    CellFormat.NUMBER: "number", CellFormat.CURRENCY: "currency",
    CellFormat.PERCENT: "percent", CellFormat.SCIENTIFIC: "scientific",
    CellFormat.FRACTION: "fraction", CellFormat.NUMERAL_SYSTEM: "numeral system",
    CellFormat.TEXT: "text", CellFormat.DATE_TIME: "date and time",
    CellFormat.DURATION: "duration", CellFormat.CHECKBOX: "checkbox",
    CellFormat.STAR_RATING: "rating",
}


# A format as the inspector's Data Format menu titles it.
dataFormatTitles: dict[CellFormat, str] = {
    CellFormat.NUMBER: "Number", CellFormat.CURRENCY: "Currency",
    CellFormat.PERCENT: "Percentage", CellFormat.SCIENTIFIC: "Scientific",
    CellFormat.FRACTION: "Fraction", CellFormat.NUMERAL_SYSTEM: "Numeral System",
    CellFormat.TEXT: "Text", CellFormat.DATE_TIME: "Date & Time",
    CellFormat.DURATION: "Duration", CellFormat.CHECKBOX: "Checkbox",
    CellFormat.STAR_RATING: "Star Rating",
}


def findControlNames(control: CellControl) -> tuple[str, str] | None:
    """Return a control's AppleScript format name and its Data Format menu title."""
    match control:
        case CellControlCheckbox():
            return ("checkbox", "Checkbox")
        case CellControlStarRating():
            return ("rating", "Star Rating")
        case CellControlSlider():
            return ("slider", "Slider")
        case CellControlStepper():
            return ("stepper", "Stepper")
        case CellControlPopUpMenu():
            return ("pop up menu", "Pop-Up Menu")
        case CellControlUnknown():
            return None
        case _:
            assert_never(control)


def findNumbersFormat(cell: ExpectedCell) -> tuple[str, str] | None:
    """Return the format Numbers names for a cell, or None when no name is measured."""
    if cell.control is not None:
        return findControlNames(cell.control)
    if not cell.formatChosen or cell.format is None:
        return ("automatic", "Automatic")
    if cell.format not in numbersFormatNames:
        return None
    return (numbersFormatNames[cell.format], dataFormatTitles[cell.format])


def listInspectorSettings(cell: ExpectedCell) -> dict[str, str]:
    """Return the Data Format settings the inspector shows, by the helper's names."""
    settings: dict[str, str] = {}
    names = findNumbersFormat(cell)
    if names is not None:
        settings["Data Format"] = names[1]
    if cell.currencyMenu is not None:
        settings["Currency"] = cell.currencyMenu
    match cell.control:
        case CellControlSlider(minimum, maximum, increment) | CellControlStepper(
            minimum, maximum, increment
        ):
            settings |= {"Minimum": str(minimum), "Maximum": str(maximum),
                         "Increment": str(increment)}
        case CellControlPopUpMenu(items, _):
            settings["Items"] = ", ".join(items)
    return settings


def checkNeedsInspector(cell: ExpectedCell) -> bool:
    """Report whether a cell holds a setting only the inspector shows."""
    return cell.control is not None or cell.currencyMenu is not None


def checkValue(expected: pybers.CellValue, reading: dict[str, str]) -> bool:
    """Compare a value pybers read with what Numbers read, region-free."""
    kind, text = reading["kind"], reading["text"]
    match expected:
        case None:
            return kind == "empty" or (kind == "text" and text == "")
        case bool():
            return kind == "boolean" and text == str(expected).lower()
        case CurrencyAmount():
            return kind == "number" and Decimal(text) == expected.amount
        case Decimal():
            return kind == "number" and float(text) == float(expected)
        case datetime():
            return kind == "date" and text == expected.strftime("%Y-%m-%dT%H:%M:%S")
        case timedelta():
            return kind == "number" and float(text) == expected.total_seconds()
        case str():
            return kind == "text" and text == expected
        case _:
            return False


def formatReadingValue(reading: dict[str, str]) -> str:
    """Return what Numbers read for a value, its kind first."""
    return f"{reading['kind']} {formatCodeSpan(reading['text'])}"


def listCoveredCells(merges: tuple[str, ...]) -> frozenset[str]:
    """Return every cell a merge covers, its anchor excepted."""
    covered = set()
    for merge in merges:
        extent = CellRange.parse(merge)
        for row in range(extent.startRow or 1, (extent.endRow or 1) + 1):
            for column in range(extent.startCol or 1, (extent.endCol or 1) + 1):
                covered.add(CellReference(row, column).asReference())
        covered.discard(CellReference(extent.startRow or 1, extent.startCol or 1)
                        .asReference())
    return frozenset(covered)


def checkTableGrid(
    expected: ExpectedTable, reading: dict[str, Any],
    savedFormulas: Mapping[str, str] | None,
) -> list[Check]:
    """Compare every cell of a table with what pybers read, a check per difference.

    A formula is compared as Numbers saved it, read back through pybers, since the text
    Numbers shows follows the document's language and region. None for `savedFormulas`
    means Numbers saved no copy to read it from.
    """
    subject = f"{expected.sheet} / {expected.table}"
    checks: list[Check] = []
    filled = {cell.cell: cell for cell in expected.cells}
    covered = listCoveredCells(expected.merges)
    for row, facts in enumerate(reading["cellFacts"], start=1):
        for column, fact in enumerate(facts, start=1):
            name = CellReference(row, column).asReference()
            # AppleScript answers for a covered cell with its anchor's value.
            if name in covered:
                continue
            cell = filled.get(name)
            value = None if cell is None else cell.value
            matched = checkValue(value, fact["value"])
            # pybers stores the result Numbers last cached and evaluates nothing, so a
            # formula's recalculated value is a person's to judge.
            if cell is not None and cell.formula is not None and not matched:
                stored = ("nothing" if value is None
                          else formatCodeSpan(formatValue(value)))
                found = formatReadingValue(fact["value"])
                checks.append(Check("qa", f"{subject} / {name}",
                                    f"Numbers recalculated it to {found}, where "
                                    f"pybers stored {stored}"))
            elif not matched:
                wanted = "empty" if cell is None else formatCodeSpan(formatValue(value))
                checks.append(Check("failed", f"{subject} / {name}",
                                    f"value {formatReadingValue(fact['value'])}, "
                                    f"expected {wanted}"))
            shown = readFormulaText(fact.get("formula") or "") or None
            wantedFormula = None if cell is None else cell.formula
            if savedFormulas is None:
                if wantedFormula is not None:
                    checks.append(Check(
                        "failed", f"{subject} / {name}",
                        "Numbers saved no copy to read its formula from",
                    ))
            elif (saved := savedFormulas.get(name)) != wantedFormula:
                checks.append(Check("failed", f"{subject} / {name}",
                                    f"formula {formatCodeSpan(saved)} as Numbers saved "
                                    f"it, expected {formatCodeSpan(wantedFormula)}"))
            elif shown != wantedFormula:
                checks.append(Check(
                    "qa", f"{subject} / {name}",
                    f"Numbers shows the formula as {formatCodeSpan(shown)}, in the "
                    "document's language and region",
                ))
            names = None if cell is None else findNumbersFormat(cell)
            found = fact.get("formatKind") or ""
            if names is not None and found != names[0]:
                checks.append(Check("failed", f"{subject} / {name}",
                                    f"format {formatCodeSpan(found)}, expected "
                                    f"{formatCodeSpan(names[0])}"))
    if not any(check.status == "failed" for check in checks):
        checks.append(Check("passed", subject,
                            f"every cell holds the value, formula and format pybers "
                            f"read, {len(filled)} of them filled"))
    for axis, declared, counted in (
        ("row", expected.rows, reading["rowCount"]),
        ("column", expected.columns, reading["columnCount"]),
    ):
        detail = f"{counted} {axis}{'' if counted == 1 else 's'}"
        passed = counted == declared
        checks.append(Check("passed" if passed else "failed", subject,
                            detail if passed else f"{detail}, expected {declared}"))
    merged = readMerges(subject, reading["cellNames"])
    for merge in sorted({*expected.merges, *merged}, key=readMergeOrder):
        if merge not in merged:
            checks.append(Check("failed", subject, f"{merge} is not merged"))
        elif merge not in expected.merges:
            checks.append(Check("failed", subject, f"{merge} is merged, unexpectedly"))
        else:
            checks.append(Check("passed", subject, f"{merge} is merged"))
    return checks


def checkCellInspector(
    expected: ExpectedTable, cell: ExpectedCell, reading: dict[str, Any]
) -> list[Check]:
    """Compare the inspector's Data Format settings with what pybers read."""
    subject = f"{expected.sheet} / {expected.table} / {cell.cell}"
    evidence = Path(reading.get("inspectorCapture") or "").name
    settings = readDataFormatSettings(reading.get("dataFormat", []))
    checks = []
    for name, wanted in listInspectorSettings(cell).items():
        found = settings.get(name)
        label = name if name == "Data Format" else f"Data Format {name}"
        detail = f"{label} {formatCodeSpan(found)}"
        passed = found == wanted
        checks.append(Check("passed" if passed else "failed", subject,
                            detail if passed else
                            f"{detail}, expected {formatCodeSpan(wanted)}", evidence))
    if isinstance(cell.control, CellControlPopUpMenu):
        start = "its first item" if cell.control.startsWithFirstItem else "blank"
        checks.append(Check("qa", subject, f"the pop-up menu starts with {start}",
                            evidence))
    return checks


def listLabelChecks(expected: ExpectedTable) -> list[Check]:
    """Return a person's check of each measured cell against the label beneath it."""
    byName = {cell.cell: cell for cell in expected.cells}
    return [
        Check("qa", f"{expected.sheet} / {expected.table} / {cell.cell}",
              f"matches {cell.label}: {byName[cell.label].value}")
        for cell in expected.cells if cell.label is not None
    ]


def renderQuickLook(golden: Path, outputDirectory: Path) -> list[tuple[str, Path]]:
    """Render each sheet of the golden's Quick Look preview sharply, as it was stored.

    The thumbnail is the 720-pixel preview.jpg inside the file, so the full preview's
    per-sheet vector PDFs are rendered instead, at three times their own size.
    """
    rendered: list[tuple[str, Path]] = []
    with tempfile.TemporaryDirectory(prefix="pybers-quick-look-") as work:
        runTool(["qlmanage", "-p", "-o", work, str(golden)])
        preview = Path(work) / f"{golden.name}.qlpreview"
        index = (preview / "Preview.html").read_text(errors="replace")
        # Each sheet tab follows its page: `AttachmentN.html`, then `>Name</div>`.
        pages = re.findall(r"(Attachment\d+\.html).*?>([^<>]+)</div>", index, re.DOTALL)
        for position, (page, sheet) in enumerate(dict(pages).items(), start=1):
            pdfs = re.findall(r"Attachment\d+\.pdf", (preview / page).read_text())
            if not pdfs:
                continue
            pdf = preview / pdfs[0]
            size = runTool(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(pdf)])
            points = [float(value) for value in re.findall(r": ([\d.]+)", size.stdout)]
            pixels = str(int(max(points) * quickLookScale))
            runTool(["qlmanage", "-t", "-s", pixels, "-o", work, str(pdf)])
            target = outputDirectory / formatQuickLookName(position, sheet)
            (Path(work) / f"{pdf.name}.png").rename(target)
            rendered.append((sheet, target))
    if not rendered:
        raise GoldenConfirmError(f"Quick Look rendered no sheet of {golden.name}")
    return rendered


def formatQuickLookName(position: int, sheet: str) -> str:
    """Name a sheet's Quick Look image so the images sort in sheet order."""
    slug = re.sub(r"[^a-z0-9]+", "-", sheet.lower()).strip("-")
    return f"quick-look-{position}-{slug}.png"


def readSavedCopyDifferences(golden: Path, saved: Path) -> list[str]:
    """Name every member and archive the Numbers-saved copy holds differently (AC 7)."""
    before, after = readPackage(golden), readPackage(saved)
    return [str(difference) for difference in listPackageDifferences(before, after)]


def readSavedFormulas(saved: Path) -> dict[tuple[str, str], dict[str, str]]:
    """Return each formula of the copy Numbers saved, by table and cell."""
    return {
        (sheet.name, table.name): {
            str(address): cell.formulaText for address, cell in table.cells.items()
            if cell.formulaText is not None
        }
        for sheet in pybers.open(saved).sheets for table in sheet.tables
    }


def listInspectedCells(
    expected: ExpectedValues,
) -> list[tuple[ExpectedTable, ExpectedCell]]:
    """Return every cell whose settings only the inspector shows, with its table."""
    return [(table, cell) for table in expected.tables for cell in table.cells
            if checkNeedsInspector(cell)]


def findInspectDeadline(expected: ExpectedValues) -> float:
    """Return how long a run may take, longer for a table with more cells to read."""
    gridCells = sum(table.rows * table.columns for table in expected.tables)
    return inspectDeadlineSeconds + gridSecondsPerCell * gridCells


def confirmGolden(golden: Path, run: GoldenRun) -> GoldenRun:
    """Drive the helper over one golden, with the display held awake around it."""
    expected = buildExpectedValues(golden)
    inspected = listInspectedCells(expected)
    outputDirectory = run.outputDirectory
    checkHelperCanRun()
    if outputDirectory.exists():
        shutil.rmtree(outputDirectory)
    outputDirectory.mkdir(parents=True)
    # A copy to open by hand, since Numbers rewrites a document it saves.
    shutil.copyfile(golden, outputDirectory / golden.name)
    writeExpectations(expected, outputDirectory)
    writeExpectationsJson(expected, outputDirectory)
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
            "cells": [{"sheet": t.sheet, "table": t.table, "cell": c.cell}
                      for t, c in inspected],
            "tables": [{"sheet": t.sheet, "table": t.table} for t in expected.tables],
            "maxCaptures": maxCaptures,
        }, deadlineSeconds=findInspectDeadline(expected),
            logPath=outputDirectory / "helper.log")
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
        savedFormulas = (
            readSavedFormulas(saved) if result.get("savedCopy") and saved.is_file()
            else None
        )
        tableReadings = {
            (r["address"]["sheet"], r["address"]["table"]): r
            for r in result.get("tables", [])
        }
        for table in expected.tables:
            tableReading = tableReadings.get((table.sheet, table.table))
            if tableReading is None:
                if opened == "opened":
                    run.checks.append(Check(
                        "failed", f"{table.sheet} / {table.table}",
                        "the helper returned no reading for it"))
                continue
            run.checks.extend(checkTableGrid(
                table, tableReading,
                None if savedFormulas is None
                else savedFormulas.get((table.sheet, table.table), {}),
            ))
            run.checks.extend(listLabelChecks(table))
        readings = {
            (r["address"]["sheet"], r["address"]["table"], r["address"]["cell"]): r
            for r in result.get("cells", [])
        }
        for table, cell in inspected:
            reading = readings.get((table.sheet, table.table, cell.cell))
            if reading is None:
                if opened == "opened":
                    run.checks.append(Check(
                        "failed", f"{table.sheet} / {table.table} / {cell.cell}",
                        "the helper returned no inspector reading for it"))
                continue
            run.checks.extend(checkCellInspector(table, cell, reading))
        for capture in result.get("sheetCaptures", []):
            run.checks.append(Check(
                "qa", capture["sheet"], "the sheet as Numbers displays it",
                Path(capture["path"]).name))
        if result.get("savedCopy") and saved.is_file():
            differences = readSavedCopyDifferences(golden, saved)
            run.archiveDifferences.extend(differences)
            run.checks.append(Check(
                "qa", "saved copy",
                f"{len(differences)} members or archives differ once Numbers saves it",
                "report.md"))
    for sheet, image in renderQuickLook(golden, outputDirectory):
        run.checks.append(Check(
            "qa", f"Quick Look {sheet}",
            "what pybers stored, before Numbers recalculates", image.name))
    unchanged = readFileHash(golden) == goldenHash
    run.checks.append(Check(
        "passed" if unchanged else "failed", "golden",
        "byte-identical after the run" if unchanged else "CHANGED during the run"))
    writeReport(run)
    return run


def summarizeChecks(status: str, count: int, checked: int) -> str:
    """Return the line under a heading, as the merge-readiness comment reads.

    A QA check is not one Numbers answered, so it is counted on its own rather
    than against the checks the run made.
    """
    checks = "check" if checked == 1 else "checks"
    if status == "qa":
        return f"Left {count} {'check' if count == 1 else 'checks'} for QA."
    return f"{status.capitalize()} {count} of {checked} {checks}."


def writeReport(run: GoldenRun) -> Path:
    """Write the Markdown report beside its screenshots, images linked relatively."""
    lines = [
        f"# {run.golden.name}",
        "",
        f"{run.ticket}, {datetime.now().strftime('%Y-%m-%d %H:%M')}, "
        f"Numbers {run.numbersVersion or 'unknown'}",
        "",
        f"Open [{run.golden.name}]({run.golden.name}), a copy safe to open and save, "
        "beside [what it should show](expectations.md).",
        "",
    ]
    for problem in run.problems:
        lines += [f"- **{problem.kind}**: {problem.detail}. {problem.remedy}"]
    checked = sum(1 for check in run.checks if check.status in ("passed", "failed"))
    for status, heading in (
        ("failed", "Failed"), ("qa", "Left for QA"), ("passed", "Passed"),
    ):
        chosen = [check for check in run.checks if check.status == status]
        if not chosen:
            continue
        lines += [
            "", f"## {heading}", "",
            summarizeChecks(status, len(chosen), checked), "",
        ]
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


def writeDamagedCopies(golden: Path, work: Path) -> dict[str, Path]:
    """Write a truncated copy, and a copy with its first tile archive overwritten."""
    truncated = work / "truncated.numbers"
    data = golden.read_bytes()
    truncated.write_bytes(data[: len(data) // 2])

    damaged = work / "damaged-tile.numbers"
    with zipfile.ZipFile(golden) as source, zipfile.ZipFile(damaged, "w") as target:
        tiles = [name for name in source.namelist() if "/Tile" in name]
        if not tiles:
            raise GoldenConfirmError(f"{golden.name} holds no tile archive to damage")
        for info in source.infolist():
            member = bytearray(source.read(info.filename))
            if info.filename == tiles[0]:
                middle = len(member) // 2
                member[middle : middle + 64] = b"\xff" * 64
            target.writestr(info, bytes(member))
    return {"truncated file": truncated, "zip holding a damaged tile archive": damaged}


def checkDamagedCopies(golden: Path) -> list[Check]:
    """Open each damaged copy and check that the run fails and says why (AC 3)."""
    ticket = readTicketKey()
    checkHelperCanRun()
    outputDirectory = reportRoot / ticket / "damage-check"
    if outputDirectory.exists():
        shutil.rmtree(outputDirectory)
    outputDirectory.mkdir(parents=True)
    checks: list[Check] = []
    with (holdDisplayAwake(),
          tempfile.TemporaryDirectory(prefix="pybers-golden-damage-") as work):
        for label, copy in writeDamagedCopies(golden, Path(work)).items():
            result = requestHelper({
                "operation": "documentInspect",
                "documentPath": str(copy),
                "savedCopyPath": str(Path(work) / f"{copy.stem}-saved.numbers"),
                "captureDirectory": str(outputDirectory),
                "cells": [],
                "maxCaptures": maxCaptures,
                "freshNumbers": True,
            }, deadlineSeconds=inspectDeadlineSeconds,
                logPath=outputDirectory / f"{copy.stem}-helper.log")
            outcome = result.get("openOutcome")
            reasons = [problem.detail for problem in readProblems(result)]
            said = "; ".join(reasons) or "no reason given"
            failedLoudly = outcome in ("refused", "alert", "crashed") and bool(
                result.get("problems"))
            checks.append(Check(
                "passed" if failedLoudly else "failed", label,
                f"Numbers {outcome or 'was never asked'}: {said}"))
    return checks
