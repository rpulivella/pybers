#!/usr/bin/env python3
"""\
A created sheet and table hold only what Numbers needs, each field as Numbers writes it.

Every archive pybers composes is paired with the one Numbers wrote for an inserted
table in `48-table-inserted` and an inserted sheet in `49-sheet-inserted`. A field
pybers holds carries Numbers' value, apart from identities, placement and the pybers
reset, and a field it leaves out is one the ladder in findings-10-creation.md found
Numbers rebuilds or does without.

UPDATES
2026-11-02  Written for PYB-276.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/02"

import re
from pathlib import Path

import pytest
from google.protobuf.message import Message

import pybers
from conftest import copyDocument, findDocumentPath
from pybers._engine import findCalculationEngine
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSCEArchives_pb2 as tsce
from pybers._generated import TSPArchiveMessages_pb2 as tspArchive
from pybers._generated import TSPMessages_pb2 as tsp
from pybers._generated import TSTArchives_pb2 as tst
from pybers._generated import TSWPArchives_pb2 as tswp
from pybers._persistence import readPackage
from pybers._persistence.index import ArchiveIndex, findRoot
from pybers._persistence.types import parseArchive

storeLists: tuple[str, ...] = (
    "stringTable", "styleTable", "formula_table", "format_table_pre_bnc",
    "control_cell_spec_table", "format_table",
)

# Fields that may differ by identity, placement or the reset, by the part holding them.
expectedDifferences: dict[str, frozenset[str]] = {
    "info": frozenset({
        "super.geometry.position.y", "super.geometry.size.width",
        "super.geometry.size.height",
    }),
    "model": frozenset({
        "table_id", "table_name", "default_row_height", "default_column_width",
    }),
    "uids": frozenset({
        "column_index_for_uid", "column_uid_for_index", "row_index_for_uid",
        "row_uid_for_index",
    }),
    "owner": frozenset({"internal_formula_owner_id"}),
    "sheet": frozenset({
        "content_scale", "is_autofit_on", "show_page_numbers", "print_margins.left",
        "print_margins.right",
    }),
}

# What pybers leaves out, each found by a rung of the PYB-276 ladder.
ownerDependencies: frozenset[str] = frozenset({
    "cell_dependencies", "cell_errors", "range_dependencies", "spill_range_sizes",
    "tiled_cell_dependencies", "tiled_range_dependencies", "uuid_references",
    "whole_owner_dependencies.dependent_cells",
    *(f"volatile_dependencies.volatile_{kind}" for kind in (
        "geometry_cell_refs", "locale_cells", "random_cells", "remote_data_cells",
        "sheet_table_name_cells", "time_cells",
    )),
    *(f"spanning_{axis}_dependencies.{extent}_range_for_table.{corner}_{line}"
      for axis in ("column", "row") for extent in ("body", "total")
      for corner in ("top_left", "bottom_right") for line in ("column", "row")),
})
groupByFormulas: tuple[str, ...] = (
    "aggs_in_group_root", "column_order_changed", "grouping_column_headers",
    "grouping_columns", "hidden_states_changed", "indirect_agg_type_change",
    "row_order_changed", "row_order_changed_ignoring_recalc",
)
hiddenExtentFields: tuple[str, ...] = (
    "filter_set", "hidden_state_extent_uid", "needs_to_update_filter_set_for_import",
    "row_or_column_direction",
)
recordedOmissions: dict[str, frozenset[str]] = {
    "info": frozenset({
        "summary_model", "category_order", "group_by_uuid", "hidden_states_uuid",
        "formula_coord_space", "super.title", "super.caption", "super.title_hidden",
        "super.caption_hidden", "super.locked", "super.aspect_ratio_locked",
        "super.geometry.angle", "super.exterior_text_wrap.is_html_wrap",
        "layout_engine.width_height_cache.columns_count",
        "layout_engine.width_height_cache.rows_fitting_entries.fitting_index",
        "layout_engine.width_height_cache.rows_fitting_entries.fitting_size",
    }),
    "model": frozenset({
        *(f"base_data_store.{field}" for field in (
            "commentStorageTable", "conditionalstyletable", "formulaErrorTable",
            "importWarningSetTable", "multipleChoiceListFormatTable",
            "rich_text_table", "storage_version_pre_bnc",
        )),
        "category_owner", "category_owner_deprecated.owner_uid",
        *(f"category_owner_deprecated.group_by.{field}" for field in (
            "group_by_uid", "group_node_root.format_manager",
            "group_node_root.group_uid", "is_enabled", "owner_index",
        )),
        *(f"category_owner_deprecated.group_by.{name}_formula.{axis}"
          for name in groupByFormulas for axis in ("column", "row")),
        "conditional_style_formula_owner_id", "haunted_owner.owner_uid",
        "hidden_state_formula_owner_for_columns", "hidden_state_formula_owner_for_rows",
        "hidden_states_owner.owner_uid",
        "hidden_states_owner.hidden_states.hidden_states_uid",
        *(f"hidden_states_owner.hidden_states.{axis}_hidden_state_extent.{field}"
          for axis in ("column", "row") for field in hiddenExtentFields),
        "merge_owner.owner_id", "merge_owner.formula_store.next_formula_index",
        "pencil_annotation_owner.owner_id",
        "pencil_annotation_owner.formula_store.next_formula_index",
        "sort_order.type", "sort_rule_reference_tracker.reference_tracker",
        "spill_owner.owner_uid", "stroke_sidecar", "style_apply_clears_all",
        "table_name_height",
    }),
    "owner": ownerDependencies,
    "sheet": frozenset({
        "layout_direction", "page_order", "should_print_comments",
        "uses_single_header_footer", "userDefinedGuideStorage",
    }),
    # The page number Numbers puts in the center footer, which the reset leaves out.
    "footer-center": frozenset({
        "text", "table_attachment.entries.character_index",
        "table_attachment.entries.object",
    }),
}


def listFieldValues(message: Message, path: str = "") -> dict[str, object]:
    """Return every field a message holds by its path, a reference or UUID as a mark."""
    found: dict[str, object] = {}
    for descriptor, value in message.ListFields():
        name = f"{path}.{descriptor.name}" if path else descriptor.name
        if descriptor.message_type is None:
            found[name] = list(value) if descriptor.is_repeated else value
            continue
        items = list(value) if descriptor.is_repeated else [value]
        for position, item in enumerate(items):
            key = f"{name}[{position}]" if descriptor.is_repeated else name
            kind = descriptor.message_type.full_name
            if kind == "TSP.Reference":
                found[key] = "reference"
            elif kind in ("TSP.UUID", "TSP.CFUUIDArchive"):
                found[key] = "uuid"
            elif item.ListFields():
                found.update(listFieldValues(item, key))
            else:
                found[key] = "empty"
    return found


def findTableParts(index: ArchiveIndex, table: pybers.Table) -> dict[str, Message]:
    """Return every archive a table holds, and its owner of kind 1, by role."""
    info = index.resolve(
        tsp.Reference(identifier=table._identifier), tst.TableInfoArchive
    )
    model = index.resolve(info.tableModel, tst.TableModelArchive)
    store = model.base_data_store
    words = [int(table.identifier[at:at + 8], 16) for at in range(0, 32, 8)]
    base = words[0] | words[1] << 32 | words[2] << 64 | words[3] << 96
    owners = [
        owner for reference in
        findCalculationEngine(index).dependency_tracker.formula_owner_dependencies
        if (owner := index.resolve(reference, tsce.FormulaOwnerDependenciesArchive))
        .owner_kind == 1
        and owner.formula_owner_uid.upper << 64 | owner.formula_owner_uid.lower == base
    ]
    return {
        "info": info,
        "model": model,
        "tile": index.resolve(store.tiles.tiles[0].tile, tst.Tile),
        "rowHeaders": index.resolve(
            store.rowHeaders.buckets[0], tst.HeaderStorageBucket
        ),
        "columnHeaders": index.resolve(store.columnHeaders, tst.HeaderStorageBucket),
        "uids": index.resolve(model.base_column_row_uids, tst.ColumnRowUIDMapArchive),
        "owner": owners[0],
        **{
            field: index.resolve(getattr(store, field), tst.TableDataList)
            for field in storeLists
        },
    }


def findSheetParts(index: ArchiveIndex, position: int) -> dict[str, Message]:
    """Return a sheet and its six header and footer storages, by role."""
    sheet = index.resolve(findRoot(index).sheets[position], tn.SheetArchive)
    roles = [
        f"{kind}-{side}" for kind in ("header", "footer")
        for side in ("left", "center", "right")
    ]
    return {
        "sheet": sheet,
        **{
            role: index.resolve(reference, tswp.StorageArchive)
            for role, reference in zip(
                roles, [*sheet.headers, *sheet.footers], strict=True
            )
        },
    }


def readPartDifferences(
    composed: dict[str, Message], numbers: dict[str, Message]
) -> dict[str, tuple[set[str], set[str], set[str]]]:
    """Return, by role, the fields differing, held only by pybers, and left out."""
    found = {}
    for role, message in composed.items():
        mine, theirs = listFieldValues(message), listFieldValues(numbers[role])
        found[role] = (
            {path for path in mine if path in theirs and mine[path] != theirs[path]},
            {path for path in mine if path not in theirs},
            {re.sub(r"\[\d+\]", "", path) for path in theirs if path not in mine},
        )
    return found


@pytest.fixture(scope="module")
def created(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return `48-table-inserted` with a table and a sheet pybers created."""
    path = copyDocument("48-table-inserted", tmp_path_factory.mktemp("floor"))
    document = pybers.open(path)
    document.sheet(1).tableAdd("Table 1", rows=3, cols=4)
    document.sheetAdd("Sheet 2")
    document.save()
    return path


def testACreatedTableHoldsNumbersValuesAndOmitsOnlyWhatTheLadderFound(
    created: Path,
) -> None:
    mine = ArchiveIndex(readPackage(created))
    theirs = ArchiveIndex(readPackage(findDocumentPath("48-table-inserted")))

    differences = readPartDifferences(
        findTableParts(mine, pybers.open(created).sheet(1).tables[1]),
        findTableParts(
            theirs,
            pybers.open(findDocumentPath("48-table-inserted")).sheet(1).tables[0],
        ),
    )

    for role, (differing, extra, omitted) in differences.items():
        assert differing <= expectedDifferences.get(role, frozenset()), role
        assert extra == set(), role
        assert omitted == recordedOmissions.get(role, frozenset()), role


def testACreatedSheetHoldsNumbersValuesAndOmitsOnlyWhatTheLadderFound(
    created: Path,
) -> None:
    differences = readPartDifferences(
        findSheetParts(ArchiveIndex(readPackage(created)), 1),
        findSheetParts(
            ArchiveIndex(readPackage(findDocumentPath("49-sheet-inserted"))), 1
        ),
    )

    for role, (differing, extra, omitted) in differences.items():
        assert differing <= expectedDifferences.get(role, frozenset()), role
        assert extra == set(), role
        assert omitted == recordedOmissions.get(role, frozenset()), role


def testEveryCreatedArchiveCarriesItsRequiredFieldsAndNoFieldInfos(
    created: Path,
) -> None:
    source = max(
        ArchiveIndex(readPackage(findDocumentPath("48-table-inserted"))).byIdentifier
    )
    index = ArchiveIndex(readPackage(created))

    archives = [
        archive for identifier, archive in index.byIdentifier.items()
        if identifier > source
    ]

    assert len(archives) > 20
    for archive in archives:
        assert parseArchive(archive).IsInitialized(), archive.identifier
        info = tspArchive.ArchiveInfo()
        info.ParseFromString(archive.infoBytes)
        assert not info.message_infos[0].field_infos, archive.identifier
