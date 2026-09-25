As a Python developer I want pybers never to write faked typography, and to tell me where a document already carries it, so that output looks typeset rather than approximated.

## Acceptance criteria

1. Superscript, subscript and small caps are written as the font's real feature, never as Numbers' synthetic scaling.
1. Reading text reports synthetic superscript, synthetic small caps and synthetic bold or italic as synthetic, distinct from the real forms.
1. A baseline shift is never reported as a superscript, and a superscript is never written as one.
1. All caps is written together with the capital spacing features it needs to render well.
1. A document read and saved keeps whatever synthetic typography it had.

## Constraints

- `superscript` and `capitalization = kSmallCaps` are Numbers' synthetic routes, and `kAllCaps` is legitimate, measured in `07`, `09`, `32` and `37` (`findings-04-text.md`).
