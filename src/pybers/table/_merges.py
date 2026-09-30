#!/usr/bin/env python3
"""\
A table's merges: the merge store written, moved with its lines, and compared.

**A merge is stored as a formula**, shaped like `SUM($A$1:$B$1)` and evaluated by
nothing. It lives with the table rather than with the calculation engine because a
merge belongs to a table, and it was the one thing in the engine that knew a model
type.

Private. Part of the table feature's archive half.

UPDATES
2026-09-22  Split out of the table writer and the structural edit for PYB-113.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/22"

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSTArchives_pb2 as tst
from .._persistence.index import wordBits, wordMask
from ..addressing.reference import originOffset
from ._lines import GridMaps
from ._read import readMerges
from .cells import Table
from .merges import MergeRange

# A merge is written as `SUM($A$1:$B$1)`, so it carries SUM's index in Apple's
# own function table. The number is theirs and is not derivable from the schemas.
sumFunctionIndex: int = 168


def writeMergeFormula(
    store: tst.FormulaStoreArchive, merge: MergeRange, ownerUid: tsp.UUID
) -> None:
    """Add one merged region to a table's merge store, as the formula Numbers writes.

    **A merge is stored as a formula, not as a flag on a cell.** Each region is a
    complete formula shaped like `SUM($A$1:$B$1)`: a colon-tract node carrying the
    rectangle with all four sticky bits set, then the function node for SUM. Nothing
    evaluates it; the shape is how a merge is expressed.

    The tract's table identifier is the table's own `formula_owner_uid`, split from
    two 64-bit halves into four 32-bit words, which is a different spelling of the
    same value in a different archive. Measured 2026-09-02 against `22-merge-2x2`.
    """
    pair = store.formulas.add()
    pair.formula_index = len(store.formulas) - 1

    node = pair.formula.AST_node_array.AST_node.add()
    node.AST_node_type = tsce.ASTNodeArrayArchive.COLON_TRACT_NODE
    identifier = node.AST_cross_table_reference_extra_info.table_id
    identifier.uuid_w0 = ownerUid.lower & wordMask
    identifier.uuid_w1 = ownerUid.lower >> wordBits
    identifier.uuid_w2 = ownerUid.upper & wordMask
    identifier.uuid_w3 = ownerUid.upper >> wordBits
    node.AST_sticky_bits.begin_row_is_absolute = True
    node.AST_sticky_bits.begin_column_is_absolute = True
    node.AST_sticky_bits.end_row_is_absolute = True
    node.AST_sticky_bits.end_column_is_absolute = True

    startRow, startCol, endRow, endCol = merge.bounds
    tract = node.AST_colon_tract
    columns = tract.absolute_column.add()
    columns.range_begin = startCol - originOffset
    rows = tract.absolute_row.add()
    rows.range_begin = startRow - originOffset
    # `range_end` is omitted for a span of one rather than repeating the beginning,
    # which is how Numbers writes its own and how the reader expects to find them.
    if endCol != startCol:
        columns.range_end = endCol - originOffset
    if endRow != startRow:
        rows.range_end = endRow - originOffset
    tract.preserve_rectangular = True

    function = pair.formula.AST_node_array.AST_node.add()
    function.AST_node_type = tsce.ASTNodeArrayArchive.FUNCTION_NODE
    function.AST_function_node_index = sumFunctionIndex
    function.AST_function_node_numArgs = 1


def findAddedMerges(table: Table, model: tst.TableModelArchive) -> list[MergeRange]:
    """Return the merges the model holds that the stored archive does not.

    Compared against what is stored rather than tracked as merges are added, for
    the same reason `applyMerges` does it: a caller reaches `mergeRanges`
    directly, so a flag set at `mergeAdd` would go stale.

    **Call this BEFORE `applyMerges`**, which rewrites the very store it reads.
    Measured 2026-09-07 on `22c-merge-overpaints`: the same call returns one
    merge before and none after, so the wrong order leaves every covered position
    unswallowed and raises nothing.
    """
    stored = {str(merge.extent) for merge in readMerges(model)}
    return [merge for merge in table.mergeRanges if str(merge.extent) not in stored]


def listSwallowedPositions(
    table: Table, model: tst.TableModelArchive
) -> frozenset[tuple[int, int]]:
    """Return every position a merge being added covers, in stored coordinates.

    Only a merge being ADDED clears its covered positions. One already in the file
    may carry a style-only record at each of them, which an XLSX import writes and
    Numbers then keeps forever, and stripping those would rewrite a document the
    caller only asked to save.
    """
    return frozenset(
        (reference.row - originOffset, reference.col - originOffset)
        for merge in findAddedMerges(table, model)
        for reference in merge.extent
        if reference != merge.anchor
    )


def applyMerges(
    table: Table, model: tst.TableModelArchive, ownerUid: tsp.UUID
) -> frozenset[tuple[int, int]]:
    """Rewrite a table's merge store when its merges differ, and say which cells moved.

    **A merge changes what a reference means, so it changes results**, which is why
    every position whose merge state changed is returned for dirty-marking. **The
    store is emptied rather than removed** when the last merge goes; `merge_owner` is
    present in both twins. Both measured 2026-09-02 across `22-merge-2x2` and its
    unmerged twin, recorded in findings-03-structure.md.

    Compared against what is stored rather than tracked as merges are added, since a
    caller reaches `mergeRanges` directly and a dirty flag would go stale.
    """
    stored = readMerges(model)
    wanted = sorted(str(merge.extent) for merge in table.mergeRanges)
    if wanted == sorted(str(merge.extent) for merge in stored):
        return frozenset()

    store = model.merge_owner.formula_store
    del store.formulas[:]
    for merge in table.mergeRanges:
        writeMergeFormula(store, merge, ownerUid)
    store.next_formula_index = len(store.formulas)

    # Both directions matter: a merge that appeared invalidates references INTO it,
    # and one that went away makes references valid again.
    before = {str(merge.extent): merge for merge in stored}
    after = {str(merge.extent): merge for merge in table.mergeRanges}
    changed = (set(before) ^ set(after))
    return frozenset(
        (reference.row - originOffset, reference.col - originOffset)
        for extent in changed
        for reference in (before.get(extent) or after[extent]).extent
    )


def remapMergeStore(model: tst.TableModelArchive, maps: GridMaps) -> None:
    """Move each stored merge with its lines, as Numbers rewrote them in `23`.

    Kept in place rather than rebuilt, so a merge the edit only moved keeps its
    formula index and is not then mistaken for one the caller added.
    """
    if not model.HasField("merge_owner"):
        return
    store = model.merge_owner.formula_store
    kept = []
    for pair in store.formulas:
        tracts = [
            node.AST_colon_tract for node in pair.formula.AST_node_array.AST_node
            if node.HasField("AST_colon_tract")
        ]
        survives = True
        for tract in tracts:
            for axis, lines in (
                (tract.absolute_row, maps.rows), (tract.absolute_column, maps.columns)
            ):
                for span in axis:
                    begin = span.range_begin
                    end = span.range_end if span.HasField("range_end") else begin
                    mapped = lines.spanMap(begin, end)
                    if mapped is None:
                        survives = False
                        continue
                    span.range_begin = mapped[0]
                    if mapped[1] != mapped[0]:
                        span.range_end = mapped[1]
                    else:
                        span.ClearField("range_end")
        if survives:
            kept.append(pair)
    if len(kept) == len(store.formulas):
        return
    copies = [tst.FormulaStoreArchive.FormulaStorePair() for _ in kept]
    for copy, pair in zip(copies, kept, strict=True):
        copy.CopyFrom(pair)
    del store.formulas[:]
    store.formulas.extend(copies)


__all__ = [
    "applyMerges",
    "findAddedMerges",
    "listSwallowedPositions",
    "remapMergeStore",
]
