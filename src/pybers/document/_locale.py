#!/usr/bin/env python3
"""\
A document's language and region, written into its archive as Numbers writes them.

A changed region rewrites `TSK.DocumentArchive`: its locale identifier, whether a person
chose it, and every field of its formatting symbols, each composed from the locale
table rather than copied from another document. `TSA.DocumentArchive` takes the
language's code. A result such as `DOLLAR` depends on the region, and Numbers does not
recalculate on open, so the save marks every formula. See
findings-12-language-and-region.md.

Private. The locale's archive half, beside `locale`.

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

from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSKArchives_pb2 as tsk
from pybers._persistence.index import ArchiveIndex, findRootIdentifier
from pybers.document.locale import findLocaleSymbols
from pybers.document.sheets import Document


def checkLocaleChanged(document: Document, root: tn.DocumentArchive) -> bool:
    """Report whether the model's region differs from the one the archive holds."""
    wanted = document.localeIdentifier
    return wanted is not None and wanted != root.super.super.locale_identifier


def buildFormattingSymbols(identifier: str) -> tsk.FormattingSymbolsArchive:
    """Return a region's formatting symbols, each field built from the locale table."""
    composed = tsk.FormattingSymbolsArchive()
    for name, value in findLocaleSymbols(identifier).items():
        if name == "currency_symbols":
            assert isinstance(value, tuple)
            for code, symbol in value:
                composed.currency_symbols.add(code=code, symbol=symbol)
        elif isinstance(value, tuple):
            getattr(composed, name).extend(value)
        else:
            setattr(composed, name, value)
    return composed


def writeLocale(document: Document, index: ArchiveIndex) -> bool:
    """Write the model's region into the document archive, reporting whether it did."""
    rootIdentifier = findRootIdentifier(index)
    root = index.identifierResolve(rootIdentifier, tn.DocumentArchive)
    if not checkLocaleChanged(document, root):
        return False
    identifier = document.localeIdentifier
    assert identifier is not None
    locale = root.super.super
    locale.locale_identifier = identifier
    locale.has_user_defined_locale = True
    locale.formatting_symbols.CopyFrom(buildFormattingSymbols(identifier))
    root.super.document_language = identifier.partition("_")[0]
    index.archiveWrite(rootIdentifier, root)
    return True


__all__ = ["buildFormattingSymbols", "writeLocale"]
