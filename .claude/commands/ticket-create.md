---
description: Write and file a new GitHub Issue for pybers in this repo's exact format (opener, ACs, SPEC), then add it to the Project board as Todo or Concept.
argument-hint: <description of the ticket>
---

# /ticket-create

Write and file a new GitHub Issue. The skill drafts the body in the required format,
then files it through the Python tool (`scripts/ticket.py`. See `scripts/README.md`),
which adds it to the pybers Project board and sets its Status. It does NOT assign the
issue, assignment happens at `/ticket-startwork`, when work begins. Never hand-run the
GitHub API outside the tool.

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
   python3 scripts/ticket.py create --label <label> --title "<title>" --body-file <draft>
   python3 scripts/ticket.py create --label <label> --title "<title>" --body-file <draft> --status Concept
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
2. **Acceptance criteria** (human · the outcome). Numbered list immediately after the
   opener. **An AC states an outcome someone can check, never how the code is built.**
   That someone is whoever uses the thing, and for a repo tool or a skill it is the
   developer, who is still a user. "The writer mutates the archives rather than
   rebuilding them" is a design note wearing an AC's clothes, settling a decision the
   build has not reached yet. **Conformance to a format is an outcome rather than an
   implementation detail**, so "the value is written as decimal128" and "the saved
   package opens with the macOS unzip tool" both belong. The line is whether the AC
   fixes what the artifact must BE or dictates how the code gets WRITTEN, and **of ten
   ACs nine still read from the outside**.
   Each AC is concrete, testable and individually referenceable ("AC 3 fails because…").
   ACs may nest **one level**, no deeper, `4.a`, `4.b` under `4`. A third level means the
   parent is really two tickets. **No label may repeat anywhere in the list**.
3. **SPEC** (agent · read before building). **Usually absent, and never a plan.** When a
   ticket is written nobody knows yet how it will be built, so anything resembling
   ordered steps is a guess that gets obeyed anyway. Two or three lines at most, holding
   only a fact already established that a competent build would otherwise get wrong
   *without failing*: a format trap the fixtures proved, a decision still open, a
   constraint that rules out the obvious approach. Anything phrasable as observable
   belongs in the ACs instead, and a SPEC as long as its ACs is a plan. A missing
   primitive is still a *separate prerequisite ticket*.
4. **Out of scope** (optional, OMIT BY DEFAULT).
5. **Context / notes** (optional, OMIT BY DEFAULT).

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
- ACs come before the SPEC; SPEC comes before any optional section.
- No "Definition of Done" section, the ACs are that.
- One label per issue.

$ARGUMENTS
