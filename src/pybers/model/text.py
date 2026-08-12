#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rich text — a run of characters sharing one Style, grouped into paragraphs.

Numbers allows mixed formatting within a single text box or cell (part of a sentence
bold, part a different color). A plain Cell.value/Style pair cannot express that, so
richer text content is modeled as a sequence of styled runs instead. This is the
primitive TextBox uses today; it is also the natural home for intra-cell rich text if
that is ever needed, not yet wired into Cell.

UPDATES
2026-08-12  Initial scaffold.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pybers.model.style import Style


@dataclass(frozen=True, slots=True)
class TextRun:
    """A contiguous span of characters sharing one Style."""

    text: str
    style: Style = field(default_factory=Style)


@dataclass(frozen=True, slots=True)
class Paragraph:
    """One paragraph — a sequence of styled runs plus paragraph-level alignment."""

    runs: tuple[TextRun, ...] = ()
    alignment: str = "left"


@dataclass(frozen=True, slots=True)
class RichText:
    """A block of text — the content of a TextBox, made of one or more paragraphs."""

    paragraphs: tuple[Paragraph, ...] = ()
