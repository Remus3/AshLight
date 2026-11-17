"""AUDIT-HYGIENE (audit findings H2-H6, docs/audit/2026-11-17-audit.md).

H2 the ASCII / LF check covers every non-binary tracked file, not a suffix
   list (.log, .vbs, .sh, .xml, .svg and LICENSE were skipped).
H4 paths.SIDECAR_SUBDIRS names every sidecar folder CLAUDE.md lists, and
   all_runtime_paths() includes the worktree folder and the overlay profile.
H5 the drive-path scan covers tools/.
H6 the hand-off spells the sidecar as <sidecar>, not a drive path.
H3 decision 0002 names pytest as the one test dependency.
"""

import re
from pathlib import Path

import test_ascii_lf as ascii_lf
import test_sidecar_paths as sidecar_test
from server.al import paths

ROOT = Path(__file__).resolve().parents[1]


def test_ascii_check_has_no_suffix_allowlist():
    names = ["x.log", "x.vbs", "x.sh", "x.xml", "x.svg", "LICENSE", "Makefile",
             "a.py", "a.ps1", "b.cmd"]
    picked = ascii_lf.checked([ROOT / n for n in names])
    assert sorted(p.name for p in picked) == sorted(names)
    # binaries are told apart by content (NUL) or a known binary suffix
    assert ascii_lf.checked([ROOT / "icon.png", ROOT / "font.woff2"]) == []
    assert not hasattr(ascii_lf, "TEXT_SUFFIXES")


def test_sidecar_subdirs_match_claude_md():
    text = (ROOT / "CLAUDE.md").read_text(encoding="ascii")
    m = re.search(r"\(Worktree, ([A-Za-z,\s]+)\)", text)
    assert m, "CLAUDE.md Sidecar list not found"
    listed = {s.strip() for s in m.group(1).split(",")}
    assert listed == set(paths.SIDECAR_SUBDIRS), (listed, paths.SIDECAR_SUBDIRS)


def test_all_runtime_paths_include_worktree_and_overlay_profile(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.SIDECAR_ENV, str(tmp_path / "AL"))
    got = paths.all_runtime_paths()
    assert got["worktree"] == (tmp_path / "AL" / "Worktree").resolve()
    assert got["overlay_profile"] == (tmp_path / "AL" / "Cache" / "overlay-profile").resolve()
    main_js = (ROOT / "app" / "main.js").read_text(encoding="utf-8")
    assert '"Cache", "overlay-profile"' in main_js  # same place the overlay uses


def test_drive_scan_covers_tools():
    assert "tools" in sidecar_test.SCANNED


def test_hand_off_spells_no_drive_path():
    text = (ROOT / "AL-NEXT-SESSION.txt").read_text(encoding="ascii")
    assert not re.search(r"(?<![A-Za-z0-9])[A-Za-z]:\\", text)


def test_decision_0002_names_pytest():
    text = (ROOT / "docs" / "decisions" / "0002-stack.md").read_text(encoding="ascii")
    assert "AUDIT-HYGIENE" in text and "pytest" in text
