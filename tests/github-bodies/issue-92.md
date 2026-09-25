As a Python developer I want merging cells to release the strings and styles of the records it removes, so that a later edit in Numbers cannot discard a string or style other cells still use, or keep one nothing uses.

## Acceptance criteria

1. Merging a range releases the string entry each removed text record names.
2. Merging a range releases the style entries each removed record names in byte 8 `0x20` and `0x40`.
3. A save that takes a string entry's refcount to 0 writes the string list without that entry and leaves its `nextListID` unchanged.
4. `45-merged-by-pybers`, regenerated, stores a string refcount equal to its cells for every entry, `22c-merged-by-pybers`, regenerated, stores a style refcount equal to its cells for every entry, and `11-text-written-and-retyped`, regenerated for AC 3, holds no string entry that no cell names, and all three open in Numbers without a repair prompt.
5. Merging a range releases what each removed record names beyond its formats, strings and styles:
   1. a formula, whose entry loses that reference and whose cell the calculation engine no longer holds as a formula, shown in a golden of a merge over a formula cell that opens in Numbers without a repair prompt,
   1. rich text, whose entry loses that reference.

## Constraints

- A string's refcount is how many text records name it, and a style's is how often its key sits in byte 8 `0x20` and `0x40`. Both rules reproduce every list in all 92 tables of the fixtures.
- `54b-format-star-rating-released` measured Numbers removing a string entry at 0. Nothing has measured a formula entry at 0, so the formula pool keeps emptying rather than removing.
