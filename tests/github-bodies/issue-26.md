## Ticket
Link: https://github.com/rpulivella/pybers/issues/25
Closes #25

Editing a cell that a formula depends on used to leave a document displaying arithmetic that disagreed with its own operands, silently and with no repair prompt. `Document.save` now marks the cells it changed in the document's calculation engine, and Numbers recalculates whatever depends on them the next time it opens the file. This library still evaluates nothing: it names the cells that moved and Numbers does the arithmetic.

The approach was chosen by measurement rather than by design. `TSCE.CalculationEngineArchive.refs_to_dirty` points at a `TSCE.ReferencesToDirtyArchive` that every document carries and every clean save leaves at zero bytes. Populating it with the twelve edited cells of `20-formula-shapes`, and nothing else, made Numbers recompute all eight dependent formulas including two that reach into another table and another sheet. A second run naming the dependent formulas as well produced identical output, which is how we know Numbers walks its own dependency graph and a writer needs to know only what it wrote.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] Archive round-trip behavior changed (new golden-file test attached)

### What changed on disk

A save that edits at least one cell now writes one further archive, the `ReferencesToDirtyArchive`, naming the cells by owner, column and row range. Both goldens were regenerated and re-confirmed in Numbers on 2026-09-02 because of it. A save that changes nothing reaches none of this code and stays byte-for-byte identical, which is its own test.

The value stored for a dependent formula does not change and should not. `A11` in the multi-sheet golden still holds 55 on disk while its operands sum to 10055, because pybers never computes a result. Numbers displays 10055 on open. A test asserting the recalculated number against the file would be asserting something the file does not contain.

### AC 3 was struck rather than implemented

AC 1 permitted two outcomes: Numbers recalculates, or pybers declines the save and names the formula that would be stranded. AC 3 specified the second. The measurement under AC 1.iii settled it as the first, so no save is ever declined for this reason and a decline path would be code nothing reaches. The ticket records this at AC 3 itself rather than only here.

### AC 4 is met in behavior, not in bytes

The intent was to skip the dirty set for a document with no formulas. That gate would never fire: all 46 fixtures report a non-zero `number_of_formulas`, `00-baseline` and `11-value-types-noformats` both at seven, because merges and interactive controls are stored as formulas too. Whether a specific formula depends on a specific cell is only answerable from the dependency graph, which this approach exists to avoid decoding. What is guaranteed instead is that all calculation-engine work is reached only when a cell actually moved, so an unchanged save costs exactly what it did before.

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None.

**Object model (public dataclass fields)**: None. No type gained, lost or changed a field.

**Archive round-trip**: An edited save writes one archive it did not write before. An unchanged save is unaffected and still round-trips byte-for-byte. Both goldens were regenerated and confirmed in Numbers 15.3.1: the multi-sheet one recalculates row 11 to 10055, 10056, 10055, `big`, 20110, 20110, 1042 and 1053, and the single-cell one keeps its checkbox, three-star rating, slider, stepper and popup menu working.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None
