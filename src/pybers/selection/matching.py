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
2026-11-24  Placing components, comparing names and meeting conditions moved to
            `resolver`, which the typefaces' resolver shares, for PYB-315.
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-18  A typed lookup parses a reference rather than one literal name, and a
            refusal quotes reference text verbatim, for PYB-267.
2026-11-17  `findBlockTarget`, the one block a border is drawn on, for PYB-266.
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

from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import partial
from typing import NoReturn

from pybers.addressing.ranges import CellRange, SelectionMatch
from pybers.addressing.reference import (
    CellAddress,
    CellReference,
    SheetReference,
    TableReference,
    cellPattern,
)
from pybers.addressing.text import (
    ReferenceError,
    escapeSelectorName,
    quoteReferenceText,
    readEscapedText,
)
from pybers.document.sheets import Document, SelectionError, Sheet
from pybers.errors import (
    composeRefusal,
    composeTextRefusal,
    nothingWritten,
)
from pybers.selection.conditions import (
    documentScheme,
    matchPseudoClass,
    positionNames,
)
from pybers.selection.resolver import (
    listPresent,
    matchConditions,
    matchName,
    placeComponents,
    quoteChoices,
    refuseExactMiss,
)
from pybers.selection.scheme import SelectorNameMatch
from pybers.selection.selector import (
    SelectorComponent,
    SelectorError,
    SelectorGroup,
    SelectorLike,
    toSelector,
)
from pybers.table.bounds import findCellsMiss
from pybers.table.cell import CellSkip
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


def selectNamed[NamedT: Sheet | Table](
    items: Sequence[NamedT], component: SelectorComponent | None,
    nameMatch: SelectorNameMatch,
) -> list[NamedT]:
    """Return the items a component matches, in their order."""
    return [item for item in items if matchName(component, item.name, nameMatch)]


def readCellsComponent(
    component: SelectorComponent, group: SelectorGroup
) -> CellAddress | CellRange | None:
    """Return the cell or range a cells component selects, None for any cell."""
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
        raise SelectorError(composeTextRefusal(
            written, where, "is not a cell, a range, a column or a row",
            "Write it as `B3`, `B2:D9`, `B` or `3`, counting rows from one",
        )) from exc


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
        merge = table.mergeFind(address) if table.mergeRanges else None
        if merge is not None and merge.anchor != address:
            continue
        if any(
            each == address if isinstance(each, CellAddress) else each.covers(address)
            for each in exclusions
        ):
            continue
        cell = cells.get(address)
        if matchConditions(
            group.conditions, documentScheme, cell,
            partial(matchPseudoClass, table=table, address=address, cell=cell),
        ):
            found.append(address)
    return found


def matchCells(
    tables: Sequence[tuple[Sheet | None, Table]],
    component: SelectorComponent | None,
    group: SelectorGroup,
) -> list[PartMatch]:
    """Return what a cells component and a group's conditions match in each table."""
    selected = None if component is None else readCellsComponent(component, group)
    exclusions = [] if component is None else [
        found for each in component.exclusions
        if (found := readCellsComponent(SelectorComponent(each), group)) is not None
    ]
    expand = bool(group.conditions or exclusions)
    matches: list[PartMatch] = []
    misses: list[str] = []
    for sheet, table in tables:
        extent = table.extent
        if selected is None:
            if extent is None:
                continue
            area: CellRange | CellAddress = extent
        else:
            miss = findCellsMiss(table, selected)
            if miss is not None:
                misses.append(miss)
                continue
            area = selected
        if not expand:
            matches.append(PartMatch(sheet, table, area))
            continue
        assert extent is not None
        bounded = (
            CellRange.fromReferences(area, area) if isinstance(area, CellAddress)
            else area.resolve(extent)
        )
        matches += [
            PartMatch(sheet, table, address)
            for address in listCells(table, bounded, group, exclusions)
        ]
    if selected is not None and misses and len(misses) == len(tables):
        if len(misses) == 1:
            raise ReferenceError(misses[0])
        raise ReferenceError(composeRefusal(
            f"`{selected}`", f"is outside each of the {len(tables)} tables selected"
        ))
    return matches


def formatTablesPlace(
    owner: Document | Sheet, component: SelectorComponent | None, sheets: list[Sheet]
) -> str:
    """Return where a refusal says tables were looked for: a sheet or the document."""
    if len(sheets) == 1 and (isinstance(owner, Sheet) or (
        component is not None and component.exact
    )):
        return quoteReferenceText(str(SheetReference(sheets[0].name)))
    if component is None or component.pattern in ("", "*"):
        return "this document"
    return "the sheets selected"


def matchGroup(owner: SelectionOwner, group: SelectorGroup) -> list[PartMatch]:
    """Return what one group matches within an owner, in the owner's order."""
    placed, depth = placeComponents(
        group, positionNames, findPositions(owner), type(owner).__name__.lower()
    )
    if isinstance(owner, Table):
        return matchCells([(owner.sheet, owner)], placed[2], group)
    if isinstance(owner, Sheet):
        sheets = [owner]
    else:
        sheets = selectNamed(owner.sheets, placed[0], SelectorNameMatch.EXACT)
        if not sheets:
            refuseExactMiss(
                placed[0], "sheet", "this document", listPresent(
                    "sheet", [str(SheetReference(each.name)) for each in owner.sheets]
                ),
            )
        if depth == 0:
            return [PartMatch(sheet) for sheet in sheets]
    tables = [
        (sheet, table) for sheet in sheets
        for table in selectNamed(sheet.tables, placed[1], SelectorNameMatch.CASELESS)
    ]
    if sheets and not tables:
        within = formatTablesPlace(owner, placed[0], sheets)
        refuseExactMiss(
            placed[1], "table", within, listPresent("table", [
                str(TableReference(
                    sheet=None if len(sheets) == 1 else SheetReference(sheet.name),
                    name=each.name,
                ))
                for sheet in sheets for each in sheet.tables
            ]),
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
    raise SelectionError(composeRefusal(
        quoteReferenceText(str(SheetReference(sheets[0].name))),
        f"names {len(sheets)} sheets in this document, at positions {positions}",
        remedy,
    ))


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
                    "Rename one, since a selector reaches a sheet by its name",
                )
    return list(matches.values())


def selectWithin(
    owner: SelectionOwner, selector: SelectorLike
) -> tuple[SelectionMatch, ...]:
    """Return what a selector matches within an owner, as references."""
    return tuple(part.reference for part in selectParts(owner, selector))


def findSheet(document: Document, name: str | SheetReference | None) -> Sheet:
    """Return the one sheet a reference names, or the only sheet when none is named."""
    if name is None:
        sheets = document.sheets
    else:
        reference = SheetReference.parse(name) if isinstance(name, str) else name
        group = SelectorGroup((SelectorComponent(escapeSelectorName(reference.name)),))
        sheets = [part.sheet for part in matchGroup(document, group)
                  if part.sheet is not None]
    if len(sheets) == 1:
        return sheets[0]
    if name is None and not sheets:
        raise SelectionError(
            composeRefusal("This document", "holds no sheet", "Add one first")
        )
    if name is None:
        present = [str(SheetReference(each.name)) for each in document.sheets]
        raise SelectionError(composeRefusal(
            "This document", f"holds {len(sheets)} sheets, and no sheet was named",
            f"Name one of the sheets, {quoteChoices(present)}",
        ))
    refuseSharedSheetName(document, sheets, "Reach one by its position instead")


def buildTableGroup(
    owner: Document | Sheet, reference: TableReference
) -> SelectorGroup:
    """Return the one-group selection a table reference makes within an owner.

    A reference naming its sheet, given to a sheet, names that sheet or is refused.
    """
    name = SelectorComponent(escapeSelectorName(reference.name))
    if isinstance(owner, Sheet):
        if reference.sheet is not None and reference.sheet.name != owner.name:
            raise SelectionError(composeRefusal(
                quoteReferenceText(str(reference)),
                f"selects a table on sheet {quoteReferenceText(str(reference.sheet))}, "
                "and this is sheet "
                f"{quoteReferenceText(str(SheetReference(owner.name)))}",
                f"Look it up on {quoteReferenceText(str(reference.sheet))} instead",
            ))
        return SelectorGroup((name,))
    if reference.sheet is None:
        return SelectorGroup((SelectorComponent(""), name))
    sheet = SelectorComponent(escapeSelectorName(reference.sheet.name))
    return SelectorGroup((sheet, name))


def findTable(owner: Document | Sheet, name: str | TableReference | None) -> Table:
    """Return the one table a reference names, or the only table when none is named."""
    if name is None:
        depth = 2 if isinstance(owner, Document) else 1
        group = SelectorGroup(tuple(SelectorComponent("") for _ in range(depth)))
    else:
        reference = TableReference.parse(name) if isinstance(name, str) else name
        group = buildTableGroup(owner, reference)
    found = [part for part in matchGroup(owner, group) if part.table is not None]
    if len(found) == 1 and found[0].table is not None:
        return found[0].table
    qualified = [
        str(TableReference(name=part.table.name)) if isinstance(owner, Sheet)
        else str(part.reference)
        for part in found if part.table is not None
    ]
    within = (
        "This document" if isinstance(owner, Document)
        else quoteReferenceText(str(SheetReference(owner.name)))
    )
    if name is None:
        if not found:
            raise SelectionError(
                composeRefusal(within, "holds no table", "Add one first")
            )
        raise SelectionError(composeRefusal(
            within, f"holds {len(found)} tables, and no table was named",
            f"Name one of the tables, {quoteChoices(qualified)}",
        ))
    raise SelectionError(composeRefusal(
        quoteReferenceText(str(name)), "selects a table on more than one sheet",
        f"Name its sheet as well, as {quoteChoices(qualified)} do",
    ))


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
            skipped.append(CellSkip(part.reference, f"is a {kind}, not a cell"))
            continue
        addresses = (
            [cells] if isinstance(cells, CellAddress)
            else [] if table.extent is None
            else [each for each in cells.resolve(table.extent)
                  if table.isAddressable(each)]
        )
        for address in addresses:
            targets.setdefault((id(table), address), (table, address))
    return list(targets.values()), skipped


def findBlockTarget(
    document: Document, selector: SelectorLike, action: str
) -> tuple[Table, CellRange]:
    """Return the one bounded block of one table a selector selects, or refuse.

    Refused before anything is written, listing what the selector matched.
    """
    parts = selectParts(document, selector)
    if len(parts) != 1 or parts[0].table is None or parts[0].cells is None:
        raise SelectionError(composeRefusal(
            f"`{selector}`",
            f"matches {formatMatches([part.reference for part in parts])}, and a "
            f"{action} is drawn on one block of cells in one table",
            "Select one block, such as `Q3::B2:D9`", nothingWritten,
        ))
    table, cells = parts[0].table, parts[0].cells
    block = (
        CellRange.fromReferences(cells, cells) if isinstance(cells, CellAddress)
        else cells
    )
    return table, table._rangeSingle(block, action)


def findExtendTarget(
    document: Document, selector: SelectorLike
) -> tuple[Table, CellAddress]:
    """Return the one table and address a write growing its table writes.

    The selector selects one cell in one table, which may lie past the table's end.
    """
    found = toSelector(selector)
    group = found.groups[0]
    placed, depth = placeComponents(
        group, positionNames, len(positionNames), "document"
    )
    component = placed[2]
    address = (
        None if len(found.groups) != 1 or group.conditions or depth != 2
        or component is None or component.exclusions
        else readCellsComponent(component, group)
    )
    if not isinstance(address, CellAddress):
        raise SelectionError(composeRefusal(
            f"`{found}`", "selects more than one cell, and growing a table to hold "
            "a cell takes one", "Select one cell, such as `Sheet 1::Table 1::B30`",
            nothingWritten,
        ))
    tables = matchGroup(document, SelectorGroup(
        tuple(SelectorComponent("") if each is None else each for each in placed[:2])
    ))
    table = tables[0].table if len(tables) == 1 else None
    if table is None:
        matched = formatMatches([each.reference for each in tables])
        raise SelectionError(composeRefusal(
            f"`{found}`", f"matches {matched}, and growing a table to hold a cell "
            "grows one table", "Select one table", nothingWritten,
        ))
    if not table.isAddressable(address):
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
