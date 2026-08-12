---
description: Create and push a release tag on develop to trigger a PyPI publish.
argument-hint: <release type and version, e.g. "beta 0.1.0" or "final 0.1.0">
---

# /release-tag

Create and push an annotated release tag on `develop`. There are no release branches —
the tag alone records exactly what shipped.

## Steps

1. Parse `$ARGUMENTS` to determine the release type. If ambiguous, ask. Types:
   - `beta <version> [iteration]` → `release/v<version>-b<NN>` (default b01)
   - `final <version>` → `release/v<version>-Final`
2. Show the exact tag that will be created. Confirm with the user before doing anything.
3. Verify the current state:
   - `git status` — working tree should be clean
   - `git log --oneline -3` — confirm the commit being tagged looks right
   - Confirm the `version` field in `pyproject.toml` matches `<version>`
   - Warn if there are uncommitted changes
4. **Update `CHANGELOG.md`** before a `final` tag. List what shipped and reconcile it
   against the `## Unreleased` entries:
   ```
   python3 scripts/ticket.py list --status Done
   ```
   Run `/changelog-add` for any ticket missing a line, or confirm none are missing.
5. Create the tag: `git tag <tag>`.
6. **Do not push automatically.** Show the push command and ask the user to confirm:
   `git push origin <tag>`.

## Tag format reference

```
release/v0.1.0-b01     # pre-release build iteration
release/v0.1.0-Final   # shipped PyPI release
```

## Hard rules

- Never push a tag without explicit user confirmation.
- Always lowercase prefix; always a `v` prefix on the version.
- Leading zeros on iteration suffixes: `-b01`, never `-b1`.
- Never reuse a tag — increment the iteration if a rebuild is needed.
- Update `CHANGELOG.md` before a `final` release tag.

$ARGUMENTS
