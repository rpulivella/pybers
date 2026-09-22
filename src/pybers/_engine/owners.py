#!/usr/bin/env python3
"""\
Which calculation-engine owner is which table, and the identity a formula names it by.

A table records neither its internal owner id nor the identity a formula in another
table names it by. Both live on the engine's dependency entry for it, so finding
either means walking the tracker rather than reading the table, and reading the
table the obvious way finds nothing at all.

UPDATES
2026-09-22  Split out of the engine module for PYB-113, and the engine archive is
            found by its class.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/22"

from dataclasses import dataclass

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSPMessages_pb2 as tsp
from .._persistence.index import ArchiveIndex, wordBits, wordMask
from .._persistence.types import findArchiveTypeId, readArchiveTypeId
from ..errors import ReadError, WriteError

# The `owner_kind` a table's dependency entry carries, as against the other owners
# the calculation engine tracks.
tableOwnerKind: int = 1


def findCalculationEngine(index: ArchiveIndex) -> tsce.CalculationEngineArchive:
    """Return the document's one calculation engine, or refuse and say why.

    Exactly one archive in a document carries this type, the same way exactly one
    carries `TN.DocumentArchive`. All 46 documents have one, so a document without
    one is not what this library expects rather than a case to work around.
    """
    found = [
        archive for archive in index.byIdentifier.values()
        if readArchiveTypeId(archive)
        == findArchiveTypeId(tsce.CalculationEngineArchive)
    ]
    if len(found) != 1:
        raise ReadError(
            f"Expected exactly one TSCE.CalculationEngineArchive, found {len(found)}. "
            "Without it a table has no identity, and neither a merge nor a "
            "recalculation request can be written."
        )
    return index.identifierResolve(
        found[0].identifier, tsce.CalculationEngineArchive
    )


@dataclass(frozen=True, slots=True)
class TableOwner:
    """One table's calculation-engine entry, and the archive holding it.

    The identifier travels with the message because registering a formula cell
    changes that archive and it has to be written back. Looking it up a second
    time would mean walking the dependency tracker again to find what this walk
    already had in hand.
    """

    identifier: int
    dependencies: tsce.FormulaOwnerDependenciesArchive


def readTableOwnerEntries(
    index: ArchiveIndex, engine: tsce.CalculationEngineArchive
) -> dict[int, TableOwner]:
    """Return each table's dependency entry, keyed by its `TST.TableInfoArchive`.

    Read the long way round because there is no short one: a table records neither
    its internal owner id nor its owner uid. Both live here, on the entry whose
    `owner_kind` is 1 and whose `formula_owner` points back at the table. Measured
    2026-09-02, see findings-02-formulas.md and findings-03-structure.md.
    """
    entries: dict[int, TableOwner] = {}
    for reference in engine.dependency_tracker.formula_owner_dependencies:
        dependencies = index.resolve(reference, tsce.FormulaOwnerDependenciesArchive)
        if dependencies.owner_kind != tableOwnerKind:
            continue
        if not dependencies.HasField("formula_owner"):
            continue
        entries[dependencies.formula_owner.identifier] = TableOwner(
            identifier=reference.identifier, dependencies=dependencies
        )
    return entries


def readOwnerUuid(uid: tsp.UUID) -> str:
    """Return a table's owner uid as the hexadecimal a formula names it by.

    A formula spells the identity as four 32-bit words and the owner entry spells
    it as two 64-bit halves, low half first. The two are the same value, matched
    across `20-formula-shapes` on 2026-09-08, and this is the only conversion
    between them on the read path.
    """
    words = (
        uid.lower & wordMask,
        uid.lower >> wordBits,
        uid.upper & wordMask,
        uid.upper >> wordBits,
    )
    return "".join(f"{word:08x}" for word in words)


def readTableIdentities(index: ArchiveIndex) -> dict[int, str]:
    """Return each table's formula identity, keyed by its `TST.TableInfoArchive`."""
    return {
        identifier: readOwnerUuid(owner.dependencies.formula_owner_uid)
        for identifier, owner in readTableOwnerEntries(
            index, findCalculationEngine(index)
        ).items()
    }


def findOwnerEntry(
    entries: dict[int, TableOwner],
    identifier: int,
    name: str,
) -> TableOwner:
    """Return one table's dependency entry, or refuse naming the table."""
    entry = entries.get(identifier)
    if entry is None:
        raise WriteError(
            f"{name!r} has no calculation-engine owner entry, so neither its merges "
            "nor its edited cells can be written. Every table in the documents "
            "has one."
        )
    return entry


def readTableOwnerIds(
    index: ArchiveIndex, engine: tsce.CalculationEngineArchive
) -> dict[int, int]:
    """Return each table's internal owner id, keyed by its own archive."""
    return {
        identifier: owner.dependencies.internal_formula_owner_id
        for identifier, owner in readTableOwnerEntries(index, engine).items()
    }


__all__ = [
    "TableOwner",
    "findCalculationEngine",
    "findOwnerEntry",
    "readOwnerUuid",
    "readTableIdentities",
    "readTableOwnerEntries",
    "readTableOwnerIds",
    "tableOwnerKind",
]
