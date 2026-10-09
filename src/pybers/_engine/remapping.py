#!/usr/bin/env python3
"""\
The engine's cell-keyed records a structural edit or a moved block carries, which no
registration rewrites.

UPDATES
2026-09-23  Every record follows a mapping of cells, so a moved block reuses what a
            structural edit does, for PYB-18.
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

from collections.abc import Callable, Mapping
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
            "table, and moving that record is not supported."
        )


# Where a stored (row, column) lands, or None when its cell is gone.
type CellMapping = Callable[[int, int], tuple[int, int] | None]

# Whether an edit cuts a spill anchored at (row, column) of a height and width.
type SpillCut = Callable[[int, int, int, int], bool]


def remapCoordinateSet(
    coordinates: tsce.CellCoordSetArchive, cellMap: CellMapping
) -> None:
    """Move every cell a set names, dropping those whose cell is gone.

    The set is columns, each holding row ranges, which is how `NOW()` and `RAND()`
    are recorded in `57-structure-refusals-base`.
    """
    moved: dict[int, set[int]] = {}
    for entry in coordinates.column_entries:
        for extent in entry.row_set.entries:
            begin = extent.range_begin
            last = extent.range_end if extent.HasField("range_end") else begin
            for stored in range(begin, last + 1):
                landed = cellMap(stored, entry.column)
                if landed is not None:
                    moved.setdefault(landed[1], set()).add(landed[0])
    del coordinates.column_entries[:]
    for column in sorted(moved):
        entry = coordinates.column_entries.add()
        entry.column = column
        for row in sorted(moved[column]):
            entry.row_set.entries.add(range_begin=row)


def remapSpills(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
    cellMap: CellMapping,
    spillCut: SpillCut,
    name: str,
) -> None:
    """Move each spill with its formula, refusing an edit that cuts one.

    **Numbers re-flows a spill cut by an edit**, measured 2026-09-21 in
    `57-engine-row-inserted`: a row added inside `SEQUENCE(3)` left the spilled
    cells where they were and moved the row below instead. Following that means
    evaluating the formula. An edit outside a spill moves it whole, as
    `57-engine-column-inserted` moved `C4:D4` to `D4:E4`, which is ordinary movement.
    """
    for spill in dependencies.spill_range_sizes.spills:
        if spillCut(
            spill.coordinate.row, spill.coordinate.column,
            spill.spill_size.num_rows or 1, spill.spill_size.num_columns or 1,
        ):
            raise WriteError(
                f"{name!r} has an edit landing inside a formula's spill. Numbers "
                "re-flows a spill by evaluating its formula, which is not supported."
            )
    # A moved spill is listed first, as Numbers listed it in both measurements
    # where one moved and one stayed.
    moved: list[tsce.CellSpillSizesArchive.SpillForCell] = []
    stayed: list[tsce.CellSpillSizesArchive.SpillForCell] = []
    for spill in dependencies.spill_range_sizes.spills:
        landed = cellMap(spill.coordinate.row, spill.coordinate.column)
        assert landed is not None
        copy = tsce.CellSpillSizesArchive.SpillForCell()
        copy.CopyFrom(spill)
        copy.coordinate.row, copy.coordinate.column = landed
        unchanged = landed == (spill.coordinate.row, spill.coordinate.column)
        (stayed if unchanged else moved).append(copy)
    del dependencies.spill_range_sizes.spills[:]
    dependencies.spill_range_sizes.spills.extend(moved + stayed)


def remapCellErrors(
    dependencies: tsce.FormulaOwnerDependenciesArchive, cellMap: CellMapping
) -> None:
    """Move each error with its cell, or drop it with a removed one.

    The errors' text is left for the recalculation every moved formula is marked for.
    """
    errors = dependencies.cell_errors
    for field in ("errors", "enhanced_errors"):
        entries = getattr(errors, field)
        kept = []
        for entry in entries:
            landed = cellMap(entry.coordinate.row, entry.coordinate.column)
            if landed is None:
                continue
            entry.coordinate.row, entry.coordinate.column = landed
            kept.append(entry)
        copies = [type(entry)() for entry in kept]
        for copy, entry in zip(copies, kept, strict=True):
            copy.CopyFrom(entry)
        del entries[:]
        entries.extend(copies)


def remapOwnerCells(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
    cellMap: CellMapping,
    spillCut: SpillCut,
    name: str,
) -> None:
    """Move the engine's cell-keyed records: volatile cells, spills and errors."""
    refuseUnmovableEngineState(dependencies, name)
    volatile = dependencies.volatile_dependencies
    for kind in (
        "volatile_time_cells", "volatile_random_cells", "volatile_locale_cells",
        "volatile_sheet_table_name_cells", "volatile_remote_data_cells",
    ):
        remapCoordinateSet(getattr(volatile, kind), cellMap)
    remapSpills(dependencies, cellMap, spillCut, name)
    remapCellErrors(dependencies, cellMap)


def remapOwnerCoordinates(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
    rows: LineMapping,
    columns: LineMapping,
    name: str,
) -> None:
    """Move the engine's cell-keyed records through rows or columns added or removed.

    The table's own extent follows its size as well.
    """
    def cellMap(row: int, column: int) -> tuple[int, int] | None:
        movedRow, movedColumn = rows.lineMap(row), columns.lineMap(column)
        if movedRow is None or movedColumn is None:
            return None
        return (movedRow, movedColumn)

    def spillCut(row: int, column: int, height: int, width: int) -> bool:
        return rows.spanCut(row, row + height - 1) or columns.spanCut(
            column, column + width - 1
        )

    remapOwnerCells(dependencies, cellMap, spillCut, name)
    for spanning in (
        dependencies.spanning_column_dependencies,
        dependencies.spanning_row_dependencies,
    ):
        for extent in (spanning.total_range_for_table, spanning.body_range_for_table):
            if not extent.ByteSize():
                continue
            extent.bottom_right_row += rows.growth
            extent.bottom_right_column += columns.growth


def moveOwnerCoordinates(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
    moves: Mapping[tuple[int, int], tuple[int, int]],
    name: str,
) -> None:
    """Move the engine's cell-keyed records with cells moved as a block."""
    def cellMap(row: int, column: int) -> tuple[int, int] | None:
        return moves.get((row, column), (row, column))

    def spillCut(row: int, column: int, height: int, width: int) -> bool:
        cells = [
            (row + down, column + across)
            for down in range(height) for across in range(width)
        ]
        carried = sum(1 for cell in cells if cell in moves)
        return 0 < carried < len(cells)

    remapOwnerCells(dependencies, cellMap, spillCut, name)


__all__ = [
    "LineMapping",
    "moveOwnerCoordinates",
    "remapOwnerCoordinates",
]
