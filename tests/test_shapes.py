#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke tests for floating graphical objects (text boxes, images, shapes) and the rich
text primitives a text box's content is made of.

UPDATES
2026-08-12  Initial scaffold.
"""

import pybers


def testTextBoxHoldsRichTextWithMixedRunStyles() -> None:
    """A text box's rich text can mix styles within one paragraph, the whole reason
    plain Cell.value/Style is not enough for text box content."""
    paragraph = pybers.Paragraph(
        runs=(
            pybers.TextRun(text="Hello, "),
            pybers.TextRun(text="world", style=pybers.Style(bold=True, italic=True)),
        )
    )
    box = pybers.TextBox(
        position=pybers.Position(x=10, y=20),
        size=pybers.Size(width=100, height=50),
        richText=pybers.RichText(paragraphs=(paragraph,)),
    )
    assert box.richText.paragraphs[0].runs[1].style.bold is True


def testSheetHoldsTablesAndGraphicalObjectsIndependently() -> None:
    """Tables (grid content) and graphical objects (floating content) coexist on one
    sheet without one containing the other."""
    sheet = pybers.Sheet(
        name="Sheet 1",
        tables=[pybers.Table(name="Table 1")],
        graphicalObjects=[
            pybers.Image(
                position=pybers.Position(x=0, y=0),
                size=pybers.Size(width=200, height=200),
                sourcePath="logo.png",
            )
        ],
    )
    assert len(sheet.tables) == 1
    assert len(sheet.graphicalObjects) == 1
