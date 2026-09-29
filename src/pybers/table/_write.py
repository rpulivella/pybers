#!/usr/bin/env python3
"""\
One table's save: the entry point the document writer calls for every table.

Everything that happens to one table during a save starts here: creating the
tables the model gained, the structural edit, the tile pass, the merge store, and
telling the calculation engine what moved and what each formula reads. The
document writer walks sheets and tables and calls `TableSave.tableWrite`.

**Saving mutates the archives that were read rather than building new ones**, so
whatever the model does not yet represent survives untouched.

Private. The table feature offers `Table` and `Cell`, not the machinery that saves
one.

UPDATES
2026-09-29  Filled cells are found and carried after any move, for PYB-118.
2026-09-24  A moved merge keeps the records it carries, for PYB-18.
2026-09-23  Cells moved as a block are found and carried, for PYB-18.
2026-09-22  The entry point for one table's save, gathered from the document
            writer for PYB-113. Records, refcounts, merges and the tile pass
            moved to modules of their own.
2026-09-22  Type identifiers are asked of the registry by class, for PYB-113.
2026-09-22  Archives written through the save's index, for PYB-109.
2026-09-08  Split out of the writer for #58, taking the merge formula with it.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .._engine import (
    FormulaDependencies,
    TableOwner,
    findCalculationEngine,
    findOwnerEntry,
    listRegisteredCells,
    moveOwnerCoordinates,
    readTableIdentities,
    readTableOwnerEntries,
    readTableOwnerIds,
    registerFormulaCells,
    remapOwnerCoordinates,
)
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSTArchives_pb2 as tst
from .._persistence.index import ArchiveIndex
from .._persistence.metadata import PackageRegistry
from ..addressing.reference import originOffset
from ..errors import WriteError
from ..formula._dependencies import resolveFormulaDependencies
from ._create import createTables
from ._edits import applyTableEdits
from ._lines import buildGridMaps
from ._merges import applyMerges, listSwallowedPositions
from ._relocation import findCellCopies, findCellMoves
from ._structure import applyGridStructure, listModelFormulas
from .cells import Table

if TYPE_CHECKING:
    # Guarded because the document feature imports this one to save its tables.
    from ..document.sheets import Document


def collectFormulaDependencies(
    table: Table,
    hostOwner: int,
    added: list[tuple[int, int]],
    ownerIds: dict[str, int],
    extents: dict[str | None, tuple[int, int]],
) -> dict[tuple[int, int], FormulaDependencies]:
    """Return what each newly attached formula reads, in the engine's own terms."""
    extents = {**extents, None: (table.rowCount, table.colCount)}
    dependencies: dict[tuple[int, int], FormulaDependencies] = {}
    for row, column in added:
        cell = table.cell(row=row + originOffset, col=column + originOffset)
        if cell.formula is None:
            raise WriteError(
                f"{table.name!r} reports a formula at row {row + originOffset}, "
                f"column {column + originOffset} that the model does not hold."
            )
        dependencies[(row, column)] = resolveFormulaDependencies(
            cell.formula, cell.reference, hostOwner, ownerIds, table.name, extents
        )
    return dependencies


@dataclass(slots=True)
class TableSave:
    """One save's view of the calculation engine, and every table written through it.

    `written` collects the cells each table moved, keyed by its info archive, for
    the one recalculation request the whole document makes.
    """

    index: ArchiveIndex
    registry: PackageRegistry
    entries: dict[int, TableOwner]
    ownerIds: dict[str, int]
    extents: dict[str | None, tuple[int, int]]
    written: dict[int, list[tuple[int, int]]] = field(default_factory=dict)

    def tableWrite(self, table: Table, reference: tsp.Reference) -> None:
        """Write one table back into its archives and tell the engine what moved."""
        index = self.index
        tableInfo = index.resolve(reference, tst.TableInfoArchive)
        modelIdentifier = tableInfo.tableModel.identifier
        model = index.resolve(tableInfo.tableModel, tst.TableModelArchive)
        entry = findOwnerEntry(self.entries, reference.identifier, table.name)

        # Before the merges are compared, since a merge the edit only moved must
        # not read as one the caller added.
        maps = buildGridMaps(index, model, table)
        registered: list[tuple[int, int]] = []
        plan = None
        if maps.changed:
            registered = listRegisteredCells(entry.dependencies)
            plan = applyGridStructure(
                index, self.registry, table, tableInfo,
                reference.identifier, model, maps,
            )
            remapOwnerCoordinates(
                entry.dependencies, maps.rows, maps.columns, table.name
            )
        moves = findCellMoves(table, maps)
        if moves:
            moveOwnerCoordinates(entry.dependencies, moves, table.name)
        copies = findCellCopies(table)

        # A moved merge reads as an added one, and the records it carries are kept.
        swallowed = listSwallowedPositions(table, model) - frozenset(moves.values())
        edits = applyTableEdits(
            index, table, model, swallowed, maps, self.registry, plan, moves, copies
        )
        moved = applyMerges(table, model, entry.dependencies.formula_owner_uid)
        if moved or swallowed or maps.changed or moves or copies:
            # A structural edit or a moved block can create and remove tiles and
            # buckets, which the model has to declare as it points at them.
            index.archiveWrite(
                modelIdentifier, model,
                self.registry.referencesReconcile(modelIdentifier, model)
                if maps.changed or moves or copies else None,
            )
        # The engine's register of formula-bearing cells, which is a separate
        # fact from a cell having moved and is what makes a newly attached
        # formula evaluate at all, and recompute afterward. A structural edit
        # moves every formula, so every one is registered afresh.
        added = edits.formulaAdded
        removed = edits.formulaRemoved
        if maps.changed:
            added = listModelFormulas(table)
            removed = registered + removed
        registerFormulaCells(
            index,
            self.registry,
            entry,
            collectFormulaDependencies(
                table, entry.dependencies.internal_formula_owner_id,
                added, self.ownerIds, self.extents,
            ),
            removed,
        )
        recalculated = added if maps.changed else []
        if edits.written or moved or recalculated:
            self.written[reference.identifier] = (
                edits.written + sorted(moved) + recalculated
            )


def openTableSave(document: Document, registry: PackageRegistry) -> TableSave:
    """Create every table the model gained, then read the engine the save writes to.

    Read after creation, since a created table registers owners of its own.
    """
    createTables(document, registry)
    index = registry.index
    engine = findCalculationEngine(index)
    # A formula names the table it reads by identity, and the engine by internal
    # owner id, so declaring what a formula reads needs both halves in hand.
    internalIds = readTableOwnerIds(index, engine)
    ownerIds = {
        identity: internalIds[identifier]
        for identifier, identity in readTableIdentities(index).items()
        if identifier in internalIds
    }
    return TableSave(
        index=index,
        registry=registry,
        entries=readTableOwnerEntries(index, engine),
        ownerIds=ownerIds,
        extents={
            table.identifier: (table.rowCount, table.colCount)
            for sheet in document.sheets for table in sheet.tables
        },
    )


__all__ = [
    "TableSave",
    "openTableSave",
]
