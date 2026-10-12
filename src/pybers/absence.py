#!/usr/bin/env python3
"""\
The reasons a value can be missing, beyond there being nothing to hold.

`None` means nothing exists. A sentinel here means something exists, or will, and
pybers does not have it, and names why. Each one earns its place only where a caller
acts differently on that reason, which is why there are three and not one per case.

Defined once and compared by identity, so a second definition anywhere would never
match the first. Every feature imports them from here.

UPDATES
2026-10-12  Written for PYB-190.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/12"

# Unannotated, because mypy accepts a sentinel as a type only in this exact form.
NOT_REQUESTED = sentinel("NOT_REQUESTED")
UNDETERMINED = sentinel("UNDETERMINED")
WITHHELD = sentinel("WITHHELD")

__all__ = ["NOT_REQUESTED", "UNDETERMINED", "WITHHELD"]
