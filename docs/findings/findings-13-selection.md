# Findings: how fast the one resolver selects

How long `document.select` takes in its simplest form, which walks the sheets, tables and cells a selector reaches and parses the selector's text on each call. Measured for PYB-223 on 3 November 2026 with `tools/local/selection_benchmark.py` on an Apple silicon Mac under macOS 26.6.1 and Python 3.15.0, the fastest of three runs of each selector. Back to the [index](FINDINGS.md).

The benchmark builds each document in memory with `pybers.create` and never saves it. Every table but the large one has one header row, and every table has text across row 1 and a number in every other column of every other row:

| Document | Sheets | Tables on each | Each table | Stored cells |
| --- | --- | --- | --- | --- |
| Simple | 1 | 1 | 20 rows by 5 columns | 62 |
| Typical | 5 | 4 | 200 rows by 12 columns | 24,120 |
| Far beyond | 50 | 20 | 100 rows by 10 columns, and one table of 50,000 rows by 20 columns | 1,005,010 |

## The measurements

Seconds for each selection, and how many matches it returned:

| Selector | Simple | Typical | Far beyond |
| --- | --- | --- | --- |
| `Sheet 1` | 0.0000, 1 | 0.0000, 1 | 0.0001, 1 |
| `Sheet 1::Table 1::B2` | 0.0000, 1 | 0.0000, 1 | 0.0001, 1 |
| `::Table 1::B2` | 0.0000, 1 | 0.0001, 5 | 0.0021, 50 |
| `*::*` | 0.0000, 1 | 0.0001, 20 | 0.0024, 1,001 |
| `::B2:D9` | 0.0000, 1 | 0.0002, 20 | 0.0108, 1,001 |
| `[kind=number]` | 0.0003, 57 | 0.1328, 23,880 | 7.0746, 994,990 |
| `Sheet 1::Table *[kind=number]:not(:header)` | 0.0003, 57 | 0.0289, 4,776 | 0.0598, 9,900 |
| `:empty:nth-row(2n)` | 0.0002, 20 | 0.1049, 12,000 | 5.0925, 500,000 |

## Whether the simple form is fast enough

**It is.** A selection by name, by range or by pattern over names finishes within 11 milliseconds even across a thousand tables, since it never visits a cell. A condition visits every position of every table it reaches, about 3 microseconds each, so it costs 0.13 seconds across the typical document and 7 seconds across a document holding a million cells, returning a million references.

An index would not shorten that last case, because the time goes into producing and returning the matches themselves, not into finding the tables. A condition narrowed by its sheet and table, as a person or an agent writes one, stays near a twentieth of a second even in the far document. No dictionary, index or cache is added, and no timing check runs in CI.
