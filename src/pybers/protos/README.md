# Provenance of the pybers protobuf schemas

These 33 `.proto` files describe Apple's iWork archive format. They were **extracted from
the Numbers application binary on a developer machine**, not written by hand and not
copied from another project.

| | |
|---|---|
| Extracted from | Numbers **15.4**, build **7051.0.79** |
| Extracted on | 2026-10-12 |
| Generated Python | `src/pybers/_generated/*_pb2.py`, compiled from these with `protoc` |

Both directories are **committed on purpose**, so that `pip install pybers` works on a
machine with no Numbers installed and no protoc available.

## Why extracted rather than vendored

Apple compiles the protobuf descriptors for its own format into the Numbers binary, so
they are the source of truth and dumping them is a mechanical step. A project that vendors
another project's dump inherits an artifact it cannot regenerate, explain, or update when
Apple ships a new Numbers. See "numbers-parser is NOT vendored here" in `docs/decisions.md`
for the full reasoning.

That is not theoretical here. Comparing this extraction against the schemas vendored in
numbers-parser's own `src/protos/` (taken from an earlier Numbers) found **20 of 33
schemas differ**. Among the differences, `TSTArchives.proto` (the table archives this
library is built on) gained an entire `StructuredTextImportRecordUID` message plus
`source_row_count` and `source_column_count` fields that the older copy does not contain.
Vendoring would have meant modeling today's files with yesterday's schemas.

One difference runs the other way and is recorded here so it is not rediscovered as a bug:
`TSWPCommandArchives.proto` is **66 lines shorter** than numbers-parser's copy, having
lost the `enum Kind` inside `TextCommandArchive`. `kKindReplaceText` and its siblings
appear nowhere in the current dump, and the message count is identical (44 in both), so
this reads as Apple removing the enum rather than an incomplete extraction.

Numbers 15.4 changed two schemas from 15.3.1. `TSS.StylesheetArchive` gained
`styles_for_15_4`, field 27, and a command archive's `sheet_index` in
`TNCommandArchives.proto` became `int32` where it was `uint32`. The two integer types
read the same bytes until an index is negative.

Apple adds one `styles_for_*` slot every release, and no document Numbers made here fills
any after `styles_for_10_1`: not one 15.4 re-saved, created blank or created from its
templates, and not one given a 15.3 sheet tab color, whose style lands in
`styles_for_10_0`. The new templates offered only with a Creator Studio subscription are
untried.

## Regenerating

Regeneration needs a local Numbers install and `protodump.py`, so it cannot run on a fresh
clone or in CI, which is why the output is committed. See
`tools/protos-extract.py` for the process, its prerequisites, and the credited
provenance of the extraction technique.

**Do not hand-edit anything in this directory or in `_generated/`.** Both are machine
output; a manual correction would be silently destroyed by the next extraction, and a
schema that disagrees with the binary it was dumped from is worse than no schema at all.
