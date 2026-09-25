As the maintainer I want a ticket or pull request body to render on GitHub exactly as its author meant, however many times it is exported, edited and posted, so that editing one never quietly rewrites the parts nobody touched.

## Acceptance criteria

1. Every issue and pull request body filed up to 2026-09-24, exported with `export-as-source` and posted back unedited, renders on GitHub exactly as it did, checked against a snapshot of those bodies committed to the repository.
1. A draft written locally with hard-wrapped paragraphs posts with each paragraph on one line, and every line meant to stand alone renders on its own line: a hard break, a list item, a heading, a table row, a code line, a comment, and a line italic from end to end.
1. A line break typed in GitHub's editor survives an export, an edit elsewhere in the body, and a post.
1. A body whose posting would change what GitHub renders is refused before anything is posted, naming the lines that would change.
1. More than one blank line in a row posts as one, and a body ends with no blank line.
1. Each case found on 2026-09-24 is a named regression test: the italic `Closes` line, a comment above a line, an `NA` checklist line without its dash, a trailing hard break, Windows line endings, unbolded label lines, and lines typed on GitHub as separate lines.
1. Tickets, pull requests and comments all post through the same handling, so a fix to one reaches all three.
1. The formatter is a floor in the `dev` extras, and `import pybers` loads none of it.

## Constraints

- **GitHub renders a single newline in a body as a line break, and a local `.md` file renders it as a space**, so the same text means two things. The current unwrapper assumes the second on a body that came from the first.
- **`mdformat` with its GFM plugin was chosen on 2026-09-24** and is measured against the snapshot before anything is built on it. If it cannot meet AC 1, this ticket returns to Concept.
- The snapshot is not a fixture: `tests/fixtures/` holds only `.numbers` documents.
