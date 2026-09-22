#!/usr/bin/env python3
"""\
Write a `Document` back to a `.numbers` package: the write half of the binding.

The mirror of `pybers.document._read`. `Document.save` reaches it through a
function-local import, so that importing the model never drags in the persistence
layer. See CLAUDE.md, "Document is the single handle".

Formulas are in `pybers.writeformula` and the calculation engine's three registers
in `pybers.writeengine`. What is left here is the cell records, the tiles they sit
in, and staging a package on disk.

**Saving mutates the archives that were read rather than building new ones.** A
document holds far more than this model represents yet, and every one of those
parts survives only because nothing touched it. Constructing a fresh package from
the model would silently drop all of it, and the loss would show up as a document
Numbers opens with its charts, conditional formats and print settings quietly
gone, rather than as an error.

UPDATES
2026-09-01  Written for #2: the unchanged round trip.
2026-09-01  Numeric edits reach the tile they came from, for #2.
2026-09-02  Edited cells are marked for recalculation, for #25.
2026-09-02  Merges are written back to the merge store, for #16.
2026-09-08  Formulas and the engine moved to modules of their own, for #45.
2026-09-14  A sheet or table the model gained is created before anything else is
            written, for PYB-63.
2026-09-18  Rows and columns added or removed reach every archive indexed by one,
            and the edited table's formulas are registered afresh, for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/02"

import tempfile
from pathlib import Path

from .._engine import (
    CellEdge,
    FormulaDependencies,
    RangeEdge,
    SpanEdge,
    TableOwner,
    findCalculationEngine,
    findOwnerEntry,
    readTableIdentities,
    readTableOwnerEntries,
    readTableOwnerIds,
    registerFormulaCells,
    requestRecalculation,
)
from .._generated import TNArchives_pb2 as tn
from .._generated import TSTArchives_pb2 as tst
from .._persistence import (
    NumbersPackage,
    PackageRegistry,
    writePackage,
)
from .._persistence.index import (
    ArchiveIndex,
    findRoot,
    originOffset,
    tableInfoTypeId,
)
from ..errors import WriteError
from ..formula.precedents import resolveFormulaPrecedents
from ..table._create import createTables
from ..table._lines import buildGridMaps
from ..table._structure import (
    applyGridStructure,
    listModelFormulas,
    listRegisteredFormulas,
    remapOwnerCoordinates,
)
from ..table._write import applyMerges, applyTableEdits, findAddedMerges
from ..table.cells import Table
from ._create import createSheets
from .sheets import Document, Sheet


def collectFormulaDependencies(
    table: Table,
    entry: TableOwner,
    added: list[tuple[int, int]],
    ownerIds: dict[str, int],
) -> dict[tuple[int, int], FormulaDependencies]:
    """Return what each newly attached formula reads, in the engine's own terms.

    The formula says which table by identity and where by offset; the engine wants
    an internal owner id and an absolute coordinate, so this is where the two meet.
    """
    host = entry.dependencies.internal_formula_owner_id

    def owner(identity: str | None) -> int:
        if identity is None:
            return host
        found = ownerIds.get(identity)
        if found is None:
            raise WriteError(
                f"A formula in {table.name!r} reads table {identity}, which this "
                "document's calculation engine does not register, so what the "
                "formula depends on cannot be recorded."
            )
        return found

    dependencies: dict[tuple[int, int], FormulaDependencies] = {}
    for row, column in added:
        cell = table.cell(row=row + originOffset, col=column + originOffset)
        if cell.formula is None:
            raise WriteError(
                f"{table.name!r} reports a formula at row {row + originOffset}, "
                f"column {column + originOffset} that the model does not hold."
            )
        reads = resolveFormulaPrecedents(cell.formula, cell.reference)
        dependencies[(row, column)] = FormulaDependencies(
            cells=tuple(
                CellEdge(
                    row=precedent.row,
                    column=precedent.column,
                    owner=(
                        None if precedent.tableId is None
                        else owner(precedent.tableId)
                    ),
                )
                for precedent in reads.cells
            ),
            ranges=tuple(
                RangeEdge(
                    top=extent.top,
                    left=extent.left,
                    bottom=extent.bottom,
                    right=extent.right,
                    owner=owner(extent.tableId),
                )
                for extent in reads.ranges
            ),
            spans=tuple(
                SpanEdge(
                    begin=span.begin,
                    end=span.end,
                    columns=span.columns,
                    owner=owner(span.tableId),
                )
                for span in reads.spans
            ),
        )
    return dependencies


def applyDocumentEdits(document: Document, package: NumbersPackage) -> int:
    """Write every changed cell of every table back into the package.

    The model is compared against the archives rather than tracked as it is edited.
    A caller assigns to `Cell.value` directly, so there is no hook to record a
    change, and a comparison cannot go stale the way a dirty flag can.
    """
    registry = PackageRegistry(package)
    createSheets(document, package, registry)
    createTables(document, package, registry)
    index = ArchiveIndex(package)
    owners = {
        archive.identifier: iwaFile
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
    }
    root = findRoot(index)
    written: dict[int, list[tuple[int, int]]] = {}
    engine = findCalculationEngine(index)
    entries = readTableOwnerEntries(index, engine)
    # A formula names the table it reads by identity, and the engine by internal
    # owner id, so declaring what a formula reads needs both halves in hand.
    internalIds = readTableOwnerIds(index, engine)
    ownerIds = {
        identity: internalIds[identifier]
        for identifier, identity in readTableIdentities(index).items()
        if identifier in internalIds
    }

    # Strict, because `createSheets` has made the two lists one list, and a plain
    # `zip` would stop at the shorter side in silence if that ever stopped holding.
    for sheet, reference in zip(document.sheets, root.sheets, strict=True):
        sheetArchive = index.resolve(reference, tn.SheetArchive)
        tableReferences = [
            drawable for drawable in sheetArchive.drawable_infos
            if index.typeOf(drawable) == tableInfoTypeId
        ]
        if len(sheet.tables) != len(tableReferences):
            raise WriteError(
                f"{sheet.name!r} holds {len(tableReferences)} tables and the model "
                f"holds {len(sheet.tables)}. Adding or removing a table is not "
                "supported."
            )
        for table, tableReference in zip(sheet.tables, tableReferences, strict=True):
            tableInfo = index.resolve(tableReference, tst.TableInfoArchive)
            modelArchive = index.archive(tableInfo.tableModel.identifier)
            model = index.resolve(tableInfo.tableModel, tst.TableModelArchive)
            entry = findOwnerEntry(entries, tableReference.identifier, table.name)

            # Before the merges are compared, since a merge the edit only moved must
            # not read as one the caller added.
            maps = buildGridMaps(index, model, table)
            registered: list[tuple[int, int]] = []
            plan = None
            if maps.changed:
                registered = listRegisteredFormulas(entry.dependencies)
                plan = applyGridStructure(
                    index, registry, owners, table, tableInfo,
                    tableReference.identifier, model, maps,
                )
                remapOwnerCoordinates(entry.dependencies, table, maps)

            # Only a merge being ADDED clears its covered positions. One already
            # in the file may carry a style-only record at each of them, which an
            # XLSX import writes and Numbers then keeps forever, and stripping
            # those would rewrite a document the caller only asked to save.
            swallowed = frozenset(
                (reference.row - originOffset, reference.col - originOffset)
                for merge in findAddedMerges(table, model)
                for reference in merge.extent
                if reference != merge.anchor
            )
            edits = applyTableEdits(
                index, owners, table, model, swallowed, maps, registry, plan
            )
            moved = applyMerges(
                table, model, entry.dependencies.formula_owner_uid
            )
            if moved or swallowed or maps.changed:
                # A structural edit can create and remove tiles and buckets, which
                # the model has to declare as it points at them.
                owners[modelArchive.identifier].messageReplace(
                    modelArchive.identifier, 0, model.SerializeToString(),
                    registry.referencesReconcile(modelArchive, model)
                    if maps.changed else None,
                )
            # The engine's register of formula-bearing cells, which is a separate
            # fact from a cell having moved and is what makes a newly attached
            # formula evaluate at all, and recompute afterward. A structural edit
            # moves every formula, so every one is registered afresh in one call:
            # a second would read the tiles this one rewrote as they were.
            added = edits.formulaAdded
            removed = edits.formulaRemoved
            if maps.changed:
                added = listModelFormulas(table)
                removed = registered + removed
            registerFormulaCells(
                index,
                registry,
                entry,
                collectFormulaDependencies(table, entry, added, ownerIds),
                removed,
            )
            recalculated = added if maps.changed else []
            if edits.written or moved or recalculated:
                written[tableReference.identifier] = (
                    edits.written + sorted(moved) + recalculated
                )

    requestRecalculation(index, owners, written)
    registry.save()
    return sum(len(cells) for cells in written.values())


def resolveSaveTarget(document: Document, path: Path | str | None) -> Path:
    """Resolve where a save lands: the argument, or where the document came from.

    A document that was never read from disk has no path to fall back on, so an
    argumentless save on one is refused rather than guessed at.
    """
    if path is not None:
        return Path(path)
    if document._sourcePath is None:
        raise WriteError(
            "This document was not read from a file, so there is nowhere to save "
            "it in place. Pass a path to save."
        )
    return document._sourcePath


def writeAtomically(package: NumbersPackage, target: Path) -> None:
    """Write a package to a temporary name beside the target, then take its place.

    A `.numbers` package is a zip rewritten whole, so writing straight to the
    target would leave a truncated file where the document used to be if anything
    failed part way through. The temporary lands in the same directory, and
    therefore on the same filesystem, which is what makes the replacement atomic.
    """
    directory = target.parent
    if not directory.is_dir():
        raise WriteError(f"Cannot save to {target}: {directory} is not a directory.")

    # Opened only to reserve a unique name in the target's own directory, so that
    # the replace below is atomic on the same filesystem. `delete=False` keeps the
    # file after the block, and the block is what closes it.
    with tempfile.NamedTemporaryFile(
        dir=directory, prefix=f".{target.stem}-", suffix=".numbers", delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        writePackage(package, temporary)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def listIdentifiable(document: Document) -> list[Sheet | Table]:
    """Return every sheet and table, each of which records the archive it has."""
    items: list[Sheet | Table] = []
    for sheet in document.sheets:
        items.append(sheet)
        items.extend(sheet.tables)
    return items


def writeDocument(document: Document, path: Path | str | None = None) -> None:
    """Write a document back to a `.numbers` package.

    Reached through `Document.save`, which is the caller-facing spelling. This
    function exists separately so the model layer can stay free of any import of
    the persistence layer.
    """
    package = document._package
    if package is None:
        raise WriteError(
            "This document carries no archives, so there is nothing to write. Only "
            "a document from `pybers.open` can be saved; building one from scratch "
            "is not supported yet."
        )
    # Created sheets and tables change both the package and the model's identifiers,
    # so a save that fails part way undoes both rather than leaving a retry to
    # create them twice.
    snapshot = package.snapshot()
    identified = {
        id(item) for item in listIdentifiable(document) if item._identifier is not None
    }
    try:
        applyDocumentEdits(document, package)
        writeAtomically(package, resolveSaveTarget(document, path))
    except Exception:
        package.restore(snapshot)
        for item in listIdentifiable(document):
            if id(item) not in identified:
                item._identifier = None
        raise


# `Document.save` reaches `writeDocument` and nothing else, and no other module in
# `src/` imports from here at all. Everything above exists to get that one function
# its job done, so it is named for the call site rather than for a caller who does
# not exist. Stated rather than assumed, because a published package makes every
# undeclared name someone else's dependency.
__all__ = ["WriteError", "writeDocument"]
