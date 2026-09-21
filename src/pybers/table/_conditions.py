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

A rule reading a cell relative to the one it colors is refused: every measured
rule reads a locked cell or a literal. So is a spanning reference.

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
from .._persistence.cells import CellRecord
from .._persistence.index import ArchiveIndex, assignUuid
from .._persistence.iwa import createArchive
from .._persistence.metadata import PackageRegistry
from ..errors import WriteError

if TYPE_CHECKING:
    # Guarded because the structural pass imports this module to plan the rules.
    from ._structure import GridMaps

# The slot naming a cell's rule set, and the slot caching which rule matched. The
# cache holds the matching rule's index, or 15 when none did, measured against the
# values each cell of `57-structure-refusals-base` holds.
conditionalSlot: tuple[int, int] = (8, 0x80)
matchSlot: tuple[int, int] = (9, 0x01)
noMatch: int = 15

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
    """What happens to each of a table's rule sets, and the entries it creates.

    `moved` maps an old key to the key of the rule it became. `broken` maps an old
    key to the broken form, which each cell naming it receives a copy of.
    """

    index: ArchiveIndex
    registry: PackageRegistry
    owners: dict[int, IWAFile]
    dataList: tst.TableDataList
    listIdentifier: int
    moved: dict[int, int] = field(default_factory=dict)
    broken: dict[int, tst.ConditionalStyleSetArchive] = field(default_factory=dict)
    siblings: dict[int, int] = field(default_factory=dict)

    def keyFor(self, key: int) -> int:
        """Return the key a cell naming `key` names after the edit."""
        if key in self.broken:
            return self.entryCreate(self.broken[key], self.siblings[key])
        return self.moved.get(key, key)

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
    maps: GridMaps,
    rowIdentities: Sequence[int],
    columnIdentities: Sequence[int],
    name: str,
) -> tuple[str, tst.ConditionalStyleSetArchive]:
    """Return what an edit does to one rule set: `same`, `moved` or `broken`.

    The operand naming the colored cell itself is an offset of zero, unlocked, and
    never moves. Every other operand has to be a locked cell, whose offsets are
    then its stored row and column.
    """
    changed = tst.ConditionalStyleSetArchive()
    changed.CopyFrom(rules)
    outcome = "same"
    for operand in listRuleOperands(changed):
        reference = operand.relative_cell_ref
        if reference.is_spanning_column or reference.is_spanning_row:
            raise WriteError(
                f"{name!r} carries a highlighting rule reading a whole row or column, "
                "and moving one is not measured."
            )
        locked = reference.preserve_row and reference.preserve_column
        if not locked:
            if reference.relative_row_offset or reference.relative_column_offset:
                raise WriteError(
                    f"{name!r} carries a highlighting rule reading a cell relative to "
                    "the one it colors, and moving one is not measured."
                )
            continue
        row, column = reference.relative_row_offset, reference.relative_column_offset
        movedRow, movedColumn = maps.rows.lineMap(row), maps.columns.lineMap(column)
        if movedRow is None or movedColumn is None:
            rewriteBrokenOperand(
                changed, operand, row, column,
                rowIdentities[row], columnIdentities[column],
            )
            outcome = "broken"
            continue
        if (movedRow, movedColumn) == (row, column):
            continue
        reference.relative_row_offset = movedRow
        reference.relative_column_offset = movedColumn
        for formula in listRuleFormulas(changed):
            for node in formula.AST_node_array.AST_node:
                if (
                    node.AST_node_type == referenceNodeType
                    and node.AST_column.column == column
                    and node.AST_row.row == row
                ):
                    node.AST_column.column = movedColumn
                    node.AST_row.row = movedRow
        if outcome == "same":
            outcome = "moved"
    return outcome, changed


def rewriteBrokenOperand(
    rules: tst.ConditionalStyleSetArchive,
    operand: tst.FormulaPredArgArchive,
    row: int,
    column: int,
    rowIdentity: int,
    columnIdentity: int,
) -> None:
    """Rewrite a locked operand whose cell is gone, as `57-conditions-column-deleted`.

    The reference keeps its lock and takes the lost lines as a tract, while the
    operand drops its own copy of the lock. Each formula copy turns the matching
    reference into `#REF!` carrying the same tract.
    Only the beginning of each axis is marked locked, which is how Numbers writes a
    single locked cell.
    """
    operand.arg_type = brokenReferenceArgument
    operand.ClearField("preserve_row")
    operand.ClearField("preserve_column")
    operand.relative_cell_ref.relative_row_offset = 0
    operand.relative_cell_ref.relative_column_offset = 0
    writeLostTract(operand.uid_tract_list, rowIdentity, columnIdentity)
    for formula in listRuleFormulas(rules):
        for node in formula.AST_node_array.AST_node:
            if not (
                node.AST_node_type == referenceNodeType
                and node.AST_column.column == column
                and node.AST_row.row == row
            ):
                continue
            node.AST_node_type = brokenReferenceNodeType  # type: ignore[assignment]
            node.AST_column.column = brokenColumnSentinel
            node.AST_column.absolute = True
            node.AST_row.row = brokenRowSentinel
            node.AST_row.absolute = True
            markBeginLocked(node.AST_sticky_bits)
            writeLostTract(node.AST_tract_list, rowIdentity, columnIdentity)


def markBeginLocked(bits: tsce.ASTNodeArrayArchive.ASTStickyBits) -> None:
    """Mark the beginning of both axes locked and the end not, as a broken cell is."""
    bits.begin_row_is_absolute = True
    bits.begin_column_is_absolute = True
    bits.end_row_is_absolute = False
    bits.end_column_is_absolute = False


def writeLostTract(
    tracts: tsce.ASTNodeArrayArchive.ASTUidTractList,
    rowIdentity: int,
    columnIdentity: int,
) -> None:
    """Record one lost cell's row and column, the tract every broken reference holds."""
    tracts.ClearField("tract")
    tract = tracts.tract.add()
    assignUuid(tract.columnUids.uid.add(), columnIdentity)
    assignUuid(tract.rowUids.uid.add(), rowIdentity)
    tract.is_range_ref = False
    tract.purpose = tsce.ASTNodeArrayArchive.UIDS_INCLUDED
    tract.preserve_rectangular = True
    markBeginLocked(tracts.sticky_bits)


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
    """Decide what the edit does to every rule set, creating the moved ones now.

    `rowIdentities` and `columnIdentities` are the lines as stored, which is what a
    broken rule records.
    """
    if not store.HasField("conditionalstyletable"):
        return None
    dataList = index.resolve(store.conditionalstyletable, tst.TableDataList)
    if not len(dataList.entries):
        return None
    plan = ConditionalPlan(
        index, registry, owners, dataList, store.conditionalstyletable.identifier
    )
    for entry in list(dataList.entries):
        rules = index.resolve(entry.reference, tst.ConditionalStyleSetArchive)
        outcome, changed = mapRuleSet(
            rules, maps, rowIdentities, columnIdentities, name
        )
        plan.siblings[int(entry.key)] = entry.reference.identifier
        if outcome == "moved":
            plan.moved[int(entry.key)] = plan.entryCreate(
                changed, entry.reference.identifier
            )
        elif outcome == "broken":
            plan.broken[int(entry.key)] = changed
    return plan


def findSlotValue(record: CellRecord, slot: tuple[int, int]) -> int | None:
    """Return the reference one slot of a record holds, or None when it is empty."""
    from ._write import listReferenceSlots

    slots = listReferenceSlots(record.raw)
    if slot not in slots:
        return None
    return int(record.references[slots.index(slot)])


def patchSlotValue(raw: bytes, slot: tuple[int, int], value: int) -> bytes:
    """Return a record with one filled slot holding a different reference."""
    from ._write import listReferenceSlots, referenceWidth

    slots = listReferenceSlots(raw)
    at = len(raw) - (len(slots) - slots.index(slot)) * referenceWidth
    encoded = value.to_bytes(referenceWidth, "little")
    return raw[:at] + encoded + raw[at + referenceWidth:]


def buildInheritedRecord(key: int) -> bytes:
    """Return the empty record a line added beside a highlighted cell receives."""
    return (
        emptyRecordHeader
        + key.to_bytes(4, "little")
        + noMatch.to_bytes(4, "little")
    )


def rewriteConditionalRecord(record: CellRecord, plan: ConditionalPlan) -> bytes | None:
    """Return a record naming the rule its old one became, or None when unchanged.

    A cell whose rule broke caches no match, as every one did in `57-conditions-
    column-deleted`; one whose rule only moved keeps what it cached.
    """
    key = findSlotValue(record, conditionalSlot)
    if key is None:
        return None
    moved = plan.keyFor(key)
    if moved == key:
        return None
    raw = patchSlotValue(record.raw, conditionalSlot, moved)
    if key in plan.broken and findSlotValue(record, matchSlot) is not None:
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
    "findSlotValue",
    "buildConditionalPlan",
    "rewriteConditionalRecord",
    "writeConditionalCounts",
]
