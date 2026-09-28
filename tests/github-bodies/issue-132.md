As a Python developer I want to rewrite synthetic typography in an existing document as the real thing, so that documents I inherit meet the same standard as the ones pybers writes.

## Acceptance criteria

1. Synthetic superscript and subscript become the font's real features where the font carries them.
1. Synthetic small caps become the real feature where the font carries it.
1. Text whose font lacks the real feature is left as it was and reported.
1. A dry run reports every change it would make and writes nothing.
1. The repair is locked in by a golden file opened once in Numbers and confirmed correct.

## Constraints

- **Open decision, and what holds this at Concept:** a real feature can change widths and line breaks, and whether a repair may reflow text is undecided.
