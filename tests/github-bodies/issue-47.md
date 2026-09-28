[PYB-44](https://github.com/rpulivella/pybers/issues/44)

A formula now says it sums a range rather than that it calls function 168, and says how many arguments that function takes. The table is derived from the Numbers binary, ships committed so `pip install pybers` needs no local Numbers, and regenerating reports what changed rather than replacing it silently.

## Detail your changes
- [x] Known issues remain (described below)
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

**371 functions, and existing is not the same as being offered.** Every index Numbers declares is carried, with `availability` saying how it may be used: 344 offered, 23 internal, 4 reserved. Reading names all of them, and only an offered one may be written by name. `SPILL` is internal and fills every cell a formula spills into, so without it any document containing a spill read as a bare number.

**A reader defect, found by this ticket's own fixture.** The formula key sits past a preceding reference when byte 8 carries `0x40`, and pybers read a fixed slot. Every formula in the new fixture resolved to the same wrong pooled entry and reported itself as `TEXT`: a plausible wrong answer rather than an exception, which is this format's characteristic failure. The rule was solved by refcount reproduction across ten fixtures and 74 formula cells, where exactly one assignment of slots to flag shapes reproduces every pooled formula's own refcount.

**Where the review effort belongs.** The extraction reads three things out of the binary and two of them corroborate each other, agreeing on 324 indices with no disagreement. Argument counts come from a third place and are the least corroborated, so they are checked against every valid formula in the corpus, and against the one Numbers itself marks as an error. A repeating group makes the maximum a floor rather than a ceiling, which is how an eight-argument `SUM` is legal.

**Known issue: `RANGE` and `TEXT` are named by Numbers with nothing behind them**, no class and no argument spec, and the parser rejects both. `LET` and `LAMBDA` are real but stored as node types rather than indexed calls, so they carry counts and no index.

## Preconditions / setup for testing
None for the library or the suite. `tools/functions-extract.py` needs a local Numbers, which is why its output is committed. It shells out to nothing: the Mach-O parsing and the AArch64 decoding are both Python.

## Breaking Changes
**CI / automation / build**: None. `scripts/` keeps the repository harness and `tools/` now holds the extractors that build pybers itself. **Object model (public dataclass fields)**: None. `NumbersFunction` is new, and `FormulaFunctionCall` gains properties rather than fields. **Archive round-trip**: None. Reading resolves differently where it was wrong before, and a document read and written back is byte-identical as it was.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #44_
