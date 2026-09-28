As a Python developer I want every format entry pybers changes to count exactly the cells that name it, so that a later edit in Numbers cannot discard a format that other cells still use.

## Acceptance criteria

1. Writing text into several cells of one table in one save raises the text format's refcount by one for each cell.
2. Writing numbers into several cells of a table pybers created raises the automatic number format's refcount by one for each cell.
3. Retyping a cell lowers by one the refcount of the format it no longer names:
   1. a number becoming text releases the number format it displayed with,
   1. text becoming a number releases the text format.
1. A format entry pybers neither adds a reference to nor releases one from keeps the refcount Numbers wrote, including one that already disagrees with its cells.
1. `11-text-written-and-retyped`, regenerated, stores a refcount equal to its cells for every entry pybers changed, and opens in Numbers without a repair prompt.
1. What Numbers does with a format entry whose refcount reaches 0 is measured against a fixture Numbers made, and recorded in findings-01-values.md.
1. A cell pybers writes stores in byte 9 `0x10` the kind of format it displays with, counted from 1 in slot order (5 for text, 1 for a number), and never a format entry's key.
1. `20-first-text-in-a-table` and `20-tables-added`, regenerated, store that kind for every cell pybers wrote, open in Numbers without a repair prompt, and read Automatic in the Data Format inspector for each of those cells, while `11-text-written-and-retyped` stays unchanged.
1. A save that takes a format entry's refcount to 0 writes the format list without that entry and leaves its `nextListID` unchanged, and `11-text-written-and-retyped`, regenerated, holds no star-rating format entry and opens in Numbers without a repair prompt.
1. Merging a range releases every format reference of each record the merge removes, and `45-merged-by-pybers`, regenerated, stores a refcount equal to its cells for every format entry and opens in Numbers without a repair prompt.

## Constraints

- This does not wait for every format slot to be writable. pybers adds references only in the number and text format slots, and releases references only from those slots or from a record it removes.
- Byte 9 `0x10` holds a kind rather than a key, and no refcount counts it: 1 number, 2 currency, 3 date, 4 duration, 5 text, 6 checkbox. `11-value-types-noformats` keys its number and text formats 1 and 5, which is why a key written there passed every golden built on that fixture.
- `11-value-types-noformats` and `12-number-currency` agree with their cells once all six per-kind slots are counted. The audit that reported a mismatch read fewer slots than Numbers uses.
