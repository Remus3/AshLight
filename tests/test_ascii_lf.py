"""FLEET item 8: every tracked (or to-be-tracked) text file is ASCII and LF
(PowerShell included)."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# AUDIT-HYGIENE H2: every non-binary file is checked (no suffix allowlist);
# a file is binary by a known binary suffix or a NUL byte in its content.
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".zip",
                   ".gz", ".7z", ".exe", ".dll", ".pyc", ".woff", ".woff2", ".ttf",
                   ".otf", ".pdf", ".node"}


def checked(files):
    """The files the ASCII / LF check reads: all but known binaries."""
    return [p for p in files if p.suffix.lower() not in BINARY_SUFFIXES]


def _tracked(run=subprocess.run):
    # Plan 150 (TESTS-A-02): a failing git used to read as "no files", so the
    # check passed after checking nothing.
    # tracked files plus untracked, not-ignored ones: a file is checked before
    # its first commit too (and the tree before its initial commit)
    out = run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others",
               "--exclude-standard"], capture_output=True, timeout=60)
    assert out.returncode == 0, f"git ls-files failed: {out.stderr!r}"
    files = [ROOT / f for f in out.stdout.decode().split("\0") if f]
    assert files, "git ls-files listed no tracked files"
    return files


def _problems(rel, data):
    out = []
    try:
        data.decode("ascii")
    except UnicodeDecodeError:
        out.append(f"{rel}: non-ascii")
    if b"\r" in data:  # CRLF and a bare CR alike
        out.append(f"{rel}: crlf")
    return out


def test_git_failure_is_not_a_pass():
    def run(*a, **k):
        return subprocess.CompletedProcess(a, 128, stdout=b"", stderr=b"fatal: dubious")
    with pytest.raises(AssertionError, match="git ls-files failed"):
        _tracked(run)

    def empty(*a, **k):
        return subprocess.CompletedProcess(a, 0, stdout=b"", stderr=b"")
    with pytest.raises(AssertionError, match="no tracked files"):
        _tracked(empty)


def test_bare_cr_and_ps1_are_checked():
    assert _problems("a.ps1", b"x\ry\n") == ["a.ps1: crlf"]
    assert _problems("a.py", b"ok\n") == []
    assert checked([Path("a.ps1")]) == [Path("a.ps1")]


@pytest.mark.git  # plan 097: git ls-files (read-only); run it by name
def test_tracked_text_is_ascii_lf():
    files = [p for p in checked(_tracked()) if p.is_file() and "fleet_kit" not in p.parts]
    bad = []
    for p in files:
        data = p.read_bytes()
        if b"\0" in data:
            continue
        bad.extend(_problems(p.relative_to(ROOT), data))
    assert bad == []
