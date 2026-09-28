As a Python developer I want pybers to open a table with more than 255 columns so that a wide spreadsheet is readable rather than raising on its first row.

1. `tests/fixtures/45-columns-over-255.numbers` exists, saved from Numbers with 300 columns, every cell labeling its own address and one row carrying gaps so an empty slot is covered too.
2. That fixture opens, and every populated cell reports the value Numbers displays for it.
3. Reading it and writing it back leaves the archives identical, the base contract every other fixture holds to.
4. pybers names the two things that actually differ, the offset scale and the slot count, rather than naming the layouts themselves, so no identifier and no sentence claims an offset width that does not vary.
5. A row whose offsets cannot be read names the document, the table and the row, rather than reporting a byte count with no way to find it.
6. A table of 255 columns or fewer reads exactly as it does today, so the fix adds a case rather than moving one.
7. A cleared cell inside a wide row reports empty rather than a neighbor's value.

## SPEC

- **There is no 32-bit offset layout, and this ticket was filed believing there was.** Measured 2026-09-06 against AC 1's fixture: a 300-column row carries 600 bytes of offsets, two bytes each, and `0xFFFF` marks an empty slot in both layouts. Reading them as `uint32`, which `reader.py` does today, puts every offset past the end of its own buffer.
- **Two things differ, and neither is the offset width.** A row of 255 columns or fewer carries a fixed 255 slots holding byte offsets; a wider row carries one slot per column holding offsets in units of four bytes. Both counts fall out of the array length, so neither rule needs writing down, and the scaling is lossless because all 9,497 offsets in the 46 earlier fixtures are multiples of four.
- **The `_pre_bnc` pair was the other candidate and is not the live one.** Every row of the fixture carries four bytes in `cell_offsets_pre_bnc` against 600 in `cell_offsets`.
- **`should_use_wide_rows` is sticky and the array shrinks with the table**, so a table that once exceeded 255 columns keeps the wide form after they are deleted. That is what the private document behind this ticket is, and it stays out of the repository.
- **Apple's field names stay as Apple spells them.** `has_wide_offsets` and `should_use_wide_rows` are upstream identifiers, so AC 4 covers this project's own names and never those.
