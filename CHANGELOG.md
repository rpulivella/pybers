# Changelog

Newest first. One line per ticket, the issue title **verbatim** — no categories, no extra
formatting. Skeleton follows [Keep a Changelog](https://keepachangelog.com) (minus its
category sub-blocks); versions follow [Semantic Versioning](https://semver.org) with the
build number, as `## X.Y.Z (build) - date`.

Maintained by `/changelog-add` — one verbatim ticket-title bullet per line under
`## Unreleased`.

## Unreleased

- [init] Type cell values and pin numbers to Decimal for exact round-tripping
- [init] Add real Numbers fixtures and record the archive format findings
- [init] Add the archive container layer for reading and writing .numbers files
- [init] Declare the protobuf runtime dependency
- [init] Extract the iWork protobuf schemas from Numbers 15.3.1
- [init] Add the object model split by feature area (style, geometry, text, shapes, table, sheet)
- [init] Vendor the numbers-parser fork and its patch rationale as reference material
- [init] Scaffold the project, package graph, and pytest gate
