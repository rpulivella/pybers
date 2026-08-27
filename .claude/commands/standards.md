---
description: Proofread prose against the repo's writing standards, in two passes
---

# /standards

Proofread written prose. This is the rubocop equivalent for **writing**, and the
only thing it does is check words. Execution lives in
`scripts/standards-check.py`, one deterministic Python pass; this skill invokes
it, then performs the second pass itself, and relays both.

**Imported from `another repository` on 2026-08-27**, which stays upstream for the
script. When a check improves there, diff and re-import. Divergences are recorded in
the script's `UPDATES` block.

## ⚠ /standards IS TWO PASSES. ALWAYS BOTH. NO EXCEPTIONS.

**1. `scripts/standards-check.py`**
**2. The judgment read** — the inlined rubric at the end of this file.

**Every invocation. No conditions.** Not "the change was small", not "it was only
a docstring", not "the script came back clean". The script cannot see slop; it
matches patterns. **Reporting the script result alone is not a `/standards` run
and must never be presented as one.**

## Prose lives in more places than docs

Deliberately broad, because the writing rules do not care where a sentence sits:

```
markdown        README, CONTRIBUTING, CHANGELOG, docs/, findings-*
python          DOCSTRINGS AND COMMENTS ONLY — code is blanked first, so an
                identifier is never read as English
tickets, PRs    drafted to a file, so lint the file before filing it
```

The last is why this is a gate rather than a PR-review step: a ticket is quoted forever,
and catching it after filing is too late.

## Running it

```
python3 scripts/standards-check.py                      # git-changed files (preflight)
python3 scripts/standards-check.py --all                # the whole tree
python3 scripts/standards-check.py path/to/file.md      # exactly this
python3 scripts/standards-check.py --text 'draft copy'  # a raw string, no file
```

Untracked files are in the default scope, since a new file is the likeliest to carry a
fresh violation. Naming a path bypasses the auto-exclusions, which is how a `workarea/`
note gets checked on demand. `--text` is the fastest way to check a sentence before it
goes into a ticket, a PR body or a commit message.

Needs `rich`. Exit 1 on any FAILURE, so it gates cleanly. Relay the report; if there are
FAILURES, do not call the prose ready.

## What it checks

**The docstring and `-h` are the authority. Do not restate the checks here.**
Two things neither tells you:

- **Em dashes FAIL here, and the ceiling is zero.** Upstream allows two per file
  as a density warning. The global writing rules ban them outright, so this repo
  is stricter than its own upstream. Expect this to be the loudest finding on any
  file written before the gate existed.
- **Split verbs and stranded prepositions are heuristics, and they WARN.** A good
  number are benign — "can only express" is correct English, not a split verb.
  Read them, do not obey them.

## ⚠ This is NOT a code linter

The line is whether a rule is about **words**. A docstring saying "colour" is this
gate's business; whether the function above it is named in camelCase is not. Naming,
imports, type hints and error handling belong to ruff and mypy.

## Suppressing a deliberate exception

Put `standards-ok` **on the offending line**, with the reason:

```markdown
The upstream field is named `colour`.  <!-- standards-ok: third-party identifier -->
```

Line-scoped, never file-scoped: a file-level opt-out silently covers violations added
long after the exception was justified. File-level findings report line 0 and cannot be
suppressed at all, by design. Use it for quoted third-party copy and upstream
identifiers; `rg standards-ok` audits every one.

## The second pass — the judgment read

**Deliberately NOT an external skill.** The sibling repos call one, and it is installed
on this machine. This repo does not, for a reason that matters more here than there: pybers is going open source, and a contributor should
not have to install anything before they can write a ticket. A dependency that lives
outside the repo also goes stale outside the repo, silently, and takes the gate with
it.

So the second pass is inlined, versioned with this repository, and shorter. What it
loses in breadth it gains in never being absent.

**Read the whole piece, then answer these.** Every one is a judgment the script cannot
make. Report what you find; do not rewrite unasked.

1. **Fragments used for drama.** "Every time." "No exceptions." Complete sentences is
   the rule, and this is the most common tell.
2. **Prose that builds to a turn of phrase.** If a paragraph is arranged so the last
   line lands, the arrangement is the problem.
3. **Marketing register.** `robust`, `seamless`, `powerful`, `elegant`. Occasionally
   earned in an engineering claim; usually filler.
4. **The same point twice.** Restatement reads as emphasis and works as padding.
5. **Announcing instead of stating.** "It is worth noting that X" is longer than "X".
   Same for "importantly", "crucially", "the key insight is".
6. **Comments that are paragraphs.** A comment explains why, in one line.
7. **Claims that cannot be dated or checked.** "Recently" is not a date.
8. **Hedging over an unverified claim.** "Appears to" is honest when something was not
   verified and dishonest when it softens a claim nobody checked. Say which.

**The rubric is the authority, and it is short on purpose.** If a check becomes
mechanical, move it into the script and delete it from here. This list should only
ever hold what requires reading.

## Hard rules

- **`/standards` is both passes, always.** The script alone is never a
  `/standards` run.
- **No external skill dependency, on purpose.** The second pass is inlined so the
  gate cannot go stale or missing on a fresh clone. If it ever needs to grow
  substantially, that is a signal to reconsider, not to reach for an install step.
- **Never ship prose with a FAILURE.** Warnings are review items, not blocks.
- **A rule in CLAUDE.md is not enforced until a check exists.** If a writing rule
  is added, change the script in the same commit, or it will sit unenforced.
