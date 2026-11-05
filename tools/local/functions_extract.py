#!/usr/bin/env python3
"""\
pybers function table

Derive the table of Numbers formula functions, each with its index, its name and
the argument counts it accepts, by reading the compiled code of the Numbers on
this machine. Report how it differs from the table committed at
src/pybers/_generated/functions.py.

**Why the binary is the only source.** A `.numbers` package stores a function
call as a bare `uint32` and an argument count, and nothing else. No name and no
signature appears in the archives, in the schemas, or anywhere in the package.
Excel's older binary format numbers its functions the same way and Microsoft
publishes that table as the `Ftab` in `[MS-XLS]`, but the numbering disagrees
completely: `SUM` is 4 there and 168 here, so borrowing it yields plausible
wrong functions rather than a failure.

**This reads the binary. It never runs it.** Nothing here loads, links, executes
or modifies any part of Numbers. The technique of finding the values in compiled
code rather than in a published table comes from the numbers-parser project and
is not claimed as this project's invention.

Three readings, two of them independent, all measured on Numbers 15.4:

    names       every `TSCEFunction_<NAME>` class declares `+functionIndex` as a
                two-instruction method returning its index. 387 classes.
    corroborant `TSCEFormulaCreationMagic` carries one authoring method per
                function, loading the index before a call. It reaches fewer
                functions and exists here to disagree if either reading is
                wrong.
    arity       one 133 KB function builds every `TSCEFunctionSpec`, sending
                `specWithFunctionName:minArgs:maxArgs:...` with the counts as
                literal immediates. 385 calls across eight selector variants.

**A repeating group makes the maximum a floor rather than a ceiling.** `SUM`
declares a maximum of two with a repeating group of one, which is how a document
holding an eight-argument `SUM` is legal. Reading `maxArgs` as a hard limit
rejects real formulas, measured against the documents 2026-09-04.

Numbers' own localized function list decides which extracted names are real. A
class whose name is absent from `en.lproj/TSCalculationEngine.strings` is an
internal spelling rather than a function, which is how `SHOW` and
`RANGE.TRACKING.FORMULA` are excluded without a hand-maintained list to go stale.

Output is committed for the same reason the schemas are: `pip install pybers` has
no Numbers to read. Nothing is written unless --write is passed.

Usage:
    .venv/bin/python3 -m tools.local.functions_extract
    .venv/bin/python3 -m tools.local.functions_extract --gaps
    .venv/bin/python3 -m tools.local.functions_extract \
        --numbers "/Applications/Numbers.app"
    .venv/bin/python3 -m tools.local.functions_extract --write
    .venv/bin/python3 -m tools.local.functions_extract --write --preview

Runs on the repository's venv. Needs no other tooling: the Mach-O parsing and the
AArch64 decoding are both Python, so there is no objdump, no c++filt and no
architecture-specific toolchain to install.

UPDATES
2026-10-23  `--preview` names what was `--dry-run`, as the command-line design does,
            for PYB-156.
2026-10-14  Moved here from `tools/functions-extract.py`, and run as a module,
            for PYB-204.
2026-10-13  The repository root and the help formatter come from
            `scripts/lib/shared.py`, for PYB-204.
2026-10-13  The table, its reading and its comparison moved to
            `functiontable.py`, so a test imports them, for PYB-204.
2026-10-12  The registry is found by its calls to the spec factories, since
            Numbers 15.4 no longer loads the spec class's address, for PYB-139.
2026-09-04  Names moved to the Objective-C metadata and arity added, for #44.
            The authoring methods reach 324 functions and the classes 346, so
            the first reading became the cross-check rather than the source.
2026-09-04  Written for #44.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/04"
__usage__ = ".venv/bin/python3 -m tools.local.functions_extract [options]"

import argparse
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from tools.local.lib.functionscan import (
    ExtractionError,
    buildTable,
    knownPairs,
)
from tools.local.lib.functiontable import (
    FunctionTable,
    TableComparison,
    compareTables,
    readCommitted,
    renderModule,
)
from tools.local.lib.machoreader import MachOError
from tools.local.lib.numbersapp import (
    formatApplication,
    locateNumbers,
)
from tools.workflow.lib.shared import RichHelpFormatter, repositoryRoot

console: Console = Console()

# Committed, so that naming a function never needs a local Numbers.
generatedPath: Path = repositoryRoot / "src" / "pybers" / "_generated" / "functions.py"


def showTable(table: FunctionTable, showGaps: bool) -> None:
    """Print what was extracted, and everything it could not reach."""
    total = len(table.functions) + len(table.uncovered)
    values = table.functions.values()
    reserved = sorted(f.name for f in values if f.availability == "reserved")
    internal = sorted(f.name for f in values if f.availability == "internal")
    withoutIndex = sorted(f.name for f in values if f.index is None)
    unbounded = sum(1 for f in values if f.unbounded and not f.reserved)
    console.print(
        f"\n[bold]{len(table.functions)}[/] of {total} names Numbers lists are "
        "described here."
    )
    console.print(f"  {unbounded:>4}  accept a repeating group, so no fixed maximum")
    console.print(
        f"  {len(reserved):>4}  reserved: an index and no argument spec, so "
        "Numbers refuses the name"
    )
    if reserved:
        console.print(f"        {escape(', '.join(reserved))}", highlight=False)
    console.print(
        f"  {len(internal):>4}  internal: real and used by Numbers, never offered"
    )
    if internal:
        console.print(f"        {escape(', '.join(internal))}", highlight=False)
    console.print(
        f"  {len(withoutIndex):>4}  stored as node types rather than as an "
        "indexed call"
    )
    if withoutIndex:
        console.print(f"        {escape(', '.join(withoutIndex))}", highlight=False)
    colour = "green" if not table.disagreements else "red"
    console.print(
        f"  {table.corroborated:>4}  corroborated by the authoring methods, "
        f"[{colour}]{len(table.disagreements)} disagreement(s)[/]"
    )
    for name, wasRead, declaredAs in table.disagreements:
        console.print(
            f"        [red]{escape(name)}[/] read {wasRead}, declared {declaredAs}"
        )
    for label, names, listed in (
        ("listed by Numbers with nothing behind the name", table.uncovered, showGaps),
    ):
        console.print(f"  {len(names):>4}  {label}")
        if names and listed:
            console.print(f"        {escape(', '.join(names))}", highlight=False)
        elif names:
            console.print("        pass --gaps to list them")

    console.print("\n[bold]Known pairs[/], each measured against a real document:")
    for name, index in knownPairs.items():
        function = table.functions[name]
        bound = "unbounded" if function.unbounded else function.maximumArguments
        console.print(
            f"  {index:>4}  {escape(name)}, "
            f"{function.minimumArguments} to {bound} argument(s)"
        )


def showComparison(comparison: TableComparison | None, path: Path) -> None:
    """Print how the extracted table differs from the committed one."""
    console.print(f"\n[bold]Against {escape(str(path.relative_to(repositoryRoot)))}[/]")
    if comparison is None:
        console.print(
            "  [yellow]nothing to compare with[/], the file is absent or written "
            "in an older shape"
        )
        return
    console.print(f"  {comparison.unchangedCount} unchanged")
    for function in comparison.added:
        console.print(f"  [green]added[/]    {escape(function.name)}")
    for function in comparison.removed:
        console.print(f"  [red]removed[/]  {escape(function.name)}")
    for was, now in comparison.changed:
        console.print(
            f"  [yellow]changed[/]  {escape(now.name)}  "
            f"{was.index} {was.minimumArguments}..{was.maximumArguments}/"
            f"{was.repeatingGroupSize} {escape(was.availability)} -> "
            f"{now.index} {now.minimumArguments}..{now.maximumArguments}/"
            f"{now.repeatingGroupSize} {escape(now.availability)}"
        )
    if not (comparison.added or comparison.removed or comparison.changed):
        console.print("  [green]identical[/]")


def main() -> int:
    """Parse arguments, extract the table, report it, and write it when asked."""
    parser = argparse.ArgumentParser(
        description=(
            "Derive the Numbers formula function table from the application "
            "binary, and report how it differs from the committed one."
        ),
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("--numbers", help="path to the Numbers application bundle")
    parser.add_argument(
        "--gaps",
        action="store_true",
        help="list the functions Numbers names that this run could not read",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=f"write {generatedPath.relative_to(repositoryRoot)}",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="with --write, print what would be written and write nothing",
    )
    arguments = parser.parse_args()

    try:
        application = locateNumbers(
            Path(arguments.numbers) if arguments.numbers else None
        )
        table = buildTable(application)
    except (ExtractionError, MachOError, FileNotFoundError, RuntimeError) as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return 1

    for line in formatApplication(application):
        console.print(line)
    showTable(table, arguments.gaps)
    committed = readCommitted(generatedPath)
    showComparison(
        None if committed is None else compareTables(table.functions, committed),
        generatedPath,
    )

    if not arguments.write:
        console.print(
            "\nRead-only run. Pass --write to update "
            f"{generatedPath.relative_to(repositoryRoot)}."
        )
        return 0

    source = renderModule(table)
    if arguments.preview:
        console.print("\n[bold]Would write[/]")
        console.print(source, markup=False, highlight=False)
        return 0

    generatedPath.parent.mkdir(parents=True, exist_ok=True)
    generatedPath.write_text(source)
    console.print(
        f"\n[green]Wrote[/] {escape(str(generatedPath.relative_to(repositoryRoot)))}, "
        f"{len(table.functions)} functions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
