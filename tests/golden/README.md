# Golden files

A golden file is a `.numbers` package this library produced, **opened once in real
Numbers and confirmed correct by eye**, then committed so that any later change to the
writer that alters the output fails a test instead of shipping.

That confirmation step is what makes these worth having. Every other test in this
repository checks pybers against pybers, which can agree with itself while both halves
are wrong. Only Numbers itself can say that a file this library wrote is a file Numbers
considers valid.

## What is here

A golden lives here rather than under `tests/fixtures/` because it is not a fixture.
A fixture is input this library reads and was made by Numbers; a golden is output this
library wrote and Numbers accepted. Keeping them apart means nobody mistakes one for the
other when reaching for something to test against.

| File | Source fixture | Mutation | Confirmed |
| --- | --- | --- | --- |
| `11-value-types-noformats-A1-edited.numbers` | `11-value-types-noformats.numbers` | `A1` set to `Decimal("98765.4321")` | 2026-09-01, Numbers 15.3.1 |

The 2026-09-01 confirmation checked more than the edited cell. Every interactive control
in the row survived: the checkbox, the three-star rating, the slider at 50, the stepper at
1 and the popup menu all render as they did before. Those are carried by the trailing
references on each cell record, so their survival is what proves the writer patched only
the sixteen value bytes rather than rebuilding the record.

The source fixture labels itself: row 2 describes what each cell of row 1 holds. After
the mutation `A2` still reads "plain number 1234.5" while `A1` holds 98765.4321, which is
deliberate. The stale label is how a reader confirms at a glance that the edit landed in
the right cell and that nothing else moved.

## Confirming one

**Copy it somewhere else first, and open the copy.** Opening a `.numbers` file in
Numbers rewrites it. Confirmed on 2026-09-01: opening this golden renamed
`Index/ViewState-913882.iwa` to `Index/ViewState.iwa` and grew the package by 235 bytes,
because macOS document autosave saved it back with no edit and no prompt. Opening the
golden itself therefore destroys the very bytes being confirmed, and the file left behind
is Numbers' output rather than this library's.

Then open the copy. It must open with no warning and no repair prompt, the edited cell
must hold its new value, and every other cell must still match the description beneath it.
Record the date and the Numbers version in the table above.

Generation is deterministic, so a golden accidentally opened in place is restored by
regenerating it: the same source and the same edit produce byte-identical output, verified
on 2026-09-01.

**A golden file that has not been confirmed is not a golden file.** Until that row says
so, the test guarding it proves only that the writer is consistent with itself.

## Regenerating one

Deliberately not automated, because regenerating is how a bug gets locked in as the
expected answer. A golden is replaced only when the change to the output is intended, and
the replacement is confirmed in Numbers again before it lands.

```python
import shutil
from decimal import Decimal
from pathlib import Path
import pybers

source = Path("tests/fixtures/11-value-types-noformats.numbers")
golden = Path("tests/golden/11-value-types-noformats-A1-edited.numbers")
shutil.copy(source, golden)
document = pybers.open(golden)
document.sheets[0].tables[0].cell("A1").value = Decimal("98765.4321")
document.save()
```
