#!/usr/bin/env python3
"""\
A body carried between GitHub and a file on disk, and posted back unchanged.

**The bodies under `tests/github-bodies/` are a few real ones, each kept for a
construct it holds**, and a construct no real body holds is written out below. A body is
compared by the HTML it renders to, in GitHub's reading, where a newline inside a
paragraph is a break.

UPDATES
2026-10-06  The snapshot reduced to five bodies named for what they hold, for
            PYB-162.
2026-09-25  Written for PYB-134, replacing the tests of the unwrapper it removed.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/25"

import subprocess
import sys
from pathlib import Path

import pytest

# `scripts/` is not a package and is not installed, so it is reached by path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import github_body  # noqa: E402
import ticket  # noqa: E402

repositoryRoot: Path = Path(__file__).resolve().parent.parent
bodyDirectory: Path = Path(__file__).resolve().parent / "github-bodies"
snapshot: list[Path] = sorted(
    path for path in bodyDirectory.glob("*.md") if path.name != "README.md"
)


def readBody(path: Path) -> str:
    """Return a snapshotted body with its line endings as GitHub stored them."""
    return path.read_bytes().decode("utf-8")


def runRoundTrip(body: str) -> str:
    """Return a GitHub body as it posts back after an unedited export."""
    return github_body.formatBodyForPosting(
        github_body.convertBodyForEditing(body)
    ).text


def renderOnGitHub(body: str) -> str:
    """Return a body's HTML as GitHub renders a body, a newline being a break."""
    return github_body.renderHtml(body, breaks=True)


@pytest.mark.parametrize("path", snapshot, ids=[path.stem for path in snapshot])
def testAnExportedBodyPostsBackRenderingAsItDid(path: Path) -> None:
    """PYB-134 AC 1."""
    body = readBody(path)
    assert renderOnGitHub(runRoundTrip(body)) == renderOnGitHub(body)


@pytest.mark.parametrize("path", snapshot, ids=[path.stem for path in snapshot])
def testAnExportDiffersOnlyByABackslashOnEachBreak(path: Path) -> None:
    """PYB-134 AC 9: the same bytes, save a backslash where GitHub shows a break."""
    body = readBody(path)
    exported = github_body.convertBodyForEditing(body)
    assert exported.replace("\\\r\n", "\r\n").replace("\\\n", "\n") == body


def testABodyWithNoBreakInAParagraphExportsUnchanged() -> None:
    """PYB-134 AC 9, on a body this repository's tools wrote."""
    body = "Intro paragraph on one line.\n\n## Heading\n\n- item\n\n_Closes #1_\n"
    assert github_body.convertBodyForEditing(body) == body


def testAPostedBodyIsStableThroughASecondRoundTrip() -> None:
    """Posting what an export gave back changes nothing further."""
    for path in snapshot:
        posted = runRoundTrip(readBody(path))
        assert runRoundTrip(posted) == posted, path.name


def testAHardWrappedDraftPostsOneParagraphPerLine() -> None:
    """PYB-134 AC 2: a wrap is joined, and every line meant to stand alone stays."""
    draft = (
        "A paragraph wrapped by an editor\nat an arbitrary column.\n\n"
        "A hard break\\\nkeeps its line.\n\n"
        "## A heading\n\n"
        "- a list item\n- another\n\n"
        "| a | b |\n| - | - |\n| 1 | 2 |\n\n"
        "```\ncode line one\ncode line two\n```\n\n"
        "<!-- a comment -->\nNone\n\n"
        "_Closes #1_\n"
    )
    posted = github_body.formatBodyForPosting(draft).text
    assert "A paragraph wrapped by an editor at an arbitrary column.\n" in posted
    assert renderOnGitHub(posted) == github_body.renderHtml(draft, breaks=False)


def testABreakTypedOnGitHubSurvivesAnEditElsewhere() -> None:
    """PYB-134 AC 3: export, change another paragraph, post."""
    body = "Steps\nOpen the file\nMove B2:D5\n\nAn old sentence.\n"
    edited = github_body.convertBodyForEditing(body).replace("old", "new")
    posted = github_body.formatBodyForPosting(edited).text
    assert renderOnGitHub(posted) == renderOnGitHub(body.replace("old", "new"))


def testARenderingChangeIsRefusedNamingTheLines() -> None:
    """PYB-134 AC 4, through the check both directions share."""
    with pytest.raises(github_body.BodyRenderingError, match=r"\+<p>after</p>"):
        github_body.refuseRenderingChange("<p>before</p>", "<p>after</p>", "Posting")


def testBlankLineRunsCollapseAndNoBlankLineEndsABody() -> None:
    """PYB-134 AC 5."""
    posted = github_body.formatBodyForPosting("one\n\n\n\ntwo\n\n\n").text
    assert posted == "one\n\ntwo\n"


@pytest.mark.parametrize(
    "body",
    [
        "None\n_Closes #18_\n",
        "## Screenshots\n<!-- If none, write None. -->\nNone\n\n_Closes #18_\n",
        "- [x] tests\nNA The golden, since no archive changed\n",
        "line one  \nline two\n",
        "first line\r\nsecond line\r\n\r\n_Closes #5_\r\n",
        "CI: None\nObject model: None\n",
        "Steps to reproduce\nOpen the file\nMove B2:D5\n",
        "**CI**: None\n**Object model**: None\n",
    ],
    ids=[
        "italic closes line", "comment above a line", "NA line without its dash",
        "trailing hard break", "windows line endings", "unbolded labels",
        "lines typed on github", "bold labels",
    ],
)
def testEachCaseFoundOn20260924RoundTrips(body: str) -> None:
    """PYB-134 AC 6: each case the probe of 2026-09-24 found the unwrapper breaking."""
    assert renderOnGitHub(runRoundTrip(body)) == renderOnGitHub(body)


def testTicketsPullRequestsAndCommentsPostThroughOneReader() -> None:
    """PYB-134 AC 7: `pr.py` formats nothing itself; it calls `ticket.readBodyFile`."""
    source = (repositoryRoot / "scripts" / "pr.py").read_text(encoding="utf-8")
    assert source.count("ticket.readBodyFile(bodyPath)") == 4
    assert "mdformat" not in source and "github_body" not in source


def testReadingABodyFileFormatsIt(tmp_path: Path) -> None:
    """The reader every posting command uses returns the formatted body."""
    path = tmp_path / "body.md"
    path.write_text("wrapped\nline\n", encoding="utf-8")
    posted = ticket.readBodyFile(path)
    assert posted is not None and posted.text == "wrapped line\n"
    assert posted.tidied == 2


def testAnInterpreterLackingTheFormatterSaysSoAndPostsNothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The system interpreter lacks the dev extras, and a post there must not crash."""
    monkeypatch.delitem(sys.modules, "github_body")
    monkeypatch.setitem(sys.modules, "mdformat", None)
    path = tmp_path / "body.md"
    path.write_text("a body\n", encoding="utf-8")
    assert ticket.readBodyFile(path) is None
    assert "lacks mdformat" in " ".join(capsys.readouterr().out.split())


def testImportingPybersLoadsNoneOfTheFormatter() -> None:
    """PYB-134 AC 8."""
    loaded = subprocess.run(
        [sys.executable, "-c", "import pybers, sys; print(sorted(sys.modules))"],
        capture_output=True, text=True, check=True,
    ).stdout
    for name in ("mdformat", "markdown_it", "mdit_py_plugins"):
        assert f"'{name}" not in loaded, name


def testTheToolsImportWithoutTheFormatter() -> None:
    """The job posting the readiness comment installs rich alone, and imports these."""
    script = (
        "import sys; sys.path.insert(0, 'scripts'); import ticket, pr; "
        "print(sorted(sys.modules))"
    )
    loaded = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True,
        cwd=repositoryRoot,
    ).stdout
    assert "'mdformat" not in loaded and "'markdown_it" not in loaded


def testTheFormatterIsAFloorInTheDevExtras() -> None:
    """PYB-134 AC 8: declared as floors, and never as a library dependency."""
    import tomllib

    project = tomllib.loads(
        (repositoryRoot / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    development = project["optional-dependencies"]["dev"]
    for name in ("mdformat", "mdformat-gfm", "markdown-it-py", "mdit-py-plugins"):
        assert any(item.startswith(f"{name}>=") for item in development), name
        assert not any(item.startswith(name) for item in project["dependencies"])


def testTheTemplatesBreakingChangesLabelsEachStandAlone() -> None:
    """PYB-134 AC 10: a body filled from the template posts as it reads."""
    template = (repositoryRoot / ".github" / "pull_request_template.md").read_text(
        encoding="utf-8"
    )
    html = renderOnGitHub(github_body.formatBodyForPosting(template).text)
    for label in (
        "CI / automation / build",
        "Object model (public dataclass fields)",
        "Archive round-trip",
    ):
        assert f"<p><strong>{label}</strong>" in html, label
