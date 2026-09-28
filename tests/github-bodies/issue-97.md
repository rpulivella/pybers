[PYB-83](https://github.com/rpulivella/pybers/issues/83)

`Cell.textLiteralSet` writes text whose Data Format is chosen as Text, so a label such as `=SUM(A1:A5)` opens as Text rather than Automatic. Every cell that is read now reports byte 6's `0x80` as `Cell.formatChosen`, and the writer carries that bit on each record it writes. Writing literal text over a formula raises immediately, because the formula would be lost.

## Detail your changes
- [x] No regressions / known issues found
- [x] Object-model shape changed (compatibility note in Breaking Changes below)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Known issues
None

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None
**Object model (public dataclass fields)**: `Cell` gains `_formatChosen`, keyword only and defaulting to False, exposed read-only as `formatChosen`. Nothing existing changes.
**Archive round-trip**: a written record's byte 6 `0x80` now follows the model. Every earlier golden still reproduces archive for archive, and `11-text-literal-written` was confirmed in Numbers on 2026-09-17.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #83_
