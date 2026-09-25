As a Python developer I want to apply OpenType features to a cell's text or to part of it, and have pybers confirm the font carries them, so that a feature asked for is a feature shown.

## Acceptance criteria

1. Features apply by tag to all of a cell's text or to a range of it.
1. A feature the font lacks is refused, naming the font and the tag.
1. A font pybers cannot find where it runs is reported rather than assumed to carry the feature.
1. Each case is locked in by a golden file opened once in Numbers and confirmed correct.

## Constraints

- Fonts are inspected with `fontTools`, decided 2026-09-23 for being cross-platform, and declared as a floor.
