#!/usr/bin/env python3
"""\
Whether a cell's control can show a value, read from the control's own spec.

Numbers clamps a number outside a range control and drops a pop-up menu from text that
is none of its items, measured in `73-values-typed-over-controls`. pybers never clamps,
since a value reads back as written, so a control that cannot show a value is dropped.

Private. Part of the table feature's archive half.

UPDATES
2026-10-20  Written for PYB-144.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/20"

from decimal import Decimal

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSTArchives_pb2 as tst
from .._persistence.index import ArchiveIndex
from .cell import CellValue

# The interaction types of the stepper, slider and star rating in
# `11-value-types-noformats`, each bounded by the spec's range.
rangeInteractions: frozenset[int] = frozenset({4, 5, 6})
popUpInteraction: int = 7
# The item kinds a pop-up menu in the documents holds: its blank choice and text.
measuredItemTypes: frozenset[int] = frozenset({
    tsce.CellValueArchive.NIL_TYPE, tsce.CellValueArchive.STRING_TYPE,
})


def checkControlShows(
    index: ArchiveIndex, controls: tst.TableDataList, key: int, value: CellValue
) -> bool:
    """Report whether the control a key specifies can show a value of its own kind.

    A control or an item kind no document has measured is taken to show it, so
    pybers drops only a control the documents prove cannot.
    """
    entry = next((each for each in controls.entries if each.key == key), None)
    if entry is None:
        return True
    spec = entry.cell_spec
    if spec.interaction_type in rangeInteractions and isinstance(value, Decimal):
        return (
            Decimal(spec.range_control_min) <= value <= Decimal(spec.range_control_max)
        )
    if spec.interaction_type == popUpInteraction and isinstance(value, str):
        items = index.resolve(spec.chooser_control_popup_model, tst.PopUpMenuModel)
        kinds = {item.cell_value_type for item in items.tsce_item}
        if not kinds <= measuredItemTypes:
            return True
        return value in {
            item.string_value.value for item in items.tsce_item
            if item.cell_value_type == tsce.CellValueArchive.STRING_TYPE
        }
    return True


__all__ = ["checkControlShows"]
