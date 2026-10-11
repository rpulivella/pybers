#!/usr/bin/env python3
"""\
Every concern of the write path sits in one module of its own, checked from source.

A module growing past its limit, or a writer reaching past the one entry point it
is given, reads correctly and saves correctly, so no behavioral test notices. These
read the source instead.

UPDATES
2026-10-09  Nested sequences flattened by comprehension unpacking, for PYB-181.
2026-09-22  Written for PYB-113.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/22"

import ast
from pathlib import Path

import pytest

from pybers._generated import TSCEArchives_pb2 as tsce
from pybers._persistence.types import (
    ArchiveTypeError,
    archiveTypes,
    findArchiveTypeId,
)

packageRoot: Path = Path(__file__).resolve().parent.parent / "src" / "pybers"
tableModuleLimit: int = 600
engineModuleLimit: int = 300


def listImportedModules(path: Path) -> set[str]:
    """Return every module a file imports from, resolved to its dotted name."""
    package = ".".join(path.relative_to(packageRoot.parent).with_suffix("").parts[:-1])
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            base = package.rsplit(".", node.level - 1)[0] if node.level else ""
            module = node.module or ""
            found.add(f"{base}.{module}".strip(".") if node.level else module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def countLines(path: Path) -> int:
    """Return how many lines a file holds."""
    return len(path.read_text().splitlines())


def testTheDocumentWriterReachesTheTableFeatureThroughOneModule() -> None:
    """PYB-113 AC 1.ii."""
    imported = listImportedModules(packageRoot / "document" / "_write.py")

    private = {module for module in imported if module.startswith("pybers.table._")}

    assert private == {"pybers.table._write"}


def testTheDocumentWriterTranslatesNoFormula() -> None:
    """PYB-113 AC 1.iv."""
    imported = listImportedModules(packageRoot / "document" / "_write.py")

    assert not {module for module in imported if module.startswith("pybers.formula")}


def testNoTableModuleExceedsItsLimit() -> None:
    """PYB-113 AC 1.iii."""
    oversized = {
        path.name: countLines(path)
        for path in (packageRoot / "table").glob("*.py")
        if countLines(path) > tableModuleLimit
    }

    assert oversized == {}


@pytest.mark.parametrize("module", ["_merges", "_refcounts", "_records"])
def testEachTableSaveConcernHasAModuleOfItsOwn(module: str) -> None:
    """PYB-113 AC 1.iii."""
    assert (packageRoot / "table" / f"{module}.py").is_file()


def testAStructuralEditImportsNothingFromTableCreation() -> None:
    """PYB-113 AC 2."""
    imported = listImportedModules(packageRoot / "table" / "_structure.py")

    assert "pybers.table._create" not in imported


@pytest.mark.parametrize("module", ["_create", "_structure"])
def testCreationAndAStructuralEditWriteTheUidMapTheSameWay(module: str) -> None:
    """PYB-113 AC 2."""
    tree = ast.parse((packageRoot / "table" / f"{module}.py").read_text())

    sources = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and any(alias.name == "assignUids" for alias in node.names)
    }

    assert sources == {"_lines"}


def testTheEngineIsAPackageOfSmallModules() -> None:
    """PYB-113 AC 3."""
    modules = sorted((packageRoot / "_engine").glob("*.py"))

    oversized = {
        path.name: countLines(path)
        for path in modules
        if countLines(path) > engineModuleLimit
    }

    assert not (packageRoot / "_engine.py").exists()
    assert {path.stem for path in modules} >= {
        "owners", "registration", "remapping", "recalculation"
    }
    assert oversized == {}


def listLiteralTypeIds(path: Path) -> list[str]:
    """Return each place a file spells an archive type identifier as a number."""
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.keyword) and node.arg == "type":
            if isinstance(node.value, ast.Constant):
                found.append(f"{path.name}:{node.value.lineno}")
        elif isinstance(node, ast.AnnAssign | ast.Assign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            named = any(
                isinstance(target, ast.Name) and target.id.endswith("TypeId")
                for target in targets
            )
            if named and isinstance(node.value, ast.Constant):
                found.append(f"{path.name}:{node.lineno}")
    return found


def testNoModuleSpellsATypeIdentifierOutsideTheRegistry() -> None:
    """PYB-113 AC 4."""
    found = [
        *listLiteralTypeIds(path)
        for path in sorted(packageRoot.rglob("*.py"))
        if "_generated" not in path.parts and path.name != "types.py"
    ]

    assert found == []


@pytest.mark.parametrize(
    ("typeId", "messageClass"), sorted(archiveTypes.items()), ids=str
)
def testEveryRegisteredClassFindsItsTypeIdentifier(
    typeId: int, messageClass: type
) -> None:
    """PYB-113 AC 4."""
    assert findArchiveTypeId(messageClass) == typeId


def testAClassTheRegistryDoesNotHoldIsRefusedByName() -> None:
    """PYB-113 AC 4."""
    unregistered = tsce.ASTNodeArrayArchive

    with pytest.raises(ArchiveTypeError, match="TSCE.ASTNodeArrayArchive"):
        findArchiveTypeId(unregistered)
