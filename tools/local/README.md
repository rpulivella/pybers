# pybers: Local tools

**Development tooling only pybers needs.** The extractors read the Numbers application on
this machine and write a committed artifact into `src/pybers/`, the golden confirmation
drives Numbers itself, and the merge readiness report runs in CI. None of them ships in
the wheel, and the extractors cannot run on a fresh clone, which is why their output is
committed rather than built.

Contrast [`tools/workflow/`](../workflow/README.md), the shared development workflow:
filing tickets, opening pull requests, running the gates. That folder may not depend on
this one, and its workflow rules govern both. Run a command from the repository root as
`.venv/bin/python3 -m tools.local.<command>`. What a command imports sits in `lib/`.

```
protos_extract.py    dump the iWork protobuf schemas pybers builds on, and diff them
                     against the vendored reference set. Writes src/pybers/protos/
                     and src/pybers/_generated/*_pb2.py. Needs protodump and protoc,
                     both obtained separately
functions_extract.py derive the table of formula functions, each with its index,
                     name and the argument counts it accepts. Writes
                     src/pybers/_generated/functions.py
golden_confirm.py    confirm a golden in running Numbers and write a report of what
                     Numbers shows, through a helper app that holds the permissions
                     so Terminal holds none. Backs `/golden-confirm`, and nothing in
                     the preflight, CI or the suite runs it
merge_readiness.py   gather a branch's facts, check a pull request, and post one
                     verdict as a comment. `collect` runs on the branch with no
                     write access, and `report` runs this repository's code over
                     those facts
```

## Reading a binary is not running one

Both extractors open the application read-only and parse it as data. Nothing loads,
links, executes or modifies any part of Numbers, which is the line CLAUDE.md draws when
it rejects an approach that would execute an unsigned copy of the app.

The technique of finding values in compiled code rather than in a published table comes
from the numbers-parser project and from `protodump.py` by Peter Sobot, credited in each
extractor's docstring. Neither is vendored here.

## Why the output is committed

`pip install pybers` has no Numbers to read, and CI has none either. An artifact whose
generator is missing is the opacity this project refused when it declined to vendor
another project's schema dump, so the generators are committed beside what they produce
even though nobody can run them without a local Numbers.

Every extractor writes nothing unless `--write` is passed. The default run is a
read-only report and the differential check at once, which is what makes regenerating on
a newer Numbers reviewable rather than a silent replacement.

## What a golden confirmation leaves behind

`golden_confirm.py run <golden>` writes its report into `workarea/golden-confirm/<ticket>/<golden>/`,
beside a copy of the golden that is safe to open and save. Its expected values are
generated from the golden by `lib/golden_expected.py` on every run, every filled cell of
every table as pybers reads it, and written as `expectations.md`, to read beside the
copy, and `expectations.toml`, their machine form.

Every cell of every table is read through AppleScript for its value, formula and format,
and a cell the expectations leave out must be empty. A currency or a control is read in
the inspector too, since only the inspector shows its settings.

## A measurement's recipe

`golden_confirm.py measure <name>` makes `tests/measurements/<name>.numbers` in Numbers
from `<name>.recipe.toml` beside it: a copy of `base` and any `documents`, then each
`[[step]]` in order. Every step names its `document`, counted from 0, and the cell it
acts on by `sheet`, `table` and `range`. A `dataFormatSet` or `customFormatEdit` step
reads back what it changed, so a control Numbers did not take stops the run.

```
select           select the range
menuPress        press menuItem: copy, paste, delete or autofillDown
formatSet        set the range's format kind through AppleScript
valueSet         type value into one cell, as a person would
tableExtend      grow the table until it reaches the cell in range
dataFormatSet    set one Data Format control, named by setting, to value
customFormatEdit build a custom format, one part per step, named by setting
```

`dataFormatSet` names a control by the label Numbers shows beside it, such as
`Decimals`, or by its caption, such as `Minimum`. A control with neither is
`Unlabeled PopUpButton 1`, counted in screen order. A menu that titles two items alike
takes ` #2` after the title for the second. `customFormatEdit` parts are `Open`, `Name`,
`Type`, `Clear`, `Text`, `TextBefore`, `Token` for the last token's menu, `Rule`,
`RuleValue` and `OK`, and any other setting drags the palette token it names into the
newest format field.
