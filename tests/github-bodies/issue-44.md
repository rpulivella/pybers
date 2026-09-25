As a Python developer I want a formula to name the functions it calls so that reading one tells me it sums a range rather than that it calls function 168.

1. Reading a formula reports each call by name, so `SUM`, `IF` and `SUMIFS` appear where 168, 62 and 231 do now.
2. A function the map does not know keeps its index and reads back unchanged, rather than raising or being dropped.
3. Writing a formula by name produces the same archive as writing it by index, so a document authored either way is byte-identical.
4. The map ships in the wheel, so `pip install pybers` names functions on a machine with no copy of Numbers.
5. Regenerating the map on a newer Numbers reports what changed, rather than silently replacing it.
6. A function call reports the argument counts its function accepts, so a caller learns that `HYPERLINK` takes one or two before writing either.
7. A function with no fixed maximum reports the repeating group that makes it unbounded, so `SUMIFS` reads as three arguments and then pairs rather than as an arbitrary limit.
8. Every argument count the fixtures and the example documents already contain is accepted by the function holding it, so a maximum a real document contradicts fails rather than ships.
9. `TRUE`, `HYPERLINK` and `CURRENCY` report their names, not bare indices.
10. Regenerating reports any index its two readings of Numbers disagree on, rather than picking one of them.
11. A function Numbers declares but refuses in a formula is named when read and refused when authored, so a document calling one reads as a name rather than as a bare number.
12. A function the format stores as its own node types reports the argument counts it accepts and no index, so a caller learns what `LET` and `LAMBDA` take without being handed an index that does not exist.
13. A function Numbers uses itself but never offers is named when read, so a document holding a spilled formula reads as `SPILL` rather than as a bare number.
14. A cell resolves to the formula it holds whatever else its record refers to, so styling a cell does not change which formula it reads as.

## SPEC

- The index is the only thing the archive holds: `AST_function_node_index` is a bare `uint32` and no name appears anywhere in the schemas. Arity is carried separately on the call, measured 2026-09-04, so `ROUND(2.5)` and `ROUND(2.5,0)` share index 126.
- **Operators are outside this entirely.** An operator IS its node type and carries no index, so nothing here should try to name one. Measured for PYB-41 and recorded in findings-02.
- **Excel's table is not a shortcut.** Its older binary format stores formulas the same way and Microsoft documents the index table as the `Ftab` in `[MS-XLS]`, but the numbering disagrees completely: `SUM` is 4 there against 168 here. Borrowing it yields plausible wrong functions rather than a failure.
- **Extraction reads the binary rather than running it**, which separates this from the archive-type map CLAUDE.md warns about: that one executes an unsigned copy of the app and this one does not. Names and indices sit in the compiled code, and reading them needs no toolchain: the Mach-O parsing and the AArch64 decoding are both Python, so there is no `objdump` and no `c++filt`. The technique is numbers-parser's and should be credited where `scripts/protos-extract.py` credits the schema dump.
- **The Objective-C metadata names every function and the authoring methods do not.** `TSCEFormulaCreationMagic` reaches 324 of the 350 functions Numbers lists; `+[TSCEFunction_<NAME> functionIndex]` reaches 346 and agrees with it on all 324. Measured 2026-09-04 on 15.3.1.
- **Arity is not the overload set.** The authoring class carries one overload per argument count Apple happened to need, which is why `SUM` has 1, 2 and 4 while `18-formula-literals` holds a three-argument `SUM` and an example document an eight-argument one. The real shape is `TSCEFunctionSpec`, built through `specWithFunctionName:minArgs:maxArgs:repeatingGroupSize:shipVersion:arguments:functionIndex:` at 367 sites in one function. That selector carries a ship version, so a function has more than one spec and choosing between them is the open question.
- That code shape **changed at Numbers 14.2**, so the extractor is tied to a version of the app rather than to the format, which is what AC 5 exists for. Output must be committed, for the same reason the schemas are: `pip install pybers` has no Numbers. The known-good pairs to check any run against are 168, 62, 231 and 126.
