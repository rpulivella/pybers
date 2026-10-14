---
description: Write and file a new GitHub Issue for pybers in this repo's exact format (opener, ACs, constraints), then add it to the Project board as Todo or Concept.
argument-hint: <description of the ticket>
---

# /ticket-create

Write and file a new GitHub Issue. The skill drafts the body in the required format,
then files it through the Python tool (`tools/workflow/ticket.py`. See `tools/workflow/README.md`),
which adds it to the pybers Project board and sets its Status. It does NOT assign the
issue, assignment happens at `/ticket-startwork`, when work begins. Never hand-run the
GitHub API outside the tool without the user's permission.

## Concept or Todo: the spec-in decision

Every ticket is filed into one of two starting states, and the difference is not
readiness of the *work* but readiness of the *specification*.

- **`Todo`** asserts the ticket is specified well enough to drive autonomously. Its ACs
  are concrete and testable, and any decision the build cannot make for itself has already
  been made. File here only when that is genuinely true.
- **`Concept`** means a human still has to think. Use it for work that is wanted but not
  yet pinned down, for anything blocked on a decision (e.g. the dual-consumer library/CLI
  split, or the named-styles design), and for a placeholder that will later split into
  several tickets.

`Concept` is also where a ticket **returns** when its spec turns out to be inadequate.
That is the signal that a human is needed again, which is why the board has no separate
blocked state.

Pass `--status Concept` when filing; `Todo` is the default.

## Steps

1. Read `$ARGUMENTS`, the user's description.
2. Pick exactly one **label** (the table below). The label IS the classification.
3. Draft the body using the [exact order](#body--exact-order) below.
4. **Run `/standards` on the draft file, both passes, and fix what it finds.** A ticket
   body is read by people and by agents and is then quoted verbatim into a branch name,
   a PR title and the CHANGELOG. Proofreading it after filing is too late.
5. **Show the draft to the user and wait for explicit approval before filing.** This is
   the spec-in touchpoint.
6. Decide the starting Status. See [Concept or Todo](#concept-or-todo--the-spec-in-decision).
7. On approval, file it:
   ```
   .venv/bin/python3 -m tools.workflow.ticket create --label <label> --title "<title>" --body-file <draft>
   .venv/bin/python3 -m tools.workflow.ticket create --label <label> --title "<title>" --body-file <draft> --status Concept
   ```
8. Report the issue URL the tool prints.

## Title format

The title carries three jobs: it becomes the **branch slug**, the **PR title**, and
the **CHANGELOG entry**, so it must be short and useful in all three.

- **≤ ~60 characters**, imperative and **verb-first**, or an `Area:` prefix when it aids
  scanning. e.g. "Read a real .numbers file into the object model", "Fix merge-range
  round-trip losing its anchor".
- Sentence case, **no trailing punctuation**.
- **No `feat:` / `[feat]` prefix**, the label carries the classification.

## Body: exact order

1. **Persona opener** (human). One sentence: "As a [role] I want [outcome] so that
   [reason]."
2. **Acceptance criteria** (human · the outcome). An `## Acceptance criteria` heading,
   then a numbered list, immediately after the opener. **The heading is required**, so
   that the contract is as findable as the SPEC under it. A ticket filed before
   2026-09-06 carries the headingless form and keeps it, since reformatting one buys
   nothing and `/ticket-edit` replaces whole bodies.
   **An AC states an outcome someone can check, never how the code is built.**
   That someone is whoever uses the thing, and for a repo tool or a skill it is the
   developer, who is still a user. "The writer mutates the archives rather than
   rebuilding them" is a design note wearing an AC's clothes, settling a decision the
   build has not reached yet. **Conformance is an outcome rather than an implementation
   detail, and it counts for an API as much as for a file format**, so "the value is
   written as decimal128", "the saved package opens with the macOS unzip tool" and
   "`pybers.open` returns one object that owns every edit" all belong. The line is
   whether the AC fixes what the artifact must BE or dictates how the code gets
   WRITTEN, and **of ten ACs nine still read from the outside**.
   Each AC is concrete, testable and individually referenceable ("AC 3 fails because…").
   ACs nest **one level**, an indented ordered list with markers all `1.` since markdown
   counts them. GitHub shows `i.`, `ii.`, so cite `4.ii`. A third level means two tickets.
   **Docs are ACs too.** Cover user docs with examples, for `import pybers` and the CLI
   or TUI, and the developer docs the change adds to, corrects or removes, or name the
   ticket that does.
3. **Design** (optional), under a `## Design` heading: CLI, TUI or GUI specifications,
   Figma links, screenshots or wireframes. Reference for the outcome, never
   implementation, and never in place of an AC.
4. **Constraints** (agent · read before building), under a `## Constraints` heading.
   **Usually absent, and never a plan.** The acceptance criteria above ARE the
   specification, which is why this section is not called one: a heading reading
   `SPEC` invites an author to specify, and specifying is directing the build.
   When a ticket is written nobody knows yet how it will be built, so anything
   resembling ordered steps is a guess that gets obeyed anyway. Two or three lines
   at most, holding only a fact already established that a competent build would
   otherwise get wrong *without failing*: a format trap the fixtures proved, a
   decision still open, a constraint that rules out the obvious approach. Anything
   phrasable as observable belongs in the ACs instead, and a constraints section as
   long as its ACs is a plan. A missing primitive is still a *separate prerequisite
   ticket*. A ticket filed before 2026-09-06 carries this section as `## SPEC` and
   keeps it.

**No other section.** A measurement goes in `docs/findings/`, a settled decision in
`docs/decisions.md`, and anything else in a comment on the ticket or a ticket of its own.
`.github/ticket_template.md` is the same shape.

## Labels

| Label | When to use |
|---|---|
| `feat` | New model type, archive read/write capability, or visible capability |
| `fix` | Bug fix, round-trip, formula, style |
| `perf` | Parse/write speed, memory |
| `refactor` | Restructure without behavior change |
| `docs` | Repo docs only, CLAUDE.md, READMEs, workarea, code comments. |
| `chore` | Config, tooling, dependencies, scripts |

## Hard rules

- **Never use `[ ]` checkbox syntax in the ACs.** Numbered lists only.
- Sections run opener, ACs, Design, Constraints, and no other.
- No "Definition of Done" section, the ACs are that.
- One label per issue.

$ARGUMENTS
