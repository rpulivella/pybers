[PYB-72](https://github.com/rpulivella/pybers/issues/72)

A body drafted with CRLF line endings had every one of them converted to `\n` before it reached GitHub, silently, and the count `unwrapParagraphs` returns tracked only the paragraphs it joined. Inside a fenced code block that ending is the author's code rather than their formatting. AC 1 is met by removing the change rather than reporting it: the endings now survive, so there is nothing to report.

The defect sat at two layers and fixing either alone leaves it fully intact. `unwrapParagraphs` split on `str.splitlines` and rejoined on `"\n".join`. It now keeps every separator as it splits, and restores the one its own line carried. Above it, `readBodyFile` called `Path.read_text`, whose universal-newline default converted each `\r\n` before the unwrap could preserve anything, so it now reads without translation. The second layer is the one the unit tests could not see, and it was found by exercising a real comment end to end against GitHub.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None **Object model (public dataclass fields)**: None **Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

Nothing here touches the archive layer. The change is confined to `scripts/ticket.py`, which posts text to GitHub and never opens a document.

`tests/test_body_unwrapping.py` is the first test under `tests/` covering anything in `scripts/`, which has none. It is written narrowly on purpose: these two functions are pure over a string, needing no network and no credential, which is what makes them worth pinning before PYB-11 decides what testing repo tooling should look like generally. The fix was confirmed the same way, by reading back what GitHub stored.

## Screenshot(s) / video(s)
None

_Closes #72_
