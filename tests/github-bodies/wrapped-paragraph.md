As the owner of this machine I want the agent's write access bounded to this repository
so that no tool call can create or modify a file outside it.

1. A `deny` list exists in the project settings and refuses writes outside the repository
   working directory.
2. An attempt to create a path under the home directory but outside the repository is
   refused rather than performed.
3. The scratchpad directory the session is given remains writable, since it is the
   sanctioned place for temporary files.
4. `workarea/` remains writable, since it is the sanctioned in-repository scratch.
5. Read-only commands keep working without a prompt, so the existing allow list is not
   narrowed by this change.
6. The stale settings backup file, if one is still present, is deleted rather than left
   beside the live settings.
7. `CLAUDE.md` records that the deny list exists and what it bounds, so a future session
   does not remove it as unexplained configuration.

## SPEC

- Neither `.claude/settings.json` nor the user-level settings carries a `deny` list today,
  and `defaultMode` is unset. That gap is what allowed a directory to be created outside
  this repository without a prompt.
- The bound belongs in the project settings rather than the user-level file, because it is
  a property of this repository rather than of the machine.
