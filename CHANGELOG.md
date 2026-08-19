# Changelog

Newest first. One line per ticket, the issue title **verbatim** — no categories, no extra
formatting. Skeleton follows [Keep a Changelog](https://keepachangelog.com) (minus its
category sub-blocks); versions follow [Semantic Versioning](https://semver.org) with the
build number, as `## X.Y.Z (build) - date`.

Maintained by `/changelog-add` — one verbatim ticket-title bullet per line under
`## Unreleased`.

## Unreleased

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
- [init] Vendor the numbers-parser fork and its patch rationale as reference material
- [init] Scaffold the project, package graph, and pytest gate
