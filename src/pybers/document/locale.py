#!/usr/bin/env python3
"""\
A document's language and region: the regions pybers offers, and what a change did.

A region is offered when the locale table holds its formatting symbols, read from
macOS's own ICU by `tools/local/locales_extract.py`, so a region pybers offers is one
it can write as Numbers writes it. See findings-12-language-and-region.md.

UPDATES
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-10-28  Written for PYB-272.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/28"

from dataclasses import dataclass

from pybers._generated.locales import locales as localeTable
from pybers.errors import PybersError, composeChoiceRefusal, nothingWritten

locales: tuple[str, ...] = tuple(sorted(localeTable))


class LocaleError(PybersError, ValueError):
    """A language and region pybers does not offer."""


@dataclass(frozen=True, slots=True)
class LocaleChange:
    """What a region change did to a document."""

    localeBefore: str | None
    localeAfter: str

    @property
    def changed(self) -> bool:
        """Report whether the document's region changes."""
        return self.localeBefore != self.localeAfter


def findLocaleSymbols(identifier: object) -> frozendict[str, object]:
    """Return a region's formatting symbols, refusing one pybers does not offer."""
    if not isinstance(identifier, str) or identifier not in localeTable:
        # A region sharing the language asked for is the likeliest one meant.
        language = f"{str(identifier).partition('_')[0]}_"
        candidates = [each for each in locales if each.startswith(language)] or locales
        raise composeChoiceRefusal(
            LocaleError, identifier, "a region pybers offers", candidates,
            nothingWritten,
        )
    symbols: frozendict[str, object] = localeTable[identifier]
    return symbols


__all__ = ["LocaleChange", "LocaleError", "findLocaleSymbols", "locales"]
