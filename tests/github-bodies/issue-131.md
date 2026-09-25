As a Python developer I want to set tracking, leading and baseline shift in the units InDesign and CSS use, so that values from a design specification go in unchanged.

## Acceptance criteria

1. Tracking is given in thousandths of an em, as InDesign states it, so 20 shows in Numbers as a character spacing of 2%.
1. Leading is given as exact, at least, or space between lines, in points, and reads back with the same mode.
1. Baseline shift is given in signed points, positive raising the text.
1. Setting tracking leaves kerning alone.
1. Each value is locked in by a golden file opened once in Numbers and confirmed correct.

## Constraints

- Tracking is stored as a fraction, and every template already carries -0.01, so its presence is not evidence of a setting (`findings-04-text.md`).
- That Numbers' percentage is a fraction of the em is inferred from `32-named-styles`, not measured against a rendered width.
- Line spacing is a mode and an amount. A rich-text cell's line spacing is read from its payload's paragraph style, not from the cell's own style.
