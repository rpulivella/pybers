# Changelog

Newest first. One line per ticket, the issue title **verbatim**, no categories, no extra
formatting. Skeleton follows [Keep a Changelog](https://keepachangelog.com) (minus its
category sub-blocks); versions follow [Semantic Versioning](https://semver.org) with the
build number, as `## X.Y.Z (build) - date`.

Maintained by `/changelog-add`, one verbatim ticket-title bullet per line under
`## Unreleased`.

## Unreleased

- [PYB-39] Adopt the PYB-34 and PR #38 reference conventions
- [#34] Raise the Python floor to 3.14
- [#36] Refuse a merge when CI has not passed
- [#5] Run the preflight in CI on every pull request
- [#3] Author the pull request preflight check script
- [#29] Bring the README current with the library and its gates
- [#7] Declare build in the dev extras
- [#4] Configure ruff and mypy for the camelCase house style
- [#16] Merge and unmerge a range of cells
- [#25] Fix an edit leaving dependent formula results stale
- [#14] Reach sheets and tables by name and walk every cell
- [#2] Write a document back to a .numbers package
- [#2] Rename pybers.archive to pybers.numbersfile
- [#2] Fix decimal128 decoding obeying the caller's decimal context
- [#20] Add a pr-merge skill to own the merge step
- [#19] Add export-as-source to pr.py
- [#9] Add a cell reference type for A1 and range addressing
- [#1] Read a .numbers document into the object model
- [init] Cut implementation steps from the ticket SPEC section
- [init] Adopt subject-first verb-last method naming
- [init] Make Document the single in-memory handle for a document
- [init] Catch markdown hard breaks in the standards gate
- [init] Rewrite the README for a public audience
- [init] Rename Workbook to Document to match the archive format
- [init] License the project under Apache-2.0
- [init] Map stroke dash arrays and connector attachment
- [init] Establish that a style name does not make it user-visible
- [init] Map table titles, captions and text insets
- [init] Map table geometry, row sizing and UUID-based row hiding
- [init] Map header bands, band precedence and the header storage bucket
- [init] Map tab stops, indents and the two indent mechanisms
- [init] Map text outlines, shadows and the null-property convention
- [init] Map baseline shift and the four line spacing modes
- [init] Establish that text run indices count UTF-16 code units
- [init] Map text boxes, shapes, images and the point coordinate unit
- [init] Resolve how named styles and local overrides relate
- [init] Map cell insets and paragraph indents
- [init] Establish which style kinds can be named, and that cell styles cannot
- [init] Map alignment styles and resolve the cell style reference tail
- [init] Map the three border mechanisms and the stroke sidecar
- [init] Map cell fills, gradients, color spaces and embedded images
- [init] Resolve tiles through the tile list rather than archive order
- [init] Map merges, structural edits, sheets and table geometry
- [init] Add duration, scientific and custom number format fixtures
- [init] Map cross-table references, multi-range functions and formula error shapes
- [init] Establish that formula references are relative offsets, shared by refcount
- [init] Add cell value decoding for numbers, text, dates, booleans and durations
- [init] Establish that formulas are a postfix AST with per-axis reference locking
- [init] Escape arbitrary text in all rich console output
- [init] Type cell values and pin numbers to Decimal for exact round-tripping
- [init] Add real Numbers fixtures and record the archive format findings
- [init] Add the archive container layer for reading and writing .numbers files
- [init] Declare the protobuf runtime dependency
- [init] Extract the iWork protobuf schemas from Numbers 15.3.1
- [init] Add the object model split by feature area (style, geometry, text, shapes, table, sheet)
- [init] Scaffold the project, package graph, and pytest gate
