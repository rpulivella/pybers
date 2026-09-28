As a Python developer, or an agent working in this repository, I want the package laid out by concern with its internals plainly private, so that reading one file answers one question and adding charting or pivot tables adds a directory rather than editing four.

## Acceptance criteria

1. `import pybers` reaches everything a caller needs and nothing a caller does not: the object model, the formula text functions, and `open`.
2. A package holding implementation carries a leading underscore, so an import states its own privacy rather than relying on a document to say so.
3. Each feature owns its whole vertical, its model types, its text where it has any, its archive read and its archive write, so adding a feature touches no existing one.
4. What more than one feature uses sits below the feature line rather than inside whichever feature reached it first: the container format, the calculation engine, and the generated schemas.
5. Each module holds one concern and its name says which, so a developer looks in one place and finds what they expected there. No module is split merely to reach a line count.
6. Nothing about a written document changes: every round trip, every golden file and every test passes, the imports they name aside.
7. `CLAUDE.md` describes the layout that exists, naming which packages are private and which are the public surface.

## Constraints

- `CLAUDE.md` names `pybers.model` and `pybers.numbersfile` today, so renaming either is a change to that document as well as to the tree.
- The tests import internals directly and are right to. Repointing them is part of the move rather than evidence that the boundary is in the wrong place.
- `Document.save` reaches the writer through a function-local import so that importing the model never drags in the persistence layer. That survives any layout, and no arrangement undoes it as a side effect.
