#!/usr/bin/env python3
"""\
Conditional highlighting carried through rows and columns added or removed.

**Numbers rewrites a rule rather than moving it**, measured 2026-09-21 across the
four `57-conditions-*` documents. A rule is a `TST.ConditionalStyleSetArchive` a
cell names by key, holding a predicate whose operands are cell references, and
three things happen to it under an edit:

- **A rule reading a cell that moves becomes a new rule**, under a new key, and
  every cell naming the old one names the new one. The old entry goes.
- **A rule reading a cell that is removed breaks, once per cell.** Six cells
  sharing one rule came out holding six identical rules at refcount 1, each
  reference written as `#REF!` carrying the lines it lost.
- **A line added takes the rules of the line it displaced**, as empty records
  naming the rule and caching no match.

Each axis of an operand follows the formula rule: locked, it holds a stored line;
unlocked, an offset from the cell the rule colors. A whole-column operand is a
column alone, and breaks with a zero identity for its row.

Private. Reached from the structural pass in `_structure` and the tile pass in
`_write`.

UPDATES
2026-09-21  Written for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/21"

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSPArchiveMessages_pb2 as tspArchive
from .._generated import TSTArchives_pb2 as tst
from .._persistence import IWAFile, chooseOffsetUnit, decodeRow
from .._persistence.cells import (
    CellRecord,
    conditionalSlot,
    findSlotValue,
    matchSlot,
    noMatch,
    patchSlotValue,
)
from .._persistence.index import ArchiveIndex, assignUuid
from .._persistence.iwa import createArchive
from .._persistence.metadata import PackageRegistry

if TYPE_CHECKING:
    # Guarded because the structural pass imports this module to plan the rules.
    from ._structure import GridMaps

# An operand that is a cell reference, and the form Numbers gives one it broke.
cellReferenceArgument: int = 4
brokenReferenceArgument: int = 9

# The empty record Numbers writes into a line added beside a highlighted one: no
# value, and the two slots above. Measured in `57-conditions-row-inserted`.
emptyRecordHeader: bytes = bytes.fromhex("050000000000000080010000")

brokenColumnSentinel: int = 32767
brokenRowSentinel: int = 2147483647
referenceNodeType: int = 36
brokenReferenceNodeType: int = 46


@dataclass
class ConditionalPlan:
    """What happens to each rule set a table holds, decided cell by cell.

    A relative operand is an offset from the cell a rule colors, so two cells
    sharing a rule can land on different rules after an edit. Each cell's result is
    worked out alone, and cells with the same result share one new entry, as the
    twelve cells of `59-conditions-relative-column-inserted` do. A broken result is
    never shared, which is how Numbers wrote every broken rule measured.
    """

    index: ArchiveIndex
    maps: GridMaps
    registry: PackageRegistry
    owners: dict[int, IWAFile]
    dataList: tst.TableDataList
    listIdentifier: int
    rowIdentities: Sequence[int]
    columnIdentities: Sequence[int]
    name: str
    rules: dict[int, tst.ConditionalStyleSetArchive] = field(default_factory=dict)
    siblings: dict[int, int] = field(default_factory=dict)
    shared: dict[tuple[int, bytes], int] = field(default_factory=dict)

    def keyFor(self, key: int, row: int, column: int) -> tuple[int, bool]:
        """Return the key the cell stored at `row` and `column` names after the edit.

        Also says whether its rule broke, since a broken rule caches no match.
        """
        rules = self.rules.get(key)
        if rules is None:
            return key, False
        outcome, changed = mapRuleSet(
            rules, row, column, self.maps,
            self.rowIdentities, self.columnIdentities, self.name,
        )
        if outcome == "same":
            return key, False
        if outcome == "broken":
            return self.entryCreate(changed, self.siblings[key]), True
        result = (key, changed.SerializeToString(deterministic=True))
        if result not in self.shared:
            self.shared[result] = self.entryCreate(changed, self.siblings[key])
        return self.shared[result], False

    def entryCreate(self, rules: tst.ConditionalStyleSetArchive, sibling: int) -> int:
        """Add a rule set to the table's list, as a new archive, and return its key."""
        info = tspArchive.ArchiveInfo()
        info.ParseFromString(self.index.archive(sibling).infoBytes)
        info.identifier = self.registry.identifierAllocate()
        del info.message_infos[1:]
        archive = createArchive(info, [rules.SerializeToString()])
        componentId = self.registry.componentOf[sibling]
        self.registry.archiveAdd(componentId, archive)
        self.owners[archive.identifier] = self.registry.componentMember(componentId)
        self.index.byIdentifier[archive.identifier] = archive
        entry = self.dataList.entries.add()
        entry.key = self.dataList.nextListID
        entry.refcount = 0
        entry.reference.identifier = archive.identifier
        self.dataList.nextListID += 1
        return int(entry.key)


def listRuleOperands(
    rules: tst.ConditionalStyleSetArchive,
) -> list[tst.FormulaPredArgArchive]:
    """Return every operand of every rule that names a cell."""
    return [
        operand
        for rule in rules.rules.rule
        for operand in (
            rule.predicate.param_value0,
            rule.predicate.param_value1,
            rule.predicate.param_value2,
        )
        if operand.arg_type == cellReferenceArgument
    ]


def listRuleFormulas(
    rules: tst.ConditionalStyleSetArchive,
) -> list[tsce.FormulaArchive]:
    """Return both copies of every rule's formula, the rule's and the pre-pivot one."""
    return [rule.predicate.formula for rule in rules.rules.rule] + [
        rule.predicate.formula for rule in rules.rules_prepivot
    ]


def mapRuleSet(
    rules: tst.ConditionalStyleSetArchive,
    row: int,
    column: int,
    maps: GridMaps,
    rowIdentities: Sequence[int],
    columnIdentities: Sequence[int],
    name: str,
) -> tuple[str, tst.ConditionalStyleSetArchive]:
    """Return what an edit does to one cell's rule set: `same`, `moved` or `broken`.

    Each axis of an operand follows the formula rule, measured across the
    `59-conditions-relative-*` documents: a locked axis holds a stored line, and
    an unlocked one an offset from the colored cell. A whole-column operand has no
    row, and a whole-row one no column.
    """
    changed = tst.ConditionalStyleSetArchive()
    changed.CopyFrom(rules)
    outcome = "same"
    movedRow, movedColumn = maps.rows.lineMap(row), maps.columns.lineMap(column)
    assert movedRow is not None and movedColumn is not None
    for operand in listRuleOperands(changed):
        reference = operand.relative_cell_ref
        axes = []
        if not reference.is_spanning_row:
            axes.append(("column", reference.preserve_column, column, movedColumn,
                         maps.columns, reference.relative_column_offset))
        if not reference.is_spanning_column:
            axes.append(("row", reference.preserve_row, row, movedRow,
                         maps.rows, reference.relative_row_offset))
        values: dict[str, int] = {}
        lost: dict[str, int] = {}
        for axis, locked, host, movedHost, lines, value in axes:
            target = value if locked else host + value
            moved = lines.lineMap(target)
            if moved is None:
                lost[axis] = target
                continue
            values[axis] = moved if locked else moved - movedHost
        if lost:
            rewriteBrokenOperand(
                changed, operand,
                findLostIdentity(reference, row, "row", lost, rowIdentities),
                findLostIdentity(reference, column, "column", lost, columnIdentities),
            )
            outcome = "broken"
            continue
        old = (reference.relative_row_offset, reference.relative_column_offset)
        new = (values.get("row", old[0]), values.get("column", old[1]))
        if new == old:
            continue
        rewriteReferenceNodes(changed, reference, new)
        # Only the axes an operand has, since a whole-column one stores no row.
        if not reference.is_spanning_column:
            reference.relative_row_offset = new[0]
        if not reference.is_spanning_row:
            reference.relative_column_offset = new[1]
        if outcome == "same":
            outcome = "moved"
    return outcome, changed


def findLostIdentity(
    reference: tsce.RelativeCellRefArchive,
    host: int,
    axis: str,
    lost: dict[str, int],
    identities: Sequence[int],
) -> int:
    """Return the identity of the line a broken operand named on one axis.

    A whole-column operand names no row, and Numbers records a zero identity for
    it, measured in `59-conditions-relative-column-a-deleted`.
    """
    spanning = (
        reference.is_spanning_column if axis == "row" else reference.is_spanning_row
    )
    if spanning:
        return 0
    if axis in lost:
        return identities[lost[axis]]
    locked = reference.preserve_row if axis == "row" else reference.preserve_column
    value = (
        reference.relative_row_offset if axis == "row"
        else reference.relative_column_offset
    )
    return identities[value if locked else host + value]


def checkReferenceNode(
    node: tsce.ASTNodeArrayArchive.ASTNodeArchive,
    reference: tsce.RelativeCellRefArchive,
) -> bool:
    """Report whether a formula node spells the operand a rule holds."""
    if node.AST_node_type != referenceNodeType:
        return False
    if not reference.is_spanning_row and (
        node.AST_column.column != reference.relative_column_offset
        or node.AST_column.absolute != reference.preserve_column
    ):
        return False
    return reference.is_spanning_column or (
        node.AST_row.row == reference.relative_row_offset
        and node.AST_row.absolute == reference.preserve_row
    )


def rewriteReferenceNodes(
    rules: tst.ConditionalStyleSetArchive,
    reference: tsce.RelativeCellRefArchive,
    moved: tuple[int, int],
) -> None:
    """Move the formula nodes spelling an operand, in both copies of the formula."""
    for formula in listRuleFormulas(rules):
        for node in formula.AST_node_array.AST_node:
            if not checkReferenceNode(node, reference):
                continue
            if not reference.is_spanning_column:
                node.AST_row.row = moved[0]
            if not reference.is_spanning_row:
                node.AST_column.column = moved[1]


def rewriteBrokenOperand(
    rules: tst.ConditionalStyleSetArchive,
    operand: tst.FormulaPredArgArchive,
    rowIdentity: int,
    columnIdentity: int,
) -> None:
    """Rewrite an operand whose cell is gone, as Numbers wrote each one measured.

    The formula nodes spelling it become `#REF!` whose sentinels carry each axis's
    lock, and whose sticky bits mark the beginning of a locked axis only. The
    operand takes the lost lines as a tract, drops its own copy of the lock, and
    marks its reference preserved on both axes, locked or not.
    """
    reference = operand.relative_cell_ref
    rowLocked, columnLocked = reference.preserve_row, reference.preserve_column
    for formula in listRuleFormulas(rules):
        for node in formula.AST_node_array.AST_node:
            if not checkReferenceNode(node, reference):
                continue
            node.AST_node_type = brokenReferenceNodeType  # type: ignore[assignment]
            node.AST_column.column = brokenColumnSentinel
            node.AST_column.absolute = columnLocked
            node.AST_row.row = brokenRowSentinel
            node.AST_row.absolute = rowLocked
            markBeginLocked(node.AST_sticky_bits, rowLocked, columnLocked)
            writeLostTract(
                node.AST_tract_list, rowIdentity, columnIdentity,
                rowLocked, columnLocked,
            )
    operand.arg_type = brokenReferenceArgument
    operand.ClearField("preserve_row")
    operand.ClearField("preserve_column")
    reference.relative_row_offset = 0
    reference.relative_column_offset = 0
    reference.preserve_row = True
    reference.preserve_column = True
    reference.is_spanning_column = False
    reference.is_spanning_row = False
    writeLostTract(
        operand.uid_tract_list, rowIdentity, columnIdentity, rowLocked, columnLocked
    )


def markBeginLocked(
    bits: tsce.ASTNodeArrayArchive.ASTStickyBits, rowLocked: bool, columnLocked: bool
) -> None:
    """Mark the beginning of each locked axis, and never the end, as a broken cell."""
    bits.begin_row_is_absolute = rowLocked
    bits.begin_column_is_absolute = columnLocked
    bits.end_row_is_absolute = False
    bits.end_column_is_absolute = False


def writeLostTract(
    tracts: tsce.ASTNodeArrayArchive.ASTUidTractList,
    rowIdentity: int,
    columnIdentity: int,
    rowLocked: bool,
    columnLocked: bool,
) -> None:
    """Record one lost cell's row and column, the tract every broken reference holds."""
    tracts.ClearField("tract")
    tract = tracts.tract.add()
    assignUuid(tract.columnUids.uid.add(), columnIdentity)
    assignUuid(tract.rowUids.uid.add(), rowIdentity)
    tract.is_range_ref = False
    tract.purpose = tsce.ASTNodeArrayArchive.UIDS_INCLUDED
    tract.preserve_rectangular = True
    markBeginLocked(tracts.sticky_bits, rowLocked, columnLocked)


def buildConditionalPlan(
    index: ArchiveIndex,
    registry: PackageRegistry,
    owners: dict[int, IWAFile],
    store: tst.DataStore,
    maps: GridMaps,
    rowIdentities: Sequence[int],
    columnIdentities: Sequence[int],
    name: str,
) -> ConditionalPlan | None:
    """Gather a table's rule sets for the tile pass to rewrite cell by cell.

    `rowIdentities` and `columnIdentities` are the lines as stored, which is what a
    broken rule records.
    """
    if not store.HasField("conditionalstyletable"):
        return None
    dataList = index.resolve(store.conditionalstyletable, tst.TableDataList)
    if not len(dataList.entries):
        return None
    plan = ConditionalPlan(
        index, maps, registry, owners, dataList,
        store.conditionalstyletable.identifier,
        rowIdentities, columnIdentities, name,
    )
    for entry in dataList.entries:
        plan.rules[int(entry.key)] = index.resolve(
            entry.reference, tst.ConditionalStyleSetArchive
        )
        plan.siblings[int(entry.key)] = entry.reference.identifier
    return plan


def buildInheritedRecord(key: int) -> bytes:
    """Return the empty record a line added beside a highlighted cell receives."""
    return (
        emptyRecordHeader
        + key.to_bytes(4, "little")
        + noMatch.to_bytes(4, "little")
    )


def rewriteConditionalRecord(
    record: CellRecord, row: int, plan: ConditionalPlan
) -> bytes | None:
    """Return a record naming the rule its old one became, or None when unchanged.

    `row` is where the record was stored. A cell whose rule broke caches no match,
    as every one did in the measurements; one whose rule moved keeps its cache.
    """
    key = findSlotValue(record, conditionalSlot)
    # A record on a removed column goes with it, so it names no rule afterward.
    if key is None or plan.maps.columns.lineMap(record.column) is None:
        return None
    moved, broken = plan.keyFor(key, row, record.column)
    if moved == key:
        return None
    raw = patchSlotValue(record.raw, conditionalSlot, moved)
    if broken and findSlotValue(record, matchSlot) is not None:
        raw = patchSlotValue(raw, matchSlot, noMatch)
    return raw


def writeConditionalCounts(plan: ConditionalPlan, tiles: Iterable[tst.Tile]) -> None:
    """Set every rule's refcount from the cells naming it, and drop the unnamed ones.

    Counted rather than tracked, since the records are the truth and a rule a cell
    stopped naming is exactly the one Numbers removed when its reference moved.
    """
    claims: Counter[int] = Counter()
    for tile in tiles:
        for rowInfo in tile.rowInfos:
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                key = findSlotValue(record, conditionalSlot)
                if key is not None:
                    claims[key] += 1
    kept = []
    for entry in plan.dataList.entries:
        if claims[int(entry.key)]:
            entry.refcount = claims[int(entry.key)]
            kept.append(entry)
        else:
            plan.registry.archiveRemove(entry.reference.identifier)
    copies = [tst.TableDataList.ListEntry() for _ in kept]
    for copy, entry in zip(copies, kept, strict=True):
        copy.CopyFrom(entry)
    del plan.dataList.entries[:]
    plan.dataList.entries.extend(copies)
    plan.owners[plan.listIdentifier].messageReplace(
        plan.listIdentifier, 0, plan.dataList.SerializeToString(),
        [int(entry.reference.identifier) for entry in plan.dataList.entries],
    )


__all__ = [
    "ConditionalPlan",
    "buildInheritedRecord",
    "buildConditionalPlan",
    "rewriteConditionalRecord",
    "writeConditionalCounts",
]
