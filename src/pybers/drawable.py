#!/usr/bin/env python3
"""Objects that float on a sheet at an absolute position, independent of any table's
grid, text boxes, images, and vector shapes.

UPDATES
2026-09-08  Renamed from `shapes` and moved out of `pybers.model` for #58,
            since a text box and an image are drawables and neither is a shape.
2026-08-12  Initial scaffold.
"""

from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/12"

from dataclasses import dataclass, field

from pybers.geometry import Position, Size
from pybers.style import Style
from pybers.text import RichText


@dataclass(slots=True)
class GraphicalObject:
    """The placement shared by everything that floats on a sheet: where, how big, how
    rotated. TextBox, Image, and Shape all extend this rather than repeating it."""

    position: Position
    size: Size
    rotationDegrees: float = 0.0


@dataclass(slots=True)
class TextBox(GraphicalObject):
    """A floating text box, placement plus its rich text content."""

    richText: RichText = field(default_factory=RichText)


@dataclass(slots=True)
class Image(GraphicalObject):
    """A floating image, referenced by the path it was imported from."""

    sourcePath: str | None = None


@dataclass(slots=True)
class Shape(GraphicalObject):
    """A floating vector shape (rectangle, line, arrow, etc.) and its fill/stroke."""

    shapeType: str = "rectangle"
    style: Style = field(default_factory=Style)
