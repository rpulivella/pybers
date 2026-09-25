As a Python developer I want a formula calling one of the four functions Numbers evaluates lazily to be stored the way Numbers stores it, so that a document this library writes opens showing the formula that was written.

## Acceptance criteria

1. Writing `CHOOSE`, `IFS` and `SWITCH` from text brackets the arguments Numbers brackets, checked against a document Numbers itself wrote.
2. A fixture holds one call to each of the four, so a later release changing the bracketing fails a test rather than passing quietly.
3. A golden file carries one of the three written by this library and confirmed on screen in Numbers.
4. `findings-08-formula-text.md` records where the bracketing was read from, so repeating the measurement on a later Numbers needs no rediscovery.

## Constraints

- Which functions thunk was settled for PYB-45: `+[TSCEFunctionSpec functionIndexUsesThunks:]` names 19, 62, 313 and 336 and nothing else. What is open is which of their arguments get brackets, measured for `IF` alone.
- `TSCEFunctionArgSpec` carries a per-argument `unwrapThunk` flag and the spec registry passes an argument list beside the counts `tools/functions-extract.py` already reads, so the binary may answer this without a fixture.
- A wrong answer here writes a document that opens wrong rather than one that fails to open, which is why only Numbers can close it.
