#!/usr/bin/env python3
"""\
Write a `Document` back to a `.numbers` package: the write half of the binding.

The mirror of `pybers.document._read`. `Document.save` reaches it through a
function-local import, so that importing the model never drags in the persistence
layer. See CLAUDE.md, "Document is the single handle".

Each table is saved by the table feature's own entry point, `TableSave`, and the
calculation engine's registers live in `pybers._engine`. What is left here is the
walk over sheets and tables, the recalculation request, and staging a package on
disk.

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
2026-09-22  One index serves the whole save, creation included, for PYB-109.
2026-09-22  Type identifiers are asked of the registry by class, for PYB-113.
2026-09-22  Only the walk is left: every table is saved through the table feature's one
            entry point, for PYB-113.
2026-09-23  A successful save records where each cell's record now sits, for
            PYB-18.
2026-09-29  A filled cell forgets the cell it copied once the save placed its
            record, for PYB-118.
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

from .._engine import requestRecalculation
from .._generated import TNArchives_pb2 as tn
from .._generated import TSTArchives_pb2 as tst
from .._persistence import (
    NumbersPackage,
    PackageRegistry,
    writePackage,
)
from .._persistence.index import ArchiveIndex, findRoot
from .._persistence.types import findArchiveTypeId
from ..errors import WriteError
from ..table._write import openTableSave
from ..table.cells import Table
from ._create import createSheets
from .sheets import Document, Sheet


def applyDocumentEdits(document: Document, package: NumbersPackage) -> int:
    """Write every changed cell of every table back into the package.

    The model is compared against the archives rather than tracked as it is edited.
    A caller assigns to `Cell.value` directly, so there is no hook to record a
    change, and a comparison cannot go stale the way a dirty flag can.
    """
    index = ArchiveIndex(package)
    registry = PackageRegistry(index)
    createSheets(document, registry)
    tables = openTableSave(document, registry)
    root = findRoot(index)
    tableInfoTypeId = findArchiveTypeId(tst.TableInfoArchive)

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
            tables.tableWrite(table, tableReference)

    requestRecalculation(index, tables.written)
    registry.save()
    return sum(len(cells) for cells in tables.written.values())


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
    updateCellOrigins(document)


def updateCellOrigins(document: Document) -> None:
    """Record where each saved cell's record now sits, since the save moved it there."""
    for sheet in document.sheets:
        for table in sheet.tables:
            for cell in table.cells.values():
                copied = cell._copiedFrom
                cell._copiedFrom = None
                if copied is not None and copied._origin is None:
                    cell._origin = None
                if (
                    cell._origin is not None
                    or cell.value is not None
                    or cell.formula is not None
                    or copied is not None and copied._origin is not None
                ):
                    cell._origin = cell.reference


# `Document.save` reaches `writeDocument` and nothing else, and no other module in
# `src/` imports from here at all. Everything above exists to get that one function
# its job done, so it is named for the call site rather than for a caller who does
# not exist. Stated rather than assumed, because a published package makes every
# undeclared name someone else's dependency.
__all__ = ["WriteError", "writeDocument"]
