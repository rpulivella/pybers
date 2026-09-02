# Code review rubric

Six questions, asked of **the change** — never of the repository around it. A problem in
a file this pull request did not touch is a ticket, not a review comment.

This file holds the **mindset**, deliberately not the rules. The laws live in
`CLAUDE.md`. No linting tooling is configured yet (see `CLAUDE.md`); if a violation keeps
recurring, the fix is real lint config, not a longer rubric.

The governing question, from which the rest follow: **would a skilled developer who knew
this codebase have built it this way?**

---

**Design** — Is the work at the right altitude? Does it belong in the object model
(`pybers.model`), the persistence layer (`pybers.numbersfile`), or the CLI/TUI layer — and does
it stay there? Building archive-format knowledge into the object model, or vice versa, is
the same defect seen from opposite sides.

**Functionality** — Does it do what the acceptance criteria said, including the edge the
ticket named? Were edge cases and new ideas that surfaced during the work filed as new
tickets for follow-up, or did scope quietly change?

**Complexity** — Could a skilled developer have done this more simply? Is anything here
solving a problem nobody has yet?

**Tests** — Does new behavior have tests? Does a persistence-layer change have a round-trip
or golden-file test, not just a model-level equality check? Was the current coverage of
the modules this ticket touched actually assessed for thoroughness?

**Consistency** — Does it look like the code around it? camelCase, full type hints,
dataclasses (not TypedDict), docstring-with-why on every function — would someone reading
the file notice where this change starts?

**Naming and comments** — Do names say what a thing is, and do comments say *why* rather
than *what*? Bytes in uncompiled code are the cheapest thing we have. Name things so they
can be read in twenty-four months.
