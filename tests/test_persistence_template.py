#!/usr/bin/env python3
"""\
Archive templates: reading one, and refusing a copy that would name a missing object.

The sheet templates are the real set these run against, so a template that stops
parsing, or a binding that stops covering what they reference, fails here by name
rather than as a sheet Numbers will not open.

UPDATES
2026-09-14  Written for PYB-63.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/14"

from pathlib import Path

import pytest

from conftest import findDocumentPath
from pybers._generated import TNArchives_pb2 as tn
from pybers._persistence import PackageRegistry, readPackage
from pybers._persistence.template import (
    TemplateError,
    templateRead,
    templatesCopy,
    templatesRead,
)
from pybers.document._create import (
    sheetTemplateDirectory,
    templateListStyle,
    templateParagraphStyle,
    templateSheetStyle,
    templateStylesheet,
)

documentBindings: dict[int, int] = {
    templateSheetStyle: templateSheetStyle,
    templateStylesheet: templateStylesheet,
    templateParagraphStyle: templateParagraphStyle,
    templateListStyle: templateListStyle,
}


def readRegistry() -> PackageRegistry:
    """Return the registry of `49-sheet-inserted`, the sheet templates' source."""
    return PackageRegistry(readPackage(findDocumentPath("49-sheet-inserted")))


def testTheSheetTemplatesReadAsOneSheetAndItsSevenParts() -> None:
    templates = templatesRead(sheetTemplateDirectory)

    assert [template.role for template in templates] == [
        "sheet",
        "guides",
        "header-left",
        "header-center",
        "header-right",
        "footer-left",
        "footer-center",
        "footer-right",
    ]
    assert isinstance(templates[0].body, tn.SheetArchive)
    assert {template.component for template in templates} == {"Document"}


def testACopyRemapsEveryReferenceToAFreshIdentifier() -> None:
    found = readRegistry()
    highest = found.metadata.last_object_identifier

    copies = templatesCopy(
        found, templatesRead(sheetTemplateDirectory), documentBindings
    )

    sheet = copies["sheet"].body
    assert isinstance(sheet, tn.SheetArchive)
    parts = [reference.identifier for reference in [*sheet.headers, *sheet.footers]]
    assert all(identifier > highest for identifier in parts)
    assert sheet.style.identifier == templateSheetStyle


def testAnUnboundReferenceIsRefusedBeforeAnythingIsAllocated() -> None:
    found = readRegistry()
    highest = found.metadata.last_object_identifier
    partial = {templateSheetStyle: templateSheetStyle}

    with pytest.raises(TemplateError, match="neither in the template set nor bound"):
        templatesCopy(found, templatesRead(sheetTemplateDirectory), partial)
    assert found.metadata.last_object_identifier == highest


def testARoleNoTemplatePlaysIsRefusedNamingTheRoles() -> None:
    copies = templatesCopy(
        readRegistry(), templatesRead(sheetTemplateDirectory), documentBindings
    )

    with pytest.raises(TemplateError, match="the roles are"):
        copies["table"]


def testATemplateThatDoesNotNameItsComponentIsRefused(tmp_path: Path) -> None:
    path = tmp_path / "01-sheet.txtpb"
    path.write_text('name: "Sheet"\n', encoding="utf-8")

    with pytest.raises(TemplateError, match="naming its component"):
        templateRead(path)


def testADirectoryWithoutTemplatesIsRefused(tmp_path: Path) -> None:
    with pytest.raises(TemplateError, match="holds no templates"):
        templatesRead(tmp_path)
