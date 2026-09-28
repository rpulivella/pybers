As a Python developer I want to set the font, weight, size and color of everything in a cell, so that formatting a cell by script matches formatting it by hand in Numbers.

## Acceptance criteria

1. A family, weight, style, size and color set on a cell apply to all of its text, and Numbers shows the cell's paragraph style as modified.
1. Only the properties set become overrides, and every other property still follows the named style.
1. A weight or style selects the family's real face, and a family without that face is refused rather than faked with Numbers' synthetic bold or italic.
1. Two cells given the same formatting over the same style share one stored style, as Numbers does.
1. Setting what a cell already shows reports no change and writes nothing.
1. Each property is locked in by a golden file opened once in Numbers and confirmed correct.

## Constraints

- **Blocked by PYB-8.** Which faces a family has is read with `fontTools`.
- Formatting a whole cell lands on its paragraph style's character properties, never in a character style (`findings-04-text.md`).
- `override_count` counts properties, not fields: a color writes two fields and counts one, so it is carried rather than recomputed. A style shared by several cells is never edited in place.
