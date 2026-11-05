#!/usr/bin/env python3
"""\
pybers selection benchmark

Time the one resolver on three documents built in memory: a simple one, a typical
one, and one far beyond anything a person would make. Each selector runs several
times, and the fastest run is reported, as `timeit` advises.
findings-13-selection.md records each run and whether the simple form is fast
enough.

**When to run it.** After a change to the resolver or to how a table holds its
cells. Never in CI, whose machines vary too much for a timing to mean anything.

Usage:
    .venv/bin/python3 -m tools.local.selection_benchmark
    .venv/bin/python3 -m tools.local.selection_benchmark --repeat 5

UPDATES
2026-11-03  Written for PYB-223.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/03"
__usage__ = ".venv/bin/python3 -m tools.local.selection_benchmark [options]"

import argparse
import platform
import time
from dataclasses import dataclass
from decimal import Decimal

from rich.console import Console
from rich.markup import escape
from rich.table import Table as RichTable

import pybers

console: Console = Console()

# What a person, a script and an agent ask for, from one name to a document-wide walk.
selectors: tuple[str, ...] = (
    "Sheet 1",
    "Sheet 1::Table 1::B2",
    "::Table 1::B2",
    "*::*",
    "::B2:D9",
    "[kind=number]",
    "Sheet 1::Table *[kind=number]:not(:header)",
    ":empty:nth-row(2n)",
)


@dataclass(frozen=True, slots=True)
class BenchmarkShape:
    """A document's shape: sheets, tables on each, and each table's size."""

    name: str
    sheets: int
    tables: int
    rows: int
    cols: int
    # One more table on the first sheet, this large, for the far case.
    largeRows: int = 0
    largeCols: int = 0


shapes: tuple[BenchmarkShape, ...] = (
    BenchmarkShape("simple", sheets=1, tables=1, rows=20, cols=5),
    BenchmarkShape("typical", sheets=5, tables=4, rows=200, cols=12),
    BenchmarkShape(
        "far beyond", sheets=50, tables=20, rows=100, cols=10,
        largeRows=50_000, largeCols=20,
    ),
)


def fillTable(table: pybers.Table) -> None:
    """Give a table a header row of text and a number in every other cell."""
    for col in range(1, table.colCount + 1):
        table.cell(row=1, col=col).value = f"Column {col}"
    for row in range(2, table.rowCount + 1):
        for col in range(1, table.colCount + 1, 2):
            table.cell(row=row, col=col).value = Decimal(row * col)


def buildDocument(shape: BenchmarkShape) -> pybers.Document:
    """Return a document of a shape, built in memory and never saved."""
    document = pybers.create("en_US")
    for index in range(shape.sheets):
        sheet = document.sheet() if index == 0 else document.sheetAdd(
            f"Sheet {index + 1}"
        )
        for number in range(shape.tables):
            table = sheet.tableAdd(f"Table {number + 1}", shape.rows, shape.cols)
            table.headersSet(headerRows=1)
            fillTable(table)
    if shape.largeRows:
        large = document.sheet("Sheet 1").tableAdd(
            "Large", shape.largeRows, shape.largeCols
        )
        fillTable(large)
    return document


def measureSelection(
    document: pybers.Document, selector: str, repeat: int
) -> tuple[float, int]:
    """Return the fastest of several runs of one selection, in seconds, and its size."""
    fastest = float("inf")
    found = 0
    for _ in range(repeat):
        start = time.perf_counter()
        found = len(document.select(selector))
        fastest = min(fastest, time.perf_counter() - start)
    return fastest, found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--repeat", type=int, default=3)
    arguments = parser.parse_args()
    console.print(f"{platform.platform()}, Python {platform.python_version()}")
    for shape in shapes:
        start = time.perf_counter()
        document = buildDocument(shape)
        built = time.perf_counter() - start
        cells = sum(len(table.cells) for sheet in document.sheets
                    for table in sheet.tables)
        report = RichTable(
            "Selector", "Matches", "Seconds", box=None,
            title=f"{shape.name}: {shape.sheets} sheets, {shape.tables} tables each, "
                  f"{cells:,} stored cells, built in {built:.1f} s",
        )
        for selector in selectors:
            seconds, found = measureSelection(document, selector, arguments.repeat)
            report.add_row(escape(selector), f"{found:,}", f"{seconds:.4f}")
        console.print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
