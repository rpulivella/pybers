## Ticket
Link: https://github.com/rpulivella/pybers/issues/4
Closes #4

`ruff check .` and `mypy` both run clean on this repository for the first time, over `src/pybers/` and `scripts/` alike, with no `# type: ignore` anywhere and no rule disabled to make something pass. Six ruff rule sets are selected with a comment saying why each is on and why three others are not, and mypy runs strict on the library.

Nothing lints this code today, so the first run had 150 ruff findings and 68 mypy errors under strict. Most were mechanical. Four were defects that had been sitting in the tree unnoticed, and one of them reached `develop` on 2026-09-02 through #14.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

### What the first run found

**A test defined twice.** `test_askingAnEmptyContainerSaysNothingIsPresent` appeared twice, byte for byte, in `tests/test_navigation.py`. The second shadowed the first, so one of them never ran. It arrived through a bad reconstruction during #14's commit split, and four reviews missed it.

**Ten `zip()` calls with no `strict=`.** Two in `applyDocumentEdits` pair the model's sheets against the document's and the model's tables against the archives'. A plain `zip` stops at the shorter side, so a count mismatch would have written some tables and skipped the rest in silence. Both now check the counts and raise a `WriteError` naming them. The two in `iwa.py` already had an explicit count check above them, so `strict=True` there states a guarantee rather than adding one.

**Four parameters with no annotation** in `reader.py`, against the house rule of full type hints everywhere. Annotating `resolveValue`'s `record` immediately exposed that the code assumed a type-3 cell's value is an integer key without ever checking. It now raises a `ReadError` naming what it got instead; a decoder regression there would previously have indexed the pool with the wrong thing and returned `None`, which reads as an empty cell.

**Three unchecked assumptions in the tooling**, which is what AC 7 was written about. `standards-check.py` read `.value` off a general AST statement and used `end_col_offset` without ever checking it for `None`, and `ticket.py` indexed a `TypedDict` with a variable key, which returns `object` and makes the tuple unpacking below uncheckable. All three ran fine and none was checked. Both tools were re-run after the narrowing.

### Protobuf type stubs, rather than silencing mypy

53 of the 68 strict errors were one cause: the generated `_pb2` modules build their classes at import time through the descriptor pool, so mypy sees a module with no attributes and reports every correct use of one.

The cheap fix is `follow_imports = "skip"`, making them `Any`. That was the first approach and it is the weaker one, because it silences the false positives and the true ones together. `protoc --mypy_out` writes a `.pyi` beside each module instead, so the protobuf surface is checked properly. Measured: with stubs, `root.sheetz` fails as `"DocumentArchive" has no attribute "sheetz"; maybe "sheets"?`; told to skip the import, that line passes. A mistyped field is the failure this format answers with a plausible wrong number, and this is the only tool that catches it before a fixture does.

The stubs cost 3.1 MB of committed output and one flag. They come from the **same** protoc invocation that already writes the modules, so there is no second step to forget, `protos-extract.py` now refuses to finish if any module lacks its stub, and `tests/test_generated.py` asserts the pairing without needing protoc installed.

### Two house-style consequences

**The `# -*- coding: utf-8 -*-` line is gone** from all 37 files and from `CLAUDE.md`. Python 3 reads source as UTF-8 already, so it declared nothing, and it was 37 of ruff's 42 `UP` findings.

**`pep8-naming` is off entirely** rather than half-disabled. It reported 752 violations, which is the whole set firing on almost every function, because this repository uses camelCase deliberately. Ignoring the four rules that fight camelCase would leave a set that is mostly disabled and reads as an oversight.

## Preconditions / setup for testing
`pip install -e ".[dev]"` now brings ruff, mypy and types-protobuf. Regenerating the protobuf schemas additionally needs `protoc-gen-mypy` on PATH, which `scripts/protos-extract.py` documents and checks for.

## Breaking Changes
**CI / automation / build**: The `dev` extra gains three packages. `mypy` with no arguments now checks both `src/pybers` and `scripts`, so CI can run one line.

**Object model (public dataclass fields)**: None. `MergeRange` gained a `bounds` property and `Decimal128` a `finiteParts` method, both stating guarantees their constructors already enforced.

**Archive round-trip**: None. The writer's behavior is unchanged except that two count mismatches now raise instead of truncating, neither of which can arise from a document this library read.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None
