As a Python developer I want to change a cell's number and save the file so that Numbers
opens it showing my new value and nothing else altered.

1. Reading a fixture and saving it with no changes produces a package Numbers opens
   cleanly, with every archive protobuf-equivalent to the input.
   1.a The comparison is field-by-field on decoded archives, not a byte compare, so that
   the one documented zip-envelope difference does not mask a real regression.
   1.b Every fixture in the suite passes this unchanged round trip.
2. Setting `Cell.value` to a `Decimal` and saving writes that value into the cell's tile,
   encoded as decimal128.
3. A saved document reopened by `pybers.open` reports the value that was written, with no
   digits gained or lost.
4. Saving a document whose cells were never touched leaves every style, merge, formula and
   graphical object unchanged, by the same comparison AC 1 uses.
5. A golden-file test covers one numeric edit against a fixture, with the expected output
   opened once in real Numbers and confirmed correct before being locked in.
6. Writing a value into a cell that carries a formula raises rather than silently
   discarding the formula.

## SPEC

- Saving mutates the archives that were read rather than building new ones. Anything the
  model does not yet represent survives only because nothing touched it, and that is what
  AC 4 measures.
- AC 1 has to be green before AC 2 is attempted. This format answers a wrong offset with a
  plausible wrong number rather than an error, so the unchanged round trip is the only
  thing that catches one. See `FINDINGS.md`.
- Tiles resolve through the tile list, never through archive order, matching the read
  path. See `findings-03-structure.md`.
- A cell's formula and its cached result are separate storage. Writing only the result
  leaves a document whose formula and displayed value disagree until Numbers recalculates,
  which is why AC 6 raises instead.

Formula writing, style writing, structural edits and graphical object placement are out of
this ticket.
