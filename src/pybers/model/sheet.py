#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, TypeVar, TYPE_CHECKING

from pybers.model.shapes import GraphicalObject
from pybers.model.table import Cell, Table

if TYPE_CHECKING:
    # Guarded so that importing the model never drags in the persistence layer.
    from pybers.numbersfile import NumbersPackage

# Sheets and tables both count from one, matching the rest of the model and matching
# what Numbers shows. The file counts from zero and the two meet only in the reader.
firstPosition: int = 1


class SelectionError(LookupError):
    """A name or a position selecting no sheet or table, or selecting more than one.

    A `LookupError` rather than a `KeyError`, because `KeyError` displays the repr of
    its argument in place of its message, which would swallow the list of what is
    actually present that these messages exist to give.
    """


class Named(Protocol):
    """Anything reachable by name: a sheet, or a table on one."""

    name: str


NamedT = TypeVar("NamedT", bound=Named)


def namesListed(items: Sequence[Named]) -> str:
    """Return the names present, for an error message that says what to ask for."""
    if not items:
        return "nothing"
    return ", ".join(repr(item.name) for item in items)


def selectedByName(
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


def selectedByPosition(
    items: Sequence[NamedT], position: int, kind: str, within: str
) -> NamedT:
    """Return the item at a one-based position in the file's own order."""
    if position < firstPosition or position > len(items) + firstPosition - 1:
        raise SelectionError(
            f"Position {position} is outside {within}, which holds {len(items)} "
            f"{kind}s. Positions count from {firstPosition}."
        )
    return items[position - firstPosition]


def selected(
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
    """The root of the pybers object model, matching Apple's own TN.DocumentArchive.

    Named for the format rather than for the spreadsheet convention: Numbers has no
    workbook, and calling it one would invent a concept the format does not carry.

    The two private fields hold the archives this document was read from and its
    origin on disk. Both are excluded from equality and from `repr`, so a Document
    still reads as an ordinary dataclass to a caller. `pybers.writer` explains why a
    save needs them.
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

    def cellsIterate(self) -> Iterator[tuple[Sheet, Table, Cell]]:
        """Yield every cell this document stores, in one defined order.

        Sheets in document order, tables in sheet order, and cells row by row and
        left to right within each table. The order is stated here rather than
        inherited from the dictionary the reader filled, because an iteration
        driving an edit has to survive a save and a reopen unchanged.

        Measured 2026-09-02: all 81 tiles in the fixture corpus already store their
        tiles, rows and records in that order, so the sort changes nothing today.
        It stays because that makes the order a guarantee of this method rather
        than a property of 44 files that nothing obliges Numbers to preserve.

        Each cell arrives with the table and the sheet holding it, because a cell
        knows only its own reference and `Table 1` on two sheets is otherwise
        indistinguishable. A plain tuple rather than a type of its own, since a
        caller writes `for sheet, table, cell in ...` and there is no fourth thing
        to carry.

        Only stored cells are yielded. A Numbers table is sparse: an empty cell has
        no record at all, and a cell covered by a merge has none either, so
        iterating stored cells and iterating the declared rectangle are two
        different traversals. `Table.extent` is what turns the second into the
        first, and it is spelled differently on purpose.
        """
        for sheet in self.sheets:
            for table in sheet.tables:
                for reference in sorted(
                    table.cells, key=lambda address: address.asRowColumn()
                ):
                    yield (sheet, table, table.cells[reference])

    def save(self, path: Path | str | None = None) -> None:
        """Write this document back to a `.numbers` package, in place by default.

        Nothing is closed and nothing is invalidated. A Document holds no file handle,
        so saving is repeatable and the object stays usable afterward, which is why
        there is no `close` and no context manager to pair with `pybers.open`.

        **A formula depending on a cell you changed is recalculated by Numbers when it
        next opens the file, not by this library.** Saving marks the edited cells in
        the document's calculation engine, and Numbers walks its own dependency graph
        from there, so a `SUM` over cells you raised shows the new total. pybers never
        evaluates a formula and never writes a result, which is why the value stored
        for such a formula is still the one Numbers last computed. Reading the file
        back through pybers therefore shows the old result; opening it in Numbers
        shows the new one.
        """
        # Imported here rather than at module scope, because the writer reaches into
        # `pybers.numbersfile` and the model layer must stay importable without it.
        from pybers.writer import writeDocument

        writeDocument(self, path)
