#!/usr/bin/env python3
"""\
What more than one tooling script needs, implemented once.

Imported by every tool under `tools/`, including the job that posts
the readiness comment, which installs rich alone. Nothing here may need more than the
standard library and rich.

UPDATES
2026-10-13  Written for PYB-204.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/13"

import argparse
import re
from pathlib import Path

try:
    from rich_argparse import RichHelpFormatter
except ImportError:  # the readiness posting job installs rich alone
    RichHelpFormatter = argparse.HelpFormatter  # type: ignore[assignment,misc]

__all__ = ["RichHelpFormatter", "readTicketNumber", "repositoryRoot"]

repositoryRoot: Path = Path(__file__).resolve().parents[3]

ticketBranchPattern: re.Pattern[str] = re.compile(r"^[a-z]+/(\d+)-")


def readTicketNumber(branch: str) -> str:
    """Return the ticket number a `<type>/<N>-<title>` branch carries, or ''."""
    match = ticketBranchPattern.match(branch)
    return match.group(1) if match else ""
