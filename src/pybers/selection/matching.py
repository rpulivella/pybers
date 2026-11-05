#!/usr/bin/env python3
"""\
The one resolver: what a selector matches in a document, a sheet or a table.

Each owner reads a selector relative to itself, as a path is read: a document's
positions are sheet, table and cells, a sheet's table and cells, and a table's cells
alone. The resolver walks the sheets, tables and cells a selector reaches, and parses
its text on each call; `docs/findings/findings-13-selection.md` measures that this
simple form is fast enough. The typed lookups, `document.sheet`, `document.table`,
`sheet.table` and `table.cell`, are one-group selections through it.

A table name matches without regard to case and a sheet name with it. Numbers will
not create two table names differing only in case on one sheet, and enforces nothing
about sheet names, so folding them would invent a collision the file does not have.

UPDATES
2026-11-03  Written for PYB-223.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/03"

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import NoReturn

from pybers.addressing.ranges import CellRange, SelectionMatch
from pybers.addressing.reference import (
    CellAddress,
    CellReference,
    ReferenceError,
    SheetReference,
    TableReference,
    cellPattern,
    tableNameSeparator,
)
from pybers.document.sheets import Document, SelectionError, Sheet, listPresent
from pybers.selection.conditions import matchPseudoClass, selectorAttributes
from pybers.selection.selector import (
    SelectorAttribute,
    SelectorComponent,
    SelectorCondition,
    SelectorError,
    SelectorGroup,
    SelectorLike,
    SelectorNegation,
    SelectorPseudoClass,
    escapeMarker,
    formatPlace,
    positionNames,
    quoteSelectorName,
    readEscapedText,
    toSelector,
)
from pybers.table.bounds import findCellsMiss
from pybers.table.cell import Cell, CellSkip
from pybers.table.cells import Table

type SelectionOwner = Document | Sheet | Table

# The most matches a refusal lists before counting the rest.
listedLimit: int = 10


@dataclass(frozen=True, slots=True)
class PartMatch:
    """One sheet, table, range or cell a group matched, as the model holds it."""

    sheet: Sheet | None
    table: Table | None = None
    cells: CellAddress | CellRange | None = None

    @property
    def reference(self) -> SelectionMatch:
        """Return how to point at this from anywhere in its document."""
        sheetReference = None if self.sheet is None else SheetReference(self.sheet.name)
        if self.table is None:
            assert sheetReference is not None
            return sheetReference
        tableReference = TableReference(sheet=sheetReference, name=self.table.name)
        if self.cells is None:
            return tableReference
        if isinstance(self.cells, CellAddress):
            return CellReference(
                self.cells.row, self.cells.col, table=tableReference
            )
        return replace(self.cells, table=tableReference)


def formatMatches(matches: Sequence[SelectionMatch]) -> str:
    """Return matches as a list of their written forms, the rest counted."""
    if not matches:
        return "nothing"
    shown = ", ".join(f"`{each}`" for each in matches[:listedLimit])
    rest = len(matches) - listedLimit
    return shown if rest <= 0 else f"{shown} and {rest} more"


def findPositions(owner: SelectionOwner) -> int:
    """Return how many positions a selector given to an owner fills."""
    if isinstance(owner, Document):
        return len(positionNames)
    return 2 if isinstance(owner, Sheet) else 1


def placeComponents(
    group: SelectorGroup, owner: SelectionOwner
) -> tuple[list[SelectorComponent | None], int]:
    """Return a component for each of the three positions, and the deepest reached."""
    positions = findPositions(owner)
    first = len(positionNames) - positions
    components = group.components
    if len(components) > positions:
        kind = type(owner).__name__.lower()
        reached = positionNames[first:]
        raise SelectorError(
            f"`{group}` names {len(components)} positions, and a selector given to a "
            f"{kind} names at most {positions}: {', '.join(reached)}. Select from "
            "the document to name more."
        )
    placed: list[SelectorComponent | None] = [None] * len(positionNames)
    last = len(positionNames) - 1
    if group.fromRight:
        start = len(positionNames) - len(components)
        depth = last
    else:
        start = first
        depth = last if group.conditions else first + len(components) - 1
    for index, component in enumerate(components):
        placed[start + index] = component
    return placed, depth


def buildPattern(pattern: str, foldCase: bool) -> re.Pattern[str]:
    """Return a written name pattern as an expression, `*` and `?` its wildcards."""
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == escapeMarker and index + 1 < len(pattern):
            parts.append(re.escape(pattern[index + 1]))
            index += 2
            continue
        parts.append({"*": ".*", "?": "."}.get(character, re.escape(character)))
        index += 1
    return re.compile("".join(parts), re.IGNORECASE if foldCase else 0)


def matchName(component: SelectorComponent | None, name: str, foldCase: bool) -> bool:
    """Report whether a name fits a component and none of its exclusions."""
    if component is None:
        return True
    if component.pattern and not buildPattern(
        component.pattern, foldCase
    ).fullmatch(name):
        return False
    return not any(
        buildPattern(each, foldCase).fullmatch(name) for each in component.exclusions
    )


def selectNamed[NamedT: Sheet | Table](
    items: Sequence[NamedT], component: SelectorComponent | None, foldCase: bool
) -> list[NamedT]:
    """Return the items a component matches, in their order."""
    return [item for item in items if matchName(component, item.name, foldCase)]


def refuseExactMiss(
    component: SelectorComponent | None, kind: str, within: str, names: list[str]
) -> None:
    """Refuse a component naming one thing exactly that nothing searched carries."""
    if component is None or not component.exact:
        return
    name = readEscapedText(component.pattern)
    raise SelectionError(
        f"No {kind} in {within} is named {name!r}. {listPresent(kind, names)}"
    )


def readCellsComponent(
    component: SelectorComponent, group: SelectorGroup
) -> CellAddress | CellRange | None:
    """Return the cell or range a cells component names, None for any cell."""
    text = readEscapedText(component.pattern)
    if text in ("", "*"):
        return None
    try:
        if cellPattern.match(text) is not None:
            return CellReference.parse(text).address
        return CellRange.parse(text)
    except ReferenceError as exc:
        written = str(group)
        where = max(written.find(component.pattern), 0)
        raise SelectorError(
            f"{formatPlace(written, where)} `{text}` is in the cells position, and is "
            "not an address, a range, a column or a row such as `B3`, `B2:D9`, `B` "
            f"or `3`. {exc}"
        ) from exc


def matchConditions(
    conditions: tuple[SelectorCondition, ...], table: Table, address: CellAddress,
    cell: Cell | None,
) -> bool:
    """Report whether a cell at an address meets every condition."""
    for condition in conditions:
        match condition:
            case SelectorAttribute(name=name, value=value):
                found = selectorAttributes[name].read(cell)
                met = found is not None if value is None else found == value
            case SelectorPseudoClass(name=name, argument=argument):
                met = matchPseudoClass(name, argument, table, address, cell)
            case SelectorNegation(alternatives=alternatives):
                met = not any(
                    matchConditions(each, table, address, cell) for each in alternatives
                )
        if not met:
            return False
    return True


def listCells(
    table: Table,
    area: CellRange,
    group: SelectorGroup,
    exclusions: list[CellAddress | CellRange],
) -> list[CellAddress]:
    """Return each cell of an area meeting a group's conditions, a merge once."""
    found = []
    cells = table.cells
    for address in area:
        merge = table.mergeCovering(address) if table.mergeRanges else None
        if merge is not None and merge.anchor != address:
            continue
        if any(
            each == address if isinstance(each, CellAddress) else each.covers(address)
            for each in exclusions
        ):
            continue
        if matchConditions(group.conditions, table, address, cells.get(address)):
            found.append(address)
    return found


def matchCells(
    tables: Sequence[tuple[Sheet | None, Table]],
    component: SelectorComponent | None,
    group: SelectorGroup,
) -> list[PartMatch]:
    """Return what a cells component and a group's conditions match in each table."""
    named = None if component is None else readCellsComponent(component, group)
    exclusions = [] if component is None else [
        found for each in component.exclusions
        if (found := readCellsComponent(SelectorComponent(each), group)) is not None
    ]
    expand = bool(group.conditions or exclusions)
    matches: list[PartMatch] = []
    misses: list[str] = []
    for sheet, table in tables:
        extent = table.extent
        if named is None:
            if extent is None:
                continue
            area: CellRange | CellAddress = extent
        else:
            miss = findCellsMiss(table, named)
            if miss is not None:
                misses.append(miss)
                continue
            area = named
        if not expand:
            matches.append(PartMatch(sheet, table, area))
            continue
        assert extent is not None
        bounded = (
            CellRange.fromReferences(area, area) if isinstance(area, CellAddress)
            else area.boundedBy(extent)
        )
        matches += [
            PartMatch(sheet, table, address)
            for address in listCells(table, bounded, group, exclusions)
        ]
    if named is not None and misses and len(misses) == len(tables):
        if len(misses) == 1:
            raise ReferenceError(misses[0])
        raise ReferenceError(
            f"{named} names no cell in the tables selected. {' '.join(misses)}"
        )
    return matches


def formatTablesPlace(
    owner: Document | Sheet, component: SelectorComponent | None, sheets: list[Sheet]
) -> str:
    """Return where a refusal says tables were looked for: a sheet or the document."""
    if len(sheets) == 1 and (isinstance(owner, Sheet) or (
        component is not None and component.exact
    )):
        return repr(sheets[0].name)
    if component is None or component.pattern in ("", "*"):
        return "this document"
    return "the sheets selected"


def matchGroup(owner: SelectionOwner, group: SelectorGroup) -> list[PartMatch]:
    """Return what one group matches within an owner, in the owner's order."""
    placed, depth = placeComponents(group, owner)
    if isinstance(owner, Table):
        return matchCells([(owner.sheet, owner)], placed[2], group)
    if isinstance(owner, Sheet):
        sheets = [owner]
    else:
        sheets = selectNamed(owner.sheets, placed[0], foldCase=False)
        if not sheets:
            refuseExactMiss(
                placed[0], "sheet", "this document",
                [each.name for each in owner.sheets],
            )
        if depth == 0:
            return [PartMatch(sheet) for sheet in sheets]
    tables = [
        (sheet, table) for sheet in sheets
        for table in selectNamed(sheet.tables, placed[1], foldCase=True)
    ]
    if sheets and not tables:
        within = formatTablesPlace(owner, placed[0], sheets)
        refuseExactMiss(
            placed[1], "table", within,
            [
                each.name if len(sheets) == 1
                else f"{sheet.name}{tableNameSeparator}{each.name}"
                for sheet in sheets for each in sheet.tables
            ],
        )
    if depth == 1:
        return [PartMatch(sheet, table) for sheet, table in tables]
    return matchCells(tables, placed[2], group)


def refuseSharedSheetName(
    document: Document, sheets: list[Sheet], remedy: str
) -> NoReturn:
    """Refuse a name several sheets carry, giving each one's position, then a remedy."""
    positions = ", ".join(
        str(position) for position, each in enumerate(document.sheets, start=1)
        if any(each is sheet for sheet in sheets)
    )
    raise SelectionError(
        f"{len(sheets)} sheets in this document are named {sheets[0].name!r}, at "
        f"positions {positions}. {remedy}"
    )


def selectParts(owner: SelectionOwner, selector: SelectorLike) -> list[PartMatch]:
    """Return every part a selector matches within an owner, each once, in order.

    Two parts a reference cannot tell apart, on two sheets of one name, are refused.
    """
    found = toSelector(selector)
    matches: dict[SelectionMatch, PartMatch] = {}
    for group in found.groups:
        for part in matchGroup(owner, group):
            held = matches.setdefault(part.reference, part)
            if held.sheet is not part.sheet and isinstance(owner, Document):
                assert held.sheet is not None and part.sheet is not None
                refuseSharedSheetName(
                    owner, [held.sheet, part.sheet],
                    "A selector reaches a sheet by its name, so rename one.",
                )
    return list(matches.values())


def selectWithin(
    owner: SelectionOwner, selector: SelectorLike
) -> tuple[SelectionMatch, ...]:
    """Return what a selector matches within an owner, as references."""
    return tuple(part.reference for part in selectParts(owner, selector))


def buildNameGroup(name: str, fromRight: bool = False, depth: int = 1) -> SelectorGroup:
    """Return a group naming one thing literally, at the position `depth` counts."""
    components = (
        *(SelectorComponent("") for _ in range(depth - 1)),
        SelectorComponent(quoteSelectorName(name)),
    )
    return SelectorGroup(components, fromRight)


def findSheet(document: Document, name: str | None) -> Sheet:
    """Return the one sheet a name names, or the only sheet when none is named."""
    if name is None:
        sheets = document.sheets
    else:
        sheets = [part.sheet for part in matchGroup(document, buildNameGroup(name))
                  if part.sheet is not None]
    if len(sheets) == 1:
        return sheets[0]
    if name is None:
        raise SelectionError(
            f"No sheet was named, and this document holds {len(sheets)}. Name one. "
            f"{listPresent('sheet', [each.name for each in document.sheets])}"
        )
    refuseSharedSheetName(document, sheets, "Reach one by position instead.")


def findTable(owner: Document | Sheet, name: str | TableReference | None) -> Table:
    """Return the one table a name names, or the only table when none is named."""
    depth = 2 if isinstance(owner, Document) else 1
    if isinstance(name, TableReference) and name.sheet is not None:
        group = SelectorGroup((
            SelectorComponent(quoteSelectorName(name.sheet.name)),
            SelectorComponent(quoteSelectorName(name.name)),
        ))
    elif name is None:
        group = SelectorGroup(tuple(SelectorComponent("") for _ in range(depth)))
    else:
        written = name.name if isinstance(name, TableReference) else name
        group = buildNameGroup(written, depth=depth)
    found = [part for part in matchGroup(owner, group) if part.table is not None]
    if len(found) == 1 and found[0].table is not None:
        return found[0].table
    qualified = [
        part.table.name if isinstance(owner, Sheet) else str(part.reference)
        for part in found if part.table is not None
    ]
    within = "this document" if isinstance(owner, Document) else repr(owner.name)
    if name is None:
        if not found:
            raise SelectionError(f"No table was named, and {within} holds none.")
        raise SelectionError(
            f"No table was named, and {within} holds {len(found)}. Name one. "
            f"{listPresent('table', qualified)}"
        )
    shared = ", ".join(repr(each) for each in qualified)
    raise SelectionError(
        f"{str(name)!r} names a table on more than one sheet. Name its sheet as "
        f"well: {shared}."
    )


def findCellTargets(
    document: Document, selector: SelectorLike
) -> tuple[list[tuple[Table, CellAddress]], list[CellSkip]]:
    """Return each cell a write to every matched cell writes, once, and each skip.

    A range is each cell it covers, a merge at its anchor.
    """
    targets: dict[tuple[int, CellAddress], tuple[Table, CellAddress]] = {}
    skipped: list[CellSkip] = []
    for part in selectParts(document, selector):
        table, cells = part.table, part.cells
        if table is None or cells is None:
            kind = "sheet" if table is None else "table"
            skipped.append(CellSkip(
                part.reference, f"{part.reference} is a {kind}, and a value is "
                "written into cells.",
            ))
            continue
        addresses = (
            [cells] if isinstance(cells, CellAddress)
            else [] if table.extent is None
            else [each for each in cells.boundedBy(table.extent)
                  if table.addressable(each)]
        )
        for address in addresses:
            targets.setdefault((id(table), address), (table, address))
    return list(targets.values()), skipped


def findExtendTarget(
    document: Document, selector: SelectorLike
) -> tuple[Table, CellAddress]:
    """Return the one table and address a write growing its table writes.

    The selector names one address in one table, which may lie past the table's end.
    """
    found = toSelector(selector)
    group = found.groups[0]
    placed, depth = placeComponents(group, document)
    component = placed[2]
    address = (
        None if len(found.groups) != 1 or group.conditions or depth != 2
        or component is None or component.exclusions
        else readCellsComponent(component, group)
    )
    if not isinstance(address, CellAddress):
        raise SelectionError(
            f"`{found}` names more than one address, and growing a table to hold "
            "a cell takes one, such as `Sheet 1::Table 1::B30`."
        )
    tables = matchGroup(document, SelectorGroup(
        tuple(SelectorComponent("") if each is None else each for each in placed[:2])
    ))
    table = tables[0].table if len(tables) == 1 else None
    if table is None:
        raise SelectionError(
            f"`{found}` matches {len(tables)} tables, and growing a table to hold "
            f"a cell grows one: {formatMatches([each.reference for each in tables])}."
        )
    if not table.addressable(address):
        raise ReferenceError(str(findCellsMiss(table, address)))
    return table, address


__all__ = [
    "PartMatch",
    "SelectionMatch",
    "SelectionOwner",
    "formatMatches",
    "findCellTargets",
    "findExtendTarget",
    "findSheet",
    "findTable",
    "selectParts",
    "selectWithin",
]
