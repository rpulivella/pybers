#!/usr/bin/env python3
"""\
Every reference reads back from the text it prints, and only the grammar writes it.

A reference printed by one reader and read by another drifted once: `document.table`
refused the `Sheet 1::Table 1` its own refusal offered. Each reference type here
round-trips through its own `parse` and through the resolver over names holding every
special character, and the source is scanned for any other module writing reference
text itself.

UPDATES
2026-11-18  Written for PYB-267.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/18"

import ast
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

import pybers
import pybers.addressing
from pybers import CellRange, CellReference, SheetReference, TableReference
from pybers.addressing.text import referenceSeparator, specialCharacters

pybersDirectory: Path = Path(pybers.__file__).resolve().parent
# The grammar, and the selector parser reading `::` as its combinator.
separatorOwners: frozenset[str] = frozenset({
    "addressing/text.py", "selection/selector.py",
})
# Numbers' formula text, a grammar of its own that pybers reads as Numbers writes it.
formulaGrammar: frozenset[str] = frozenset({"formula/syntax.py"})
splittingMethods: frozenset[str] = frozenset({
    "split", "rsplit", "partition", "rpartition", "join",
})

adversarialNames: tuple[str, ...] = (
    "Plain", "Budget, draft*", "a::b", "Q3: plan", " leading", "trailing ",
    "back\\slash", "[x](y)?", ":::", "\\",
    *(f"one{character}" for character in specialCharacters),
)
sheetName, tableName = "Budget, draft*", "a::b"

builders: dict[type, Callable[[str], object]] = {
    SheetReference: SheetReference,
    TableReference: lambda name: TableReference(
        sheet=SheetReference(sheetName), name=name
    ),
    CellReference: lambda name: CellReference(
        2, 3, colAbsolute=True,
        table=TableReference(sheet=SheetReference(name), name=tableName),
    ),
    CellRange: lambda name: replace(
        CellRange.parse("B2:$D9"),
        table=TableReference(sheet=SheetReference(sheetName), name=name),
    ),
}


def listReferenceTypes() -> set[type]:
    """Return every type `pybers.addressing` exports that names a sheet or a table."""
    exported = (getattr(pybers.addressing, name) for name in pybers.addressing.__all__)
    return {
        each for each in exported
        if isinstance(each, type) and hasattr(each, "parse")
        and bool(
            {"name", "sheet", "table"} & set(getattr(each, "__dataclass_fields__", {}))
        )
    }


def testEveryReferenceTypeNamingAPartIsHeldToItsRoundTrip() -> None:
    assert listReferenceTypes() == set(builders)


@pytest.mark.parametrize("name", adversarialNames)
@pytest.mark.parametrize("kind", list(builders), ids=lambda kind: kind.__name__)
def testAReferenceParsesBackFromTheTextItPrints(kind: type, name: str) -> None:
    reference = builders[kind](name)
    assert kind.parse(str(reference)) == reference  # type: ignore[attr-defined]


@pytest.fixture
def document() -> pybers.Document:
    """Return a document whose sheets and tables carry every special character."""
    created = pybers.create("en_US")
    for name in adversarialNames:
        created.sheetAdd(name).tableAdd(name, rows=2, cols=2)
    return created


def testTheResolverSelectsExactlyWhatEachPrintedReferenceNames(
    document: pybers.Document,
) -> None:
    for sheet in document.sheets:
        for table in sheet.tables:
            for reference in (
                SheetReference(sheet.name), table.reference, table.cell("B2").reference,
            ):
                assert document.select(str(reference)) == (reference,)


def testTheTypedLookupsReachWhatEachPrintedReferenceNames(
    document: pybers.Document,
) -> None:
    for sheet in document.sheets:
        assert document.sheet(str(SheetReference(sheet.name))) is sheet
        for table in sheet.tables:
            assert document.table(str(table.reference)) is table
            assert sheet.table(str(TableReference(name=table.name))) is table


def listSourceFiles() -> list[Path]:
    """Return every library module, the generated protobuf left out."""
    return sorted(
        path for path in pybersDirectory.rglob("*.py")
        if "_generated" not in path.relative_to(pybersDirectory).parts
    )


def findReferenceTextWritten(path: Path) -> list[str]:
    """Return each place a module writes or splits reference text itself."""
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Name) and node.id == "referenceSeparator":
            found.append(f"line {node.lineno} uses referenceSeparator")
        if isinstance(node, ast.Constant) and node.value == referenceSeparator:
            found.append(f"line {node.lineno} holds a `::` of its own")
        if isinstance(node, ast.JoinedStr):
            pieces = node.values
            for index, piece in enumerate(pieces):
                if not isinstance(piece, ast.Constant) or not isinstance(
                    piece.value, str
                ):
                    continue
                joinsBefore = index > 0 and piece.value.startswith(referenceSeparator)
                joinsAfter = (
                    index < len(pieces) - 1 and piece.value.endswith(referenceSeparator)
                )
                if joinsBefore or joinsAfter:
                    found.append(f"line {node.lineno} joins names with `::`")
        if (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in splittingMethods
            and any(
                isinstance(each, ast.Constant) and each.value == referenceSeparator
                for each in (node.func.value, *node.args)
            )
        ):
            found.append(f"line {node.lineno} calls {node.func.attr} on `::`")
    return found


@pytest.mark.parametrize(
    "path", listSourceFiles(), ids=lambda path: str(path.relative_to(pybersDirectory))
)
def testOnlyTheGrammarWritesOrSplitsReferenceText(path: Path) -> None:
    relative = path.relative_to(pybersDirectory).as_posix()
    if relative in separatorOwners | formulaGrammar:
        return
    assert findReferenceTextWritten(path) == []


def testTheScanFindsEachWayAModuleWritesReferenceText(tmp_path: Path) -> None:
    module = tmp_path / "cheat.py"
    module.write_text(
        'joined = f"{sheet}::{table}"\n'
        "split = text.split('::')\n"
        'named = f"{sheet}{referenceSeparator}{table}"\n'
        'separator = "::"\n'
    )
    flagged = {each.split()[1] for each in findReferenceTextWritten(module)}
    assert flagged == {"1", "2", "3", "4"}
