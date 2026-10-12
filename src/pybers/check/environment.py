#!/usr/bin/env python3
"""\
The versions a bug report needs: pybers, Python, protobuf and the system.

Each is read from the running Python, never by searching the computer.

UPDATES
2026-10-12  An uninstalled pybers reports its version as UNDETERMINED, for PYB-190.
2026-10-07  Written for PYB-169.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/07"

import platform
from importlib import metadata

from ..absence import UNDETERMINED
from .report import CheckEnvironment


def findPybersVersion() -> str | UNDETERMINED:
    """Return the installed pybers version, UNDETERMINED when it runs uninstalled."""
    try:
        return metadata.version("pybers")
    except metadata.PackageNotFoundError:
        return UNDETERMINED


def readCheckEnvironment() -> CheckEnvironment:
    """Return what pybers is running on."""
    return CheckEnvironment(
        pybersVersion=findPybersVersion(),
        pythonVersion=platform.python_version(),
        protobufVersion=metadata.version("protobuf"),
        operatingSystem=platform.platform(),
    )


__all__ = ["readCheckEnvironment"]
