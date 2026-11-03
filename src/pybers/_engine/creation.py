#!/usr/bin/env python3
"""\
Create the calculation engine a document's first table registers its owner in.

A document holding no table holds no engine, as a created one does, and Numbers builds
one on save. A table pybers adds registers an owner, so the engine is created first: a
dependency tracker holding no owner, the dirty list a recalculation request writes, and
the document root naming it. Numbers builds every owner beside the table's own.
Measured 2026-11-02 in findings-10-creation.md.

UPDATES
2026-11-02  Written for PYB-261.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/02"

from .._generated import TNArchives_pb2 as tn
from .._generated import TSCEArchives_pb2 as tsce
from .._persistence.index import findRootIdentifier
from .._persistence.metadata import PackageRegistry, composeArchive

engineLocator: str = "CalculationEngine"


def createCalculationEngine(registry: PackageRegistry) -> int:
    """Create an engine holding no owner, name it from the root, and return its id."""
    index = registry.index
    engineId = registry.identifierAllocate()
    dirtyId = registry.identifierAllocate()
    engine = tsce.CalculationEngineArchive()
    engine.dependency_tracker.SetInParent()
    engine.refs_to_dirty.identifier = dirtyId
    dirty = tsce.ReferencesToDirtyArchive()
    registry.componentAdd(composeArchive(engineId, engine), engineLocator, engine)
    registry.archiveAdd(engineId, composeArchive(dirtyId, dirty), dirty)

    rootId = findRootIdentifier(index)
    root = index.identifierResolve(rootId, tn.DocumentArchive)
    root.super.calculation_engine.identifier = engineId
    registry.archiveReplace(
        rootId, root, [*registry.strongReferencesOf(rootId), engineId]
    )
    return engineId


__all__ = ["createCalculationEngine", "engineLocator"]
