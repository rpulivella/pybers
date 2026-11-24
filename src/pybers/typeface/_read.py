#!/usr/bin/env python3
"""\
The fonts a document names: every PostScript name its paragraph and character styles
hold, named styles, variations and the styles of runs of text alike.

A style stores its font as `char_properties.font_name`, and a variation that changes no
font leaves it unset, so each name a document uses appears in some style that sets it.

Private. The font feature's archive half, reached by `checkDocument`.

UPDATES
2026-11-24  Moved to the typeface feature, for PYB-318.
2026-11-24  Written for PYB-315.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"

from .._generated import TSWPArchives_pb2 as tswp
from .._persistence.index import ArchiveIndex
from .._persistence.types import findArchiveTypeId, readArchiveTypeId

# The style kinds whose character properties name a font, by archive type.
type StyleClass = type[tswp.ParagraphStyleArchive] | type[tswp.CharacterStyleArchive]
styleClasses: frozendict[int, StyleClass] = frozendict({
    findArchiveTypeId(each): each
    for each in (tswp.ParagraphStyleArchive, tswp.CharacterStyleArchive)
})


def listFontNames(index: ArchiveIndex) -> tuple[str, ...]:
    """Return every PostScript name a document's styles name, each once, sorted."""
    found: set[str] = set()
    for identifier, archive in index.byIdentifier.items():
        styleClass = styleClasses.get(readArchiveTypeId(archive))
        if styleClass is None:
            continue
        properties = index.identifierResolve(identifier, styleClass).char_properties
        if properties.font_name:
            found.add(properties.font_name)
    return tuple(sorted(found, key=str.casefold))


__all__ = ["listFontNames"]
