As a developer maintaining pybers I want each concern of the write path in one module of its own so that I know where to look for any part of it.

## Acceptance criteria

1. A table's save lives in the table feature.
   1. Everything that happens to one table during a save is reached from one entry point in the table feature, and the document writer does no more than walk sheets and tables and call it.
   1. The document writer imports no private table module other than the one holding that entry point.
   1. Merges, list refcounting, and cell record writing each sit in a module of their own, and no table module exceeds 600 lines.
   1. Translating what a formula reads into the calculation engine's terms lives in the formula feature or the engine, not in the document writer.
1. A structural edit imports nothing from the table creation module, and creating a table and editing its lines write the UID map through the same operation.
1. The calculation engine is a package with one module per concern (owners and identities, formula registration, coordinate remapping, recalculation), and no module in it exceeds 300 lines.
1. Each archive type identifier is written once, in the type registry. A module needing one obtains it by the generated class, and asking for a class the registry does not hold raises an error naming it.
1. No saved file changes: every existing test, golden included, passes unchanged.

## Constraints

- `findAddedMerges` has to run before `applyMerges`, which rewrites the merge store the comparison reads.
