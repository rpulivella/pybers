<!-- PR title format: [#<N>] Ticket title verbatim — this comment does not render in the PR body -->

## Ticket
Link: https://github.com/rpulivella/pybers/issues/<N>
Closes #<N>

_Describe what this PR achieves in 2-3 sentences. Borrow from the ticket._

## Detail your changes
<!-- Remove any checkbox that does not apply. Do not leave irrelevant unchecked boxes. -->
- [ ] No regressions / known issues found
- [ ] Known issues remain (described below)
- [ ] No change to the object-model shape (Cell/Table/Sheet/Workbook fields)
- [ ] Object-model shape changed (compatibility note in Breaking Changes below)
- [ ] No change to the on-disk archive round-trip contract
- [ ] Archive round-trip behavior changed (new golden-file test attached)

## Preconditions / setup for testing
<!-- If nothing special, write None. Otherwise number the steps. -->
None

## Breaking Changes
<!-- Write None after each heading if not applicable, otherwise a short list. -->
**CI / automation / build**:
**Object model (public dataclass fields)**: any change to a public dataclass's field names/types
**Archive round-trip**: any change to what a written `.numbers` file looks like on disk

## Checklist (before requesting review)
- [ ] I performed a self-review
- [ ] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [ ] I added or updated pytest tests covering the change
- [ ] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
<!-- If none, write None. -->
None
