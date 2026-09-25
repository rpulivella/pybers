As a developer arriving at pybers once it is public I want the README to say what the library does today so that I can judge it without reading the source.

## Acceptance criteria

1. The status line names what is built and what is not as of the pull request's merge, with adding and deleting rows and columns among the built and styles among the not built.
1. The status line carries the date it was last made true.
1. The status block renders on GitHub as one quotation, with no stray `>` inside its text.
1. "What works today" lists adding and deleting rows and columns, and every other capability the CHANGELOG's Unreleased list names that the table omits.
1. Every count and every claim of existence in the README (schemas, gates, workflows, directories, commands) matches the repository at the merge.
