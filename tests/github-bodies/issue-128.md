As a Python developer I want to define a named set of cell formatting once, as InDesign cell styles work, and apply it to any cell, so that a script restyles a report by changing one definition.

## Acceptance criteria

1. A named set combines box formatting with a paragraph style, and applying it gives a cell both.
1. pybers reports which cells a named set was applied to.
1. Changing a definition and applying it again restyles every cell that carries it.
1. Nothing in a saved document claims to be a named cell style, since Numbers has no such thing.

## Constraints

- **Numbers never names a cell style**, in 309 of 309 measured (`findings-06-styles.md`), so this is a pybers concept and has to say so.
- **Open decision, and what holds this at Concept:** whether the name and its cells persist between sessions, and where, when the document itself cannot hold them.
