---
description: Add the current ticket's verbatim title to the CHANGELOG.md Unreleased list.
argument-hint: <optional issue number; inferred from the branch if omitted>
---

# /changelog-add

Add an entry to the `CHANGELOG.md` Unreleased list for the current ticket.

## Steps

1. Get the ticket number from `$ARGUMENTS` or the branch name (`<label>/<N>-...`).
2. **If there is a ticket number**, fetch the **issue title only**:
   `python3 scripts/ticket.py export-as-source <N> --title`. It is copied verbatim into
   `CHANGELOG.md`, so it must come from `export-as-source`; `show` prefixes `#<N> ` and
   wraps. **If there is none**, see
   [Entries with no ticket](#entries-with-no-ticket) below and write the summary
   yourself.
3. Read `CHANGELOG.md`, find the `## Unreleased` header, and insert **at the top of its
   list** (reverse-chronological, newest first) exactly:
   ```
   - [#<N>] <issue title verbatim>
   ```
4. Use the title as-is. Only expand it if it is genuinely ambiguous standing alone.
5. Write the file and show the user the line that was added.

## Entries with no ticket

Not every change has an issue behind it, so the bracket is never empty. It carries the
same vocabulary `/commit` uses, and for the same reasons:

```
- [hotfix] <summary>     genuinely ticketless, a commit landing straight on develop
- [init] <summary>       pre-ticket-system work, until the first ticket-numbered commit
```

`workarea/` is gitignored here, so nothing in it reaches a commit and there is no
`[workarea]` entry form to write.

Without a ticket there is no title to fetch, so write the summary in the same voice a
ticket title would use: imperative, verb-first, sentence case, no trailing punctuation.

## Hard rules

- **One line per ticket**. Never a multi-line entry.
- **Verbatim**. Do not paraphrase or summarize the title.
- **Never a bare bullet.** Every line opens with a bracket, `[#<N>]`, `[init]`, or
  `[hotfix]`.
- **No headers, no blank lines, no formatting** beyond the bullet.
- Newest entry goes to the top of the Unreleased list.

$ARGUMENTS
