As a Python developer I want to give a cell a background fill, an inset and an alignment, so that the box around a value is as easy to style as the value.

## Acceptance criteria

1. A solid fill, a padding and a vertical alignment set on a cell show in Numbers' Cell inspector.
1. A horizontal alignment set alongside them shows as well.
1. A color is written in CSS syntax, so `#1a2b3c` is sRGB and `color(display-p3 0.1 0.2 0.3)` is Display P3, and the color space is stored with it.
1. Cells given the same box formatting share one stored style.
1. A padding uneven between sides is refused, since Numbers has never been seen to write one.
1. Setting what a cell already shows reports no change and writes nothing.
1. Each property is locked in by a golden file opened once in Numbers and confirmed correct.

## Constraints

- **Blocked by PYB-8.**
- Cell styles are never named and are shared by value (309 of 309 anonymous). Horizontal alignment belongs to the paragraph, where 1 is right and 2 is center (`findings-06-styles.md`).
- The default 4pt padding and top alignment are expressed by omission, so setting them removes an override rather than writing one.
