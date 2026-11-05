#!/usr/bin/env python3
"""A table's header rows, header columns and footer rows, and how an edit moves them.

Header rows sit at the top of a table, header columns at its left and footer rows at
its bottom, never in its middle, the names Numbers' schema and its Headers & Footer
controls give them. Each count runs from none to five, measured in `40-table-bands`,
and at least one row and one column stay outside them, as Numbers enforces.

Numbers styles header and footer rows through the table's own templates, so a cell
pybers created carries no style and changes between them without anything else
changing. A cell read from a file can carry a style parented to one, which Numbers
re-parents when it changes, so `headersSet` refuses to move one.
See findings-03-structure.md.

UPDATES
2026-11-05  Named for Numbers' Headers & Footer, and at least one row and one
            column stay outside them, in a set and an edit alike, for PYB-223.
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

import re
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from pybers.addressing.lines import GridEdit
from pybers.addressing.reference import CellAddress, ReferenceError

if TYPE_CHECKING:
    from pybers.table.cells import Table

# The most lines each count holds, measured in `40-table-bands`, which maxes all three.
headerLimit: int = 5


@dataclass(frozen=True, slots=True)
class TableHeaders:
    """How many header rows, header columns and footer rows a table holds."""

    headerRows: int = 0
    headerColumns: int = 0
    footerRows: int = 0

    def __post_init__(self) -> None:
        for each in fields(self):
            count = getattr(self, each.name)
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ReferenceError(
                    f"A header or footer holds a count of lines, and "
                    f"{formatHeaderName(each.name)} {count!r} is not one."
                )

    def membershipFind(
        self, address: CellAddress, rowCount: int
    ) -> tuple[bool, bool, bool]:
        """Return whether a cell is in the header rows, header columns, footer rows."""
        return (
            address.row <= self.headerRows,
            address.col <= self.headerColumns,
            address.row > rowCount - self.footerRows,
        )


def formatHeaderName(field: str) -> str:
    """Return a count's field name as the words a message uses, `header rows`."""
    return re.sub(r"(?<!^)(?=[A-Z])", " ", field).lower()


def refuseHeadersUnfit(
    headers: TableHeaders, rowCount: int, colCount: int, action: str
) -> None:
    """Refuse headers Numbers would not allow in a grid this size, naming the action.

    Each count holds at most five lines, and at least one row and one column stay
    outside the headers and footers. Numbers disables every control and action that
    would break
    either, as the maintainer confirmed in Numbers 15.4 on 5 November 2026.
    """
    for each in fields(headers):
        count = getattr(headers, each.name)
        if count > headerLimit:
            raise ReferenceError(
                f"{action} would make {count} {formatHeaderName(each.name)}, and "
                f"Numbers allows at most {headerLimit}."
            )
    for counted, held, axis in (
        (headers.headerRows + headers.footerRows, rowCount, "row"),
        (headers.headerColumns, colCount, "column"),
    ):
        if counted >= held:
            raise ReferenceError(
                f"{action} would leave no {axis} outside the headers and footers, and "
                "Numbers keeps at least one."
            )


def checkHeadersFit(table: Table, headers: TableHeaders) -> None:
    """Refuse headers a table's grid cannot hold, or that would move a stored cell.

    A cell carrying a record from a file may carry a style its header or footer
    parents, which pybers does not re-parent, so moving one is refused.
    """
    refuseHeadersUnfit(
        headers, table.rowCount, table.colCount,
        f"Setting the headers of {table.reference}",
    )
    held = table.headers
    for address, cell in table.cells.items():
        recorded = cell._origin is not None or cell._copiedFrom is not None
        moved = held.membershipFind(address, table.rowCount) != (
            headers.membershipFind(address, table.rowCount)
        )
        if recorded and moved:
            raise ReferenceError(
                f"{cell.reference} would move into or out of the headers, and it "
                "holds a record read from the file, whose style Numbers re-parents "
                "and pybers does not. Changing the headers of a table Numbers saved "
                "with cells in them is not supported."
            )


def mapHeaders(headers: TableHeaders, edit: GridEdit, held: int) -> TableHeaders:
    """Return the headers after a structural edit of `held` lines on one axis.

    A line added at the first footer row, or after the last line,
    lands inside it, measured in `57-bands-row-inserted-before-footer`.
    """
    leading = headers.headerRows if edit.rows else headers.headerColumns
    trailing = headers.footerRows if edit.rows else 0
    if edit.removing:
        lines = range(edit.at, edit.last + 1)
        leading -= sum(1 for line in lines if line <= leading)
        trailing -= sum(1 for line in lines if line > held - trailing)
    else:
        leading += edit.count if edit.at <= leading else 0
        trailing += edit.count if trailing and edit.at > held - trailing else 0
    if edit.rows:
        return TableHeaders(leading, headers.headerColumns, trailing)
    return TableHeaders(headers.headerRows, leading, headers.footerRows)


__all__ = [
    "TableHeaders", "checkHeadersFit", "headerLimit", "mapHeaders",
    "refuseHeadersUnfit",
]
