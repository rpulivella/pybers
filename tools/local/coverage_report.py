#!/usr/bin/env python3
"""\
Write the coverage badge and report that the `health` workflow publishes.

Reads what the suite measured, writes `badge.json` for a Shields endpoint badge and
`README.md` for GitHub to render on the `coverage` branch, and annotates the run so
the readiness check can read the number from another workflow.

UPDATES
2026-11-05  Written for PYB-277.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/05"
__usage__ = ".venv/bin/python3 -m tools.local.coverage_report --output DIR --commit SHA"

import argparse
import io
import json
import sys
from pathlib import Path

lazy import coverage

from tools.local.lib.readiness import coverageNoticeTitle


def chooseBadgeColor(percent: float) -> str:
    """Name the color a percent earns, so a drop shows without reading the number."""
    if percent >= 90:
        return "brightgreen"
    return "yellow" if percent >= 75 else "red"


def renderBadge(percent: float) -> str:
    """Return the JSON a Shields endpoint badge reads."""
    badge = {
        "schemaVersion": 1,
        "label": "coverage",
        "message": f"{percent:.1f}%",
        "color": chooseBadgeColor(percent),
    }
    return json.dumps(badge, indent=1) + "\n"


def renderReport(table: str, commit: str) -> str:
    """Return the Markdown page the badge links to."""
    return (
        f"# Coverage of `develop` at {commit}\n\n"
        "Line and branch coverage of `src/pybers`, omitting generated code. The "
        "`health` workflow replaces this branch on each push to `develop`.\n\n"
        f"{table}"
    )


def main() -> int:
    """Read the measured data and write the two published files."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True, help="the directory")
    parser.add_argument("--commit", required=True, help="the commit measured")
    arguments = parser.parse_args()

    measured = coverage.Coverage()
    measured.load()
    table = io.StringIO()
    percent = measured.report(file=table, output_format="markdown")

    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "badge.json").write_text(renderBadge(percent))
    report = renderReport(table.getvalue(), arguments.commit)
    (arguments.output / "README.md").write_text(report)
    print(f"::notice title={coverageNoticeTitle}::{percent:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
