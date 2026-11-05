#!/usr/bin/env python3
"""\
pybers locale sweep

Change a copy of `95-region-base` to each region the locale table holds, open it in
Numbers through the golden-confirm helper, and report which regions Numbers shows as
macOS formats them. findings-12-language-and-region.md records each run.

**What a region must show.** Numbers opens the copy without an alert, and five cells
read as macOS's ICU formats the same values for that region:

    A1  1234.5 as a number with two decimals and a thousands separator
    F1  `=1.5+2`, in the region's digits and decimal separator
    G1  `=SUM(1,2,3)`, its arguments separated by `;` where the decimal is not a point
    H1  `=DOLLAR(1234.5,2)`, recalculated in the region's currency, whose symbol it
        shows wherever Numbers places it
    I1  `=FIXED(1234.567,1)`, recalculated with the region's separators

A plain space and a no-break space count as one, since AppleScript reports either.

**When to run it.** After `locales_extract.py` writes a new table, and when a new major
version of Numbers ships. Never in CI, which has no Numbers. A run resumes where it
stopped, since the results it has are kept.

Usage:
    .venv/bin/python3 -m tools.local.locales_sweep
    .venv/bin/python3 -m tools.local.locales_sweep --locales de_DE en_ZA

UPDATES
2026-10-29  Written for PYB-272.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/29"
__usage__ = ".venv/bin/python3 -m tools.local.locales_sweep [options]"

import argparse
import datetime
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape

import pybers
from pybers._generated.locales import locales as localeTable
from tools.local.lib.golden_confirm import (
    GoldenConfirmError,
    checkHelperCanRun,
    findDocument,
    holdDisplayAwake,
    readProblems,
    requestHelper,
)
from tools.local.lib.icudata import Icu, decimalStyle
from tools.workflow.lib.shared import RichHelpFormatter, repositoryRoot

console: Console = Console()

baseStem: str = "95-region-base"
sheetName, tableName = "Sheet 1", "Table 1"
checkedCells: tuple[str, ...] = ("A1", "F1", "G1", "H1", "I1")
inspectDeadlineSeconds: float = 120.0
# The helper accepts captures only here, and the merge of the ticket purges them.
captureRoot: Path = (
    repositoryRoot / "workarea" / "golden-confirm" / "PYB-272" / "locale-sweep"
)
spaces: re.Pattern[str] = re.compile(r"[\s  ]")


def formatSpaces(text: str) -> str:
    """Return text with every kind of space as a plain one, as AppleScript gives it."""
    return spaces.sub(" ", text)


def buildExpectations(icu: Icu, identifier: str) -> dict[str, str]:
    """Return what each checked cell must show in a region, as macOS formats it.

    Formula text shows the region's own digits, and separates arguments with `;`
    wherever the decimal separator is not a point.
    """
    symbols = localeTable[identifier]
    separator = "," if symbols["decimal_separator"] == "." else ";"
    digit = {
        each: icu.valueFormat(identifier, each, decimalStyle, 0) for each in (1, 2, 3)
    }
    code = str(symbols["currency_code"])
    pairs = symbols["currency_symbols"]
    assert isinstance(pairs, tuple)
    currency = dict(pairs).get(code, code)
    return {
        "A1": icu.valueFormat(identifier, 1234.5, decimalStyle, 2),
        "F1": f"={icu.valueFormat(identifier, 1.5, decimalStyle, 1)}+{digit[2]}",
        "G1": f"({digit[1]}{separator}{digit[2]}{separator}{digit[3]})",
        "H1": str(currency),
        "I1": icu.valueFormat(identifier, 1234.567, decimalStyle, 1),
    }


def checkShown(cell: str, shown: str, expected: str) -> bool:
    """Report whether a cell shows what is expected, H1 only needing its currency.

    `DOLLAR` places the symbol and its marks as Numbers does, so its result passes when
    it was recalculated in the region's currency.
    """
    if cell == "H1":
        return expected in shown
    return formatSpaces(shown) == formatSpaces(expected)


def readShown(cell: str, reading: dict[str, Any]) -> str:
    """Return what a cell shows: its value, its formula's text, or G1's arguments."""
    if cell == "F1":
        return str(reading.get("formula") or "")
    if cell == "G1":
        return re.sub(r"^=[^(]*", "", str(reading.get("formula") or ""))
    return str(reading.get("formattedValue") or "")


def checkLocale(icu: Icu, identifier: str, base: Path) -> dict[str, Any]:
    """Write one region with pybers, open it in Numbers, and check what it shows."""
    expected = buildExpectations(icu, identifier)
    with tempfile.TemporaryDirectory(prefix="pybers-locale-sweep-") as work:
        written = Path(work) / f"{identifier}.numbers"
        document = pybers.open(base)
        document.localeSet(identifier)
        document.save(written)
        captures = captureRoot / identifier
        captures.mkdir(parents=True, exist_ok=True)
        result = requestHelper({
            "operation": "documentInspect",
            "documentPath": str(written),
            "savedCopyPath": str(Path(work) / "saved.numbers"),
            "captureDirectory": str(captures),
            "cells": [{"sheet": sheetName, "table": tableName, "cell": cell}
                      for cell in checkedCells],
            "tables": [],
            "maxCaptures": 0,
            "textOnly": True,
        }, deadlineSeconds=inspectDeadlineSeconds)
        shutil.rmtree(captures)
    # A refusal before anything opened says nothing of the region, so the run stops.
    refused = readProblems(result)
    if refused and result.get("openOutcome") is None:
        first = refused[0]
        raise GoldenConfirmError(
            f"the helper refused before opening: {first.detail}. {first.remedy}"
        )
    readings = {each["address"]["cell"]: each for each in result.get("cells", [])}
    cells = {}
    for cell in checkedCells:
        shown = readShown(cell, readings.get(cell, {}))
        cells[cell] = {
            "expected": expected[cell],
            "shown": shown,
            "passed": checkShown(cell, shown, expected[cell]),
        }
    problems = [f"{each.kind}: {each.detail}" for each in readProblems(result)]
    opened = result.get("openOutcome") == "opened" and not result.get("alertText")
    return {
        "opened": opened,
        "alerts": result.get("alertText", []),
        "problems": problems,
        "cells": cells,
        "passed": opened and not problems and all(c["passed"] for c in cells.values()),
        "numbersVersion": result.get("numbersVersion"),
    }


def writeReport(results: dict[str, dict[str, Any]], directory: Path) -> Path:
    """Write the regions that failed and why, then a count of those that passed."""
    failed = {key: value for key, value in results.items() if not value["passed"]}
    lines = [
        f"# Locale sweep, {directory.name}",
        "",
        f"{len(results) - len(failed)} of {len(results)} regions passed.",
        "",
    ]
    for identifier, result in sorted(failed.items()):
        lines.append(f"## {identifier}")
        if not result["opened"]:
            alerts = " ".join(result["alerts"]) or "no reading"
            lines.append(f"- not opened cleanly: {alerts}")
        lines.extend(f"- {problem}" for problem in result["problems"])
        for cell, check in result["cells"].items():
            if not check["passed"]:
                shown, expected = check["shown"], check["expected"]
                lines.append(f"- {cell}: shows `{shown}`, expected `{expected}`")
        lines.append("")
    report = directory / "report.md"
    report.write_text("\n".join(lines))
    return report


def main() -> int:
    """Sweep the regions asked for, or every one the table holds, and report them."""
    parser = argparse.ArgumentParser(
        description="Open each region pybers writes in Numbers, and check it.",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("--locales", nargs="+", help="the regions to sweep")
    arguments = parser.parse_args()
    directory = (
        repositoryRoot / "workarea" / "locale-sweep"
        / datetime.date.today().isoformat()
    )
    directory.mkdir(parents=True, exist_ok=True)
    resultsPath = directory / "results.json"
    results: dict[str, dict[str, Any]] = (
        json.loads(resultsPath.read_text()) if resultsPath.is_file() else {}
    )
    wanted = arguments.locales or list(pybers.locales)
    try:
        checkHelperCanRun()
        icu = Icu()
        base = findDocument(baseStem)
        with holdDisplayAwake():
            for position, identifier in enumerate(wanted, start=1):
                if identifier in results:
                    continue
                results[identifier] = checkLocale(icu, identifier, base)
                resultsPath.write_text(
                    json.dumps(results, indent=2, ensure_ascii=False)
                )
                passed = results[identifier]["passed"]
                mark = "[green]passed[/]" if passed else "[red]failed[/]"
                console.print(f"{position}/{len(wanted)} {escape(identifier)} {mark}")
    except GoldenConfirmError as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return 1
    report = writeReport(results, directory)
    console.print(f"Wrote {escape(str(report.relative_to(repositoryRoot)))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
