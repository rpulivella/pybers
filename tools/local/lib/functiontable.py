#!/usr/bin/env python3
"""\
The function table `functions-extract.py` writes, read back and compared.

Prints nothing and reads no binary, so a test imports it without Numbers installed.

UPDATES
2026-10-13  Moved here from `functions-extract.py`, for PYB-204.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/04"

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NumbersFunction:
    """One function as Numbers declares it: name, index and argument counts.

    `index` is absent for a function the format stores as its own node types
    rather than as an indexed call. `availability` is one of three: offered in
    the function browser, reserved with an index and no argument spec, or
    internal, which Numbers uses itself and does not offer.
    """

    name: str
    index: int | None
    minimumArguments: int
    maximumArguments: int
    repeatingGroupSize: int
    availability: str = "offered"

    @property
    def reserved(self) -> bool:
        """Report whether Numbers declares this and refuses the name."""
        return self.availability == "reserved"

    @property
    def unbounded(self) -> bool:
        """Report whether a repeating group removes the maximum entirely."""
        return self.repeatingGroupSize > 0


@dataclass(frozen=True)
class FunctionTable:
    """An extracted table, and everything a reader needs to judge it."""

    functions: dict[str, NumbersFunction]
    uncovered: tuple[str, ...]
    corroborated: int
    disagreements: tuple[tuple[str, int, int], ...]
    version: str
    build: str


@dataclass(frozen=True)
class TableComparison:
    """How a freshly extracted table differs from the committed one."""

    added: tuple[NumbersFunction, ...]
    removed: tuple[NumbersFunction, ...]
    changed: tuple[tuple[NumbersFunction, NumbersFunction], ...]
    unchangedCount: int


def readCommitted(path: Path) -> dict[str, NumbersFunction] | None:
    """Return the committed table, or None when there is nothing to compare with.

    Read as a literal rather than imported, so comparing depends neither on
    pybers being installed nor on running the file about to be overwritten.
    None covers both an absent file and one written in an older shape, because
    refusing to run until the output is already correct would leave no way to
    correct it.
    """
    if not path.is_file():
        return None
    for statement in ast.parse(path.read_text(), str(path)).body:
        if not isinstance(statement, ast.AnnAssign | ast.Assign):
            continue
        targets = (
            [statement.target] if isinstance(statement, ast.AnnAssign)
            else statement.targets
        )
        named = any(
            isinstance(target, ast.Name) and target.id == "functions"
            for target in targets
        )
        if not named or statement.value is None:
            continue
        try:
            return {
                str(name): NumbersFunction(
                    str(name),
                    None if row[0] is None else int(row[0]),
                    int(row[1]), int(row[2]), int(row[3]), str(row[4]),
                )
                for name, row in ast.literal_eval(statement.value).items()
            }
        except (IndexError, TypeError, ValueError):
            # A table written in an older shape, which the next --write replaces.
            return None
    return None


def compareTables(
    extracted: dict[str, NumbersFunction], committed: dict[str, NumbersFunction]
) -> TableComparison:
    """Report what a regeneration would change, which is what makes it reviewable."""
    added = tuple(
        function for name, function in sorted(extracted.items())
        if name not in committed
    )
    removed = tuple(
        function for name, function in sorted(committed.items())
        if name not in extracted
    )
    changed = tuple(
        (committed[name], function)
        for name, function in sorted(extracted.items())
        if name in committed and committed[name] != function
    )
    unchanged = sum(
        1 for name, function in extracted.items() if committed.get(name) == function
    )
    return TableComparison(added, removed, changed, unchanged)


def renderModule(table: FunctionTable) -> str:
    """Return the source of the generated module, one line per function."""
    entries = "\n".join(
        f'    "{function.name}": ({function.index}, '
        f"{function.minimumArguments}, {function.maximumArguments}, "
        f'{function.repeatingGroupSize}, "{function.availability}"),'
        for _name, function in sorted(table.functions.items())
    )
    total = len(table.functions) + len(table.uncovered)
    return f'''#!/usr/bin/env python3
"""\\
Numbers formula functions, by index. Machine output, do not edit.

Written by tools/local/functions_extract.py from Numbers {table.version}
(build {table.build}). A correction made here is destroyed by the next
extraction; correct the extractor instead.

Each row is the index, the minimum argument count, the maximum, the size of the
repeating group that makes the maximum a floor rather than a ceiling, and how
the function may be used. A group of zero means the maximum is exact.

An index of None means the format stores the function as its own node types
rather than as an indexed call. Availability is one of three: offered in the
function browser, reserved with an index and no argument spec so Numbers
refuses the name, or internal, which Numbers uses itself and never offers.

{len(table.functions)} of the {total} functions Numbers names are covered.
"""

functions: dict[str, tuple[int | None, int, int, int, str]] = {{
{entries}
}}
'''
