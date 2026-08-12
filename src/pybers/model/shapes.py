#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Objects that float on a sheet at an absolute position, independent of any table's
grid — text boxes, images, and vector shapes.

UPDATES
2026-08-12  Initial scaffold.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pybers.model.geometry import Position, Size
from pybers.model.style import Style
from pybers.model.text import RichText


@dataclass(slots=True)
class GraphicalObject:
    """The placement shared by everything that floats on a sheet: where, how big, how
    rotated. TextBox, Image, and Shape all extend this rather than repeating it."""

    position: Position
    size: Size
    rotationDegrees: float = 0.0


@dataclass(slots=True)
class TextBox(GraphicalObject):
    """A floating text box — placement plus its rich text content."""

    richText: RichText = field(default_factory=RichText)


@dataclass(slots=True)
class Image(GraphicalObject):
    """A floating image, referenced by the path it was imported from."""

    sourcePath: str | None = None


@dataclass(slots=True)
class Shape(GraphicalObject):
    """A floating vector shape (rectangle, line, arrow, etc.) and its fill/stroke."""

    shapeType: str = "rectangle"
    style: Style = field(default_factory=lambda: __import__("pybers.model.style", fromlist=["Style"]).Style())
