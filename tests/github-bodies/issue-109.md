As a Python developer extending the writer I want an archive to read as it was last written within one save so that a second pass over it cannot silently undo the first.

## Acceptance criteria

1. Within one save, reading an archive after it was written returns what was written, never the content it held when the document was opened.
2. Two passes that each change the same archive in one save both reach the saved file: the second keeps the first's changes unless it changes the same fields itself.
3. An archive created during a save reads like any other, and reading one removed during a save raises an error naming it rather than returning its old content.
4. The structural edits of PYB-17 no longer depend on reading each archive only once: the comments and orderings that exist only to avoid a second read are gone, and every test measured against Numbers still passes.
5. Saving an unchanged document still writes it back byte for byte.

## Constraints

- `IWAFile.messageReplace` puts a new frozen `Archive` into its member while `ArchiveIndex.byIdentifier` keeps the old one, and `ArchiveIndex.resolve` parses afresh on every call, so two reads are two unrelated objects. Both halves of that produce the defect.
