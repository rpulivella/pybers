# GitHub bodies

Real issue and pull request bodies, each copied byte for byte as GitHub stored it and
kept for a construct it holds. `tests/test_github_body.py` exports each one, posts it
back and checks it renders unchanged. A construct no real body holds, such as a table
row or a trailing hard break, is written out in that test file instead.

| File | Construct |
| --- | --- |
| `html-comment.md` | an HTML comment |
| `italic-closes-line.md` | the italic `Closes` line, a line italic from end to end |
| `lines-typed-on-github.md` | unbolded label lines, and lines typed on GitHub as separate lines |
| `windows-line-endings.md` | Windows line endings |
| `wrapped-paragraph.md` | a paragraph whose lines were typed as separate lines |

Every body also carries headings and list items. These files are frozen data, so the
prose gate skips them and nothing here is ever corrected.
