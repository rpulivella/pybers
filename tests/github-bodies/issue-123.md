As a Python developer I want to switch a table's alternating row color, gridlines and outline, as InDesign table styles do, so that a whole table's look changes in one place.

## Acceptance criteria

1. Alternating row color turns on with a chosen color, and off.
1. Horizontal and vertical gridlines turn on and off for each band.
1. The table outline turns on and off.
1. Each setting is locked in by a golden file opened once in Numbers and confirmed correct.

## Constraints

- A table's style is anonymous, one per band, with more than sixty stroke slots, and a changed setting is stored as an override on a variation (`findings-06-styles.md`).
- **What holds this at Concept:** banding is only lightly measured, in `29-style-border`.
