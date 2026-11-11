#!/usr/bin/env python3
"""\
What Numbers changed in each cell of a golden when it opened and saved a copy.

A cell Numbers corrects on opening, such as a duration format whose units disagree
with its value, keeps the correction when the copy is saved, so reading both files
cell by cell names it where the archive count alone cannot. Each cell is compared on
what pybers models and on the format entry and control behind it, since an entry can
change in a field no model holds yet. A formula's value, kind and format are left to
Numbers, which recalculates them.

UPDATES
2026-11-10  Written for PYB-145, after a chip Numbers drew on a golden went unreported.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/10"

from dataclasses import dataclass, fields
from pathlib import Path

import pybers
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import readPackage
from pybers._persistence.cells import (
    CellRecord,
    countedFormatSlots,
    displayedKindSlot,
    findSlotValue,
)
from pybers._persistence.index import ArchiveIndex, findRoot
from pybers._persistence.types import findArchiveTypeId
from pybers.format._read import findWaitingFormatKey
from pybers.table._read import iterateCellRecords

type SavedAddress = tuple[str, str, str]
tableInfoTypeId: int = findArchiveTypeId(tst.TableInfoArchive)


@dataclass(frozen=True, slots=True)
class SavedCell:
    """One cell as a file stores it, each field as text to compare and to report."""

    value: str
    kind: str
    formula: str
    format: str
    control: str
    formatEntry: frozendict[str, str]


def readFormatEntryFields(entry: object) -> frozendict[str, str]:
    """Return each field a format entry sets, by name, its value as text."""
    listed = getattr(entry, "ListFields", None)
    if listed is None:
        return frozendict()
    return frozendict({field.name: str(value) for field, value in listed()})


def findDisplayedFormatKey(record: CellRecord) -> int | None:
    """Return the key of the format entry a record displays with, or None for none."""
    displayed = findSlotValue(record, displayedKindSlot)
    if displayed is None:
        return findWaitingFormatKey(record)
    if not 1 <= displayed <= len(countedFormatSlots):
        return None
    return findSlotValue(record, countedFormatSlots[displayed - 1])


def readSavedCell(cell: pybers.Cell, entry: object) -> SavedCell:
    """Return a cell's fields as text, its format entry beside its model."""
    shown = cell.presentation
    return SavedCell(
        value=pybers.formatCellValue(cell.value), kind=cell.kind.value,
        formula=cell.formulaText or "none",
        format="none" if shown.format is None
        else pybers.formatCellFormat(shown.format),
        control="none" if shown.control is None
        else pybers.formatCellControl(shown.control),
        formatEntry=readFormatEntryFields(entry),
    )


def readSavedCells(path: Path) -> dict[SavedAddress, SavedCell]:
    """Return every cell a file stores a record for, by sheet, table and address."""
    document = pybers.open(path)
    index = ArchiveIndex(readPackage(path))
    cells: dict[SavedAddress, SavedCell] = {}
    for sheetReference in findRoot(index).sheets:
        sheetArchive = index.resolve(sheetReference, tn.SheetArchive)
        for drawable in sheetArchive.drawable_infos:
            if index.typeOf(drawable) != tableInfoTypeId:
                continue
            info = index.resolve(drawable, tst.TableInfoArchive)
            model = index.resolve(info.tableModel, tst.TableModelArchive)
            table = document.sheet(sheetArchive.name).table(model.table_name)
            store = model.base_data_store
            formats = (
                {entry.key: entry.format for entry in index.resolve(
                    store.format_table, tst.TableDataList).entries}
                if store.format_table.identifier else {}
            )
            for address, record in iterateCellRecords(index, model, path):
                if not table.addressable(address):
                    continue
                key = findDisplayedFormatKey(record)
                where = (sheetArchive.name, model.table_name, str(address))
                cells[where] = readSavedCell(
                    table.cell(address), None if key is None else formats.get(key)
                )
    return cells


def listCellChanges(written: SavedCell, saved: SavedCell) -> list[str]:
    """Return each field Numbers changed in one cell, its formula's results left out.

    A formula's value and kind are Numbers' to recalculate, and so is its format while
    Automatic picks it, but a format pybers chose for it must survive.
    """
    automatic = written.format == "none" or written.format.endswith("(automatic)")
    recalculated = (
        set() if written.formula == "none"
        else {"value", "kind", "format", "formatEntry"} if automatic
        else {"value", "kind"}
    )
    changed = [
        f"{field.name} {getattr(written, field.name)!r} became "
        f"{getattr(saved, field.name)!r}"
        for field in fields(SavedCell)
        if field.name not in recalculated | {"formatEntry"}
        and getattr(written, field.name) != getattr(saved, field.name)
    ]
    if "formatEntry" in recalculated:
        return changed
    before, after = written.formatEntry, saved.formatEntry
    return changed + [
        f"format entry {name} {before.get(name, 'unset')} became "
        f"{after.get(name, 'unset')}"
        for name in sorted(before.keys() | after.keys())
        if before.get(name) != after.get(name)
    ]


def readSavedCellChanges(golden: Path, saved: Path) -> dict[SavedAddress, list[str]]:
    """Return each cell Numbers changed when it saved a golden, and what it changed."""
    written, after = readSavedCells(golden), readSavedCells(saved)
    changes: dict[SavedAddress, list[str]] = {}
    for address in sorted(written.keys() | after.keys()):
        before, now = written.get(address), after.get(address)
        if before is None or now is None:
            held = before or now
            assert held is not None
            if held.value != "" or held.control != "none":
                changes[address] = [
                    "Numbers added a record" if before is None
                    else "Numbers removed its record"
                ]
            continue
        found = listCellChanges(before, now)
        if found:
            changes[address] = found
    return changes


__all__ = ["SavedCell", "listCellChanges", "readSavedCellChanges", "readSavedCells"]
