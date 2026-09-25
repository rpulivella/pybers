As a developer I want a line opening with a bold label to stay on its own line so that a pull request body filled from the template reaches GitHub as the template wrote it.

## Acceptance criteria

1. A line whose content opens with a bold run ending in a colon is its own block, and is never joined to the line after it.
2. The three labels under `## Breaking Changes` in `.github/pull_request_template.md` reach GitHub on three lines.
3. Prose that is joined today is still joined, and every change is still reported.
4. A regression test fails for the original defect.

## Constraints

- `blockOpener` in `scripts/ticket.py` requires a space after the marker, so `**bold**:` does not match it and consecutive such lines read as one wrapped paragraph. Measured on PR #77, whose three labels arrived as a single paragraph and had to be separated by hand.
