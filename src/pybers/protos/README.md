# pybers protobuf schemas — provenance

These 33 `.proto` files describe Apple's iWork archive format. They were **extracted from
the Numbers application binary on a developer machine**, not written by hand and not
copied from another project.

| | |
|---|---|
| Extracted from | Numbers **15.3.1**, build **7050.1.1** (Mac App Store) |
| Extracted on | 2026-08-13 |
| Generated Python | `src/pybers/_generated/*_pb2.py`, compiled from these with `protoc` |

Both directories are **committed on purpose**, so that `pip install pybers` works on a
machine with no Numbers installed and no protoc available.

## Why extracted rather than vendored

Apple compiles the protobuf descriptors for its own format into the Numbers binary, so
they are the source of truth and dumping them is a mechanical step. A project that vendors
another project's dump inherits an artifact it cannot regenerate, explain, or update when
Apple ships a new Numbers. See "Open architectural decisions" in `CLAUDE.md` for the full
reasoning.

That is not theoretical here. Comparing this extraction against the schemas vendored in
`reference/numbers-parser/src/protos/` (taken from an earlier Numbers) found **20 of 33
schemas differ**. Among the differences, `TSTArchives.proto` — the table archives this
library is built on — gained an entire `StructuredTextImportRecordUID` message plus
`source_row_count` and `source_column_count` fields that the older copy does not contain.
Vendoring would have meant modelling today's files with yesterday's schemas.

One difference runs the other way and is recorded here so it is not rediscovered as a bug:
`TSWPCommandArchives.proto` is **66 lines shorter** in 15.3.1, having lost the `enum Kind`
inside `TextCommandArchive`. `kKindReplaceText` and its siblings appear nowhere in the
current dump, and the message count is identical (44 in both), so this reads as Apple
removing the enum rather than an incomplete extraction.

## Regenerating

Regeneration needs a local Numbers install and `protodump.py`, so it cannot run on a fresh
clone or in CI — which is exactly why the output is committed. See
`scripts/protos-extract.py` for the process, its prerequisites, and the credited
provenance of the extraction technique.

**Do not hand-edit anything in this directory or in `_generated/`.** Both are machine
output; a manual correction would be silently destroyed by the next extraction, and a
schema that disagrees with the binary it was dumped from is worse than no schema at all.
