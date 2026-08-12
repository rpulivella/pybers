---
description: Scaffold or extend a Python tool in scripts/ following the house style.
argument-hint: <what the script should do>
---

# /script-write

Author a Python tool for: **$ARGUMENTS**

Tooling is real Python — the mechanical, repeatable half of a skill lives here; the
human-in-the-loop half stays in the skill. Pull `scripts/README.md` and follow it
exactly. Note: this governs `scripts/` (repo tooling) only — `src/pybers/` (the library
itself) follows the same core conventions but is documented separately in `CLAUDE.md`.

## Steps

1. Read `scripts/README.md` for the full house style. In brief: **never shell out when a
   library can do the work** (typed exceptions, not bash parsing); **camelCase**; **full
   type annotations** + dataclasses; **docstrings** everywhere; **`argparse`** with
   `cmd`-prefixed handlers; **`rich`** output, never bordered; **logic separated from
   presentation** (logic returns results, never prints); **`--dry-run`** on anything that
   mutates; the **dunder header block**; **no contractions**; **US English**.
2. Decide the shape. Non-trivial tools split into `<topic>_config.py` / `<topic>_lib.py`
   (pure logic) / `<topic>_presenter.py` / thin `<verb>.py` front-ends.
3. If it runs for a while (tests, batch import, sync), give it its **own timestamped log
   file** under `workarea/logs/` — parse the log, never re-run to see what happened.
4. Write it, then exercise it (including `--dry-run`) and report the result.

$ARGUMENTS
