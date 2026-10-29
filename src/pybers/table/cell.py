#!/usr/bin/env python3
"""One cell: where it sits, what it holds, and how it is pointed at from anywhere.

A cell's value is a `CellValue`, never a `float`, because Numbers stores numbers as
decimal128. A cell knows the table holding it, so reading or writing its formula as
text, and naming it from anywhere, needs nothing passed in.

UPDATES
2026-10-29  `reference` builds its own reference, for PYB-278.
2026-10-24  The unread `style` scaffold removed, for PYB-259.
2026-10-24  `valueCached`, whether a formula's value is the cached one, for PYB-259.
2026-10-22  A reference beyond its table's grid shows as `#REF!`, and a table on
            the formula's own sheet is named bare, as Numbers shows both, for PYB-255.
2026-10-22  `kind` and `presentation` replace `description`, and a control the
            value it holds cannot show is dropped with its format, for PYB-255.
2026-10-22  A cell holds a `CurrencyAmount`, and a number written into a currency
            cell keeps its currency, for PYB-220.
2026-10-20  A value of any kind is written into any cell, a `date` as midnight and an
            aware `datetime` in the document's zone, for PYB-144.
2026-10-20  A printed cell shows `value`, never the private field behind it,
            for PYB-225.
2026-10-20  Setting `value` makes an `int` exact and refuses a `float` or a value
            over a formula, and reports the change to `cellSet`, for PYB-217.
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
from dataclasses import dataclass, field, fields, replace
from decimal import Context, Decimal
from typing import TYPE_CHECKING, NoReturn

from pybers.absence import UNDETERMINED
from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import (
    CellAddress,
    CellReference,
)
from pybers.currency import CurrencyAmount, CurrencyError, findCurrency
from pybers.errors import WriteError
from pybers.formula.nodes import Formula
from pybers.formula.parse import parseFormula
from pybers.formula.render import renderFormula
from pybers.table.kinds import (
    CellFormat,
    CellKind,
    CellPresentation,
    CellStorage,
    emptyStorage,
    findCellKind,
)
from pybers.table.merges import MergeRange
from pybers.timezone import machineTimeZone, toWallClockTime

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
    | CurrencyAmount
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


def toCellValue(
    value: object, address: CellAddress, zone: datetime.tzinfo = machineTimeZone
) -> CellValue:
    """Return a value as a cell holds it: an `int` exact, a date as wall-clock time.

    A `date` is midnight and an aware `datetime` is converted to `zone`, since a
    cell stores wall-clock time alone. A `float` is refused.
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        raise WriteError(
            f"{address} was given the float {value!r}, which carries binary rounding "
            f"error. Write Decimal({str(value)!r}) instead."
        )
    if isinstance(value, datetime.datetime):
        return toWallClockTime(value, zone)
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time())
    if isinstance(value, Decimal):
        # Local, so importing the model never loads the persistence layer.
        from pybers._persistence.decimal128 import Decimal128, Decimal128Error

        try:
            Decimal128(value)
        except Decimal128Error as exc:
            raise WriteError(f"{address} cannot hold it: {exc}") from exc
        return value
    if isinstance(value, CurrencyAmount):
        try:
            findCurrency(value.currency)
        except CurrencyError as exc:
            raise WriteError(f"{address} cannot hold {value}: {exc}") from exc
        toCellValue(value.amount, address, zone)
        return value
    if isinstance(value, str | datetime.timedelta):
        return value
    raise WriteError(
        f"{address} was given a {type(value).__name__}. A cell holds a Decimal, a "
        "CurrencyAmount, an int, a str, a bool, a datetime, a date, a timedelta or "
        "None."
    )


def isSameValue(before: CellValue, after: CellValue) -> bool:
    """Report whether two values are one stored value, a Decimal down to its digits."""
    if type(before) is not type(after):
        return False
    if isinstance(before, Decimal) and isinstance(after, Decimal):
        return before.as_tuple() == after.as_tuple()
    return before == after


def refuseValueOverFormula(address: CellAddress) -> NoReturn:
    """Refuse a value written over a cell a formula backs, which would discard it."""
    raise WriteError(
        f"{address} is backed by a formula, so writing a value would discard it. "
        "Replace the formula instead, or clear it first."
    )


@dataclass(frozen=True, slots=True)
class CellChange:
    """What a write did to one cell, or would do in a preview, and how far it grew."""

    reference: CellReference
    valueBefore: CellValue
    valueAfter: CellValue
    kindBefore: CellKind
    kindAfter: CellKind
    rowsAdded: int = 0
    colsAdded: int = 0

    @property
    def changed(self) -> bool:
        """Report whether anything differs, a grown table included."""
        return bool(
            self.rowsAdded or self.colsAdded
            or self.kindBefore is not self.kindAfter
            or not isSameValue(self.valueBefore, self.valueAfter)
        )


@dataclass(slots=True)
class Cell:
    """One cell's value and optional formula, at an address.

    `value` is the result Numbers last cached, never derived from `formula`, so the
    two disagree until it recalculates. `kind` and `presentation` say what the
    record stores and how it shows it.
    """

    address: CellAddress
    _value: CellValue = field(default=None, kw_only=True)
    formula: Formula | None = None
    # The record as read, copied or saved, its chosen format the one direct edit.
    _stored: CellStorage = field(default=emptyStorage, repr=False, kw_only=True)
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
        return renderFormula(
            self.formula, self.address, tables=self.tableNames, sizes=self._tableSizes
        )

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

    def __repr__(self) -> str:
        """Return the fields the dataclass shows, a private one under its public name.

        Built from the field list rather than written out, so a field added later
        shows without anyone remembering to add it here.
        """
        shown = (
            (each.name.removeprefix("_"), getattr(self, each.name.removeprefix("_")))
            for each in fields(self)
            if each.repr
        )
        return f"Cell({', '.join(f'{name}={value!r}' for name, value in shown)})"

    @property
    def reference(self) -> CellReference:
        """Return how to point at this cell from anywhere: its address, table and sheet.

        Built from the owners on every call, so renaming the table or the sheet, or an
        edit that moves the cell, never leaves a stale copy behind.
        """
        table = None if self.table is None else self.table.reference
        return CellReference(self.address.row, self.address.col, table=table)

    @property
    def value(self) -> CellValue:
        """Return the value this cell holds, as Numbers last cached it for a formula."""
        return self._value

    @value.setter
    def value(self, value: CellValue | int | datetime.date) -> None:
        """Set this cell's value whatever it held, refusing a `float`."""
        self._valueChange(value)

    @property
    def valueCached(self) -> bool:
        """Report whether `value` is the one Numbers last cached for a formula."""
        return self.formula is not None

    @property
    def timeZone(self) -> datetime.tzinfo:
        """Return the zone an aware `datetime` written here is converted to."""
        document = None if self.table is None else self.table.document
        return machineTimeZone if document is None else document.timeZone

    def _valueChange(self, value: object, preview: bool = False) -> CellChange:
        """Set this cell's value and return the change, or only report it in preview.

        A value of another kind takes that kind's Automatic format when saved, so
        a format chosen for the old kind goes with it, as it does with a control that
        cannot show the value. A currency amount's format is always a chosen one.
        """
        written = toCellValue(value, self.address, self.timeZone)
        # A number typed into a currency cell keeps its currency, as Numbers does.
        if isinstance(written, Decimal) and isinstance(self._value, CurrencyAmount):
            written = CurrencyAmount(written, self._value.currency)
        if self.formula is not None:
            refuseValueOverFormula(self.address)
        before = self.kind
        after = findCellKind(written, self._stored.kind, self._storedValue, False)
        change = CellChange(self.reference, self._value, written, before, after)
        if not preview and change.changed:
            self._value = written
            control = self._stored.presentation.control
            dropped = control is not None and not self._controlKept()
            if after is not before or dropped:
                self._formatChosenSet(isinstance(written, CurrencyAmount))
        return change

    def _controlKept(self) -> bool:
        """Report whether a save keeps the stored control, which shows the value."""
        control = self._stored.presentation.control
        if control is None:
            return False
        if isSameValue(self.value, self._storedValue):
            return True
        return self.kind is self._stored.kind and control.showsValue(self.value)

    def _formatChosenSet(self, chosen: bool) -> None:
        """Record whether a person chose this cell's format, the one direct edit."""
        presentation = replace(self._stored.presentation, formatChosen=chosen)
        self._stored = replace(self._stored, presentation=presentation)

    @property
    def kind(self) -> CellKind:
        """Return the kind of value this cell stores, following `value` once edited."""
        pending = (
            self.formula is not None and self._origin is None
            and self._copiedFrom is None
        )
        return findCellKind(self.value, self._stored.kind, self._storedValue, pending)

    @property
    def presentation(self) -> CellPresentation:
        """Return how this cell shows its value: its format and its control."""
        presentation = self._stored.presentation
        if presentation.control is not None and not self._controlKept():
            presentation = replace(presentation, control=None, format=UNDETERMINED)
        if self.kind is not self._stored.kind:
            presentation = replace(presentation, format=UNDETERMINED)
        # None of the 897 formula records in the documents keeps a chosen Text format.
        if self.formula is not None and presentation.format is CellFormat.TEXT:
            presentation = replace(presentation, formatChosen=False)
        return presentation

    @property
    def unrecognizedTypeCode(self) -> int | None:
        """Return the record type pybers does not know, when the kind is UNKNOWN."""
        unknown = self.kind is CellKind.UNKNOWN
        return self._stored.unrecognizedTypeCode if unknown else None

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
        self._value = text
        self._formatChosenSet(True)

    @property
    def tableNames(self) -> frozendict[str, str]:
        """Return the names a formula in this cell knows its document's tables by.

        Computed from the sheet each time rather than cached, because a table
        renamed after a cached copy was taken would write a formula pointing at
        whichever table now answers to the old name.
        """
        sheet = None if self.table is None else self.table.sheet
        return frozendict() if sheet is None else sheet.tableIdentities

    @property
    def _tableSizes(self) -> dict[str | None, tuple[int, int]]:
        """Return each table's rows and columns by identity, this cell's under None."""
        if self.table is None:
            return {}
        sizes: dict[str | None, tuple[int, int]] = {
            None: (self.table.rowCount, self.table.colCount)
        }
        document = self.table.document
        if document is not None:
            sizes |= {table.identifier: (table.rowCount, table.colCount)
                      for sheet in document.sheets for table in sheet.tables
                      if table.identifier}
        return sizes

    @property
    def mergeAnchored(self) -> MergeRange | None:
        """Return the merge this cell anchors, or None when it anchors none."""
        if self.table is None:
            return None
        merge = self.table.mergeCovering(self.address)
        if merge is None or merge.anchor != self.address:
            return None
        return merge


__all__ = [
    "Cell", "CellChange", "CellCopy", "CellValue", "decimal128Context",
    "refuseValueOverFormula", "toCellValue",
]
