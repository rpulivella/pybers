[PYB-74](https://github.com/rpulivella/pybers/issues/74)

Four columns of indentation makes a block code when no fence is present, and `unwrapParagraphs` decided what every line was by matching against the line with its indentation already removed. A pasted block therefore arrived at GitHub flattened to column zero and merged onto one line, reported as one paragraph joined, which is true and does not describe what happened to it. The dispatcher now reads the raw line, and the integer return has become a record naming more than one kind of change.

`leadingWidth` counts the columns a line opens with, a tab advancing to the next stop. Two states join the loop: an indented block may not interrupt an open paragraph nor open inside a list, which keeps a six-column continuation under a sub-criterion joining as prose rather than turning into code. `BodyChanges` replaces `tuple[str, int]` across both tools, and `reportUnwrapping` prints a second line when whitespace alone was removed.

`BodyChanges` is a frozen dataclass where its three neighbors are `TypedDict`. CLAUDE.md calls for dataclasses, and those three each mirror a GitHub payload, which this one never does.

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

Nothing here touches the archive layer. The change is confined to `scripts/`, which posts text to GitHub and never opens a document.

Twelve tests were added, and all four gates ran at each of the three commits, so every one is green on its own at 1107, 1116 and 1119. No test of the tool against itself can answer AC 1, so I posted a four-space block as a comment and read it back: byte-identical, indentation held. The comment was deleted. All three AC 1 cases were confirmed broken on `develop` first.

## Screenshot(s) / video(s)
None

_Closes #74_
