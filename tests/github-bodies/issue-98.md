As a contributor reading pybers I want every module-level function name to open with the verb saying what it does so that a name reads as an action rather than as the value it returns.

## Acceptance criteria

1. Every module-level function in `src/pybers/` opens its name with a verb. The 71 found on 2026-09-17, among them `borrowedShape`, `referenceSlots` and `offsetUnitFor`, no longer exist under those names.
1. The same holds for the helpers in `tests/` and `scripts/`.
   1. The `cmd` subcommand handlers in `scripts/pr.py` and `scripts/ticket.py` are included.
   1. `main` keeps its name, because Python tooling looks for it by that name.
1. The public names among them, `functionFor`, `functionNameFor`, `functionNamed`, `functionIndexFor`, `columnLetter` and `columnNumber`, change in `pybers/__init__.py` too, and no alias keeps the old name.
1. Methods keep their subject-first names.
1. The preflight fails on a module-level function whose name does not open with a verb, and names the file, line and function.
1. The suite passes and every golden reproduces unchanged.

## Constraints

- A verb list alone misses a noun that doubles as a verb: `formatClaims` and `formatKeyFor` both pass one, so the 71 are a floor, not the whole set.
