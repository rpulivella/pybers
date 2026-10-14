---
description: Create and push a release tag on develop to trigger a PyPI publish.
argument-hint: <release type and version, e.g. "beta 0.1.0" or "final 0.1.0">
---

# /release-tag

Create and push an annotated release tag on `develop`. There are no release branches,
the tag alone records exactly what shipped.

## Steps

1. Parse `$ARGUMENTS` to determine the release type. If ambiguous, ask. Types:
   - `beta <version> [iteration]` → `release/v<version>-b<NN>` (default b01)
   - `final <version>` → `release/v<version>-Final`
2. Show the exact tag that will be created. Confirm with the user before doing anything.
3. Verify the current state:
   - `git status`, working tree should be clean
   - `git log --oneline -3`, confirm the commit being tagged looks right
   - Confirm the `version` field in `pyproject.toml` matches `<version>`
   - Warn if there are uncommitted changes
4. **Reconcile `CHANGELOG.md`** before any tag. Every ticket marked Done since the last
   final release has its line under `## Unreleased`:
   ```
   .venv/bin/python3 -m tools.workflow.ticket list --status Done
   ```
   Run `/changelog-add` for any ticket missing a line, or confirm none are missing.
5. **Write the notes from `CHANGELOG.md`**, the source, never editing it to do so. The
   grouping, the Miscellaneous judgment and the beta's "In previous betas:" split are
   in `CONTRIBUTING.md` under Releases. Show the notes and confirm them with the user.
6. Create the annotated tag. A beta's message is its notes, and a final's is the tag name:
   `git tag -a <tag> -F <notes file>` or `git tag -a <tag> -m "<tag>"`.
7. **A final release only:** add `## X.Y.Z (build) - YYYY-MM-DD` directly beneath
   `## Unreleased`, the one edit a release makes to `CHANGELOG.md`, and publish a
   GitHub release titled `pybers X.Y.Z` holding the notes. PYB-147 automates both.
8. **Do not push automatically.** Show the push command and ask the user to confirm:
   `git push origin <tag>`.

## Tag format reference

```
release/v0.1.0-b01     # a beta, tag only
release/v0.1.0-Final   # a final release, tag and GitHub release
```

## Hard rules

- Never push a tag without explicit user confirmation.
- Always lowercase prefix; always a `v` prefix on the version.
- Leading zeros on iteration suffixes: `-b01`, never `-b1`.
- Never reuse a tag, increment the iteration if a rebuild is needed.
- Never sort, group or prune `CHANGELOG.md` itself. Its one release edit is a final's heading.

$ARGUMENTS
