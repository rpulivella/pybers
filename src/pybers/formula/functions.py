#!/usr/bin/env python3
"""\
The functions a formula can call, each with its index, name and argument counts.

A `.numbers` package records a call as a bare number and an argument count, so
`SUM` is 168 and nothing in the file says so. The table comes from the Numbers
application binary, is committed under `pybers._generated`, and is regenerated
by `tools/local/functions_extract.py`, which reports what changed rather than
replacing it silently.

**The index is what the file holds, and everything here is a convenience over
it.** `FormulaFunctionCall` carries an index either way, so a formula authored
by name and one authored by index write the same bytes. That is why an unnamed
function is a `None` rather than an error, and why it round-trips untouched.

**A repeating group makes the maximum a floor rather than a ceiling.** `SUM`
declares a maximum of two arguments with a repeating group of one, which is how
an eight-argument `SUM` is legal. Read `accepts` rather than comparing against
`maximumArguments`, which is right only when there is no group. Measured across
the documents on 2026-09-04, where no valid formula contradicts the table
and the one Numbers marked as an error is the one the table rejects.

**Existing and being offered are different things**, so every index Numbers
declares is carried and `availability` says how it may be used. Reading names
all of them; only an offered one may be written by name.

    offered    in the function browser, and the only kind `named` will build
    reserved   declared with an index and no argument spec, so Numbers refuses
               the name: LATITUDE, LONGITUDE, BEARING and ALTITUDE, 281 to 284
    internal   real and used by Numbers itself, never offered. `SPILL` is one,
               and every cell a formula spills into holds `SPILL($anchor)`, so
               dropping these would read a spilled document as a bare number.

Measured against `tests/measurements/46-formula-rare-functions`, where Numbers
answers "isn't a valid function name" for each reserved one and where a
`MAKEARRAY` spill fills three cells with `SPILL`.

UPDATES
2026-10-11  The function tables are frozendict, not read-only views, for PYB-189.
2026-09-04  Argument counts added for #44, and the source moved to the
            Objective-C metadata, which names 22 functions the authoring
            methods never reached.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/04"

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from pybers._generated.functions import functions as generatedFunctions
from pybers.errors import PybersError


class FunctionAvailability(StrEnum):
    """How a function may be used, which is not the same as whether it exists."""

    offered = "offered"
    reserved = "reserved"
    internal = "internal"


class UnknownFunctionError(PybersError, ValueError):
    """A function name the table does not carry, named where an index was needed."""


class ArgumentCountError(PybersError, ValueError):
    """A call whose argument count the function it names does not accept."""


@dataclass(frozen=True, slots=True)
class NumbersFunction:
    """One of Apple's built-in functions, as Numbers itself declares it.

    Frozen and shared, so `accepts` is the only way to ask about an argument
    count: a repeating group makes `maximumArguments` a floor, not a ceiling.
    An `index` of None means the format stores this function as its own node
    types. `availability` says how it may be used, which is not the same as
    whether it exists: `SPILL` is internal and appears in every document that
    holds a spilled formula.
    """

    name: str
    index: int | None
    minimumArguments: int
    maximumArguments: int
    repeatingGroupSize: int
    availability: FunctionAvailability = FunctionAvailability.offered

    @property
    def offered(self) -> bool:
        """Report whether Numbers offers this function to write by name."""
        return self.availability is FunctionAvailability.offered

    @property
    def reserved(self) -> bool:
        """Report whether Numbers declares this and then refuses the name."""
        return self.availability is FunctionAvailability.reserved

    @property
    def unbounded(self) -> bool:
        """Report whether a repeating group removes the maximum entirely."""
        return self.repeatingGroupSize > 0 and not self.reserved

    def accepts(self, argumentCount: int) -> bool:
        """Report whether this function takes that many arguments.

        Always false for a reserved function, which has no argument spec at all
        because Numbers refuses the name before arguments matter.
        """
        if self.reserved or argumentCount < self.minimumArguments:
            return False
        return self.unbounded or argumentCount <= self.maximumArguments


# Read-only, because one shared mapping handed out mutable is the same defect
# the frozen `Style` contract exists to prevent: an edit at one call site would
# silently rename a function everywhere.
functionsByName: Final[frozendict[str, NumbersFunction]] = frozendict({
    name: NumbersFunction(
        name, index, minimum, maximum, repeating, FunctionAvailability(availability)
    )
    for name, (index, minimum, maximum, repeating, availability)
    in generatedFunctions.items()
})

# Keyed by what the archive holds, so a function stored as node types is absent
# here and present by name, which is the only honest way to index it.
functionsByIndex: Final[frozendict[int, NumbersFunction]] = frozendict({
    function.index: function
    for function in functionsByName.values()
    if function.index is not None
})


def findFunction(index: int) -> NumbersFunction | None:
    """Return the function an index names, or None when the table lacks it."""
    return functionsByIndex.get(index)


def findFunctionName(index: int) -> str | None:
    """Return the name of a function index, or None when the table lacks it."""
    function = functionsByIndex.get(index)
    return None if function is None else function.name


def findFunctionNamed(name: str) -> NumbersFunction:
    """Return the function Numbers spells `name`, `SUM` or `sum` alike.

    Raises rather than guessing, because an index invented for an unknown name
    would write a formula calling some other function.
    """
    # Exact first, then upper: Numbers is case-insensitive about the functions
    # it offers, and the internal names it never offers are mixed case.
    trimmed = name.strip()
    function = functionsByName.get(trimmed) or functionsByName.get(trimmed.upper())
    if function is None:
        raise UnknownFunctionError(
            f"{name!r} is not a function this table names. Either Numbers does "
            "not have it, or it is one of the few it declares nothing about; "
            "run tools/local/functions_extract.py --gaps to see which. Construct "
            "FormulaFunctionCall with the index directly if you know it."
        )
    return function


def findFunctionIndex(name: str) -> int:
    """Return the index of a function named as Numbers spells it.

    Raises for one the format stores as node types rather than as an indexed
    call, since there is no index to return and inventing one would write a
    formula calling something else.
    """
    function = findFunctionNamed(name)
    if function.index is None:
        raise UnknownFunctionError(
            f"{function.name} is stored as its own node types rather than as an "
            "indexed call, so it has no function index."
        )
    return function.index
