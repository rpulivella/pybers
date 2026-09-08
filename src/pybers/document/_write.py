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
    calculationEngine,
    ownerEntryFor,
    registerFormulaCells,
    requestRecalculation,
    tableOwnerEntries,
)
from .._generated import TNArchives_pb2 as tn
from .._generated import TSTArchives_pb2 as tst
from .._persistence import (
    NumbersPackage,
    writePackage,
)
from .._persistence.index import (
    ArchiveIndex,
    findRoot,
    originOffset,
    tableInfoTypeId,
)
from ..errors import WriteError
from ..table._write import applyMerges, applyTableEdits, mergesAdded
from .sheets import Document


def applyDocumentEdits(document: Document, package: NumbersPackage) -> int:
    """Write every changed cell of every table back into the package.

    The model is compared against the archives rather than tracked as it is edited.
    A caller assigns to `Cell.value` directly, so there is no hook to record a
    change, and a comparison cannot go stale the way a dirty flag can.
    """
    index = ArchiveIndex(package)
    owners = {
        archive.identifier: iwaFile
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
    }
    root = findRoot(index)
    written: dict[int, list[tuple[int, int]]] = {}
    entries = tableOwnerEntries(index, calculationEngine(index))

    # Both pairings are checked rather than zipped loosely. A plain `zip` stops at
    # the shorter side, so a model holding fewer sheets than the document does would
    # write some of them and skip the rest in silence, which is the failure this
    # format specializes in. Neither count can legitimately differ: the model was
    # built from these archives.
    if len(document.sheets) != len(root.sheets):
        raise WriteError(
            f"This document holds {len(root.sheets)} sheets and the model holds "
            f"{len(document.sheets)}. Adding or removing a sheet is not supported."
        )
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
            entry = ownerEntryFor(entries, tableReference.identifier, table.name)

            # Only a merge being ADDED clears its covered positions. One already
            # in the file may carry a style-only record at each of them, which an
            # XLSX import writes and Numbers then keeps forever, and stripping
            # those would rewrite a document the caller only asked to save.
            swallowed = frozenset(
                (reference.row - originOffset, reference.col - originOffset)
                for merge in mergesAdded(table, model)
                for reference in merge.extent
                if reference != merge.anchor
            )
            edits = applyTableEdits(index, owners, table, model, swallowed)
            moved = applyMerges(
                table, model, entry.dependencies.formula_owner_uid
            )
            if moved or swallowed:
                owners[modelArchive.identifier].messageReplace(
                    modelArchive.identifier, 0, model.SerializeToString()
                )
            # The engine's register of formula-bearing cells, which is a separate
            # fact from a cell having moved and is what makes a newly attached
            # formula evaluate at all.
            for identifier, body in registerFormulaCells(
                index, entry, edits.formulaAdded, edits.formulaRemoved
            ).items():
                owners[identifier].messageReplace(identifier, 0, body)
            if edits.written or moved:
                written[tableReference.identifier] = (
                    edits.written + sorted(moved)
                )

    requestRecalculation(index, owners, written)
    return sum(len(cells) for cells in written.values())


def targetFor(document: Document, path: Path | str | None) -> Path:
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
    applyDocumentEdits(document, package)
    writeAtomically(package, targetFor(document, path))


# `Document.save` reaches `writeDocument` and nothing else, and no other module in
# `src/` imports from here at all. Everything above exists to get that one function
# its job done, so it is named for the call site rather than for a caller who does
# not exist. Stated rather than assumed, because a published package makes every
# undeclared name someone else's dependency.
__all__ = ["WriteError", "writeDocument"]
