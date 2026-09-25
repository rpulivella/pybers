As a Python developer I want to draw borders on a cell's edges or around a range, with the width, color and style CSS `border` names, so that a report's structure shows without drawing it by hand.

## Acceptance criteria

1. A border of a given width, color and style (solid, dashed or dotted) on any edge of a cell shows in Numbers.
1. A border around a range draws its outline, and one inside a range draws only its inner lines.
1. A line between two cells reads the same from either side.
1. Removing a border leaves that line with no stroke.
1. Each case is locked in by a golden file opened once in Numbers and confirmed correct.

## Constraints

- Cell borders, the table outline and gridlines are three unrelated mechanisms. Cell borders are run layers per side in the stroke sidecar, and every line between two cells is stored twice (`findings-06-styles.md`).
- **What holds this at Concept:** which copy wins when the two disagree is not measured.
