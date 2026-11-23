#!/usr/bin/env python3
"""\
A format's and a control's text form: its name, then each setting as a CSS declaration.

`percent; fraction-digits: 1` is what `pybers set --cell-format` reads and `pybers show`
prints, a format Automatic chose followed by `(automatic)`, and `slider; minimum: 0;
maximum: 100; increment: 1` what `--cell-control` reads. The JSON form carries the same
setting names as an object, so the two say the same thing in two notations.

UPDATES
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-10  A control's text form, `formatCellControl` and `parseCellControl`.
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
import typing
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import cast

from pybers._family import listFamilyMembers
from pybers.absence import UNDETERMINED
from pybers.errors import (
    PybersError,
    composeChoiceRefusal,
    composeRefusal,
    formatChoiceList,
)
from pybers.format.controls import (
    CellControl,
    CellControlBase,
    CellControlType,
    CellControlUnknown,
)
from pybers.format.formats import (
    CellFormat,
    CellFormatAutomatic,
    CellFormatBase,
    CellFormatFamily,
    CellFormatShown,
    CellFormatUnknown,
)

automaticSuffix: str = " (automatic)"
# Each shown format a text form can specify, by its family, every one pybers builds.
type CellFormatBuild = Callable[[], CellFormatShown]
shownMembers: tuple[type[CellFormatBase], ...] = cast(
    tuple[type[CellFormatBase], ...], listFamilyMembers(CellFormatShown)
)
formatsByFamily: frozendict[CellFormatFamily, CellFormatBuild] = frozendict({
    member.formatFamily: cast(CellFormatBuild, member)
    for member in shownMembers if member is not CellFormatUnknown
})
controlMembers: tuple[type[CellControlBase], ...] = cast(
    tuple[type[CellControlBase], ...], listFamilyMembers(CellControl)
)
controlsByType: frozendict[CellControlType, type[CellControlBase]] = frozendict({
    member.controlType: member for member in controlMembers
    if member is not CellControlUnknown
})
camelBoundary: re.Pattern[str] = re.compile(r"(?<!^)(?=[A-Z])")
quotedItems: re.Pattern[str] = re.compile(r'\s*"((?:[^"\\]|\\.)*)"\s*(?:,|$)')


class CellFormatError(PybersError, ValueError):
    """A format's text form specifies no family or setting a format has."""


class CellControlError(PybersError, ValueError):
    """A control's text form specifies no control or setting a control has."""


def splitDeclarations(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Return a text form's leading name and each `name: value`, a quoted `;` kept."""
    parts, current, quoted, escaped = [], "", False, False
    for character in text:
        if character == ";" and not quoted:
            parts.append(current)
            current = ""
            continue
        current += character
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = quoted
        elif character == '"':
            quoted = not quoted
    head, *declarations = [part.strip() for part in [*parts, current]]
    return head, [
        (name.strip(), value.strip())
        for name, _, value in (each.partition(":") for each in declarations)
    ]


def refuseSetting[ErrorType: PybersError](
    errorType: type[ErrorType], given: str, owner: str, settings: list[str]
) -> ErrorType:
    """Return the refusal of a setting a format or a control does not take."""
    if not settings:
        return errorType(composeRefusal(
            repr(given), f"is not a setting of {owner}, which takes none", "Remove it"
        ))
    return composeChoiceRefusal(errorType, given, f"a setting of {owner}", settings)


def formatSettingName(field: str) -> str:
    """Return a setting's field as the text form writes it, `fraction-digits`."""
    return camelBoundary.sub("-", field).lower()


def formatCellFormat(cellFormat: CellFormat | UNDETERMINED) -> str:
    """Return a format as its text form, `(automatic)` after one Automatic chose."""
    if cellFormat is UNDETERMINED:
        return "unknown"
    if isinstance(cellFormat, CellFormatAutomatic):
        return formatCellFormat(cellFormat.computed) + automaticSuffix
    declarations = [
        f"{formatSettingName(each.name)}: "
        f"{'none' if (setting := getattr(cellFormat, each.name)) is None else setting}"
        for each in dataclasses.fields(cellFormat) if each.compare
    ]
    return "; ".join([cellFormat.formatFamily.value, *declarations])


def parseCellFormatShown(text: str) -> CellFormatShown:
    """Return the shown format a text form specifies, refusing what it cannot build."""
    family, declarations = splitDeclarations(text)
    member = next(
        (each for named, each in formatsByFamily.items() if named.value == family), None
    )
    if member is None:
        raise composeChoiceRefusal(
            CellFormatError, family, "a format family",
            ["automatic", *(each.value for each in formatsByFamily)],
        )
    shown = member()
    if declarations:
        settings = [formatSettingName(each.name) for each in dataclasses.fields(shown)]
        raise refuseSetting(CellFormatError, declarations[0][0], family, settings)
    return shown


def parseCellFormat(text: str) -> CellFormat:
    """Return the format a text form specifies, `automatic` or a family and settings.

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


def formatControlSetting(setting: object) -> str:
    """Return one setting of a control as its text form writes it."""
    if isinstance(setting, bool):
        return "yes" if setting else "no"
    if isinstance(setting, tuple):
        escaped = (item.replace("\\", "\\\\").replace('"', '\\"') for item in setting)
        return ", ".join(f'"{item}"' for item in escaped)
    return str(setting)


def formatCellControl(control: CellControl) -> str:
    """Return a control as its text form, its type then each setting it holds."""
    declarations = [
        f"{formatSettingName(each.name)}: "
        f"{formatControlSetting(getattr(control, each.name))}"
        for each in dataclasses.fields(control) if each.compare
    ]
    return "; ".join([control.controlType.value, *declarations])


def parseControlSetting(where: str, declared: object, text: str) -> object:
    """Return one setting of a control read from its text, refusing what it is not."""
    if declared is bool and text in ("yes", "no"):
        return text == "yes"
    if declared is Decimal:
        try:
            return Decimal(text)
        except InvalidOperation as exc:
            raise CellControlError(composeRefusal(
                repr(text), f"is not a number, and {where} takes one"
            )) from exc
    if typing.get_origin(declared) is tuple:
        items = quotedItems.findall(text)
        if "".join(quotedItems.split(text)[::2]).strip() == "" and items:
            return tuple(re.sub(r"\\(.)", r"\1", item) for item in items)
        raise CellControlError(composeRefusal(
            repr(text), f"is not a list of quoted items, and {where} takes one",
            'Write it as `"Low", "High"`',
        ))
    kind = "yes or no" if declared is bool else "a value"
    raise CellControlError(
        composeRefusal(repr(text), f"is not {kind}, and {where} takes {kind}")
    )


def parseCellControl(text: str) -> CellControl | None:
    """Return the control a text form specifies, or None for `none`, no control."""
    name, declarations = splitDeclarations(text)
    if name == "none" and not declarations:
        return None
    member = next(
        (each for kind, each in controlsByType.items() if kind.value == name), None
    )
    if member is None:
        raise composeChoiceRefusal(
            CellControlError, name, "a control",
            ["none", *(kind.value for kind in controlsByType)],
        )
    assert dataclasses.is_dataclass(member)
    hints = typing.get_type_hints(member)
    settings = {
        formatSettingName(each.name): each.name
        for each in dataclasses.fields(member) if each.compare
    }
    given: dict[str, object] = {}
    for setting, value in declarations:
        field = settings.get(setting)
        if field is None:
            raise refuseSetting(CellControlError, setting, name, list(settings))
        given[field] = parseControlSetting(f"{name} {setting}", hints[field], value)
    missing = [setting for setting, field in settings.items() if field not in given]
    if missing:
        raise CellControlError(composeRefusal(
            f"A {name} control", f"needs {formatChoiceList(missing)}",
            f"Write each as `{missing[0]}: value`",
        ))
    return cast(CellControl, member(**given))


__all__ = [
    "CellControlError", "CellFormatError", "formatCellControl", "formatCellFormat",
    "parseCellControl", "parseCellFormat",
]
