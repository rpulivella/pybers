As a maintainer I want the repository tooling to have an output contract and a way of
being tested so that an agent driving it can tell data from failure, and so that a change
to a script is checked by something other than the next person to run it.

1. Every script under `scripts/` can emit machine-readable output, and human presentation
   never reaches that stream.
2. Errors and progress go to stderr. Redirecting a script's stdout to a file cannot
   capture an error as though it were data.
3. Exit codes are one documented set shared by every script rather than invented per
   script. `pr.py` already carries named constants for not-found, error and partial
   success; `ticket.py` carries none.
4. An operation an agent cannot safely repeat requires explicit confirmation that works
   unattended, rather than an interactive prompt.
5. `ticket.py export-as-source` is either subsumed by the general mode or its remaining
   reason to exist is written down.
6. Tooling tests have one agreed home, one way of being run, and a stated rule bounding
   what they assert.
7. `ticket.py list` classification is covered. An under-scoped token reaches the board but
   not the issues behind it, and every issue returns with no number, so "No tickets match"
   reports a permissions failure as an empty backlog.
8. Nothing added here re-implements what ruff and mypy do, which is #4.

## SPEC

Filed as Concept because two decisions are open and neither has a precedent in this
developer's other repositories to follow.

- **How tooling tests are structured.** The sibling repositories keep them as hand-run
  `scripts/test-*.py`, which pytest does not collect because the names are hyphenated.
  This repository's CLAUDE.md says the opposite, pytest rather than hand-rolled test
  scripts. Those two conventions disagree and the answer decides where these tests live,
  how they run, and whether they gate a pull request.
- **What the machine-readable mode looks like.** A `--json` flag, output chosen by whether
  stdout is a terminal, or both. Published guidance recommends a stable flag for scripted
  callers and describes terminal detection as the way to spare a caller from remembering
  it. Choosing changes every script's argument parser.

Two things established outside this repository that the decision should respect:

- The rule is older than agents. `clig.dev` puts it as "expect the output of every program
  to become the input to another, as yet unknown, program", with machine-readable output
  on stdout, logs and errors on stderr, and a stable flag for scripted callers.
- The failure it prevents is this project's own characteristic one. An error written to
  stdout is read by an agent as data, and the agent then acts on an error object it
  believes is a result, with nothing raising. That is silent wrongness rather than a
  crash, which is the shape of every hard defect this project has hit so far.

The point of departure already exists here and was solved once by hand: `export-as-source`
is a separate command only because `show` wraps to terminal width and substitutes emoji,
which mangles what a caller needs. That is the general problem, answered for one command.

Rewriting the scripts to whatever is decided is in scope. Adding a new script is not.
