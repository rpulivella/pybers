#!/usr/bin/env python3
"""\
A document's language and region: the regions pybers offers, and what a change did.

A region is offered when the locale table holds its formatting symbols, read from
macOS's own ICU by `tools/local/locales_extract.py`, so a region pybers offers is one
it can write as Numbers writes it. See findings-12-language-and-region.md.

UPDATES
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

import difflib
from dataclasses import dataclass

from pybers._generated.locales import locales as localeTable
from pybers.errors import PybersError

locales: tuple[str, ...] = tuple(sorted(localeTable))

# How many offered regions a refusal suggests, closest first.
suggestionCount: int = 4


class LocaleError(PybersError, ValueError):
    """A language and region pybers does not offer."""


@dataclass(frozen=True, slots=True)
class LocaleChange:
    """What a region change did to a document, or would do in a preview."""

    localeBefore: str | None
    localeAfter: str

    @property
    def changed(self) -> bool:
        """Report whether the document's region changes."""
        return self.localeBefore != self.localeAfter


def findLocaleSymbols(identifier: object) -> frozendict[str, object]:
    """Return a region's formatting symbols, refusing one pybers does not offer."""
    if not isinstance(identifier, str) or identifier not in localeTable:
        shown = identifier if isinstance(identifier, str) else repr(identifier)
        # A region sharing the language asked for is the likeliest one meant.
        language = f"{str(identifier).partition('_')[0]}_"
        candidates = [each for each in locales if each.startswith(language)] or locales
        closest = difflib.get_close_matches(
            str(identifier), candidates, n=suggestionCount, cutoff=0
        )
        raise LocaleError(
            f"No region pybers offers is named {shown!r}. The closest of the "
            f"{len(locales)} it offers are {', '.join(repr(each) for each in closest)}."
        )
    symbols: frozendict[str, object] = localeTable[identifier]
    return symbols


__all__ = ["LocaleChange", "LocaleError", "findLocaleSymbols", "locales"]
