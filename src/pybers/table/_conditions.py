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

A rule's condition is a formula whose host is the cell it colors, so it is mapped
by the same machinery as a cell's formula, and each operand then takes the
coordinates of the formula node it indexes.

Private. Reached from the structural pass in `_structure` and the tile pass in
`_write`.

UPDATES
2026-09-22  Archives written through the save's index, for PYB-109.
2026-09-21  Rules mapped by the formula machinery rather than a copy of it.
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

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSTArchives_pb2 as tst
from .._persistence import chooseOffsetUnit, decodeRow
from .._persistence.cells import (
    CellRecord,
    conditionalSlot,
    findSlotValue,
    matchSlot,
    noMatch,
    patchSlotValue,
)
from .._persistence.index import ArchiveIndex
from .._persistence.metadata import PackageRegistry, createSiblingArchive
from ..addressing import CellReference
from ..addressing.reference import originOffset
from ..errors import WriteError
from ..formula._read import readFormula
from ..formula._write import encodeFormula
from ..formula.nodes import brokenReferenceNodeType
from ..formula.restructure import FormulaRestructure, mapFormula
from ._lines import GridMaps, ModelLines
from .structure import countBrokenReferences

# An operand that is a cell reference, and the form Numbers gives one it broke.
cellReferenceArgument: int = 4
brokenReferenceArgument: int = 9

# The empty record Numbers writes into a line added beside a highlighted one: no
# value, and the two slots above. Measured in `57-conditions-row-inserted`.
emptyRecordHeader: bytes = bytes.fromhex("050000000000000080010000")



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
    change: FormulaRestructure
    registry: PackageRegistry
    dataList: tst.TableDataList
    listIdentifier: int
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
        outcome, changed = mapRuleSet(rules, row, column, self.change)
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
        entry = self.dataList.entries.add()
        entry.key = self.dataList.nextListID
        entry.refcount = 0
        entry.reference.identifier = createSiblingArchive(
            self.registry, sibling, rules
        )
        self.dataList.nextListID += 1
        return int(entry.key)


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
    change: FormulaRestructure,
) -> tuple[str, tst.ConditionalStyleSetArchive]:
    """Return what an edit does to one cell's rule set: `same`, `moved` or `broken`.

    A rule's condition is a formula whose host is the colored cell, so it follows
    the edit exactly as a cell's formula does. Each copy of it is mapped, and each
    operand then takes the reference node it indexes.
    """
    changed = tst.ConditionalStyleSetArchive()
    changed.CopyFrom(rules)
    host = CellReference(row + originOffset, column + originOffset)
    outcome = "same"
    for formula in listRuleFormulas(changed):
        read = readFormula(formula)
        mapped = mapFormula(read, host, change)
        if mapped is read:
            continue
        formula.AST_node_array.CopyFrom(encodeFormula(mapped).AST_node_array)
        copyBrokenLocks(formula)
        if countBrokenReferences(mapped) > countBrokenReferences(read):
            outcome = "broken"
        elif outcome == "same":
            outcome = "moved"
    if outcome != "same":
        rewriteRuleOperands(changed)
    return outcome, changed


def copyBrokenLocks(formula: tsce.FormulaArchive) -> None:
    """Repeat each broken reference's lock in its tract, as a rule writes it.

    A cell formula leaves the tract's sticky bits clear, and a highlighting rule
    repeats the node's, measured in `57-conditions-column-deleted` and the three
    `59` columns removed.
    """
    for node in formula.AST_node_array.AST_node:
        if node.AST_node_type == brokenReferenceNodeType:
            node.AST_tract_list.sticky_bits.CopyFrom(node.AST_sticky_bits)


def rewriteRuleOperands(rules: tst.ConditionalStyleSetArchive) -> None:
    """Give each cell operand of every rule the coordinates of the node it indexes.

    The pre-pivot copy of a rule names, for each operand, the formula node that
    spells it. A broken node turns its operand into the broken form: the lost lines
    as a tract, the operand's own lock dropped, and its reference marked preserved
    on both axes, locked or not.
    """
    for number, rule in enumerate(rules.rules.rule):
        if number >= len(rules.rules_prepivot):
            raise WriteError(
                "A highlighting rule carries no pre-pivot copy naming its operands' "
                "nodes, which no measured rule lacks."
            )
        indices = rules.rules_prepivot[number].predicate
        nodes = rule.predicate.formula.AST_node_array.AST_node
        for operand, at in (
            (rule.predicate.param_value0, indices.param_index0),
            (rule.predicate.param_value1, indices.param_index1),
            (rule.predicate.param_value2, indices.param_index2),
        ):
            if operand.arg_type != cellReferenceArgument or not 0 <= at < len(nodes):
                continue
            node = nodes[at]
            reference = operand.relative_cell_ref
            if node.AST_node_type == brokenReferenceNodeType:
                operand.arg_type = brokenReferenceArgument
                operand.ClearField("preserve_row")
                operand.ClearField("preserve_column")
                reference.relative_row_offset = 0
                reference.relative_column_offset = 0
                reference.preserve_row = True
                reference.preserve_column = True
                reference.is_spanning_column = False
                reference.is_spanning_row = False
                operand.uid_tract_list.CopyFrom(node.AST_tract_list)
                continue
            if not reference.is_spanning_column and node.HasField("AST_row"):
                reference.relative_row_offset = node.AST_row.row
            if not reference.is_spanning_row and node.HasField("AST_column"):
                reference.relative_column_offset = node.AST_column.column


def buildConditionalPlan(
    index: ArchiveIndex,
    registry: PackageRegistry,
    store: tst.DataStore,
    maps: GridMaps,
    identity: str,
    rowIdentities: Sequence[int],
    columnIdentities: Sequence[int],
) -> ConditionalPlan | None:
    """Gather a table's rule sets for the tile pass to rewrite cell by cell.

    `identity` is how a rule's formula names its own table, and the identities are
    the lines as stored, which is what a broken rule records.
    """
    if not store.HasField("conditionalstyletable"):
        return None
    dataList = index.resolve(store.conditionalstyletable, tst.TableDataList)
    if not len(dataList.entries):
        return None
    change = FormulaRestructure(
        rows=ModelLines(maps.rows),
        columns=ModelLines(maps.columns),
        hostEdited=True,
        hostIdentity=identity,
        targetTable=identity,
        rowIdentities=rowIdentities,
        columnIdentities=columnIdentities,
    )
    plan = ConditionalPlan(
        index, maps, change, registry, dataList,
        store.conditionalstyletable.identifier,
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
    plan.index.archiveWrite(
        plan.listIdentifier, plan.dataList,
        [int(entry.reference.identifier) for entry in plan.dataList.entries],
    )


__all__ = [
    "ConditionalPlan",
    "buildInheritedRecord",
    "buildConditionalPlan",
    "rewriteConditionalRecord",
    "writeConditionalCounts",
]
