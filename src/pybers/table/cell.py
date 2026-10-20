#!/usr/bin/env python3
"""One cell: where it sits, what it holds, and how it is pointed at from anywhere.

A cell's value is a `CellValue`, never a `float`, because Numbers stores numbers as
decimal128. A cell knows the table holding it, so reading or writing its formula as
text, and naming it from anywhere, needs nothing passed in.

UPDATES
2026-10-20  Moved here from `cells`, which keeps `Table`, for PYB-217. The history of
            this code before the move is in that module's UPDATES.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/20"

import datetime
from dataclasses import dataclass, field, replace
from decimal import Context, Decimal
from typing import TYPE_CHECKING

from pybers.absence import UNDETERMINED
from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import (
    CellAddress,
    CellReference,
    SheetReference,
    TableReference,
)
from pybers.errors import WriteError
from pybers.formula.nodes import Formula
from pybers.formula.parse import parseFormula
from pybers.formula.render import renderFormula
from pybers.style import Style
from pybers.table.kinds import CellDescription, emptyDescription, findCellKind
from pybers.table.merges import MergeRange

if TYPE_CHECKING:
    # Guarded because `cells` imports this module, and the link back is a type
    # reference rather than anything this module calls.
    from pybers.table.cells import Table


# IEEE-754 decimal128, which is exactly what Numbers stores a numeric cell as: 34
# significant digits with this exponent range. Declared here so that any arithmetic a
# caller performs through this library rounds the way Numbers itself rounds, rather
# than the way Python's 28-digit default happens to.
decimal128Context: Context = Context(prec=34, Emax=6144, Emin=-6143)

# What a cell may hold. Deliberately not `float` anywhere.
#
# Decimal is not a compromise here, it is the matching type. Verified 2026-08-17:
# Decimal("0.1") + Decimal("0.2") == Decimal("0.3") is True, and 1.1 * 1.1 is exactly
# 1.21, where float64 gets both wrong. Division still rounds (1/3 * 3 is 0.999...9)
# but that is inherent to decimal arithmetic and Numbers, using the same decimal128,
# behaves identically. Matching its rounding is the point.
#
# Scaled integers, the fixed-point trick from finance software, were considered and
# rejected: that works because money has a fixed scale, whereas a spreadsheet cell
# ranges from 1e-300 to 1e300. It would also mean converting between two number systems
# on every read and write, which reintroduces exactly the error being avoided.
#
# THE FAILURE THIS PREVENTS, and the reason to build values from strings:
# Decimal(0.1) carries the float's binary error straight in, yielding
# 0.1000000000000000055511151231257827...
# Decimal("0.1") does not. Never construct a cell value from a float.
CellValue = (
    Decimal
    | str
    | bool
    | datetime.datetime
    | datetime.timedelta
    | None
)


@dataclass(frozen=True, slots=True)
class CellCopy:
    """The cell whose stored record a save duplicates, and whether its borders go too.

    A fill copies no border and a paste copies all four, as `63e` and `64b` measured.
    """

    source: Cell
    borders: bool


@dataclass(slots=True)
class Cell:
    """One cell's value, optional formula, and style, at an address.

    `value` is the result Numbers last cached, never derived from `formula`, so the
    two disagree until it recalculates. `description` says what the record stores.
    """

    address: CellAddress
    value: CellValue = None
    formula: Formula | None = None
    style: Style = field(default_factory=Style)
    # The record as read, copied or saved, its chosen format the one direct edit.
    _stored: CellDescription = field(
        default=emptyDescription, repr=False, kw_only=True
    )
    # The value that record holds, so an edit since is told from it.
    _storedValue: CellValue = field(
        default=None, repr=False, compare=False, kw_only=True
    )
    # Where the file stores this cell's record, so a save can tell that it moved.
    _origin: CellAddress | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )
    # The conditions of its highlighting rules, one per rule, hosted here.
    _conditions: tuple[Formula, ...] = field(
        default=(), repr=False, compare=False, kw_only=True
    )
    # The cell whose stored record a save duplicates here, set by a fill or a copy.
    _copiedFrom: CellCopy | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )
    # The table this belongs to, so that reading or writing a formula as text needs
    # neither the cell's own address nor the names of the other tables passed in.
    # Excluded from equality and `repr` for the reason `Document._package` is: it is
    # where this cell sits rather than what it holds.
    table: Table | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )

    @property
    def formulaText(self) -> str | None:
        """This cell's formula as Numbers displays it, or None when it holds none.

        Assignable: `cell.formulaText = "=SUM(B1:B5)"` parses against this cell,
        which is what an unlocked reference is an offset from, so the wrong host
        cannot be passed. Use `formulaSet` to name an address rather than write it.
        """
        if self.formula is None:
            return None
        return renderFormula(self.formula, self.address, tables=self.tableNames)

    @formulaText.setter
    def formulaText(self, text: str) -> None:
        """Give this cell the formula a written expression describes."""
        self.formulaSet(text)

    def formulaSet(
        self, text: str, **pieces: CellRange | CellReference
    ) -> Formula:
        """Give this cell the formula text describes, and return what was stored.

        A keyword argument fills a `{name}` in the text with an address this library
        already validated, so `formulaSet("=SUM({sales})", sales=extent)` never
        splices one into a string and parses it back out.
        """
        self.formula = parseFormula(
            text, self.address, tables=self.tableNames, pieces=pieces
        )
        return self.formula

    @property
    def reference(self) -> CellReference:
        """Return how to point at this cell from anywhere: its address, table and sheet.

        Built from the owners on every call, so renaming the table or the sheet, or an
        edit that moves the cell, never leaves a stale copy behind.
        """
        table = self.table
        if table is None:
            return CellReference(self.address.row, self.address.col)
        sheet = table.sheet
        return CellReference(
            self.address.row,
            self.address.col,
            table=TableReference(
                sheet=None if sheet is None else SheetReference(sheet.name),
                name=table.name,
            ),
        )

    @property
    def description(self) -> CellDescription:
        """Return the kind this cell stores, its format, and whether that was chosen.

        The kind follows `value`, so text written over rich text reports text.
        """
        pending = (
            self.formula is not None and self._origin is None
            and self._copiedFrom is None
        )
        kind = findCellKind(self.value, self._stored.kind, self._storedValue, pending)
        if kind is self._stored.kind:
            return self._stored
        return CellDescription(kind, UNDETERMINED, self._stored.formatChosen)

    def textLiteralSet(self, text: str) -> None:
        """Hold text Numbers will not interpret, as a cell formatted Text before typing.

        `=SUM(A1:A5)` then stays that text when somebody edits the cell. Refused on a
        cell holding a formula, which this would discard.
        """
        if not isinstance(text, str):
            raise WriteError(
                f"Literal text for {self.address} must be a str, and was given "
                f"{type(text).__name__}."
            )
        if self.formula is not None:
            raise WriteError(
                f"{self.address} is backed by a formula, so holding literal text "
                "would discard it. Clear the formula first."
            )
        self.value = text
        self._stored = replace(self._stored, formatChosen=True)

    @property
    def tableNames(self) -> frozendict[str, str]:
        """Return the names this cell's document knows its tables by, or nothing.

        Computed from the document each time rather than cached, because a table
        renamed after a cached copy was taken would write a formula pointing at
        whichever table now answers to the old name.
        """
        document = None if self.table is None else self.table.document
        return frozendict() if document is None else document.tableIdentities

    @property
    def mergeAnchored(self) -> MergeRange | None:
        """Return the merge this cell anchors, or None when it anchors none."""
        if self.table is None:
            return None
        merge = self.table.mergeCovering(self.address)
        if merge is None or merge.anchor != self.address:
            return None
        return merge


__all__ = ["Cell", "CellCopy", "CellValue", "decimal128Context"]
