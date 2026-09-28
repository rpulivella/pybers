<!-- PR title format: [PYB-<N>] Ticket title verbatim. This comment does not render in the PR body. -->

[PYB-<N>](https://github.com/rpulivella/pybers/issues/<N>)

_Describe what this PR achieves in 2-3 sentences. Borrow from the ticket. Nothing goes above the line before this one: GitHub already shows the title and the linked issue._

## Detail your changes
<!-- Remove any checkbox that does not apply. Do not leave irrelevant unchecked boxes. -->
- [ ] No regressions / known issues found
- [ ] Known issues remain (described below)
- [ ] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [ ] Object-model shape changed (compatibility note in Breaking Changes below)
- [ ] No change to the on-disk archive round-trip contract
- [ ] Archive round-trip behavior changed (new golden-file test attached)

## Known issues
<!-- Write None, or one bullet per issue: a few words and the ticket tracking it, such as "- Created tables undercount format refcounts, PYB-89". Bullets only, no prose. -->
None

## Preconditions / setup for testing
<!-- If nothing special, write None. Otherwise number the steps. -->
None

## Breaking Changes
<!-- Write None after each heading if not applicable, otherwise a short list. -->
**CI / automation / build**:

**Object model (public dataclass fields)**: any change to a public dataclass's field names/types

**Archive round-trip**: any change to what a written `.numbers` file looks like on disk

## Checklist (before requesting review)
<!-- An unchecked box means NOT DONE. For an item that cannot apply at all, move the line to the end of this list and replace its checkbox with NA, so the record shows it was considered rather than skipped. Deleting it would lose that. Say why in the body when the reason is worth knowing. -->
- [ ] I performed a self-review
- [ ] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [ ] I added or updated pytest tests covering the change
- [ ] Round-trip / golden-file tests pass for any archive-layer change
- [ ] I created the goldens this change earns and confirmed each in Numbers (`/golden-confirm`)

## Screenshot(s) / video(s)
<!-- If none, write None. -->
None

<!-- GitHub parses this keyword and no other form. It is what closes the ticket on merge. -->
_Closes #<N>_
