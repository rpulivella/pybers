---
description: Confirm a golden in running Numbers and write a report of what Numbers shows. Needs a Mac with Numbers and the pybersdev-golden-confirm helper.
argument-hint: <golden in tests/golden/, such as 11-text-written-and-retyped.numbers>
---

# /golden-confirm

Open a temporary copy of a golden in running Numbers, check every cell its expected-values
file names, and write a report. The report turns confirming a golden into reading one
page, rather than a manual session in Numbers.

**It does not replace QA's confirmation.** Only Numbers can confirm a golden, and
only a person can confirm what the screenshots show. A run that passes means Numbers read
what the expected-values file says. The checks it leaves for QA remain yours.

## Steps

1. **Resolve the golden** from `$ARGUMENTS`. It must be a `.numbers` file in
   `tests/golden/`, with `tests/golden/<golden>.expected.toml` beside it. If the file has
   no expected values yet, write them from what the golden's row in
   `tests/golden/README.md` records and what each formula computes, **never** from what
   Numbers shows, since copying Numbers' output into the expectation proves nothing.
2. **Check the helper and its permissions:**
   ```
   .venv/bin/python3 scripts/golden-confirm.py permissions
   ```
   A missing or stale helper, a locked screen, or a missing permission stops here and
   names where to fix it. Build or rebuild the helper with
   `.venv/bin/python3 scripts/golden-confirm.py helper-build`, and relay any grant it
   asks for to the user rather than working around it.
3. **Preview, then run:**
   ```
   .venv/bin/python3 scripts/golden-confirm.py run <golden> --dry-run
   .venv/bin/python3 scripts/golden-confirm.py run <golden>
   ```
   Numbers opens a copy hidden, and shows on screen for about a second. The run survives
   switching desktops and full-screen apps, so the developer can keep working.
4. **Relay the result:** the passed, failed and left-for-QA counts, every failure
   verbatim, and the report path
   `workarea/golden-confirm/PYB-<N>/<golden>/report.md`. Name each check left for QA
   with the screenshot that answers it.
5. **A failure is a finding, not a retry.** Decide whether the expected value, the tool
   or the golden is wrong, and say which before changing anything. An expected value is
   corrected only when it named the same thing in a different spelling.

## Proving a damaged file fails

```
.venv/bin/python3 scripts/golden-confirm.py damage-check
```

Opens a truncated copy and a copy with a damaged tile archive, and passes only when each
run fails and says why. It refuses while Numbers is running, because a damaged document
can hang or crash it.

## Hard rules

- **Never open a golden itself in Numbers**, only the copy the tool makes. Numbers
  rewrites what it opens.
- **Never claim a golden confirmed** on a passing run alone. The QA checks and the
  record in `tests/golden/README.md` still follow the confirmation rules in `CLAUDE.md`.
- **Nothing in the preflight, CI or the test suite runs this**, and nothing under `src/`
  imports it. A test may import its pure functions but must never drive Numbers, which
  needs a logged-in Mac.
- **The report folder is never committed.** `/pr-merge` purges the ticket's folder.
