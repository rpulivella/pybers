As a Python developer I want to set figure style on a range of cells with CSS `font-variant-numeric` keywords, so that a column of numbers aligns and reads as intended.

## Acceptance criteria

1. `lining-nums`, `oldstyle-nums`, `tabular-nums`, `proportional-nums`, `slashed-zero`, `diagonal-fractions` and `ordinal` are accepted as CSS writes them, combined as CSS allows.
1. A contradictory pair such as `tabular-nums proportional-nums` is refused.
1. Every cell in the range shows the chosen figures in Numbers, number cells included.
1. A font lacking a requested figure style is refused, naming the font.
1. The result is locked in by a golden file opened once in Numbers and confirmed correct.
