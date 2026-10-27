#!/usr/bin/env python3
"""\
A document's language and region, as the measurements of `95-region-base` record them.

Each `95` measurement is the base with only Language & Region changed in Numbers, and
`72b-date-time-zones-region` is the earlier English (Italy) document.

UPDATES
2026-10-27  Written for PYB-272.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/27"

import pytest

import pybers
from conftest import findDocumentPath


@pytest.mark.parametrize(("stem", "locale"), [
    ("95-region-base", "en_US"),
    ("95b-region-de-de", "de_DE"),
    ("95c-region-en-gb", "en_GB"),
    ("95d-region-language-english", "en_US"),
    ("95e-region-ja-jp", "ja_JP"),
    ("95f-region-en-za", "en_ZA"),
    ("95g-region-pt-br", "pt_BR"),
    ("95h-region-en-au", "en_AU"),
    ("95i-region-en-in", "en_IN"),
    ("72b-date-time-zones-region", "en_IT"),
])
def testADocumentReportsTheLocaleNumbersSavedItUnder(stem: str, locale: str) -> None:
    assert pybers.open(findDocumentPath(stem)).localeIdentifier == locale


def testADocumentBuiltInMemoryHasNoLocale() -> None:
    assert pybers.Document().localeIdentifier is None


def testTheLocaleIsReadOnly() -> None:
    document = pybers.open(findDocumentPath("95-region-base"))
    with pytest.raises(AttributeError):
        document.localeIdentifier = "de_DE"  # type: ignore[misc]
