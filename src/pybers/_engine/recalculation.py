#!/usr/bin/env python3
"""\
The dirty set: the cells that moved, so Numbers recalculates what depends on them.

**Numbers does not recalculate on open**, so an edited cell has to be named in
`refs_to_dirty` or its dependents keep showing what they last computed. Naming only
the cells that changed is enough: Numbers walks its own dependency graph from
there, across tables and across sheets.

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

from .._generated import TSCEArchives_pb2 as tsce
from .._persistence.index import ArchiveIndex
from ..errors import WriteError
from .owners import findCalculationEngine, readTableOwnerIds


def buildDirtySet(
    edits: dict[int, list[tuple[int, int]]]
) -> tsce.ReferencesToDirtyArchive:
    """Return the archive naming every cell that moved, grouped as Numbers groups them.

    Owners hold columns, columns hold a set of row ranges. Contiguous rows collapse
    into one range, which is how Numbers writes its own, and a run of one omits
    `range_end` rather than repeating the beginning.
    """
    dirty = tsce.ReferencesToDirtyArchive()
    for ownerId, cells in sorted(edits.items()):
        dirty.to_dirty_owner_ids.entries.add(range_begin=ownerId)
        owner = dirty.to_dirty_cells.owner_entries.add()
        owner.owner_id = ownerId
        byColumn: dict[int, list[int]] = {}
        for row, column in sorted(set(cells)):
            byColumn.setdefault(column, []).append(row)
        for column, rows in sorted(byColumn.items()):
            entry = owner.coord_set.column_entries.add()
            entry.column = column
            runs: list[list[int]] = []
            for row in rows:
                if runs and row == runs[-1][1] + 1:
                    runs[-1][1] = row
                else:
                    runs.append([row, row])
            for begin, end in runs:
                added = entry.row_set.entries.add(range_begin=begin)
                if end != begin:
                    added.range_end = end
    return dirty


def requestRecalculation(
    index: ArchiveIndex, written: dict[int, list[tuple[int, int]]]
) -> int:
    """Tell Numbers which cells moved, so it recalculates whatever depends on them.

    **A formula caches its result and opening the document does not refresh it**, so a
    save without this displays arithmetic that disagrees with its own operands, with
    no prompt. Naming the edited cells is enough: Numbers walks its own graph from
    there, transitively and across sheets, which is why this library never evaluates.
    Measured 2026-09-02 both broadly and minimally, in findings-02-formulas.md.
    """
    if not written:
        return 0
    engine = findCalculationEngine(index)
    if not engine.HasField("refs_to_dirty"):
        raise WriteError(
            "The calculation engine carries no refs_to_dirty reference, so the cells "
            "that changed cannot be marked and the saved file would display stale "
            "formula results."
        )

    ownerIds = readTableOwnerIds(index, engine)
    edits: dict[int, list[tuple[int, int]]] = {}
    for tableIdentifier, cells in written.items():
        ownerId = ownerIds.get(tableIdentifier)
        if ownerId is None:
            raise WriteError(
                f"The table in archive {tableIdentifier} has no calculation-engine "
                "owner id, so the cells edited in it cannot be marked for "
                "recalculation and the saved file would display stale results."
            )
        edits.setdefault(ownerId, []).extend(cells)

    index.archiveWrite(engine.refs_to_dirty.identifier, buildDirtySet(edits))
    return sum(len(cells) for cells in edits.values())


__all__ = [
    "buildDirtySet",
    "requestRecalculation",
]
