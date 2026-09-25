As a Python developer I want to name font features by OpenType tag, as CSS `font-feature-settings` does, so that no caller has to learn the integer pairs Numbers stores.

## Acceptance criteria

1. Reading text returns its features as OpenType tags, each on or off, in the order stored.
1. Writing tags stores the pairs Numbers itself writes for the same features chosen in its Typography panel.
1. A tag with no Numbers equivalent is refused, naming the tag.
1. A stored pair with no known tag survives a round trip and reads as unknown rather than being dropped.
1. Features explicitly cleared read differently from features never set.
1. Every tag's pair names the measurement or the line of Apple's `SFNTLayoutTypes.h` that establishes it.

## Constraints

- Numbers stores Apple Advanced Typography pairs as an ordered list in which one type may repeat, so it is not a mapping (`findings-04-text.md`).
- Only types 6, 10 and 33 are measured. The rest are verified against `SFNTLayoutTypes.h`, never from recall.
