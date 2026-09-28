As a contributor I want the documents measurement starts from, the documents made from them to measure one thing, and the findings drawn from both kept in separate directories, so that each directory's contents state their purpose.

## Acceptance criteria

1. `tests/fixtures/` holds only origins: `00-baseline`, and every Numbers document not made from another document in either directory, each with its companion files (`.csv`, `.xlsx`, `.py`, `.png`) beside it.
2. Every Numbers document made from another document by one change lives in `tests/measurements/`, with its companion files beside it.
3. Every findings file lives in `docs/findings/`, with `FINDINGS.md` as the index.
4. Every test that runs across all Numbers documents reads both `tests/fixtures/` and `tests/measurements/`, and checks at least as many documents as it did before the move.
5. No reference to a moved file points at its old path, in source, tests, scripts, `CLAUDE.md`, `.claude/`, or any README.
6. A test names a document by its stem alone, and a stem found in neither directory, or in both, fails that test rather than skipping it.
7. Each directory's README states its rule in one sentence, a short method, and a catalog of one line per document: an origin says where it came from, and a measurement names its origin, its one change, and the finding it answers.

## Constraints

- Several of the tests that run across all documents assert a floor rather than an exact count, so a glob left on the old directory checks fewer documents and still passes.
- Most of the current per-file lookups skip a test when the document is missing, so after a move they report success while checking nothing.
- A document whose origin is not recorded is asked about, never guessed.
