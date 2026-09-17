#!/usr/bin/env python3
"""\
Write the .xlsx that `22e-merge-imported.numbers` is converted from.

Excel stores a `<c>` element for every cell of a merged range, and a covered one
carries a style attribute with no value. Numbers keeps each of them on import
and across every later edit, which is the ONLY route to a record at a covered
position: its own merge command discards them under every gesture tried. See
docs/findings/findings-03-structure.md.

`G1` deliberately carries both a style and a value, which Numbers discards on
import. That is what establishes that a covered record never holds a value.

The XML is wrapped between attributes, where whitespace is insignificant, so
what a parser sees is unaffected by the line breaks.

UPDATES
2026-09-07  Written for #49.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/07"
__usage__ = (
    "python3 tests/fixtures/22e-merge-imported.py, then open the .xlsx in "
    "Numbers and Save As 22e-merge-imported.numbers"
)

import zipfile
from pathlib import Path

target: Path = Path(__file__).with_suffix(".xlsx")

package: str = "http://schemas.openxmlformats.org/package/2006/relationships"
document: str = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
spreadsheet: str = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
officeDocument: str = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml"
)

contentTypes: str = f"""<?xml version="1.0" encoding="UTF-8"?>
<Types
 xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels"
 ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml"
 ContentType="{officeDocument}.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml"
 ContentType="{officeDocument}.worksheet+xml"/>
<Override PartName="/xl/styles.xml"
 ContentType="{officeDocument}.styles+xml"/>
</Types>"""

rootRelationships: str = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="{package}">
<Relationship Id="rId1" Target="xl/workbook.xml"
 Type="{document}/officeDocument"/>
</Relationships>"""

workbook: str = f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="{spreadsheet}" xmlns:r="{document}">
<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""

workbookRelationships: str = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="{package}">
<Relationship Id="rId1" Target="worksheets/sheet1.xml"
 Type="{document}/worksheet"/>
<Relationship Id="rId2" Target="styles.xml" Type="{document}/styles"/>
</Relationships>"""

# Style 1 is a yellow fill and style 2 a blue one. A covered cell references one
# of them and holds no value, which is exactly the shape Excel writes.
styles: str = f"""<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="{spreadsheet}">
<fonts count="1"><font><sz val="12"/><name val="Calibri"/></font></fonts>
<fills count="4">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid">
<fgColor rgb="FFFFE699"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid">
<fgColor rgb="FFBDD7EE"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="1">
<border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1"/>
<xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/>
</cellXfs>
</styleSheet>"""


def text(reference: str, style: int, value: str) -> str:
    """Return one inline-string cell."""
    return f'<c r="{reference}" s="{style}" t="inlineStr"><is><t>{value}</t></is></c>'


def shell(reference: str, style: int) -> str:
    """Return one covered cell: a style and no value, as Excel writes it."""
    return f'<c r="{reference}" s="{style}"/>'


rowOne: str = (
    text("A1", 1, "two wide, anchor")
    + shell("B1", 1)
    + text("C1", 2, "three wide, anchor")
    + shell("D1", 2)
    + shell("E1", 2)
    + text("F1", 1, "covered holds a value, anchor")
    + text("G1", 1, "covered value that Numbers never shows")
)

rowTwo: str = "".join(
    text(reference, 0, label)
    for reference, label in (
        ("A2", "A1:B1 merged in Excel, B1 carries a style and no value"),
        ("C2", "C1:E1 merged in Excel, D1 and E1 carry a style and no value"),
        ("F2", "F1:G1 merged in Excel, G1 carries a style AND a value"),
    )
)

sheet: str = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{spreadsheet}">
<dimension ref="A1:G2"/>
<sheetData><row r="1">{rowOne}</row><row r="2">{rowTwo}</row></sheetData>
<mergeCells count="3">
<mergeCell ref="A1:B1"/><mergeCell ref="C1:E1"/><mergeCell ref="F1:G1"/>
</mergeCells>
</worksheet>"""

parts: dict[str, str] = {
    "[Content_Types].xml": contentTypes,
    "_rels/.rels": rootRelationships,
    "xl/workbook.xml": workbook,
    "xl/_rels/workbook.xml.rels": workbookRelationships,
    "xl/styles.xml": styles,
    "xl/worksheets/sheet1.xml": sheet,
}

if __name__ == "__main__":
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in parts.items():
            archive.writestr(name, body)
    print(f"{target} {target.stat().st_size} bytes")
