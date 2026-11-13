#!/usr/bin/env python3
"""A sheet holds tables, and a document is a list of sheets.

`Document` is the only handle a caller ever holds. It is what `pybers.open` returns,
what every edit reaches through, and what `save` writes back. See CLAUDE.md, "Document
is the single handle".

Two things about selecting by name or position that a caller would otherwise have to
learn by being wrong:

- **Position is a place in the file's own list, not a place on the page.** Sheets come
  from `TN.DocumentArchive.sheets`, which is the tab order a person sees, and tables
  from `TN.SheetArchive.drawable_infos`, which is not sorted by anything visible. The
  three tables of `25-multi-tables` arrive as `Table 1`, `Lower`, `Right`, so a caller
  reaching for the topmost table by position gets a real table that is the wrong one.
- **A table name is unique within its sheet and nowhere wider.** Numbers enforces it
  per sheet, case-insensitively, appending `-1` and `-2` to force it, so `Sheet.table`
  by name is unambiguous. It does not extend to the document: `20-formula-shapes`
  carries a `Table 1` on each of two sheets, which is why `Document.table` refuses a
  name two sheets share. Sheet names carry no such enforcement at all, so a duplicate
  is handled rather than assumed away.

UPDATES
2026-11-12  `cellSet` sets a cell style, its whole box, for PYB-265.
2026-11-10  `cellSet` sets a value, a format or both, a part not given left as it
            was, for PYB-145.
2026-11-03  `select` on a document and a sheet, and every lookup by name a typed
            call into the one resolver, replacing `partSelect`, `Document.cell`
            and `Sheet.cell`, and `cellSet` writing every cell a selector
            matches, for PYB-223.
2026-10-28  `localeSet`, a change of language and region, for PYB-272.
2026-10-27  `localeIdentifier`, the language and region a document shows its
            values in, for PYB-272.
2026-10-27  `partSelect`, the sheet, table, range or cell a selector names, and
            every refusal listing names quoting each, for PYB-260.
2026-10-24  The unread `graphicalObjects` scaffold removed, and the table naming
            rule a function the JSON form shares, and `_ownersLink` the one
            linking the reader and the JSON form share, for PYB-259.
2026-10-22  `Sheet.tableIdentities`, the names a formula on one sheet uses,
            replacing `Document.tableIdentities`, for PYB-255.
2026-10-22  A document reads its locale's currency symbols and placement, for
            PYB-220.
2026-10-20  A document carries the time zone an aware `datetime` is written in, for
            PYB-144.
2026-10-20  `cellSet` writes one cell by its reference, growing the table when asked
            and reporting the change, for PYB-217.
2026-10-20  A document and a sheet each reach a cell by a reference naming its
            table, walking down the owners, for PYB-217.
2026-10-11  Table identities are returned as a frozendict, for PYB-189.
2026-09-14  A sheet or a table is added, and each knows the archive it was read
            from, for PYB-63.
2026-09-08  Every reference in the document walked in one call, and a table
            reached by the identity a formula names it by, for #13.
2026-09-08  Moved into `pybers.document` for #58, out of `pybers.model`.
2026-09-08  The identity each table is named by in a formula, for #45.
2026-09-02  Save states what happens to a dependent formula, for #25.
2026-09-02  The whole-document cell iteration, for #14.
2026-09-02  Reaching a sheet or a table by name or by position, for #14.
2026-09-01  Document carries the package it was read from, and gained save, for #2.
2026-08-12  Initial scaffold.
"""

from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/02"

import datetime
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pybers.absence import UNCHANGED
from pybers.addressing.reference import (
    CellAddress,
    CellReference,
    TableReference,
    lastColumn,
    lastRow,
    tableNameSeparator,
)
from pybers.errors import PybersError, WriteError
from pybers.format._check import (
    findControlRefusal,
    findFormatMisfit,
    findFormatRefusal,
)
from pybers.format.controls import CellControl
from pybers.format.formats import CellFormat, CellFormatAutomatic, CellFormatConflict
from pybers.geometry import Position
from pybers.style.cells import CellStyle, findCellStyleRefusal
from pybers.table.cell import (
    Cell,
    CellChange,
    CellChanges,
    CellSkip,
    findWrittenValue,
)
from pybers.table.cells import Table, generateOwnerIdentity
from pybers.timezone import TimeZoneLike, machineTimeZone, toTimeZone

if TYPE_CHECKING:
    # Guarded so that importing the model never drags in the persistence layer.
    from pybers._persistence import NumbersPackage
    from pybers.document.locale import LocaleChange
    from pybers.document.references import ReferenceLocation
    from pybers.selection.matching import SelectionMatch
    from pybers.selection.selector import SelectorLike

# Sheets and tables both count from one, matching the rest of the model and matching
# what Numbers shows. The file counts from zero and the two meet only in the reader.
firstPosition: int = 1


class SelectionError(PybersError, LookupError):
    """A name or a position selecting no sheet or table, or selecting more than one.

    A `LookupError` rather than a `KeyError`, because `KeyError` displays the repr of
    its argument in place of its message, which would swallow the list of what is
    actually present that these messages exist to give.
    """


class Named(Protocol):
    """Anything reachable by name: a sheet, or a table on one."""

    name: str


def listPresent(kind: str, names: Sequence[str]) -> str:
    """Return the sentence ending a refusal with the names present, to ask for one."""
    if not names:
        return f"It holds no {kind}s."
    return f"The {kind}s are {', '.join(repr(name) for name in names)}."


def selectByPosition[NamedT: Named](
    items: Sequence[NamedT], position: int, kind: str, within: str
) -> NamedT:
    """Return the item at a one-based position in the file's own order."""
    if position < firstPosition or position > len(items) + firstPosition - 1:
        raise SelectionError(
            f"Position {position} is outside {within}, which holds {len(items)} "
            f"{kind}s. Positions count from {firstPosition}."
        )
    return items[position - firstPosition]


def refuseUnnamed(nameOrPosition: object, kind: str) -> None:
    """Refuse what is neither a name nor a position, a `bool` and `""` included."""
    if nameOrPosition is None or (isinstance(nameOrPosition, str) and nameOrPosition):
        return
    if isinstance(nameOrPosition, int) and not isinstance(nameOrPosition, bool):
        return
    raise SelectionError(
        f"A {kind} is reached by its name or by its position, and "
        f"{nameOrPosition!r} is neither."
    )


def findTableIdentities(
    sheets: Sequence[Sheet], local: Sheet
) -> frozendict[str, str]:
    """Return each table's identity under every name a formula on `local` uses.

    One owner for the naming rule, shared by `Sheet.tableIdentities` and by the JSON
    form, which must know the names a reader of only part of a document will have.
    """
    seen: Counter[str] = Counter(
        table.name for sheet in sheets for table in sheet.tables
    )
    names: dict[str, str] = {}
    for sheet in sheets:
        for table in sheet.tables:
            if not table.identifier:
                continue
            names[f"{sheet.name}{tableNameSeparator}{table.name}"] = table.identifier
            if seen[table.name] == 1:
                names[table.name] = table.identifier
    names |= {table.name: table.identifier for table in local.tables
              if table.identifier}
    return frozendict(names)

@dataclass(slots=True)
class Sheet:
    """One sheet (tab) in a document, and its tables."""

    name: str
    tables: list[Table] = field(default_factory=list)
    # The archive this sheet was read from or saved as, and None until it has one.
    # Excluded from equality and `repr` for the reason `Document._package` is.
    _identifier: int | None = field(default=None, repr=False, compare=False)
    # The document holding this sheet, which a table added to it is linked to.
    document: Document | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )

    def table(self, nameOrPosition: str | int | None = None) -> Table:
        """Return one of this sheet's tables by its name or position, or its only one.

        Position is the table's place in the sheet's drawable list, which says
        nothing about where the table sits on the page.
        """
        refuseUnnamed(nameOrPosition, "table")
        if isinstance(nameOrPosition, int):
            return selectByPosition(
                self.tables, nameOrPosition, "table", repr(self.name)
            )
        from pybers.selection.matching import findTable

        return findTable(self, nameOrPosition)

    def select(self, selector: SelectorLike) -> tuple[SelectionMatch, ...]:
        """Return what a selector matches on this sheet, read from its tables."""
        from pybers.selection.matching import selectWithin

        return selectWithin(self, selector)

    @property
    def tableIdentities(self) -> frozendict[str, str]:
        """Return every table's identity under each name a formula on this sheet uses.

        Every table answers to `Sheet 2::Table 1`. A bare name reaches this sheet's
        table of that name, otherwise the document's only table of that name, which is
        how Numbers shows `Table 1::A1` on Sheet 1 when Sheet 2 holds one too.
        """
        sheets = [self] if self.document is None else self.document.sheets
        return findTableIdentities(sheets, self)

    def tableAdd(
        self, name: str, rows: int, cols: int, position: Position | None = None
    ) -> Table:
        """Add an empty table of a size, its top-left corner at a point, and return it.

        With no position it lands below the tables already on the sheet. A name the
        sheet carries, ignoring case, takes the first free `-1`, `-2` suffix.
        """
        if not isinstance(name, str) or not name:
            raise SelectionError(
                f"A table is added under a name, and {name!r} is none."
            )
        for axis, count, limit in (("rows", rows, lastRow), ("cols", cols, lastColumn)):
            if (
                not isinstance(count, int)
                or isinstance(count, bool)
                or not firstPosition <= count <= limit
            ):
                raise SelectionError(
                    f"A table holds from {firstPosition} to {limit} {axis}, and "
                    f"{count!r} is not a count in that range."
                )
        if position is not None and not isinstance(position, Position):
            raise SelectionError(
                f"A table is placed at a `pybers.Position`, and {position!r} is "
                "not one."
            )
        taken = {table.name.casefold() for table in self.tables}
        unique = name
        suffix = 0
        while unique.casefold() in taken:
            suffix += 1
            unique = f"{name}-{suffix}"
        table = Table(
            name=unique,
            rowCount=rows,
            colCount=cols,
            identifier=generateOwnerIdentity(),
            document=self.document,
            _origin=position,
        )
        self.tables.append(table)
        return table


@dataclass(slots=True)
class Document:
    """The root of the model, and the single handle: every edit is reached through it.

    Named for `TN.DocumentArchive` rather than "workbook", which the format has no
    concept of. The private fields carry the archives this was read from, excluded
    from equality and `repr`, because `save` mutates those rather than rebuilding.
    """

    sheets: list[Sheet] = field(default_factory=list)
    _package: NumbersPackage | None = field(default=None, repr=False, compare=False)
    _sourcePath: Path | None = field(default=None, repr=False, compare=False)
    # Lives for the session alone, since the file has nowhere to keep a zone.
    _timeZone: datetime.tzinfo = field(
        default=machineTimeZone, repr=False, compare=False
    )
    # The document's own locale, which a currency's symbol and placement follow.
    _currencySymbols: frozendict[str, str] = field(
        default_factory=frozendict, repr=False, compare=False
    )
    _currencyPattern: str = field(default="", repr=False, compare=False)
    _localeIdentifier: str | None = field(default=None, repr=False, compare=False)

    @property
    def localeIdentifier(self) -> str | None:
        """Return the language and region this document shows its values in, `en_IT`.

        None for a document built in memory, which has none until it is saved.
        """
        return self._localeIdentifier

    def localeSet(self, identifier: str) -> LocaleChange:
        """Change the language and region this document shows its values in, `de_DE`.

        The save writes the region as Numbers writes it and marks every formula, so
        Numbers recalculates a result such as `DOLLAR` that depends on it.
        """
        from pybers.document.locale import LocaleChange, findLocaleSymbols

        findLocaleSymbols(identifier)
        change = LocaleChange(self._localeIdentifier, identifier)
        if change.changed:
            self._localeAssign(identifier)
        return change

    def _localeAssign(self, identifier: str | None) -> None:
        """Hold a region, with the currency symbols and placement pybers has for it.

        A region the table does not hold, read from a file or a JSON form, keeps the
        identifier alone, since only its own document knows its symbols.
        """
        from pybers.document.locale import findLocaleSymbols, locales

        self._localeIdentifier = identifier
        if identifier not in locales:
            return
        symbols = findLocaleSymbols(identifier)
        currencySymbols = symbols["currency_symbols"]
        assert isinstance(currencySymbols, tuple)
        self._currencySymbols = frozendict(currencySymbols)
        self._currencyPattern = str(symbols["currency_pattern"])

    @property
    def currencyPattern(self) -> str:
        """Return where this document's locale places a symbol, `¤` marking it."""
        return self._currencyPattern

    def currencySymbolFind(self, code: str) -> str | None:
        """Return the symbol this document's locale writes a currency with, if any."""
        return self._currencySymbols.get(code)

    @property
    def timeZone(self) -> datetime.tzinfo:
        """Return the zone an aware `datetime` written here is converted to."""
        return self._timeZone

    @timeZone.setter
    def timeZone(self, zone: TimeZoneLike) -> None:
        """Set that zone, as a `tzinfo` or a name `zoneinfo.ZoneInfo` knows."""
        self._timeZone = toTimeZone(zone)

    def sheet(self, nameOrPosition: str | int | None = None) -> Sheet:
        """Return a sheet by its name or position, or this document's only sheet.

        Position is the sheet's place in the document's own list, the tab order a
        person sees.
        """
        refuseUnnamed(nameOrPosition, "sheet")
        if isinstance(nameOrPosition, int):
            return selectByPosition(
                self.sheets, nameOrPosition, "sheet", "this document"
            )
        from pybers.selection.matching import findSheet

        return findSheet(self, nameOrPosition)

    def table(self, name: str | TableReference | None = None) -> Table:
        """Return the one table of a name on any sheet, or the document's only table.

        A name two sheets share is refused, listing both. A `TableReference` naming
        its sheet reaches it.
        """
        from pybers.selection.matching import findTable

        return findTable(self, name)

    def select(self, selector: SelectorLike) -> tuple[SelectionMatch, ...]:
        """Return what a selector matches in this document, as qualified references.

        `Budget::Q*[kind=number]` is every number in the tables on Budget whose
        names start with Q. Nothing is created or changed.
        """
        from pybers.selection.matching import selectWithin

        return selectWithin(self, selector)

    def sheetAdd(self, name: str, position: int | None = None) -> Sheet:
        """Add an empty sheet, last or at a position counted from one, and return it.

        Numbers enforces nothing about sheet names, so a duplicate is accepted. The
        sheet reaches the file when the document is saved.
        """
        if not isinstance(name, str) or not name:
            raise SelectionError(
                f"A sheet is added under a name, and {name!r} is none."
            )
        last = len(self.sheets) + firstPosition
        if position is None:
            position = last
        if (
            not isinstance(position, int)
            or isinstance(position, bool)
            or not firstPosition <= position <= last
        ):
            raise SelectionError(
                f"A sheet is added at a position from {firstPosition} to {last}, and "
                f"{position!r} is not one."
            )
        sheet = Sheet(name=name, document=self)
        self.sheets.insert(position - firstPosition, sheet)
        return sheet

    def cellSet(
        self,
        selector: SelectorLike,
        value: object = UNCHANGED,
        *,
        format: CellFormat | UNCHANGED = UNCHANGED,
        control: CellControl | None | UNCHANGED = UNCHANGED,
        cellStyle: CellStyle | None | UNCHANGED = UNCHANGED,
        conflict: CellFormatConflict = CellFormatConflict.REFUSE,
        extend: bool = False,
    ) -> CellChanges:
        """Set the value, format, control, cell style or several on every matched cell.

        A part not given stays as it was, and a control or cell style of None removes
        one. A cell a formula backs is skipped when given a value. A format that cannot
        show a cell's value is refused before any cell changes, unless `conflict`
        falls back to Automatic for that cell and says so.
        """
        from pybers.selection.matching import findCellTargets, findExtendTarget

        if all(part is UNCHANGED for part in (value, format, control, cellStyle)):
            raise WriteError(
                "cellSet was given no value, format, control or cell style to set."
            )
        if cellStyle is not UNCHANGED and cellStyle is not None:
            if not isinstance(cellStyle, CellStyle):
                raise WriteError(
                    f"A cell style is a CellStyle or None, and cellSet was given "
                    f"{type(cellStyle).__name__}. Nothing was written."
                )
            refusal = findCellStyleRefusal(cellStyle)
            if refusal is not None:
                raise WriteError(f"{refusal} Nothing was written.")
        targets, skipped = (
            ([findExtendTarget(self, selector)], []) if extend
            else findCellTargets(self, selector)
        )
        writing: list[tuple[Table, CellAddress, CellFormat | UNCHANGED]] = []
        for table, address in targets:
            cell = table.cells.get(address)
            if value is not UNCHANGED and cell is not None and cell.formula is not None:
                skipped.append(CellSkip(
                    cell.reference, f"{cell.reference} is backed by a formula, which "
                    "a value would discard.",
                ))
                continue
            asked = format
            current = None if cell is None else cell.value
            after = current if value is UNCHANGED else findWrittenValue(
                value, address, self.timeZone, current
            )
            where = CellReference(address.row, address.col, table=table.reference)
            if control is not UNCHANGED and control is not None:
                raise WriteError(
                    f"{findControlRefusal(cell, where, control, asked, after)} Nothing "
                    "was written."
                )
            controlAfter = (
                (None if cell is None else cell.presentation.control)
                if control is UNCHANGED else control
            )
            if asked is not UNCHANGED:
                misfit = findFormatMisfit(cell, where, asked, after)
                if misfit is not None and conflict is CellFormatConflict.REFUSE:
                    raise WriteError(f"{misfit} Nothing was written.")
                if misfit is not None:
                    asked = CellFormatAutomatic()
                    skipped.append(CellSkip(where, f"{misfit} It takes Automatic."))
                refusal = findFormatRefusal(cell, where, asked, after, controlAfter)
                if refusal is not None:
                    raise WriteError(f"{refusal} Nothing was written.")
            writing.append((table, address, asked))
        changes: list[CellChange] = []
        for table, address, asked in writing:
            rowsAdded = max(0, address.row - table.rowCount)
            colsAdded = max(0, address.col - table.colCount)
            if rowsAdded:
                table.rowAdd(table.rowCount + 1, rowsAdded)
            if colsAdded:
                table.columnAdd(table.colCount + 1, colsAdded)
            cell = table.cell(address)
            change = (
                cell._valueChange(value) if value is not UNCHANGED
                else CellChange(
                    cell.reference, cell.value, cell.value, cell.kind, cell.kind,
                    cell.presentation.format, cell.presentation.format,
                    cell.presentation.control, cell.presentation.control,
                )
            )
            styleBefore = cell.cellStyle
            if control is not UNCHANGED:
                cell._controlRequest(control)
            if asked is not UNCHANGED:
                cell._formatRequest(asked)
            if cellStyle is not UNCHANGED:
                cell._cellStyleRequest(cellStyle)
            changes.append(replace(
                change, formatAfter=cell.presentation.format,
                controlAfter=cell.presentation.control,
                cellStyleBefore=styleBefore, cellStyleAfter=cell.cellStyle,
                rowsAdded=rowsAdded, colsAdded=colsAdded,
            ))
        return CellChanges(tuple(changes), tuple(skipped))

    def tableFor(self, identity: str) -> Table:
        """Return the table a formula names by identity, or raise saying which.

        The reverse of `Sheet.tableIdentities`, and the reason renaming a table cannot
        break a formula pointing into it: the archive stores this, never the name.
        """
        # Imported inside for the reason `save` is: `references` builds on this
        # module, so reaching it from here at module scope would close a cycle.
        from pybers.document.references import indexTablesByIdentity

        table = indexTablesByIdentity(self).get(identity)
        if table is None:
            raise SelectionError(
                f"No table in this document carries the identity {identity!r}."
            )
        return table

    def _ownersLink(self) -> None:
        """Point every sheet and table at this document, once all of them are in.

        Linked only then, so a cell can name another table without the caller
        passing the names, and so `Table.document` is never half a document.
        """
        for sheet in self.sheets:
            sheet.document = self
            for table in sheet.tables:
                table.document = self

    def cellsIterate(self) -> Iterator[tuple[Sheet, Table, Cell]]:
        """Yield every STORED cell with the sheet and table holding it.

        Sheets, then tables, then rows left to right. A Numbers table is sparse, so
        an empty cell and one swallowed by a merge have no record and never appear
        here; `Table.gridIterate` walks the declared grid instead.
        """
        for sheet in self.sheets:
            for table in sheet.tables:
                # Sorted so the order is this method's guarantee rather than a
                # property of files Numbers is not obliged to keep writing that way.
                for reference in sorted(
                    table.cells, key=lambda address: address.asRowColumn()
                ):
                    yield (sheet, table, table.cells[reference])

    def referencesIterate(self) -> Iterator[ReferenceLocation]:
        """Yield every reference and range in every formula, as a movable location.

        Cells in `cellsIterate` order, then nodes in the order the formula stores
        them. A location is a view of one reference, so shifting one writes through to
        the cell holding it.
        """
        from pybers.document.references import iterateReferences

        yield from iterateReferences(self)

    def save(self, path: Path | str | None = None) -> None:
        """Write this document back to a `.numbers` package, in place by default.

        Repeatable, and the object stays usable, so there is no `close`. **pybers never
        evaluates a formula**: saving marks the edited cells and Numbers recalculates on
        open, so a dependent formula reads stale here and correct there.
        """
        # Imported here rather than at module scope, because the writer reaches into
        # `pybers._persistence` and the model layer must stay importable without it.
        from pybers.document._write import writeDocument

        writeDocument(self, path)
