As a Python developer I want a formula this library could not read to survive a save so that opening a real document and saving it back cannot silently strip work I depend on.

## Acceptance criteria

1. A cell whose stored record names a formula the reader could not resolve keeps that formula through a read and a save, and the saved package is archive-identical to the source.
   1. The reader says what it could not resolve rather than leaving a cell looking as though it never held a formula.
2. A save detaches a formula only where a caller asked for it by setting `cell.formula` to None. A formula the model never carried is never removed.
3. A document whose formula pool the reader cannot fully resolve still round-trips with every archive unchanged.

## Constraints

- Measured 2026-09-09 against a real document outside the corpus: 416 cells across 9 tables read as holding no formula while their records name one, and a save reports every one of them as a detach. In one 10 by 10 table all 63 such records name pooled key 14 while the pool resolves keys 2 through 13.
- No fixture in the corpus reproduces this, so one has to be built in Numbers before the fix can be locked in.
