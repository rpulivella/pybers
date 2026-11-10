#!/usr/bin/env python3
"""\
A format's text form: its family, then each setting as a CSS declaration.

`percent; fraction-digits: 1` is what `pybers set --cell-format` reads and `pybers show`
prints, a format Automatic chose followed by `(automatic)`. The JSON form carries the
same setting names as an object, so the two say the same thing in two notations.

UPDATES
2026-11-10  Written for PYB-145.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/10"

import dataclasses
import re
from collections.abc import Callable
from typing import cast

from pybers._family import listFamilyMembers
from pybers.absence import UNDETERMINED
from pybers.errors import PybersError
from pybers.format.formats import (
    CellFormat,
    CellFormatAutomatic,
    CellFormatBase,
    CellFormatFamily,
    CellFormatShown,
    CellFormatUnknown,
)

automaticSuffix: str = " (automatic)"
# Each shown format a text form can name, by its family, every one pybers can build.
type CellFormatBuild = Callable[[], CellFormatShown]
shownMembers: tuple[type[CellFormatBase], ...] = cast(
    tuple[type[CellFormatBase], ...], listFamilyMembers(CellFormatShown)
)
formatsByFamily: frozendict[CellFormatFamily, CellFormatBuild] = frozendict({
    member.formatFamily: cast(CellFormatBuild, member)
    for member in shownMembers if member is not CellFormatUnknown
})
camelBoundary: re.Pattern[str] = re.compile(r"(?<!^)(?=[A-Z])")


class CellFormatError(PybersError, ValueError):
    """A format's text form names no family or setting a format has."""


def formatSettingName(field: str) -> str:
    """Return a setting's field as the text form writes it, `fraction-digits`."""
    return camelBoundary.sub("-", field).lower()


def formatCellFormat(cellFormat: CellFormat | UNDETERMINED) -> str:
    """Return a format as its text form, `(automatic)` after one Automatic chose."""
    if cellFormat is UNDETERMINED:
        return "unknown"
    if isinstance(cellFormat, CellFormatAutomatic):
        return formatCellFormat(cellFormat.shown) + automaticSuffix
    declarations = [
        f"{formatSettingName(each.name)}: "
        f"{'none' if (setting := getattr(cellFormat, each.name)) is None else setting}"
        for each in dataclasses.fields(cellFormat) if each.compare
    ]
    return "; ".join([cellFormat.formatFamily.value, *declarations])


def parseCellFormatShown(text: str) -> CellFormatShown:
    """Return the shown format a text form names, refusing what it cannot build."""
    family, *declarations = [part.strip() for part in text.split(";")]
    member = next(
        (each for named, each in formatsByFamily.items() if named.value == family), None
    )
    if member is None:
        known = ", ".join(["automatic", *(each.value for each in formatsByFamily)])
        raise CellFormatError(f"{family!r} is no format family. Use one of: {known}.")
    shown = member()
    if declarations:
        settings = [formatSettingName(each.name) for each in dataclasses.fields(shown)]
        takes = f"takes {', '.join(settings)}" if settings else "takes no settings"
        name = declarations[0].split(":", 1)[0].strip()
        raise CellFormatError(f"{family} has no setting {name!r}; it {takes}.")
    return shown


def parseCellFormat(text: str) -> CellFormat:
    """Return the format a text form names, `automatic` or a family and its settings.

    A format Automatic chose, as `pybers show` prints it, reads back as that Automatic,
    and `unknown (automatic)` as one whose pick a save has yet to make.
    """
    form = text.strip()
    if form == CellFormatFamily.AUTOMATIC.value:
        return CellFormatAutomatic()
    if form.endswith(automaticSuffix):
        shown = form.removesuffix(automaticSuffix).strip()
        if shown == "unknown":
            return CellFormatAutomatic()
        return CellFormatAutomatic(parseCellFormatShown(shown))
    return parseCellFormatShown(form)


__all__ = ["CellFormatError", "formatCellFormat", "parseCellFormat"]
