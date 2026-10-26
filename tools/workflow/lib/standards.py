#!/usr/bin/env python3
"""\
The standards checks, which `standards_check` and the preflight both run.

Lint this repository's WRITING, the prose that humans and agents both read.
One deterministic pass over every file in scope; reports FAILURES (hard blocks)
and WARNINGS (review items).

**This is not a code linter and must never become one.** Naming, imports, type
hints, error handling and every other structural question belong to ruff and
mypy. The line is whether a rule is about WORDS. A docstring saying "colour" is
this gate's business; whether the function above it is named in camelCase is not.
That distinction is easy to blur, and blurring it once already produced a version
of this file that duplicated a linter nobody had configured yet.

What that leaves in scope, and why it includes Python:

  - Markdown, obviously. README, CONTRIBUTING, docs, findings, skills.
  - Python DOCSTRINGS AND COMMENTS, because a developer reading source is an
    audience, and the writing rules say so explicitly. Everything else in a .py
    file is blanked before a single prose rule runs, which is also why the
    weak-"let" check needs no carve-out for a `let` identifier: code is never in
    scope to be misread as English.

It checks prose only, with no CSS, HTML or Astro checks, since there is no markup here.

The design constraints inherited from upstream, each earned by a bug:

  - No path-less ripgrep, and no shelling out to search at all. Files are walked
    in Python, so there is no stdin to hang on and no `grep`-aliased-to-`ugrep`
    surprise.
  - Blank, never delete. Every strip replaces a span with spaces and keeps the
    newlines, so reported line numbers stay true to the source.

Scopes (argparse):
  (no args)         git-changed files, tracked and untracked. The preflight.
  --all             the full tree: src/, tests/, tools/, docs/, .claude/.
  PATH [PATH ...]   exactly those files or directories.  standards-ok: synopsis
                    Naming a path BYPASSES the auto-exclusions, so a workarea/
                    note can be linted on demand. Directories are walked.
  --text 'STRING'   lint a raw string, no file. Treated as .md unless --ext
                    says otherwise.

Generated code is never in scope. src/pybers/_generated/ is protoc output and
src/pybers/protos/ is the schema dump it came from. Neither is authored here and
neither may be hand-edited, so a finding in either is noise by construction.

Runs on the repository's venv, which holds rich.

UPDATES
2026-10-26  The split-verb check warns on a time adverb alone, as wingmate's MWM-49
            found.
2026-10-26  The exemption for `standards-check.py`, which no longer exists, removed.
2026-10-21  Comments come from the tokenizer, so a `#` inside a string is not
            read as one, for PYB-249.
2026-10-21  Fails the phrases the writing rules added, and a sentence opening
            on a conjunction or a preamble, for PYB-249.
2026-10-13  Moved here from `scripts/standards-check.py`, for PYB-204.
2026-10-13  Typed strictly, since mypy reaches this file now that its name
            imports, for PYB-204.
2026-10-13  The checks moved here from `standards-check.py`, which keeps only its
            command line, so a test and the preflight import them, for PYB-204.
2026-10-06  A line opening with a code span is checked, for PYB-178.
2026-09-28  The body snapshot is skipped, for PYB-134.
2026-09-14  `.github` and `tools` are in the default scope.
2026-09-01  Fixed a hole in the banned-phrase check that had been open since the
            list was written: every separator was a literal space, so a phrase a
            line wrap fell inside matched nothing at all. This repository wraps
            prose near 88 columns, which makes that roughly a coin flip on every
            occurrence rather than a rare case. Found by the gate passing a body
            containing "worth stating plainly" wrapped after "worth", and proved
            by the same phrase failing on one line and passing across two. All
            separators now match any whitespace run, and a new entry must follow
            suit. notJustRe already did, which is why it was never affected. No
            existing file was hiding one, so the fix closed the hole with no
            cleanup behind it.
2026-08-31  Added checkHardBreak. A markdown line ending in two or more spaces
            renders as a forced <br>, so it silently changes how a paragraph
            reflows, and the cause is invisible in the source. This repository
            hard-wraps its prose for line-based diffs, which makes the hazard
            routine rather than exotic: every paragraph line is a candidate.
            Runs against the RAW text rather than a prose view, because blanking
            a code fence replaces it with spaces and every blanked line would
            otherwise report as a finding. A LOCAL check with no upstream, so
            expect it to diverge.
2026-08-27  Added extractConsoleProse, a SECOND view of a Python file.
            extractPythonProse blanks string literals wholesale, which is right
            for docstrings and comments and hid a whole category of prose:
            console output is read by a person and is subject to the same
            rules. Measured rather than theorized, scripts/ticket.py carried
            thirty em dashes and the gate saw eighteen, the other twelve being
            console strings.

            Only literals passed to a printing call are taken, because a path, a
            URL, an API field name and a regex are all string literals and none
            of them is prose. The two views are OVERLAID rather than
            concatenated: both are the source with other regions blanked, so
            they are the same length and merge character by character.
            Concatenating doubled the file and made every line number from the
            second view wrong by the length of the first.
2026-08-27  Removed a Python house-style half that had no business here. The
            first version of this file also checked camelCase, module headers,
            pathlib, f-strings and error handling. All of that is code linting,
            it duplicates ruff and mypy, and it made a writing gate answerable
            for things writing has nothing to do with. What survived is the one
            docstring rule that is genuinely about prose: no Args/Returns
            sections. NOTE, because removing this leaves a real gap: ruff and
            mypy are configured in pyproject.toml as exclude stanzas ONLY, with
            no rule selection, and neither is installed. Nothing lints this code
            today. That is a ticket, not a reason to widen this script.
2026-08-27  First version, porting the prose checks from that upstream.

            TWO DIVERGENCES from upstream, both deliberate:
              - EM DASHES FAIL, and the ceiling is zero. The global writing
                rules ban them outright, calling for a comma, parentheses or a
                new sentence. Upstream allows two per file as a density warning.
                The rule here is absolute, so the check is too.
              - The banned-phrase list is this developer's GLOBAL list rather
                than the site's positioning bans. The site polices claims the
                site makes; nothing here makes them.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/27"

import argparse
import ast
import contextlib
import io
import itertools
import re
import subprocess
import tokenize
from pathlib import Path

from rich.console import Console

console = Console()

# A finding is its level, FAIL or WARN, the file, the line (0 for the file) and why.
type Finding = tuple[str, Path, int, str]

# ─────────────────────────────────────────────────────────────────────────────
# SCOPE
# ─────────────────────────────────────────────────────────────────────────────

# Never auto-discover these (git-changed and --all scopes).  An explicitly named
# path bypasses this list, because naming a file is the intent to check it.
skipSubstrings: tuple[str, ...] = (
    "src/pybers/_generated/",
    "src/pybers/protos/",
    "workarea/",
    ".venv/",
    # Bodies already on GitHub, frozen as test data, which a fix would corrupt.
    "tests/github-bodies/",
)
# NOTE tests/fixtures/ and tests/measurements/ are deliberately NOT here. The
# extension filter already excludes their .numbers files, and excluding either
# directory to keep binaries out would silently drop its README from the gate.

# Skipped even inside an explicitly named directory.  You never mean to lint
# protoc output just because it sits under a directory you named.
generatedOnly: tuple[str, ...] = (
    "src/pybers/_generated/",
    "src/pybers/protos/",
    ".venv/",
    ".git/",
)

# `.github` and `tools` were absent, so the pull request template and the code
# review rubric, which a contributor reads before anything else, had never been
# checked by the gate that states the rules they follow.
allRoots: tuple[str, ...] = (
    "src", "tests", "docs", ".claude", ".github", "tools",
)
checkExtensions: tuple[str, ...] = (".py", ".md")

# Files that DOCUMENT the banned language rather than commit it. They state the
# forbidden words in order to forbid them, so flagging them is pure noise.
#
# NARROW ON PURPOSE, and narrower than it first was. The exemption used to cover
# every check and to include CLAUDE.md, which made the repository's primary and
# most public document the LEAST checked prose in it. That is backwards, and it
# cost real violations: thirty-seven em dashes and a contraction sat in CLAUDE.md
# reporting clean. Only a file that enumerates banned words needs the carve-out,
# and it needs it only for the checks that read those words.
ruleDocPaths: tuple[str, ...] = (".claude/commands/",)

# The only checks a rule doc is exempt from. Everything else applies in full,
# because quoting a banned word is no reason to stop counting em dashes.
ruleDocExemptChecks: tuple[str, ...] = ("banned", "british", "weakLet")

# ─────────────────────────────────────────────────────────────────────────────
# PROSE RULES
# ─────────────────────────────────────────────────────────────────────────────

# Contractions are banned in docstrings and comments.  One pattern, accepting a
# straight (') or a curly (’) apostrophe.
contractions: tuple[str, ...] = (
    "can't", "don't", "won't", "doesn't", "isn't", "aren't", "wasn't",
    "weren't", "hasn't", "haven't", "didn't", "wouldn't", "couldn't",
    "shouldn't", "mustn't", "needn't", "let's", "what's", "here's", "who's",
    "where's", "how's", "I'm", "I've", "I'll", "it's", "that's", "there's",
    "they're", "we're", "you're", "I'd", "you'd", "he'd", "she'd", "we'd",
    "they'd", "you'll", "he'll", "she'll", "we'll", "they'll",
)
contractionRe = re.compile(
    r"\b(" + "|".join(re.escape(c).replace("'", "['’]") for c in contractions) + r")\b",
    re.IGNORECASE,
)

# British to American.  US English is a hard rule with no exceptions in prose.
# Curated word by word: deliberately NO blanket -ise/-our rule, which would
# trip promise, exercise, our and four.  A match preceded by an identifier
# separator (/ @ . - _) is skipped: that is a third-party identifier, which the
# global rule explicitly carves out.
britishSpellings: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcolour\w*", re.I), "color"),
    (re.compile(r"\bbehaviour\w*", re.I), "behavior"),
    (re.compile(r"\bfavour\w*", re.I), "favor"),
    (re.compile(r"\bflavour\w*", re.I), "flavor"),
    (re.compile(r"\bhonour\w*", re.I), "honor"),
    (re.compile(r"\bneighbour\w*", re.I), "neighbor"),
    (re.compile(r"\blabour\w*", re.I), "labor"),
    (re.compile(r"\bhumour\w*", re.I), "humor"),
    (re.compile(r"\bcatalogue\w*", re.I), "catalog"),
    (re.compile(r"\bjudgement\w*", re.I), "judgment"),
    (re.compile(r"\backnowledgement\w*", re.I), "acknowledgment"),
    (re.compile(r"\bprogrammes?\b", re.I), "program"),
    (re.compile(r"\bdefence\b", re.I), "defense"),
    (re.compile(r"\boffence\b", re.I), "offense"),
    (re.compile(r"\bpretence\b", re.I), "pretense"),
    (re.compile(r"\blicence\b", re.I), "license"),
    (re.compile(r"\bfibres?\b", re.I), "fiber"),
    (re.compile(r"\blitres?\b", re.I), "liter"),
    (re.compile(r"\bmetres?\b", re.I), "meter"),
    (re.compile(r"\bwhilst\b", re.I), "while"),
    (re.compile(r"\bamongst\b", re.I), "among"),
    (re.compile(r"\banalys(?:e|ed|ing|er)\b", re.I), "analyze"),
    (re.compile(r"\bcancell(?:ed|ing|er)\b", re.I), "single-l canceled"),
    (re.compile(r"\blabell(?:ed|ing|er)\b", re.I), "single-l labeled"),
    (re.compile(r"\bmodell(?:ed|ing|er)\b", re.I), "single-l modeled"),
    (re.compile(r"\btravell(?:ed|ing|er)\b", re.I), "single-l traveled"),
    (re.compile(r"\b(?:recogn|organ|optim|custom|initial|serial|normal|capital"
                r"|priorit|summar|minim|maxim|util|special|emphas|categor"
                r"|mechan|standard)is(?:e|ed|es|ing|ation|ations)\b", re.I),
     "-ize / -ization"),
    (re.compile(r"\bgrey(?:s|ed|ing|ish)?\b"), "gray"),
    (re.compile(r"\bcentre(?:s|d)?\b"), "center"),
)

# The global banned list.  These are this developer's own, and differ from the
# site's, which polices positioning claims the site makes and this repo does not.
# EVERY separator here is `\s+`, never a literal space, and a new entry must follow
# suit. Prose in this repository wraps near 88 columns, so a banned phrase meets a
# line break roughly as often as it does not, and a pattern written with a literal
# space matches the unwrapped half and misses the wrapped half in silence. Measured
# 2026-09-01: "worth stating plainly" failed on one line and PASSED across two, which
# is how it reached a pull request body through a gate that reported clean.
bannedPhrases: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bload[-\s]bearing\b", re.I), "banned phrase"),
    (re.compile(r"\bworth\s+stating\s+plainly\b", re.I), "banned phrase"),
    (re.compile(r"\bfull\s+stop\b", re.I), "banned phrase"),
    (re.compile(r"\bcarry\s+the\s+argument\b", re.I), "banned phrase"),
    (re.compile(r"\bthe\s+trap\b", re.I), "banned phrase, name the failure instead"),
    (re.compile(r"\bleverag(?:e|es|ed|ing)\b", re.I),
     "corporate filler, use use / apply / draw on / build on"),
    (re.compile(r"\bstanding\s+up\b", re.I),
     "corporate filler, use opening / building / bringing online"),
    (re.compile(r"\bcircl(?:e|es|ed|ing)\s+back\b", re.I),
     "corporate filler, name when and what instead"),
    # Covers "no longer is the hard part" too, so that phrase reports once.
    (re.compile(r"\bis\s+the\s+hard\s+part\b", re.I),
     "banned phrase, state the claim directly"),
    (re.compile(r"\bthe\s+(?:one|part)\s+that\s+matters\b", re.I),
     "banned phrase, state the claim directly"),
    (re.compile(r"\bcorp(?:us|uses|ora)\b", re.I),
     "use reference materials, context files or archive"),
    (re.compile(r"\bhand[-\s]+cod(?:e|ed|es|ing)\b|\bbuilt\s+by\s+hand\b", re.I),
     "misrepresents how the code is made"),
)

# A sentence never opens on a conjunction or a preamble. Case-sensitive, because a
# capital marks the opening: a wrapped line that starts `and` continues a sentence.
# A comment's `#` and a docstring's opening quote stay in the prose view.
sentenceOpenerRe = re.compile(
    r"(?:^[ \t]*(?:#+[ \t]*|[\"'][ \t]*|[-*>][ \t]+|\d+\.[ \t]+)?"
    r"|[.!?][\"'”’)\]]*[ \t\n]+)"
    r"(And|But|So|Allow\s+me|Let\s+us)\b",
    re.MULTILINE,
)

# "isn't just X, it's Y" and its variants.  Banned as a rhetorical move, not as
# a phrase, so the pattern has to catch the shape rather than a fixed string.
notJustRe = re.compile(
    r"\b(?:is|are|was|were)(?:\s+not|n['’]t)\s+(?:just|only|merely|simply)\b",
    re.IGNORECASE,
)

# The adverb goes BEFORE the auxiliary, never between it and the main verb.
splitVerbRe = re.compile(
    r"\b(am|is|are|was|were|be|been|being|have|has|had|will|would|can|could"
    r"|shall|should|may|might|must|do|does|did)\s+"
    r"(also|already|still|just|only|never|always|often|currently|recently"
    r"|simply|actually|\w+ly)\s+"
    r"(?!(?:a|an|the|in|on|at|to|of|for|with|from|about|as|than|that)\b)",
    re.IGNORECASE,
)

# Never end a sentence on a preposition.
strandedPrepRe = re.compile(
    r"\b(with|for|on|in|at|from|about|of|by|into|onto|over|under|through"
    r"|after|before|between|against|toward|towards|around|off|out|up)\s*[.!?]",
    re.IGNORECASE,
)

# A product never "lets" a user do something.  The JS/CSS keyword carve-out the
# site needs does not arise here, because prose checks never see code.
weakLetRe = re.compile(r"\b(lets?|letting)\b", re.IGNORECASE)
letCarveOut = re.compile(r"\blet\s+(alone|me|it\s+be)\b", re.IGNORECASE)

semicolonMax: int = 1





# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def read(path: Path) -> str:
    """Return a file's text, replacing anything undecodable rather than raising."""
    return path.read_text(encoding="utf-8", errors="replace")


def findLineNumber(text: str, index: int) -> int:
    """Return the one-based line number of a character offset."""
    return text.count("\n", 0, index) + 1


def blankSpan(match: re.Match[str]) -> str:
    """Replace a span with spaces, preserving newlines so offsets hold."""
    return re.sub(r"[^\n]", " ", match.group(0))


# A deliberate exception opts out by naming itself on the offending line. The
# reason is required by convention rather than by the parser: an unexplained
# suppression is indistinguishable from a mistake six months later.
suppressRe = re.compile(r"standards-ok")


def findSuppressedLines(text: str) -> set[int]:
    """Line numbers carrying a standards-ok marker.

    Line-scoped rather than file-scoped on purpose. A file-level opt-out would
    quietly cover violations added long after the exception was justified, which
    is how a suppression stops meaning anything.
    """
    return {index for index, line in enumerate(text.split("\n"), start=1)
            if suppressRe.search(line)}


def isRuleDoc(path: Path, check: str) -> bool:
    """True when this file is exempt from THIS check for documenting the rule.

    Takes the check name rather than answering in general. A blanket exemption
    silenced every rule on the files most likely to be read.
    """
    if check not in ruleDocExemptChecks:
        return False
    normalized = path.as_posix()
    return any(marker in normalized for marker in ruleDocPaths)


def extractPythonProse(text: str) -> str:
    """Everything except docstrings and comments blanked, newlines preserved.

    The writing rules cover Python docstrings and comments, because a developer
    reading source is an audience too.  However, running the prose checks over raw
    Python would flag identifiers, string literals and keywords as if they were
    sentences.  Isolating the prose resolves both at once: the rules reach the
    prose, and code is never in scope to be misread as English.

    Falls back to comments alone when the file does not parse, so a file with a
    syntax error still gets its comments checked instead of being skipped.
    """
    keep = ["\n" if character == "\n" else " " for character in text]
    offsets = list(itertools.accumulate((len(line) + 1 for line in text.split("\n")),
                                        initial=0))
    # A pattern read a `#` inside a string as a comment, and the tokenizer never does.
    with contextlib.suppress(tokenize.TokenError, SyntaxError):
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                start = offsets[token.start[0] - 1] + token.start[1]
                keep[start:start + len(token.string)] = token.string

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "".join(keep)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        docstring = ast.get_docstring(node, clean=False)
        if docstring is None:
            continue
        body = node.body[0]
        if not isinstance(body, ast.Expr):
            continue
        start, end = body.value.lineno, body.value.end_lineno
        lines = text.split("\n")
        offset = sum(len(line) + 1 for line in lines[:start - 1])
        span = "\n".join(lines[start - 1:end])
        keep[offset:offset + len(span)] = span

    # Docstrings quote code constantly, `open(..., "w")`, a usage synopsis, a
    # proto import. Those are samples, not sentences, exactly as a markdown fence
    # is, so they come out before any prose rule sees them.
    out = "".join(keep)
    # A docstring's own quotes go first, or a one-line docstring reads as a sample.
    out = re.sub(r'"""|\'\'\'', blankSpan, out)
    out = re.sub(r"`[^`\n]*`", blankSpan, out)
    return re.sub(r'"[^"\n]*"', blankSpan, out)


def extractConsoleProse(text: str) -> str:
    """String literals that reach a user, everything else blanked.

    The SECOND view of a Python file. `extractPythonProse` blanks string literals
    wholesale, which is right for docstrings and comments but hides a whole
    category of prose: `console.print("Dry run - nothing was filed.")` is read
    by a person and is subject to the same rules as any other sentence.

    Measured, not theorized. `tools/workflow/ticket.py` carried thirty em dashes and
    the gate saw eighteen; the other twelve were console output.

    Only literals passed to a printing call are taken. A path, a URL, an API
    field name and a regex are all string literals too, and none of them is
    prose. Blanking rather than removing keeps line numbers true.
    """
    keep = ["\n" if character == "\n" else " " for character in text]
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "".join(keep)

    lines = text.split("\n")
    offsets = []
    running = 0
    for line in lines:
        offsets.append(running)
        running += len(line) + 1

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        name = getattr(target, "attr", None) or getattr(target, "id", None)
        if name not in ("print", "echo", "sys.stdout.write", "write"):
            continue
        for argument in node.args:
            for piece in ast.walk(argument):
                if not (
                    isinstance(piece, ast.Constant)
                    and isinstance(piece.value, str)
                ):
                    continue
                if piece.end_lineno is None or piece.end_col_offset is None:
                    continue
                if piece.lineno != piece.end_lineno:
                    continue
                start = offsets[piece.lineno - 1] + piece.col_offset
                end = offsets[piece.end_lineno - 1] + piece.end_col_offset
                keep[start:end] = text[start:end]

    out = "".join(keep)
    # Rich markup tags are machine syntax, not words.
    out = re.sub(r"\[/?[a-z][^\]]*\]", blankSpan, out)
    return re.sub(r"`[^`\n]*`", blankSpan, out)


def mergeViews(first: str, second: str) -> str:
    """Combine two blanked views of one file, keeping offsets intact."""
    return "".join(a if a != " " else b for a, b in zip(first, second, strict=True))


def extractMarkdownProse(text: str) -> str:
    """Markdown with code fences and inline code blanked.

    A fence is a sample, not a sentence.  Blanking rather than removing keeps
    every reported line number true to the file on disk.
    """
    out = re.sub(r"```.*?```", blankSpan, text, flags=re.DOTALL)
    # Found on the original text: a blanked span at a line's start reads as indentation.
    for match in re.finditer(r"^\s{4,}\S[^\n]*$", text, flags=re.MULTILINE):
        out = out[:match.start()] + blankSpan(match) + out[match.end():]
    out = re.sub(r"`[^`\n]*`", blankSpan, out)
    return re.sub(r"\]\([^)]*\)", blankSpan, out)


# ─────────────────────────────────────────────────────────────────────────────
# PROSE CHECKS
# ─────────────────────────────────────────────────────────────────────────────

def checkContractions(path: Path, prose: str, findings: list[Finding]) -> None:
    """No contractions in docstrings, comments or docs."""
    if isRuleDoc(path, "contractions"):
        return
    for match in contractionRe.finditer(prose):
        findings.append(("FAIL", path, findLineNumber(prose, match.start()),
                         f"contraction '{match.group(0)}'"))


def checkCoAuthored(path: Path, text: str, findings: list[Finding]) -> None:
    """No AI attribution trailers, anywhere."""
    if ".claude/commands" in path.as_posix():
        return
    # Assembled in pieces so this line does not contain the literal it searches
    # for, which would make the checker flag itself.
    token = "Co-Authored" "-By:"
    for match in re.finditer(re.escape(token), text):
        findings.append(("FAIL", path, findLineNumber(text, match.start()),
                         f"{token} attribution"))


def checkBritish(path: Path, prose: str, findings: list[Finding]) -> None:
    """US English is absolute, with one carve-out for upstream identifiers.

    Rule docs are exempt for the same reason they are exempt from every other
    check here: a file that names a banned spelling in order to ban it is not
    committing the offense. Upstream exempts only this script by name, which
    left its own skill file failing on the word it exists to forbid.
    """
    if isRuleDoc(path, "british"):
        return
    for pattern, hint in britishSpellings:
        for match in pattern.finditer(prose):
            start = match.start()
            if start and prose[start - 1] in "/@.-_":
                continue
            findings.append(("FAIL", path, findLineNumber(prose, start),
                             f"British spelling '{match.group(0)}', use {hint}"))


def checkEmDash(path: Path, prose: str, findings: list[Finding]) -> None:
    """Em dashes are banned outright, not rationed.

    This is the sharpest divergence from the upstream script, which allows two
    per file and warns above that.  The rule here has no ceiling, so neither
    does the check, and it FAILS rather than warning.
    """
    if isRuleDoc(path, "emdash"):
        return
    # The literal this searches for is the character it bans, so a prose sweep
    # over this file will rewrite it and turn the detector into a comma
    # finder. That happened once. Built from a code point so no text
    # transform can reach it.
    emDash = chr(0x2014)
    for match in re.finditer(emDash, prose):
        findings.append(("FAIL", path, findLineNumber(prose, match.start()),
                         "em dash, use a comma, parentheses, or a new sentence"))


def checkBannedPhrases(path: Path, prose: str, findings: list[Finding]) -> None:
    """The global banned list, plus the not-just-X-but-Y rhetorical move."""
    if isRuleDoc(path, "banned"):
        return
    for pattern, hint in bannedPhrases:
        for match in pattern.finditer(prose):
            phrase = " ".join(match.group(0).split())
            findings.append(("FAIL", path, findLineNumber(prose, match.start()),
                             f"'{phrase}', {hint}"))
    for match in notJustRe.finditer(prose):
        findings.append(("FAIL", path, findLineNumber(prose, match.start()),
                         f"'{match.group(0)}', state the claim directly"))


def checkSentenceOpener(path: Path, prose: str, findings: list[Finding]) -> None:
    """A sentence opens on its subject, never on And, But, So, Allow me or Let us."""
    if isRuleDoc(path, "banned"):
        return
    for match in sentenceOpenerRe.finditer(prose):
        opener = " ".join(match.group(1).split())
        findings.append(("FAIL", path, findLineNumber(prose, match.start(1)),
                         f"sentence opens with '{opener}', open on the subject"))


def checkWeakLet(path: Path, prose: str, findings: list[Finding]) -> None:
    """A product enables or gives the ability; it does not 'let'."""
    if isRuleDoc(path, "weakLet"):
        return
    for match in weakLetRe.finditer(prose):
        if letCarveOut.match(prose, match.start()):
            continue
        findings.append(("WARN", path, findLineNumber(prose, match.start()),
                         f"weak '{match.group(0)}', prefer enables / gives the "
                         "ability"))


# Time adverbs read better before the auxiliary. Any other adverb, `can only express`,
# is correct English where it stands, and warning on it taught readers to ignore
# the check.
frontableAdverbs: frozenset[str] = frozenset({
    "currently", "recently", "presently", "previously", "formerly", "initially",
    "originally", "subsequently", "momentarily", "shortly", "lately",
})


def checkSplitVerb(path: Path, prose: str, findings: list[Finding]) -> None:
    """A time adverb belongs before the auxiliary, not inside the verb."""
    if isRuleDoc(path, "splitVerb"):
        return
    for match in splitVerbRe.finditer(prose):
        if match.group(2).lower() not in frontableAdverbs:
            continue
        findings.append(("WARN", path, findLineNumber(prose, match.start()),
                         f"split verb '{match.group(0).strip()}'"))


def checkStrandedPreposition(path: Path, prose: str, findings: list[Finding]) -> None:
    """A sentence does not end on a preposition."""
    if isRuleDoc(path, "strandedPrep"):
        return
    for match in strandedPrepRe.finditer(prose):
        findings.append(("WARN", path, findLineNumber(prose, match.start()),
                         f"stranded preposition '{match.group(0).strip()}'"))


def checkYearHyphen(path: Path, prose: str, findings: list[Finding]) -> None:
    """A year range takes an en dash."""
    for match in re.finditer(r"\b\d{4}-\d{4}\b", prose):
        findings.append(("FAIL", path, findLineNumber(prose, match.start()),
                         f"year range '{match.group(0)}' must use an en dash"))


def checkEllipsis(path: Path, prose: str, findings: list[Finding]) -> None:
    """Three periods are not an ellipsis."""
    for match in re.finditer(r"(?<![.\w])\.\.\.(?!\w)", prose):
        findings.append(("FAIL", path, findLineNumber(prose, match.start()),
                         "'...' must be a real ellipsis (…)"))


def checkHardBreak(path: Path, text: str, findings: list[Finding]) -> None:
    """A markdown line ending in two or more spaces renders as a forced line break.

    Never deliberate here, and invisible in the source, so it changes how a paragraph
    reflows with nothing to see in review. Write an explicit <br> when a break is
    genuinely wanted, which also says so to the next reader.

    Takes the raw text, not a prose view: blanking replaces a region with spaces of the
    same length, so every blanked line ends in whitespace and would report as a finding.
    """
    if path.suffix != ".md":
        return
    fenced = False
    for index, line in enumerate(text.split("\n"), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        # Inside a fence the spaces are literal content, not a break.
        if fenced:
            continue
        if line.strip() and line.endswith("  "):
            findings.append(("FAIL", path, index,
                             "line ends in trailing spaces, rendering as a "
                             "forced <br>"))


def checkSemicolons(path: Path, prose: str, findings: list[Finding]) -> None:
    """Semicolons in prose should be near zero."""
    if isRuleDoc(path, "semicolons") or path.suffix == ".py":
        return
    count = prose.count(";")
    if count > semicolonMax:
        findings.append(("WARN", path, 0,
                         f"{count} semicolons in prose (rule: near-zero)"))


def checkDocstringShape(path: Path, tree: ast.Module, findings: list[Finding]) -> None:
    """No Args/Returns/Raises sections, a docstring is prose, not a form.

    This is the one docstring rule that is about WRITING rather than structure.
    Whether a function HAS a docstring is a code-lint question and belongs to
    ruff; how the prose inside it is organized is a house writing rule.
    """
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        docstring = ast.get_docstring(node)
        if not docstring:
            continue
        for section in ("Args:", "Returns:", "Raises:"):
            if section in docstring:
                findings.append(("WARN", path, node.lineno,
                                 f"'{node.name}' docstring uses a '{section}' section, "
                                 "write the free-form why instead"))


# ─────────────────────────────────────────────────────────────────────────────
# DISPATCH
# ─────────────────────────────────────────────────────────────────────────────

def checkFile(path: Path, findings: list[Finding], text: str | None = None) -> None:
    """Run every check that applies to one file."""
    body = read(path) if text is None else text
    suffix = path.suffix

    if suffix == ".py":
        # Two views: docstrings and comments, then the strings a user sees.
        # OVERLAID rather than concatenated. Both are the source with the other
        # regions blanked, so they are the same length and merge character by
        # character. Concatenating doubles the file and every line number
        # reported from the second view is wrong by the length of the first.
        prose = mergeViews(extractPythonProse(body), extractConsoleProse(body))
        # A file that does not parse still has comments worth checking, and
        # reporting the syntax error is ruff's job rather than this gate's.
        with contextlib.suppress(SyntaxError):
            checkDocstringShape(path, ast.parse(body), findings)
    else:
        prose = extractMarkdownProse(body)

    local: list[Finding] = []
    # Both of these take the RAW body rather than the prose view.
    checkCoAuthored(path, body, local)
    checkHardBreak(path, body, local)
    for check in (checkContractions, checkBritish, checkEmDash, checkBannedPhrases,
                  checkSentenceOpener, checkWeakLet, checkSplitVerb,
                  checkStrandedPreposition, checkYearHyphen, checkEllipsis,
                  checkSemicolons):
        check(path, prose, local)

    # A file-level finding reports line 0 and cannot be suppressed this way, by
    # design: there is no line to carry the marker or the reason.
    skip = findSuppressedLines(body)
    findings.extend(f for f in local if not (f[2] and f[2] in skip))


def collectFiles(arguments: argparse.Namespace, warnings: list[str]) -> list[Path]:
    """Resolve the scope to a concrete list of files."""
    if arguments.paths:
        found: list[Path] = []
        for raw in arguments.paths:
            candidate = Path(raw)
            if candidate.is_dir():
                for child in sorted(candidate.rglob("*")):
                    if child.suffix in checkExtensions and child.is_file() \
                            and not any(
                                marker in child.as_posix()
                                for marker in generatedOnly
                            ):
                        found.append(child)
            elif candidate.is_file():
                found.append(candidate)
            else:
                warnings.append(f"no such path: {raw}")
        return found

    if arguments.all:
        found = []
        for root in allRoots:
            base = Path(root)
            if not base.is_dir():
                continue
            for child in sorted(base.rglob("*")):
                if child.suffix in checkExtensions and child.is_file():
                    found.append(child)
        for extra in sorted(Path(".").glob("*.md")):
            found.append(extra)
        return [p for p in found
                if not any(marker in p.as_posix() for marker in skipSubstrings)]

    # Default: whatever git says changed, tracked and untracked alike.  A new
    # file is the likeliest to carry a fresh violation and the one a
    # tracked-only default silently skips.
    changed: set[Path] = set()
    for command in (["git", "diff", "--name-only", "HEAD"],
                    ["git", "ls-files", "--others", "--exclude-standard"]):
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
        except OSError as exc:
            warnings.append(f"could not ask git for changed files: {exc}")
            continue
        for line in result.stdout.split("\n"):
            candidate = Path(line.strip())
            if (
                line.strip()
                and candidate.suffix in checkExtensions
                and candidate.is_file()
            ):
                changed.add(candidate)
    return [p for p in sorted(changed)
            if not any(marker in p.as_posix() for marker in skipSubstrings)]


def report(findings: list[Finding], files: list[Path], warnings: list[str]) -> int:
    """Print the report and return the exit code."""
    for warning in warnings:
        console.print(f"[yellow]scope:[/] {warning}")

    failures = [f for f in findings if f[0] == "FAIL"]
    reviews = [f for f in findings if f[0] == "WARN"]

    if not findings:
        console.print(f"[green]PASS[/], {len(files)} file(s) checked, no issues found.")
        return 0

    for level, colour in (("FAIL", "red"), ("WARN", "yellow")):
        rows = [f for f in findings if f[0] == level]
        if not rows:
            continue
        console.print(f"\n[bold {colour}]{level}[/] ({len(rows)})")
        for _, path, line, message in sorted(rows, key=lambda r: (str(r[1]), r[2])):
            where = f"{path}:{line}" if line else str(path)
            console.print(f"  [{colour}]{where}[/]  {message}")

    console.print(f"\n{len(files)} file(s) checked, "
                  f"[red]{len(failures)} failure(s)[/], "
                  f"[yellow]{len(reviews)} warning(s)[/].")
    return 1 if failures else 0
