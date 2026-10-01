#!/usr/bin/env python3
"""\
Write the two CSVs that `66-series-vertical-base` and `66-series-horizontal-base` are
imported from, so a series can be dragged up, down, left and right by hand.

Each case sits in the middle of an empty table with room on every side. The vertical
one has a case per column, its seeds in rows 10 and 11 (row 12 too for the case with
three), and the horizontal one is the same turned on its side, seeds in columns J
and K, its cases from row 2.
A single-cell case is dragged from its first seed alone. The label says what each case
tests and is never a seed.

UPDATES
2026-09-30  Written for PYB-137.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/30"
__usage__ = (
    "python3 tests/fixtures/66-series-directions.py, then open each CSV in Numbers "
    "and Save As its .numbers"
)

import csv
from pathlib import Path

seedIndex: int = 10
cases: list[tuple[str, list[str]]] = [
    ("numbers 1 2", ["1", "2"]),
    ("numbers 5 3", ["5", "3"]),
    ("numbers 1 2 4", ["1", "2", "4"]),
    ("numbers 0.1 0.2", ["0.1", "0.2"]),
    ("dates daily", ["2026-01-30", "2026-01-31"]),
    ("dates monthly", ["2026-01-01", "2026-02-01"]),
    ("dates monthly from the 31st", ["2026-01-31", "2026-03-31"]),
    ("dates yearly", ["2026-01-01", "2027-01-01"]),
    ("weekdays Mon Tue", ["Monday", "Tuesday"]),
    ("weekdays Mon Wed", ["Monday", "Wednesday"]),
    ("months Jan Feb", ["January", "February"]),
    ("text Item 1 2", ["Item 1", "Item 2"]),
    ("text Item 1 3", ["Item 1", "Item 3"]),
    ("text Item 01 02", ["Item 01", "Item 02"]),
    ("text no number", ["alpha", "beta"]),
    ("single number", ["7"]),
    ("single date", ["2026-03-15"]),
    ("single weekday", ["Monday"]),
    ("single month", ["January"]),
    ("single text Item 1", ["Item 1"]),
]
lineCount: int = 21


def writeVertical(target: Path) -> None:
    """Write a case per column, a label in row 1 and the seeds from row 10."""
    grid = [["" for _ in cases] for _ in range(lineCount)]
    for column, (label, seeds) in enumerate(cases):
        grid[0][column] = label
        for offset, seed in enumerate(seeds):
            grid[seedIndex - 1 + offset][column] = seed
    with target.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(grid)


def writeHorizontal(target: Path) -> None:
    """Write a case per row below a blank header row, its label in column A."""
    grid = [["" for _ in range(lineCount)] for _ in range(len(cases) + 1)]
    for row, (label, seeds) in enumerate(cases, start=1):
        grid[row][0] = label
        for offset, seed in enumerate(seeds):
            grid[row][seedIndex - 1 + offset] = seed
    with target.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(grid)


if __name__ == "__main__":
    here = Path(__file__).parent
    writeVertical(here / "66-series-vertical-base.csv")
    writeHorizontal(here / "66-series-horizontal-base.csv")
