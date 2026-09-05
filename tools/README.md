# pybers: Tools

**Development tooling that builds pybers itself.** Each program here reads the Numbers
application on this machine and writes a committed artifact into `src/pybers/`. None of
them ships in the wheel, none runs in CI, and none can run on a fresh clone, which is
exactly why their output is committed rather than built.

Contrast [`scripts/`](../scripts/README.md), the repository harness: filing tickets,
opening pull requests, running the gates. Those serve the workflow. These serve the
library. The house code rules in that README govern both.

```
protos-extract.py
             dump the iWork protobuf schemas pybers builds on, and diff them
             against the vendored reference set. Writes src/pybers/protos/ and
             src/pybers/_generated/*_pb2.py. Needs protodump and protoc, both
             obtained separately. Live now.
functions-extract.py
             derive the table of formula functions, each with its index, name
             and the argument counts it accepts. Writes
             src/pybers/_generated/functions.py. Needs nothing but rich. Live
             now.
lib/         imported, never run. numbersapp.py locates the Numbers install and
             reads its identity; machoreader.py reads a Mach-O binary as data.
             Neither is a command and neither has a CLI, which is what the
             subdirectory records.
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
