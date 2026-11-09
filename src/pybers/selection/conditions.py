#!/usr/bin/env python3
"""\
What a selector's conditions read, each name mapped once to the field it reads.

A condition selects by what pybers models, never by what a cell holds. An attribute,
`[kind=number]`, reads one field of a cell, and a pseudo-class, `:empty` or
`:nth-row(2n)`, reads its state or its place in its table. A position with no record
is read as an empty cell, so `:empty` reaches the cells a sparse table never stored.

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

import functools
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pybers.absence import UNDETERMINED
from pybers.addressing.reference import CellAddress
from pybers.table.controls import CellControlType
from pybers.table.kinds import CellFormatFamily, CellKind

if TYPE_CHECKING:
    from pybers.table.cell import Cell
    from pybers.table.cells import Table

# An+B, as `:nth-child` reads it, or one of its two names.
nthPattern: re.Pattern[str] = re.compile(
    r"(?P<odd>odd)|(?P<even>even)|(?P<a>[+-]?\d*)n(?P<b>[+-]\d+)?|(?P<only>[+-]?\d+)"
)
pseudoNegation: str = "not"


@dataclass(frozen=True, slots=True)
class SelectorAttributeField:
    """What one attribute reads from a cell, and the values it takes, None for none."""

    read: Callable[[Cell | None], object]
    values: tuple[str, ...] | None


def readKind(cell: Cell | None) -> object:
    return CellKind.EMPTY.value if cell is None else cell.kind.value


def readFormat(cell: Cell | None) -> object:
    found = None if cell is None else cell.presentation.format
    return found if found is None or found is UNDETERMINED else str(found)


def readControl(cell: Cell | None) -> object:
    control = None if cell is None else cell.presentation.control
    return None if control is None else control.controlType.value


def readConditional(cell: Cell | None) -> object:
    return True if cell is not None and cell._conditions else None


# The one table mapping each attribute to the field it reads.
selectorAttributes: frozendict[str, SelectorAttributeField] = frozendict(
    kind=SelectorAttributeField(readKind, tuple(each.value for each in CellKind)),
    format=SelectorAttributeField(
        readFormat, tuple(each.value for each in CellFormatFamily)
    ),
    control=SelectorAttributeField(
        readControl, tuple(each.value for each in CellControlType)
    ),
    conditional=SelectorAttributeField(readConditional, None),
)

# Each pseudo-class, and whether it takes a position pattern.
pseudoClasses: frozendict[str, bool] = frozendict({
    "empty": False, "formula": False, "merged": False, "header": False,
    "footer": False, "nth-row": True, "nth-column": True,
})


@functools.cache
def readNthPattern(argument: str) -> tuple[int, int]:
    """Return the step and offset of an An+B pattern, read once per pattern."""
    found = nthPattern.fullmatch(argument)
    assert found is not None
    if found["odd"]:
        step, offset = 2, 1
    elif found["even"]:
        step, offset = 2, 0
    elif found["only"] is not None:
        step, offset = 0, int(found["only"])
    else:
        written = found["a"]
        step = int(written + "1") if written in ("", "+", "-") else int(written)
        offset = int(found["b"] or 0)
    return step, offset


def matchNth(argument: str, position: int) -> bool:
    """Report whether a position counted from one fits an An+B pattern."""
    step, offset = readNthPattern(argument)
    if step == 0:
        return position == offset
    count, remainder = divmod(position - offset, step)
    return remainder == 0 and count >= 0


def matchPseudoClass(
    name: str, argument: str | None, table: Table, address: CellAddress,
    cell: Cell | None,
) -> bool:
    """Report whether a cell at an address meets one pseudo-class."""
    headers = table.headers
    match name:
        case "empty":
            return cell is None or cell.kind is CellKind.EMPTY
        case "formula":
            return cell is not None and cell.formula is not None
        case "merged":
            merge = table.mergeCovering(address)
            return merge is not None and merge.anchor == address
        case "header":
            headerRow, headerColumn, _ = headers.membershipFind(address, table.rowCount)
            return headerRow or headerColumn
        case "footer":
            return headers.membershipFind(address, table.rowCount)[2]
        case "nth-row":
            assert argument is not None
            return matchNth(argument, address.row)
        case "nth-column":
            assert argument is not None
            return matchNth(argument, address.col)
    raise AssertionError(f"The parser admitted an unknown pseudo-class, {name!r}.")


__all__ = [
    "SelectorAttributeField",
    "matchPseudoClass",
    "matchNth",
    "nthPattern",
    "pseudoClasses",
    "pseudoNegation",
    "selectorAttributes",
]
