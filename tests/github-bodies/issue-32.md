## Ticket
Link: https://github.com/rpulivella/pybers/issues/3
Closes #3

`scripts/pr-preflight-check.py` runs pytest, the prose gate, ruff and mypy in one pass and reports all four, so a contributor sees everything to fix rather than the first thing. `/pr-review-code` step 2 now calls it, which retires the caveat every review report has carried since that skill was written.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

Three of the four gates run through real interfaces rather than a shell: `pytest.main()`, `mypy.api.run()` and the standards checker's own functions. Ruff is the exception, and a narrow one, since its Python package is a shim exporting `find_ruff_bin()` and no linting API. Locating the binary through that function beats trusting PATH.

**Every gate is repository-wide, so the script asks git nothing.** A branch-scoped draft of the standards gate needed a base ref to diff against, which a single-branch clone does not carry. That was the wrong problem: the review skill already requires the preflight to be repository-wide, and the checker's own `--all` scope is clean. Removing the diff machinery cut 87 lines, and the result runs unchanged on a default shallow CI checkout, so **#5 needs no `fetch-depth` setting**.

That rewrite exposed a second defect: `mypy.api.run([])` resolves `pyproject.toml` from the working directory, so the script only ever worked when invoked from the root. `main()` now changes to the root once, making that one guarantee rather than four separate habits.

## Preconditions / setup for testing
Run it with the project venv, not the system interpreter, because pytest, ruff and mypy live only there. `scripts/README.md` now names this script as that exception, and no longer claims it does not exist.

## Breaking Changes
**CI / automation / build**: A new script, and a mypy override declaring `ruff` a package without type stubs. Nothing is silenced by it, since that package wraps a Rust binary and has no types to check.

**Object model (public dataclass fields)**: None.

**Archive round-trip**: None. No library code changed.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] Round-trip / golden-file tests pass for any archive-layer change
- NA I added or updated pytest tests covering the change

Every criterion was proven by running the script, failure paths included: a planted failing test, a planted British spelling, a confirmation that ruff still runs after the prose gate fails, and a full green pass inside a throwaway clone carrying no base branch. A pytest test of this script would run the suite inside the suite. Whether repo tooling should carry tests at all is #11.

## Screenshot(s) / video(s)
None
