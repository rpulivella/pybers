As a developer I want a ticket title printed exactly as it was filed so that a title mentioning a bracketed word is not silently shortened on its way to my terminal.

## Acceptance criteria

1. `ticket.py list` prints a title exactly as filed, brackets and all.
2. `ticket.py start` does the same.
3. Every place a script prints text it did not author either escapes it or prints it with markup off.
4. A regression test fails for the original defect.

## Constraints

- Measured 2026-09-13. A title reading `Fix [hotfix] handling and the [PYB-99] prefix` prints from both commands as `Fix  handling and the [PYB-99] prefix`. The loss is selective, because `PYB-99` is not a style rich recognizes while `hotfix` is parsed as one and dropped, so a single example cannot reveal the fault.
- `showTicket`, `cmdBlock` and every path in `pr.py` already escape. The habit exists and is not applied everywhere, so this is a sweep rather than one edit.
