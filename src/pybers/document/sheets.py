#!/usr/bin/env python3
"""A sheet holds tables (row/column grids) and graphical objects (things that float on
the sheet at an absolute position, text boxes, images, shapes) side by side, since
Numbers places both on the same sheet independently. A document is a list of sheets.

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
  carries a `Table 1` on each of two sheets, which is why there is no document-wide
  table lookup by name. Sheet names carry no such enforcement at all, so a duplicate
  is handled rather than assumed away.

UPDATES
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

from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pybers.addressing.reference import tableNameSeparator
from pybers.drawable import GraphicalObject
from pybers.errors import PybersError
from pybers.table.cells import Cell, Table

if TYPE_CHECKING:
    # Guarded so that importing the model never drags in the persistence layer.
    from pybers._persistence import NumbersPackage

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


def namesListed(items: Sequence[Named]) -> str:
    """Return the names present, for an error message that says what to ask for."""
    if not items:
        return "nothing"
    return ", ".join(repr(item.name) for item in items)


def selectedByName[NamedT: Named](
    items: Sequence[NamedT], name: str, kind: str, within: str, foldCase: bool
) -> NamedT:
    """Return the one item carrying a name, raising when none or several do.

    Case folding is a per-kind fact rather than a convenience. Numbers treats two
    table names differing only in case as one name and will not create both, so
    matching a table caselessly can never merge two things a document distinguishes.
    Nothing shows it enforcing anything about sheet names, so folding them would be
    this library inventing a collision the file does not have.
    """
    wanted = name.casefold() if foldCase else name
    matched = [
        (position, item)
        for position, item in enumerate(items, start=firstPosition)
        if (item.name.casefold() if foldCase else item.name) == wanted
    ]
    if not matched:
        raise SelectionError(
            f"No {kind} in {within} is named {name!r}. "
            f"Present: {namesListed(items)}."
        )
    if len(matched) > 1:
        positions = ", ".join(str(position) for position, _ in matched)
        raise SelectionError(
            f"{len(matched)} {kind}s in {within} are named {name!r}, at positions "
            f"{positions}. A name more than one carries selects neither, so reach "
            f"for one of them by position instead."
        )
    return matched[0][1]


def selectedByPosition[NamedT: Named](
    items: Sequence[NamedT], position: int, kind: str, within: str
) -> NamedT:
    """Return the item at a one-based position in the file's own order."""
    if position < firstPosition or position > len(items) + firstPosition - 1:
        raise SelectionError(
            f"Position {position} is outside {within}, which holds {len(items)} "
            f"{kind}s. Positions count from {firstPosition}."
        )
    return items[position - firstPosition]


def selected[NamedT: Named](
    items: Sequence[NamedT],
    nameOrPosition: str | int,
    kind: str,
    within: str,
    foldCase: bool,
) -> NamedT:
    """Return the one item a name or a one-based position names, or raise saying why.

    Shared by sheets and tables so that the two cannot drift into disagreeing about
    what a position counts from or about what a repeated name does.
    """
    if isinstance(nameOrPosition, str):
        return selectedByName(items, nameOrPosition, kind, within, foldCase)
    if isinstance(nameOrPosition, int) and not isinstance(nameOrPosition, bool):
        return selectedByPosition(items, nameOrPosition, kind, within)
    # `True` reaching this as position 1 is the reason bool is excluded above: it is
    # an int in Python and it is never a position anyone meant to write.
    raise SelectionError(
        f"A {kind} is reached by its name or by its position, and "
        f"{nameOrPosition!r} is neither."
    )


@dataclass(slots=True)
class Sheet:
    """One sheet (tab) in a document: its tables and its floating graphical objects."""

    name: str
    tables: list[Table] = field(default_factory=list)
    graphicalObjects: list[GraphicalObject] = field(default_factory=list)

    def table(self, nameOrPosition: str | int) -> Table:
        """Return one of this sheet's tables by its name or by its position.

        `tables` remains, so an ordinary loop still works and nothing here replaces
        it. Position is the table's place in the sheet's drawable list, which says
        nothing about where the table sits on the page.
        """
        return selected(
            self.tables, nameOrPosition, "table", repr(self.name), foldCase=True
        )


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

    def sheet(self, nameOrPosition: str | int) -> Sheet:
        """Return one of this document's sheets by its name or by its position.

        `sheets` remains, so an ordinary loop still works. Position is the sheet's
        place in the document's own list, which is the tab order a person sees.
        """
        return selected(
            self.sheets, nameOrPosition, "sheet", "this document", foldCase=False
        )

    @property
    def tableIdentities(self) -> dict[str, str]:
        """Return the identity of every table, under each name that names it alone.

        A formula naming another table writes `Table 2::A1`, and qualifies it as
        `Sheet 2::Table 1::A1` when a bare name would be ambiguous. Both spellings
        appear here for a table whose name is unique, and only the qualified one for
        a name two tables share, which `20-formula-shapes` is the corpus example of.
        """
        qualified: dict[str, str] = {}
        seen: Counter[str] = Counter(
            table.name for sheet in self.sheets for table in sheet.tables
        )
        for sheet in self.sheets:
            for table in sheet.tables:
                if not table.identifier:
                    continue
                qualified[f"{sheet.name}{tableNameSeparator}{table.name}"] = (
                    table.identifier
                )
                if seen[table.name] == 1:
                    qualified[table.name] = table.identifier
        return qualified

    def cellsIterate(self) -> Iterator[tuple[Sheet, Table, Cell]]:
        """Yield every STORED cell with the sheet and table holding it.

        Sheets, then tables, then rows left to right. A Numbers table is sparse, so
        an empty cell and one swallowed by a merge have no record and never appear
        here; `Table.extent` walks the declared rectangle instead.
        """
        for sheet in self.sheets:
            for table in sheet.tables:
                # Sorted so the order is this method's guarantee rather than a
                # property of files Numbers is not obliged to keep writing that way.
                for reference in sorted(
                    table.cells, key=lambda address: address.asRowColumn()
                ):
                    yield (sheet, table, table.cells[reference])

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
