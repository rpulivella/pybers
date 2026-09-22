#!/usr/bin/env python3
"""\
The engine's cell-keyed records a structural edit moves, which no registration rewrites.

UPDATES
2026-09-22  Split out of the engine module for PYB-113.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/22"

from typing import Protocol

from .._generated import TSCEArchives_pb2 as tsce
from ..errors import WriteError


class LineMapping(Protocol):
    """Where each stored row, or each stored column, of a table lands after an edit.

    Named here as a shape rather than imported, so the engine knows no table type.
    """

    @property
    def growth(self) -> int:
        """Return how many lines the edit added, less how many it removed."""
        ...

    def lineMap(self, line: int) -> int | None:
        """Return where one stored line lands, or None when the edit removed it."""
        ...

    def spanCut(self, begin: int, end: int) -> bool:
        """Report whether the edit removes a line of a span or adds one inside it."""
        ...


def refuseUnmovableEngineState(
    dependencies: tsce.FormulaOwnerDependenciesArchive, name: str
) -> None:
    """Refuse engine state keyed by cell that a structural edit does not move."""
    if dependencies.whole_owner_dependencies.dependent_cells.ByteSize():
        raise WriteError(
            f"{name!r} holds a formula the engine records as reading the whole "
            "table, and moving that record is not measured."
        )


def remapCoordinateSet(
    coordinates: tsce.CellCoordSetArchive, rows: LineMapping, columns: LineMapping
) -> None:
    """Move every cell a set names, dropping those whose line is gone.

    The set is columns, each holding row ranges, which is how `NOW()` and `RAND()`
    are recorded in `57-structure-refusals-base`.
    """
    moved: dict[int, set[int]] = {}
    for entry in coordinates.column_entries:
        column = columns.lineMap(entry.column)
        if column is None:
            continue
        for extent in entry.row_set.entries:
            begin = extent.range_begin
            last = extent.range_end if extent.HasField("range_end") else begin
            for stored in range(begin, last + 1):
                row = rows.lineMap(stored)
                if row is not None:
                    moved.setdefault(column, set()).add(row)
    del coordinates.column_entries[:]
    for column in sorted(moved):
        entry = coordinates.column_entries.add()
        entry.column = column
        for row in sorted(moved[column]):
            entry.row_set.entries.add(range_begin=row)


def remapSpills(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
    rows: LineMapping,
    columns: LineMapping,
    name: str,
) -> None:
    """Move each spill with its formula, refusing an edit that lands inside one.

    **Numbers re-flows a spill cut by an edit**, measured 2026-09-21 in
    `57-engine-row-inserted`: a row added inside `SEQUENCE(3)` left the spilled
    cells where they were and moved the row below instead. Following that means
    evaluating the formula. An edit outside a spill moves it whole, as
    `57-engine-column-inserted` moved `C4:D4` to `D4:E4`, which is ordinary movement.
    """
    for spill in dependencies.spill_range_sizes.spills:
        row, column = spill.coordinate.row, spill.coordinate.column
        height = spill.spill_size.num_rows or 1
        width = spill.spill_size.num_columns or 1
        if rows.spanCut(row, row + height - 1) or columns.spanCut(
            column, column + width - 1
        ):
            raise WriteError(
                f"{name!r} has a row or column added or removed inside a formula's "
                "spill, and Numbers re-flows a spill rather than moving it, which "
                "means evaluating the formula."
            )
    # A moved spill is listed first, as Numbers listed it in both measurements
    # where one moved and one stayed.
    moved: list[tsce.CellSpillSizesArchive.SpillForCell] = []
    stayed: list[tsce.CellSpillSizesArchive.SpillForCell] = []
    for spill in dependencies.spill_range_sizes.spills:
        movedRow = rows.lineMap(spill.coordinate.row)
        movedColumn = columns.lineMap(spill.coordinate.column)
        assert movedRow is not None and movedColumn is not None
        copy = tsce.CellSpillSizesArchive.SpillForCell()
        copy.CopyFrom(spill)
        copy.coordinate.row = movedRow
        copy.coordinate.column = movedColumn
        unchanged = (movedRow, movedColumn) == (
            spill.coordinate.row, spill.coordinate.column
        )
        (stayed if unchanged else moved).append(copy)
    del dependencies.spill_range_sizes.spills[:]
    dependencies.spill_range_sizes.spills.extend(moved + stayed)


def remapOwnerCoordinates(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
    rows: LineMapping,
    columns: LineMapping,
    name: str,
) -> None:
    """Move the engine's cell-keyed records that no formula registration rewrites.

    Errors follow their cells, or go with a removed one, and the table's own
    extent follows its size. The errors' text is left for the recalculation every
    moved formula is marked for.
    """
    refuseUnmovableEngineState(dependencies, name)
    volatile = dependencies.volatile_dependencies
    for kind in (
        "volatile_time_cells", "volatile_random_cells", "volatile_locale_cells",
        "volatile_sheet_table_name_cells", "volatile_remote_data_cells",
    ):
        remapCoordinateSet(getattr(volatile, kind), rows, columns)
    remapSpills(dependencies, rows, columns, name)
    for spanning in (
        dependencies.spanning_column_dependencies,
        dependencies.spanning_row_dependencies,
    ):
        for extent in (spanning.total_range_for_table, spanning.body_range_for_table):
            if not extent.ByteSize():
                continue
            extent.bottom_right_row += rows.growth
            extent.bottom_right_column += columns.growth
    errors = dependencies.cell_errors
    for field in ("errors", "enhanced_errors"):
        entries = getattr(errors, field)
        kept = []
        for entry in entries:
            row = rows.lineMap(entry.coordinate.row)
            column = columns.lineMap(entry.coordinate.column)
            if row is None or column is None:
                continue
            entry.coordinate.row = row
            entry.coordinate.column = column
            kept.append(entry)
        copies = [type(entry)() for entry in kept]
        for copy, entry in zip(copies, kept, strict=True):
            copy.CopyFrom(entry)
        del entries[:]
        entries.extend(copies)


__all__ = [
    "LineMapping",
    "remapOwnerCoordinates",
]
