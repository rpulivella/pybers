#!/usr/bin/env python3
"""\
A cell's control read from its spec, as the model names it.

Private. Part of the table feature's archive half.

UPDATES
2026-10-22  Each control read as the model names it, and whether one shows a value
            answered by the control itself, for PYB-255.
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
from .controls import (
    CellControl,
    CellControlCheckbox,
    CellControlPopUpMenu,
    CellControlSlider,
    CellControlStarRating,
    CellControlStepper,
    CellControlUnknown,
)

# The interaction types measured in `81-control-formats`.
stepperInteraction: int = 4
sliderInteraction: int = 5
starRatingInteraction: int = 6
popUpInteraction: int = 7
checkboxInteraction: int = 8


def readRangeBound(bound: float) -> Decimal:
    """Return a range bound as the decimal Numbers shows, 100 rather than 100.0."""
    exact = Decimal(repr(bound))
    return exact.quantize(Decimal(1)) if exact == exact.to_integral_value() else exact


def readPopUpMenu(index: ArchiveIndex, spec: tst.CellSpecArchive) -> CellControl:
    """Return a pop-up menu, or an unknown control when it holds an unmeasured item.

    Every measured menu lists its blank choice first, then its text items.
    """
    model = index.resolve(spec.chooser_control_popup_model, tst.PopUpMenuModel)
    entries = list(model.tsce_item)
    blank, *items = entries or [None]
    if blank is None or blank.cell_value_type != tsce.CellValueArchive.NIL_TYPE or any(
        item.cell_value_type != tsce.CellValueArchive.STRING_TYPE for item in items
    ):
        return CellControlUnknown(spec.interaction_type)
    return CellControlPopUpMenu(
        tuple(item.string_value.value for item in items),
        spec.chooser_control_start_w_first,
    )


def readControl(index: ArchiveIndex, spec: tst.CellSpecArchive) -> CellControl:
    """Return the control one cell spec describes."""
    kind = spec.interaction_type
    if kind in (sliderInteraction, stepperInteraction):
        bounds = (readRangeBound(spec.range_control_min),
                  readRangeBound(spec.range_control_max),
                  readRangeBound(spec.range_control_inc))
        if kind == sliderInteraction:
            return CellControlSlider(*bounds)
        return CellControlStepper(*bounds)
    if kind == popUpInteraction:
        return readPopUpMenu(index, spec)
    if kind == checkboxInteraction:
        return CellControlCheckbox()
    if kind == starRatingInteraction:
        return CellControlStarRating()
    return CellControlUnknown(kind)


def readControls(index: ArchiveIndex, store: tst.DataStore) -> dict[int, CellControl]:
    """Return every control a table's data store holds, by the key a record names."""
    if not store.HasField("control_cell_spec_table"):
        return {}
    controls = index.resolve(store.control_cell_spec_table, tst.TableDataList)
    return {each.key: readControl(index, each.cell_spec) for each in controls.entries}


__all__ = ["readControls"]
