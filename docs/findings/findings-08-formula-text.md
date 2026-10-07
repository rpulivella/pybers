# Formula text

What Numbers displays for a formula it stores as nodes, what typing one back produces, and
the four node kinds where the two are not inverses. Measured for PYB-45, with the bracket
node added for PYB-67.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

---

## The operator table is in the schema, and it is not the one a grammar would give

`TSCE.ASTNodeArrayArchive.ASTNodeType` declares fifteen operators, each its own node type
carrying nothing but that type:

```
 1  ADDITION           7  GREATER_THAN            13  NEGATION      unary minus
 2  SUBTRACTION        8  GREATER_THAN_OR_EQUAL   14  PLUS_SIGN     unary plus
 3  MULTIPLICATION     9  LESS_THAN               15  PERCENT       postfix
 4  DIVISION          10  LESS_THAN_OR_EQUAL
 5  POWER             11  EQUAL_TO
 6  CONCATENATION     12  NOT_EQUAL_TO
```

`findings-02` records "7 comparison" from the corpus, which is the one comparison the
fixtures happen to use. The enum has six, and reading the corpus rather than the enum would
have produced a table missing five of them. **Derive from the declaration, corroborate with
the corpus, never the reverse.** numbers-parser took openpyxl's Excel tokenizer instead and
its precedence table carried no comparison at all, so `1<2` worked and `A+B<=10` raised.

Precedence follows Excel, which is what Numbers implements: a prefix sign binds tighter than
the power beneath it, so `-2^2` is four rather than negative four.

## Four functions bracket their arguments, and Numbers names which

`18-formula-literals` holds `IF(1>0,1,2)` as ten nodes:

```
17 NUMBER(1)  17 NUMBER(0)  7 GREATER_THAN
34 BEGIN_THUNK  17 NUMBER(1)  35 END_THUNK
34 BEGIN_THUNK  17 NUMBER(2)  35 END_THUNK
16 FUNCTION(62, numArgs=3)
```

The condition is bare and each branch is bracketed, which is lazy evaluation expressed in
the node array. Nobody types a thunk, so a parser has to put them back, and which functions
get them is not derivable from the corpus: `IF` is the only one in it.

**Numbers answers this directly.** `+[TSCEFunctionSpec functionIndexUsesThunks:]` in
Numbers 15.3.1 is fourteen instructions long and compares its argument against exactly four
values, returning false for everything else:

```
movz w0, #0            cmp w2, #312    b.gt  ...     19   CHOOSE
cmp w2, #19            b.eq true                     62   IF
cmp w2, #62            b.eq true                    313   IFS
ret                                                  336   SWITCH
cmp w2, #336           b.eq true
cmp w2, #313           b.ne false
movz w0, #1            ret
```

All four are the lazy-branch functions, which is the answer semantics predicts. **Every
argument after the first is bracketed**, measured for `IF` against the fixture above and
consistent with what laziness means for the other three, whose first argument is the
selector rather than a branch. `TSCEFunctionArgSpec` carries a per-argument `unwrapThunk`
flag, so a later ticket wanting certainty for `CHOOSE`, `IFS` and `SWITCH` can read it out
of the spec registry the same way `tools/functions-extract.py` reads the argument counts.

`LAMBDA` uses a second pair, 56 and 57, around its body.

## A table is named in a formula by its owner uid, which the table does not carry

A cross-table reference holds `AST_cross_table_reference_extra_info.table_id`, four 32-bit
words. That value is the `formula_owner_uid` on the calculation engine's dependency entry
for the target table, low half first, matched across `20-formula-shapes` on 2026-09-08.

**`TableModelArchive.haunted_owner.owner_uid` is not it**, and it looks like it is: it agrees
in 15 of 16 bytes and differs in the low byte (`0x37` against `0x14` for `Table 2`). Reading
it instead names no table at all, which is a plausible wrong answer rather than an error.

So `Table.identifier` is read the long way round, from the engine, exactly as
`internal_formula_owner_id` already was.

## A table name cannot be found by a rule over characters

Every fixture names its tables `Table 1` and `Table 2`, so nothing in the corpus says what
a real one looks like. Numbers permits a bracket, a comma, a quote, a colon and a name of
digits alone, and `Sales (EU)::A1` is a formula it accepts. No character class can say
where such a name ends: the comma of `Sales, net::A1` is also the comma that separates
arguments.

So a qualifier is matched against the names the document carries, longest first, and the
pattern is only the fallback for a caller that supplied none. That reads `2026::A1`, whose
first token is otherwise a number, and `SUM::A1`, whose first token is otherwise a
function.

The one spelling this cannot read is a name whose own first character is whitespace, since
a formula skips the gap between tokens and the two are indistinguishable. Refused by name
rather than misread, and Numbers has never been seen to keep one.

## Node type 25 is a bracket, and it is the one the author typed

`TSCE.ASTNodeArrayArchive.ASTNodeType` names 25 `LIST_NODE` and gives it one field,
`AST_list_node_numArgs`. The name describes what the schema permits rather than what
Numbers writes. Measured for PYB-67 across six real documents, since the 46 fixtures
carry none at all.

**Every instance encloses exactly one value.** All 4364 serialize to the identical four
bytes, `08196801`, which is the node type and `numArgs = 1`. A list of one is a bracket.
None opens a formula, and every one follows an addition, a subtraction, a multiplication
or a division.

**It is arithmetically a bracket, not decoration.** In one document a cell stores
`$D2*(1-$E2)` with a type 25 after the subtraction. D2 is 2868.18 and E2 is 0.60, and the
stored result is 1147.2720, which is the bracketed reading. Without the bracket the same
nodes give 2867.58.

### It records the bracket, and it does not record every bracket

Counted by distinct formula rather than by cell, because a formula pooled across a dragged
column would otherwise count many times:

| operand of an operator | carries a type 25 | formulas |
| --- | --- | --- |
| binds looser, so the text needs a bracket | yes | 185 |
| binds looser, so the text needs a bracket | no | 0 |
| binds at least as tightly, so no bracket is needed | yes | 193 |
| binds at least as tightly, so no bracket is needed | no | 516 |
| equal precedence, right of a minus or a divide | no | 1 |

A bracket precedence requires is recorded every time, 185 out of 185. A further 193
formulas record a bracket nothing requires, which is what preserving what a person typed
looks like: `22+(3/12)` is stored with its bracket and displayed with it, confirmed in
Numbers 15.3.1 on 2026-09-11.

**The last row is the exception that shapes the design.** One formula, `F22/(C22/1000)`,
needs a bracket that no node records. Its stored result is 1233.33 for F22 of 18500 and
C22 of 15000, which is the bracketed reading. The left-associative reading gives
0.001233.
So a renderer taking brackets only from the nodes writes a different number, and one
taking them only from the tree drops 193 formulas' brackets. **Both sources are needed.**

That exception is one formula dragged into three cells, which is one authoring event and
not three observations. It is too thin to carry a rule, so no rule was fitted to it: the
parser writes a type 25 for every bracket it reads.

### Where this leaves the round trip

A fourth kind of node whose text round trips and whose node array normalizes, alongside
whitespace and type 23. Rendering and reparsing every formula in the six documents leaves
the text identical in all 6386 that render, and the node shape identical in 6383. The
three that differ are that one formula, dragged into three cells, which gains the type 25
Numbers did not store. Nothing is lost and nothing changes meaning.

### What is not established

- **Whether Numbers ever writes `numArgs` above 1.** Nothing measured does, so the
  renderer refuses a wider one rather than writing a bracket around a single value.
- ~~**What Numbers does with a bracket around one value**, such as `(5)`.~~ Settled
  2026-09-13 in Numbers 15.3.1 against `tests/golden/20-formula-brackets.numbers`, which
  no formula in six documents demonstrates: `=(5)` displays as `(5)` and evaluates to 5,
  and `=1-(2-3)` keeps a bracket Numbers stores no node for and evaluates to 2. Writing
  a list node for every bracket read is therefore safe.
- **Which bit of a cell record, if any, relates to this.** Nothing here touches the record
  layout, because a formula is pooled and the bracket lives inside it.

## Round tripping is exact for what a person can type, and not otherwise

Every formula in the corpus, 77 across the fixtures, renders to text and parses back. **74
of the 77 return the identical node array.** All three exceptions are node type 23, and all
77 return identical TEXT, which is the property a caller can rely on. The bracket node
above is the fourth kind, measured outside the fixtures because none of them carries one.

### Whitespace is a node, and it cannot be recovered from the text

Types 32 and 33, `APPEND_WHITESPACE` and `PREPEND_WHITESPACE`, carry the spaces and
newlines a person typed. `19-formula-dragged` holds `SUM($B$1:$D$3)` with a trailing
newline node, and `46-formula-rare-functions` holds four inside one `MAKEARRAY`. Where each one
attaches is not established, because postfix order and text order disagree for an operator:
the body `r * c` of `MAKEARRAY(2,2,LAMBDA(r,c,r*c))` carries one whitespace node for two
spaces.

Dropped on the way out, and never written on the way in, which is what retyping the formula
in Numbers does to it as well.

### Type 23 is a second spelling of an argument that is not there

`15-number-duration-formats` labels its own cells, and `L2` reads `DURATION(,,,K1,,)`. That
formula stores:

```
22 EMPTY  22 EMPTY  22 EMPTY  36 REFERENCE(K1)  23 TOKEN(true)  23 TOKEN(true)
```

and `M1`, labeled `DURATION(,,K1,,,)`, stores `22 22 36 23 23 22`. Six argument nodes
each, matching `numArgs=6`, with type 22 in some omitted positions and type 23 in others.
`LAMBDA()` in `46-formula-rare-functions` writes `23 TOKEN(false)` for its empty body.

**Both are nothing, arithmetically.** `K1` is 102900.000166667, and 102900 minutes is 71
days 11 hours, which is `L1` exactly. The same number read as hours is 4287 days and
12 hours, which is `M1` exactly. No other argument contributes.

The rule choosing between 22 and 23 is not established. Type 23 is therefore rendered as
the omitted argument it behaves as, and typing that text back produces type 22, which is
the only one of the two whose placement the corpus establishes: the leading commas of both
formulas are 22. Those three formulas round trip through the text and not through the node
type, and nothing else in the corpus does.

## What a reserved function does, and why an argument count is not checked

Numbers stores a function it will not resolve as node type 31 with its spelling intact, and
that includes four it declares an index for and then refuses by name: `LATITUDE`,
`LONGITUDE`, `BEARING` and `ALTITUDE`, 281 to 284. `46-formula-rare-functions` holds all
four as type 31 beside `TEXT` and `RANGE`, which Numbers does not declare at all. So a name
becomes an indexed call only when the table carries an index for it and does not mark it
reserved, and `SPILL`, which is internal rather than offered, stays an indexed call because
that is how Numbers itself writes it.

Argument counts are not validated when parsing. `18-formula-literals` holds `ROUND(2.5)`,
which Numbers accepted, stored, and marked as an error cell. Refusing it here would decline
text Numbers itself takes.
