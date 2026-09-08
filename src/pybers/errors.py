#!/usr/bin/env python3
"""\
Every error this library raises, rooted so that one `except` clause can be right.

`PybersError` is the base of all of them, which is the shape `requests`,
`sqlalchemy` and every PEP 249 database driver settled on: a caller wrapping
`pybers.open` in a `try` needs one name, and a library without one leaves them
catching `Exception` and swallowing their own bugs along with ours.

**Each error keeps the builtin base it already had**, so `ReferenceError` is still
a `ValueError` and `SelectionError` is still a `LookupError`. Adding a root rather
than replacing those is what keeps an existing `except ValueError` working, and it
is the same move `requests` makes so that its `JSONDecodeError` answers to both
names.

Only the two general ones live here. An error belonging to a feature lives with
that feature, because moving it here would put half of `formula` in a file named
for exceptions, and `pybers` re-exports them all so a caller sees one list.

UPDATES
2026-09-08  Written for #58, after finding that `ContainerError` escapes
            `pybers.open` on a file that is not a zip and was not exported,
            leaving `except Exception` as the only correct clause.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"


class PybersError(Exception):
    """Anything this library raises, and the one name a caller can always catch."""


class ReadError(PybersError, RuntimeError):
    """A `.numbers` document whose structure could not be walked."""


class WriteError(PybersError, RuntimeError):
    """A document that could not be written back to a package."""


__all__ = ["PybersError", "ReadError", "WriteError"]
