## Ticket
Link: https://github.com/rpulivella/pybers/issues/29
Closes #29

The README described the library as it stood after #2 and has not moved since, so it omitted everything four later tickets added and pointed at a directory that no longer exists. It now says what the library does, shows an example that runs, and names the four gates a contributor is expected to pass rather than the one that existed when the section was written.

Every path it names was checked rather than assumed, and the worked example was executed against a real fixture including the save and the reopen.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

### The repository map pointed at a directory that does not exist

It said `archive/` is the container and reader. That directory was renamed to `numbersfile/` in #2, so anyone following the map looked for something that had not existed for two tickets. That correction is `0bc5d4b`, on its own, because a one-line factual error deserves to be legible rather than buried in a rewrite.

The same row now mentions the type stubs sitting beside the schemas, which arrived in #4.

### What the README claimed against what is true

Two claims were checked rather than edited on memory.

**Paths.** Every backticked path, module and file the README names was resolved against the working tree, before and after: 19 checked, 0 missing. `archive/` was the only failure, which is a better result than expected and means AC 1 was the whole of AC 6.

**Evidence.** It said one numeric edit had been confirmed in Numbers. `tests/golden/` holds four files and its README carries four dated confirmation rows, so the claim now reads four, covering a numeric edit, an edit across two sheets, a merge and an unmerge.

### The example is executed, not written

The old example used `document.sheets[0].tables[0]`, which was the only spelling available before #14. The new one uses names, iterates, merges and saves, and every call in it was run against `27-big-table` including `document.save()` and reopening the file to read the value back.

While writing it I gave the iteration variable the same name as a table bound three lines above, which runs and reads badly. The table is now bound as `costs` and the loop comes first.

## Preconditions / setup for testing
None.

## Breaking Changes
**CI / automation / build**: None.

**Object model (public dataclass fields)**: None.

**Archive round-trip**: None. No code changed.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] Round-trip / golden-file tests pass for any archive-layer change
- NA I added or updated pytest tests covering the change

The last item is NA because nothing executable changed. The two claims a test could have covered were verified by running them instead: the path sweep and the worked example. Whether the path sweep should become a test is a fair question and a wider one than this ticket, since it would apply to every markdown file in the repository.

## Screenshot(s) / video(s)
None
