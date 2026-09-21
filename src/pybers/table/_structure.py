#!/usr/bin/env python3
"""\
A table's rows and columns added or removed, carried into every archive indexed by one.

**The edit is derived, never recorded.** The stored UID map says which line held
which identity, and the model says where each identity is now, so comparing the
two gives the whole mapping from stored lines to new ones. That is the same
comparison against what is stored that merges and cell values already use.

What follows the mapping here: the UID map, the header buckets and their counts,
hidden state, the declared counts, the stroke sidecar's counts, the layout cache,
and the merge store. Tiles move in `_write`, where the lists a removed record
releases are already open, and the calculation engine is re-registered by the
document writer, which knows what every formula reads.

**Refused, not guessed:** an edit inside a header or footer band, a table with
borders or conditional highlighting, and engine state keyed by cell that nothing
here moves. None of those appears in `56-structure-base`, so none is measured.

Private. The table feature offers `Table.rowAdd` and its siblings.

UPDATES
2026-09-18  Written for PYB-17.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/18"

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSPArchiveMessages_pb2 as tspArchive
from .._generated import TSTArchives_pb2 as tst
from .._persistence import IWAFile, chooseOffsetUnit, decodeRow
from .._persistence.index import ArchiveIndex, originOffset, readUuidValue
from .._persistence.iwa import createArchive
from .._persistence.metadata import PackageRegistry
from ..errors import WriteError
from ._conditions import ConditionalPlan, buildConditionalPlan
from ._create import assignUids
from ._read import readLineIdentities
from .cells import Table


@dataclass(frozen=True, slots=True)
class LineMap:
    """Where each stored line of one axis lands, counted from zero, None if removed."""

    lines: tuple[int | None, ...]
    count: int

    @property
    def changed(self) -> bool:
        """Report whether any line moved, went, or arrived."""
        return self.count != len(self.lines) or any(
            line != moved for line, moved in enumerate(self.lines)
        )

    def lineMap(self, line: int) -> int | None:
        """Return where one stored line lands, or None when it was removed."""
        return self.lines[line] if line < len(self.lines) else None

    def spanMap(self, begin: int, end: int) -> tuple[int, int] | None:
        """Return where a span lands, its first and last surviving lines kept."""
        kept = [
            moved for moved in (self.lineMap(line) for line in range(begin, end + 1))
            if moved is not None
        ]
        if not kept:
            return None
        return (min(kept), max(kept))


@dataclass(frozen=True, slots=True)
class GridMaps:
    """Both axes of one table's structural change, stored lines to new ones."""

    rows: LineMap
    columns: LineMap

    @property
    def changed(self) -> bool:
        """Report whether either axis changed."""
        return self.rows.changed or self.columns.changed


def buildLineMap(
    stored: Sequence[int], wanted: Sequence[int], axis: str, name: str
) -> LineMap:
    """Return where each stored line went, refusing lines that changed order.

    Added and removed lines are the only edits this library makes, so every line
    both sides hold keeps its order, and an identity only the model holds is new.
    """
    position = {identity: at for at, identity in enumerate(wanted)}
    lines = tuple(position.get(identity) for identity in stored)
    kept = [line for line in lines if line is not None]
    if kept != sorted(kept):
        raise WriteError(
            f"The {axis} of {name!r} are in a different order from the file's, and "
            "only adding and removing them is written."
        )
    return LineMap(lines, len(wanted))


def buildGridMaps(
    index: ArchiveIndex, model: tst.TableModelArchive, table: Table
) -> GridMaps:
    """Return how the model's rows and columns relate to the stored ones."""
    rows, columns = readLineIdentities(index, model)
    if len(rows) != model.number_of_rows or len(columns) != model.number_of_columns:
        raise WriteError(
            f"{table.name!r} declares {model.number_of_rows} by "
            f"{model.number_of_columns} and its UID map holds {len(rows)} by "
            f"{len(columns)}, so which line is which cannot be told."
        )
    return GridMaps(
        buildLineMap(rows, table._rowIdentities, "rows", table.name),
        buildLineMap(columns, table._columnIdentities, "columns", table.name),
    )


def findDisplacedLine(lines: LineMap, line: int) -> int | None:
    """Return the stored line an added line took the place of, or None at the end."""
    for stored, moved in enumerate(lines.lines):
        if moved is not None and moved > line:
            return stored
    return None


def listAddedLines(lines: LineMap) -> list[int]:
    """Return every new line the edit added, as its index afterward."""
    held = {moved for moved in lines.lines if moved is not None}
    return [line for line in range(lines.count) if line not in held]


def countBands(lines: LineMap, leading: int, trailing: int) -> tuple[int, int]:
    """Return what a leading and a trailing band hold after the edit.

    A band covers a stretch of lines rather than a count, so a line added inside
    one grows it and a line removed from one shrinks it. A line added at the
    trailing band's own first line lands inside it, measured 2026-09-21 in
    `57-bands-row-inserted-before-footer`, where a footer of one became two.
    """
    held = len(lines.lines)
    removedLeading = sum(
        1 for line in range(leading) if lines.lines[line] is None
    )
    removedTrailing = sum(
        1 for line in range(held - trailing, held) if lines.lines[line] is None
    )
    addedLeading = addedTrailing = 0
    for line in listAddedLines(lines):
        displaced = findDisplacedLine(lines, line)
        boundary = held if displaced is None else displaced
        addedLeading += boundary < leading
        addedTrailing += trailing > 0 and boundary >= held - trailing
    return (
        leading - removedLeading + addedLeading,
        trailing - removedTrailing + addedTrailing,
    )


def applyBandCounts(model: tst.TableModelArchive, maps: GridMaps) -> None:
    """Grow or shrink each band by the lines the edit added to or took from it.

    A count is written only when it changed, because a field set to the zero it
    already held is a byte a table without bands never carried.
    """
    headerRows, footerRows = countBands(
        maps.rows, model.number_of_header_rows, model.number_of_footer_rows
    )
    headerColumns = countBands(
        maps.columns, model.number_of_header_columns, 0
    )[0]
    for name, count in (
        ("number_of_header_rows", headerRows),
        ("number_of_footer_rows", footerRows),
        ("number_of_header_columns", headerColumns),
    ):
        if getattr(model, name) != count:
            setattr(model, name, count)


def mapStrokeRuns(
    layer: tst.StrokeLayerArchive, lines: LineMap
) -> list[tst.StrokeLayerArchive.StrokeRunArchive]:
    """Return one layer's runs after the edit, split where a removed line sat.

    **A removal splits a run rather than shortening it**, measured in
    `57-borders-row-deleted`: one run over six rows became two, of two lines and
    three, carrying the same stroke. Lines added inside a run are covered by it,
    which is how an inserted row takes the border of the run it fell into.
    """
    mapped: list[tst.StrokeLayerArchive.StrokeRunArchive] = []
    segment: list[int] = []
    for run in layer.stroke_runs:
        segment = []
        for line in range(run.origin, run.origin + run.length):
            if lines.lineMap(line) is None:
                if segment:
                    mapped.append(buildStrokeRun(run, segment, lines))
                segment = []
                continue
            segment.append(line)
        if segment:
            mapped.append(buildStrokeRun(run, segment, lines))
    return mapped


def buildStrokeRun(
    run: tst.StrokeLayerArchive.StrokeRunArchive,
    segment: list[int],
    lines: LineMap,
) -> tst.StrokeLayerArchive.StrokeRunArchive:
    """Return one run of a layer, covering where a stretch of lines landed."""
    first, last = lines.lineMap(segment[0]), lines.lineMap(segment[-1])
    assert first is not None and last is not None
    moved = tst.StrokeLayerArchive.StrokeRunArchive()
    moved.CopyFrom(run)
    moved.origin = first
    moved.length = last - first + 1
    return moved


def applyStrokeLayers(
    index: ArchiveIndex,
    registry: PackageRegistry,
    owners: dict[int, IWAFile],
    sidecar: tst.StrokeSidecarArchive,
    maps: GridMaps,
) -> None:
    """Move every border with the line it belongs to, as `57-borders-*` measured.

    A layer belongs to one row or column and holds runs along the other axis, so
    each list follows one map by its index and the other inside its runs. An added
    line takes a copy of the layer of the line it displaced, which is how an
    inserted column arrived carrying its neighbor's border.
    """
    lists = (
        (sidecar.left_column_stroke_layers, maps.columns, maps.rows),
        (sidecar.right_column_stroke_layers, maps.columns, maps.rows),
        (sidecar.top_row_stroke_layers, maps.rows, maps.columns),
        (sidecar.bottom_row_stroke_layers, maps.rows, maps.columns),
    )
    for references, keys, runs in lists:
        if not len(references):
            continue
        stored = {}
        for reference in references:
            layer = index.resolve(reference, tst.StrokeLayerArchive)
            stored[layer.row_column_index] = (reference.identifier, layer)
        placed: dict[int, tuple[int, tst.StrokeLayerArchive]] = {}
        for line, (identifier, layer) in stored.items():
            moved = keys.lineMap(line)
            if moved is None:
                registry.archiveRemove(identifier)
                continue
            layer.row_column_index = moved
            placed[moved] = (identifier, layer)
        sibling = next(iter(stored.values()))[0]
        for line in listAddedLines(keys):
            displaced = findDisplacedLine(keys, line)
            copied = tst.StrokeLayerArchive()
            if displaced is not None:
                copied.CopyFrom(stored[displaced][1])
            copied.row_column_index = line
            placed[line] = (
                createStrokeLayer(index, registry, owners, sibling, copied), copied
            )
        for identifier, layer in placed.values():
            rewritten = mapStrokeRuns(layer, runs)
            del layer.stroke_runs[:]
            layer.stroke_runs.extend(rewritten)
            owners[identifier].messageReplace(
                identifier, 0, layer.SerializeToString()
            )
        del references[:]
        for line in sorted(placed):
            references.add(identifier=placed[line][0])


def createStrokeLayer(
    index: ArchiveIndex,
    registry: PackageRegistry,
    owners: dict[int, IWAFile],
    sibling: int,
    layer: tst.StrokeLayerArchive,
) -> int:
    """Register a created stroke layer beside a sibling, and return its identifier.

    The sibling's archive info carries the message version and whatever else this
    library does not model, so a created layer is shaped from it rather than built.
    """
    info = tspArchive.ArchiveInfo()
    info.ParseFromString(index.archive(sibling).infoBytes)
    info.identifier = registry.identifierAllocate()
    del info.message_infos[1:]
    archive = createArchive(info, [layer.SerializeToString()])
    componentId = registry.componentOf[sibling]
    registry.archiveAdd(componentId, archive)
    owners[archive.identifier] = registry.componentMember(componentId)
    index.byIdentifier[archive.identifier] = archive
    return archive.identifier


def listStrokeLayers(sidecar: tst.StrokeSidecarArchive) -> list[int]:
    """Return every layer the sidecar points at, which is what it declares."""
    return [
        reference.identifier
        for references in (
            sidecar.left_column_stroke_layers, sidecar.right_column_stroke_layers,
            sidecar.top_row_stroke_layers, sidecar.bottom_row_stroke_layers,
        )
        for reference in references
    ]


def countSurvivingCells(
    index: ArchiveIndex, store: tst.DataStore, maps: GridMaps
) -> tuple[Counter[int], Counter[int]]:
    """Return how many records each new row and each new column will hold."""
    tileSize = store.tiles.tile_size
    rows: Counter[int] = Counter()
    columns: Counter[int] = Counter()
    for entry in store.tiles.tiles:
        tile = index.resolve(entry.tile, tst.Tile)
        for rowInfo in tile.rowInfos:
            row = maps.rows.lineMap(entry.tileid * tileSize + rowInfo.tile_row_index)
            if row is None:
                continue
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                column = maps.columns.lineMap(record.column)
                if column is None:
                    continue
                rows[row] += 1
                columns[column] += 1
    return rows, columns


# The rows one bucket of row headers holds, measured 2026-09-21: in a table of
# 100,000 rows, row 65,536 sits in the first bucket and row 65,537 in the second.
rowsPerBucket: int = 65536


def remapHeaders(
    buckets: list[tst.HeaderStorageBucket], lines: LineMap, counts: Counter[int]
) -> None:
    """Move each line's header to its new index and bucket, recounting its cells.

    A line added carries no header, which is how Numbers writes one at the default
    size, and a removed line's header goes with it. A header lands in the bucket
    its index falls in, and a table keeping one bucket keeps every header there:
    rows added past 65,536 left `58-buckets-created` with one bucket, where setting
    the row count had created sixteen.
    """
    placed: list[list[tst.HeaderStorageBucket.Header]] = [[] for _ in buckets]
    for bucket in buckets:
        for header in bucket.headers:
            moved = lines.lineMap(header.index)
            if moved is None:
                continue
            copy = tst.HeaderStorageBucket.Header()
            copy.CopyFrom(header)
            copy.index = moved
            copy.numberOfCells = counts[moved]
            placed[min(moved // rowsPerBucket, len(buckets) - 1)].append(copy)
    for bucket, headers in zip(buckets, placed, strict=True):
        del bucket.headers[:]
        bucket.headers.extend(sorted(headers, key=lambda header: header.index))


def removeHiddenStates(model: tst.TableModelArchive, table: Table) -> None:
    """Drop the hidden state of every line the model no longer holds.

    Keyed by identity, so a line that moved keeps its state untouched.
    """
    identities = set(table._rowIdentities) | set(table._columnIdentities)
    for states in model.hidden_states_owner.hidden_states:
        extents = (states.row_hidden_state_extent, states.column_hidden_state_extent)
        for extent in extents:
            kept = [
                state for state in extent.base_hidden_states
                if readUuidValue(state.row_or_column_uid) in identities
            ]
            if len(kept) == len(extent.base_hidden_states):
                continue
            copies = [
                tst.HiddenStateExtentArchive.RowOrColumnState() for _ in kept
            ]
            for copy, state in zip(copies, kept, strict=True):
                copy.CopyFrom(state)
            del extent.base_hidden_states[:]
            extent.base_hidden_states.extend(copies)


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


def applyGridStructure(
    index: ArchiveIndex,
    registry: PackageRegistry,
    owners: dict[int, IWAFile],
    table: Table,
    info: tst.TableInfoArchive,
    infoIdentifier: int,
    model: tst.TableModelArchive,
    maps: GridMaps,
) -> ConditionalPlan | None:
    """Carry a structural edit into every archive of the table indexed by a line.

    The table model and its info are mutated for the caller to serialize, and the
    archives it points at are written here.
    """
    store = model.base_data_store
    rowCounts, columnCounts = countSurvivingCells(index, store, maps)
    # Read before the UID map is rewritten, since a broken rule records the lines
    # as they were stored.
    storedRows, storedColumns = readLineIdentities(index, model)
    plan = buildConditionalPlan(
        index, registry, owners, store, maps, storedRows, storedColumns, table.name
    )

    uidReference = model.base_column_row_uids
    uids = index.resolve(uidReference, tst.ColumnRowUIDMapArchive)
    assignUids(uids, table)
    writeArchive(owners, uidReference.identifier, uids.SerializeToString())

    rowBuckets = [
        index.resolve(reference, tst.HeaderStorageBucket)
        for reference in store.rowHeaders.buckets
    ]
    remapHeaders(rowBuckets, maps.rows, rowCounts)
    for reference, bucket in zip(store.rowHeaders.buckets, rowBuckets, strict=True):
        writeArchive(owners, reference.identifier, bucket.SerializeToString())
    columnBucket = index.resolve(store.columnHeaders, tst.HeaderStorageBucket)
    remapHeaders([columnBucket], maps.columns, columnCounts)
    writeArchive(
        owners, store.columnHeaders.identifier, columnBucket.SerializeToString()
    )

    # Resolved once, because the layer pass rewrites this archive and a second
    # copy would carry the list of layers as it was before that.
    sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
    applyStrokeLayers(index, registry, owners, sidecar, maps)
    sidecar.row_count = table.rowCount
    sidecar.column_count = table.colCount
    writeArchive(
        owners, model.stroke_sidecar.identifier, sidecar.SerializeToString(),
        listStrokeLayers(sidecar),
    )

    model.number_of_rows = table.rowCount
    model.number_of_columns = table.colCount
    applyBandCounts(model, maps)
    removeHiddenStates(model, table)
    remapMergeStore(model, maps)

    # A cache Numbers refills, measured holding column indices that an edit makes
    # stale. A created table carries it empty, which Numbers already accepts.
    cache = info.layout_engine.width_height_cache
    del cache.rows_fitting_entries[:]
    cache.columns_count = table.colCount
    writeArchive(owners, infoIdentifier, info.SerializeToString())
    return plan


def writeArchive(
    owners: dict[int, IWAFile],
    identifier: int,
    data: bytes,
    references: list[int] | None = None,
) -> None:
    """Write one archive's first message back into the file holding it.

    `references` replaces what the archive declares it points at. A body that
    loses or gains one has to say so, because the registry registers what a
    component reaches from those declarations rather than from the body.
    """
    owners[identifier].messageReplace(identifier, 0, data, references)


def refuseUnmovableEngineState(
    dependencies: tsce.FormulaOwnerDependenciesArchive, name: str
) -> None:
    """Refuse engine state keyed by cell that a structural edit does not move."""
    if dependencies.whole_owner_dependencies.dependent_cells.ByteSize():
        raise WriteError(
            f"{name!r} holds a formula the engine records as reading the whole "
            "table, and moving that record is not measured."
        )


def remapCoordinateSet(
    coordinates: tsce.CellCoordSetArchive, maps: GridMaps
) -> None:
    """Move every cell a set names, dropping those whose line is gone.

    The set is columns, each holding row ranges, which is how `NOW()` and `RAND()`
    are recorded in `57-structure-refusals-base`.
    """
    moved: dict[int, set[int]] = {}
    for entry in coordinates.column_entries:
        column = maps.columns.lineMap(entry.column)
        if column is None:
            continue
        for extent in entry.row_set.entries:
            begin = extent.range_begin
            last = extent.range_end if extent.HasField("range_end") else begin
            for stored in range(begin, last + 1):
                row = maps.rows.lineMap(stored)
                if row is not None:
                    moved.setdefault(column, set()).add(row)
    del coordinates.column_entries[:]
    for column in sorted(moved):
        entry = coordinates.column_entries.add()
        entry.column = column
        for row in sorted(moved[column]):
            entry.row_set.entries.add(range_begin=row)


def checkSpanCut(lines: LineMap, begin: int, end: int) -> bool:
    """Report whether an edit removes a line of a span or adds one inside it.

    A line added before the span's first line moves the whole span, and one added
    after its last line leaves it alone, so neither cuts it.
    """
    if any(lines.lineMap(line) is None for line in range(begin, end + 1)):
        return True
    return any(
        begin < (len(lines.lines) if displaced is None else displaced) <= end
        for displaced in (
            findDisplacedLine(lines, added) for added in listAddedLines(lines)
        )
    )


def remapSpills(
    dependencies: tsce.FormulaOwnerDependenciesArchive, maps: GridMaps, name: str
) -> None:
    """Move each spill with its formula, refusing an edit that lands inside one.

    **Numbers re-flows a spill cut by an edit**, measured 2026-09-21 in
    `57-engine-row-inserted`: a row added inside `SEQUENCE(3)` left the spilled
    cells where they were and moved the row below instead. Following that means
    evaluating the formula. An edit outside a spill moves it whole, as
    `57-engine-column-inserted` moved `C4:D4` to `D4:E4`, which is ordinary movement.
    """
    for spill in dependencies.spill_range_sizes.spills:
        row, column = spill.coordinate.row, spill.coordinate.column
        rows = spill.spill_size.num_rows or 1
        columns = spill.spill_size.num_columns or 1
        if checkSpanCut(maps.rows, row, row + rows - 1) or checkSpanCut(
            maps.columns, column, column + columns - 1
        ):
            raise WriteError(
                f"{name!r} has a row or column added or removed inside a formula's "
                "spill, and Numbers re-flows a spill rather than moving it, which "
                "means evaluating the formula."
            )
    # A moved spill is listed first, as Numbers listed it in both measurements
    # where one moved and one stayed.
    moved: list[tsce.CellSpillSizesArchive.SpillForCell] = []
    stayed: list[tsce.CellSpillSizesArchive.SpillForCell] = []
    for spill in dependencies.spill_range_sizes.spills:
        movedRow = maps.rows.lineMap(spill.coordinate.row)
        movedColumn = maps.columns.lineMap(spill.coordinate.column)
        assert movedRow is not None and movedColumn is not None
        copy = tsce.CellSpillSizesArchive.SpillForCell()
        copy.CopyFrom(spill)
        copy.coordinate.row = movedRow
        copy.coordinate.column = movedColumn
        unchanged = (movedRow, movedColumn) == (
            spill.coordinate.row, spill.coordinate.column
        )
        (stayed if unchanged else moved).append(copy)
    del dependencies.spill_range_sizes.spills[:]
    dependencies.spill_range_sizes.spills.extend(moved + stayed)


def remapOwnerCoordinates(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
    table: Table,
    maps: GridMaps,
) -> None:
    """Move the engine's cell-keyed records that no formula registration rewrites.

    Errors follow their cells, or go with a removed one, and the table's own
    extent follows its size. The errors' text is left for the recalculation every
    moved formula is marked for.
    """
    refuseUnmovableEngineState(dependencies, table.name)
    volatile = dependencies.volatile_dependencies
    for name in (
        "volatile_time_cells", "volatile_random_cells", "volatile_locale_cells",
        "volatile_sheet_table_name_cells", "volatile_remote_data_cells",
    ):
        remapCoordinateSet(getattr(volatile, name), maps)
    remapSpills(dependencies, maps, table.name)
    for spanning in (
        dependencies.spanning_column_dependencies,
        dependencies.spanning_row_dependencies,
    ):
        for extent in (spanning.total_range_for_table, spanning.body_range_for_table):
            if not extent.ByteSize():
                continue
            extent.bottom_right_row += maps.rows.count - len(maps.rows.lines)
            extent.bottom_right_column += maps.columns.count - len(maps.columns.lines)
    errors = dependencies.cell_errors
    for field in ("errors", "enhanced_errors"):
        entries = getattr(errors, field)
        kept = []
        for entry in entries:
            row = maps.rows.lineMap(entry.coordinate.row)
            column = maps.columns.lineMap(entry.coordinate.column)
            if row is None or column is None:
                continue
            entry.coordinate.row = row
            entry.coordinate.column = column
            kept.append(entry)
        copies = [type(entry)() for entry in kept]
        for copy, entry in zip(copies, kept, strict=True):
            copy.CopyFrom(entry)
        del entries[:]
        entries.extend(copies)


def listRegisteredFormulas(
    dependencies: tsce.FormulaOwnerDependenciesArchive,
) -> list[tuple[int, int]]:
    """Return every cell the engine registers a formula at, as stored."""
    return [
        (record.row, record.column)
        for record in dependencies.cell_dependencies.cell_record
    ]


def listModelFormulas(table: Table) -> list[tuple[int, int]]:
    """Return every cell of the model holding a formula, in stored coordinates."""
    return sorted(
        (reference.row - originOffset, reference.col - originOffset)
        for reference, cell in table.cells.items()
        if cell.formula is not None
    )


__all__ = [
    "GridMaps",
    "LineMap",
    "applyGridStructure",
    "buildGridMaps",
    "listModelFormulas",
    "listRegisteredFormulas",
    "remapOwnerCoordinates",
]
