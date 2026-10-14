# Contributing to pybers

pybers is an open source community project built by independent contributors. This guide takes a contribution from a ready ticket to its merge, and says at each step what must be true before the next one starts.

Everyone taking part, in any space of this repository, follows the [code of conduct](CODE_OF_CONDUCT.md). A contribution written with an AI tool is held to the [AI policy](docs/ai-policy.md).

## Contributors

Write access is held by collaborators, and the project calls every collaborator a maintainer. At present only a maintainer opens a pull request. Anyone can [report a bug](https://github.com/rpulivella/pybers/issues/new?template=bug.yml), [request a feature](https://github.com/rpulivella/pybers/issues/new?template=request.yml) or [ask a question](https://github.com/rpulivella/pybers/issues/new?template=question.yml), and a security problem goes through the [security policy](SECURITY.md) instead.

A first-time contributor keeps at most one pull request open, and work that shows unguided AI use is closed under the [AI policy](docs/ai-policy.md).

## Prerequisites

- **A virtual environment at `.venv`**, holding pybers installed editable with its `dev` extra, on the Python that `requires-python` in `pyproject.toml` names.
- **A classic personal access token** with the `repo` and `project` scopes, in a git-ignored `.dev.vars` as `GITHUB_TOKEN=`. The ticket and pull request tools refuse to run without it, as [their README](tools/workflow/README.md#github-authentication) explains.
- **Claude Code, optionally.** Each step below names the skill in `.claude/commands/` that carries it out. A skill is a written procedure, so it can be followed by hand as well.

One command runs every local gate, and it is the only one this guide shows:

```bash
.venv/bin/python3 -m tools.workflow.preflight
```

## Getting Started

### 1. Start a Ticket

All work in this repository is contributed against a ticket. To get started, pick a ticket marked `Todo` on [the board](https://github.com/users/rpulivella/projects/3). A ready ticket is preferred to writing your own, and [Filing a Ticket](#filing-a-ticket) covers the case where none fits. pybers has a well-maintained harness, the skills, rules and documents an agent works from, that will expedite every step while keeping each one within the repository's rules and conventions.

`/ticket-startwork` cuts a branch named `<type>/<N>-<title-slug>` from a current `develop` and moves the ticket to `In Progress`.

**Before writing**, the branch must exist, cut from the `develop` on GitHub and not an older copy.

### 2. Write the Change

A competent Python developer would assume none of these:

- **Read [the findings](docs/findings/FINDINGS.md) before designing anything.** Several of them make the obvious approach wrong, and a wrong offset in this format yields a plausible wrong number, never an exception.
- **A number is `Decimal`, never `float`**, because Numbers stores decimal128.
- **A formula is a tree of nodes.** The file holds no formula text, so nothing here parses or edits one as a string.
- **Writing changes the archives that were read**, never new ones built from the model, and anything pybers does not understand is carried through untouched.
- **Every change to what pybers writes earns a golden**: a real document, one mutation, opened in Numbers and confirmed by a maintainer, then kept as a regression test. [The golden README](tests/golden/README.md) says how, and `/golden-confirm` drives Numbers through it.
- **Each feature is tested from both of its users**, a script calling `import pybers` and a command run in a terminal. The library prints nothing, and what a command prints follows [the command-line design](docs/cli-design.md).
- **Functions, variables and parameters are camelCase**, methods are named subject first and verb last (`rowAdd`), and type names lead with their base noun (`Table`, `TableRow`). ruff and mypy are configured for it.
- **The prose gate checks every comment, docstring and document** the way ruff checks code, because a wrong comment is a defect here.
- **A commit is one line**, in the format under [Commits](#commits), and leaves the suite green. `/commit` writes it.

**Before opening a pull request**, the preflight must pass.

### 3. Open a Pull Request

A pull request opens as a draft, filled from [the template](.github/pull_request_template.md), and carries its line in `CHANGELOG.md`. `/changelog-add` writes that line and `/pr-draft` opens the draft. Opening one early is encouraged, because a diff is easier to follow as it grows.

**Before review**, three things must be complete: every acceptance criterion is met, tests belonging to the ticket were written and pass, and the full preflight passes.

### 4. Review

`/pr-review-code` moves the ticket to `Code Review`, runs the preflight, then reads the change against [the review rubric](docs/code-review-rubric.md), six questions asked of the change and never of the code around it. A clean review takes the pull request out of draft, and GitHub then runs two checks:

- **`preflight`**, the same four gates the local command runs: pytest, the prose gate, ruff and mypy.
- **`readiness`**, what exists only on a pull request: the template and its checklist, the CHANGELOG line, the ticket identifier, currency with `develop`, dependency advisories, and a confirmation date for every golden touched. Its report is posted as one comment, replaced on every run.

**Before approval**, both checks must pass. Green means a person can now test the change, never that it is ready to merge.

### 5. Approval

A maintainer with authority over the project reviews the pull request and approves it on GitHub. Nothing merges without that approval, however green its checks.

**Before merging**, a maintainer must have approved the pull request.

### 6. Merge

That maintainer runs `/pr-merge`, which merges the pull request into `develop` as a real merge, keeping its commits, and deletes its branch. The closing keyword closes the ticket, and the board marks it `Done` by itself. A ticket split across several pull requests stays open until the last one.

## Filing a Ticket

When no ready ticket fits, write one from [the ticket template](docs/templates/ticket.md): one sentence saying who wants what and why, then acceptance criteria that each state an outcome someone can check, never how to build it. Its title becomes the branch name, the pull request title and the CHANGELOG line. `/ticket-create` files it, and `/ticket-edit` revises it.

A ticket filed as `Todo` is ready to start. A `Concept` ticket still needs a person to decide something, and goes back there whenever its specification turns out to be inadequate.

## Skills

| Skill | Where it serves |
| --- | --- |
| `/ticket-startwork` | 1. Start a Ticket |
| `/commit` | 2. Write the Change |
| `/golden-confirm` | 2. Write the Change, confirming a golden in Numbers |
| `/standards` | 2. Write the Change, proofreading prose |
| `/script-write` | 2. Write the Change, for a tool in `tools/` |
| `/changelog-add` | 3. Open a Pull Request |
| `/pr-draft` | 3. Open a Pull Request, or revise its body |
| `/pr-review-code` | 4. Review |
| `/pr-merge` | 6. Merge |
| `/ticket-create` | Filing a Ticket |
| `/ticket-edit` | Filing a Ticket, revising one |
| `/release-tag` | Releases |

## Reference

### Names

A ticket is `PYB-34` in prose and a pull request `PR #38`, never a bare number and never a bare `#`. A commit subject keeps the bare `[34]`, and `Closes #34` keeps its `#` because GitHub parses no other form. The key is declared in `pyproject.toml` under `[tool.pybers]`.

### Commits

`[<N>] <prefix>: <summary>`: the ticket number from the branch name, a prefix from `feat` `fix` `perf` `refactor` `style` `docs` `chore`, and an imperative summary. One line of at most 60 characters, with no body and no `Co-Authored-By` trailer. A ticketless urgent change is `[hotfix] <prefix>: <summary>`, and it is rare.

```
[14] feat: decode merged cell ranges from the merge store
[31] fix: keep run indices aligned across astral characters
```

Each commit takes the prefix that describes it. A `feature/12-...` branch normally holds several `feat:` commits and then `docs:` or `fix:` as the work turns.

### Branches

`develop` is the one long-lived branch, and a tag records each release. A branch's `<type>` comes from its ticket's label: `feat` becomes `feature`, `fix` becomes `bugfix`, and `perf`, `refactor`, `docs` and `chore` stay as they are.

GitHub holds `develop` to these rules:

- No direct push, and a pull request for every change
- The `preflight` and `readiness` checks passing before a merge
- One approving review from a maintainer, which an administrator bypasses on a pull request of their own, since GitHub permits no author to approve their own
- No requirement to be current with `develop`, which `readiness` reports instead
- An administrator is able to bypass each rule above

### Releases

`/release-tag` is used to issue every release, both betas and final releases, from `develop`. Since `CHANGELOG.md` is maintained during development, it provides the source of each release's notes.

- **A beta** is issued as an annotated tag whose message contains its notes. `CHANGELOG.md` is left as it is and keeps receiving entries as development continues.
- **A final release** is a tag and a GitHub release titled `pybers X.Y.Z`. One heading is added to `CHANGELOG.md`, `## X.Y.Z (build) - YYYY-MM-DD`, above the lines it published, capping that release and starting the next. New entries go above this heading, under `## Unreleased`, with one blank line between the heading and the entry just above it.

A release's notes group their lines by ticket label under short headings, in the order Features, Fixes, Performance, Refactoring, Documentation and Maintenance, each group in the order its lines were written. Miscellaneous comes last, holding every line with no such label, and the maintainer decides at publication which of them to include. A beta lists what is new since the previous beta first, and the rest under "In previous betas:".

```
release/v<version>-b<NN>    # a beta, tag only
release/v<version>-Final    # a final release, tag and GitHub release
```

### Layout

| Path | What lives here |
| --- | --- |
| `src/pybers/` | The library, a directory per feature, with the command line in `cli/`. A leading underscore means a caller has no business there. |
| `tests/` | The suite, with `fixtures/` and `measurements/` (documents Numbers wrote) and `golden/` (documents pybers wrote and Numbers confirmed). Each README catalogs its files. |
| `docs/` | The settled decisions, the format findings, the review rubric and the command-line design. |
| `tools/workflow/` | The ticket and pull request tools, the preflight and the prose gate, shared rather than pybers-specific. |
| `tools/local/` | What only pybers needs: the schema and function extractors, the golden confirmation and the merge readiness report. |
| `.claude/commands/` | The skills. |
| `.github/` | The templates and the three workflows that check a pull request. |
| `workarea/` | Scratch space, ignored by git apart from its README. |
