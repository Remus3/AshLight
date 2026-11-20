"""TEST-DOCS-INDEX (F-146, AUTO-14, F-195 c): docs_fresh index and stale.

Every decision and research file has an index line ('index --check'),
'index --write' inserts exactly the missing lines and nothing else, the
expected-stale list is shrink-only, and 'stale' lists dated PENDING /
UNVERIFIED markers older than 30 days.
"""

import datetime
import difflib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import docs_fresh as df  # noqa: E402

TOOL = str(ROOT / "tools" / "docs_fresh.py")
# The count of index lines missing at the package base; the list may only
# shrink from here.
BASE_EXPECTED = 36

DEC_README = (
    "# Decisions\n"
    "\n"
    "Intro text stays as it is.\n"
    "\n"
    "- 0005: five, the newest.\n"
    "- 0003: three, wrapped over\n"
    "  two lines.\n"
    "- 0001: one.\n"
    "\n"
    "Trailing text stays too.\n")
RES_README = (
    "# Research index\n"
    "\n"
    "- 0001 One ([0001-one.md](0001-one.md))\n"
    "- 0003 Three ([0003-three.md](0003-three.md))\n")


def _cli(*args):
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True,
                          text=True, timeout=60)


def _tree(tmp_path):
    dec = tmp_path / df.DECISIONS_DIR
    res = tmp_path / df.RESEARCH_DIR
    dec.mkdir(parents=True)
    res.mkdir(parents=True)
    (dec / "README.md").write_bytes(DEC_README.encode("ascii"))
    (res / "README.md").write_bytes(RES_README.encode("ascii"))
    for num, name in (("0001", "one"), ("0003", "three"), ("0005", "five")):
        (dec / f"{num}-{name}.md").write_bytes(
            f"# {num} - {name.title()}\n\nBody.\n".encode("ascii"))
    for num, name in (("0001", "one"), ("0003", "three")):
        (res / f"{num}-{name}.md").write_bytes(
            f"# {num} - {name.title()}\n".encode("ascii"))
    (dec / "name-check-2026-11-16.md").write_bytes(b"# not numbered\n")
    return tmp_path


def _added_only(old, new):
    """The lines new adds to old; fails when new removes or changes any."""
    diff = list(difflib.ndiff(old.split("\n"), new.split("\n")))
    assert not [d for d in diff if d.startswith("- ")], diff
    return [d[2:] for d in diff if d.startswith("+ ")]


def test_complete_fixture_checks_clean(tmp_path):
    root = _tree(tmp_path)
    proc = _cli("index", "--check", "--root", str(root))
    assert proc.returncode == 0, proc.stdout
    assert "index ok" in proc.stdout


def test_decision_with_no_index_line_fails_check(tmp_path):
    root = _tree(tmp_path)
    (root / df.DECISIONS_DIR / "0004-four.md").write_bytes(b"# 0004 - Four\n")
    proc = _cli("index", "--check", "--root", str(root))
    assert proc.returncode == 1
    assert "docs/decisions/README.md" in proc.stdout
    assert "0004-four.md" in proc.stdout
    assert df.index_problems(df.Tree(root)) == [
        "docs/decisions/README.md: index: no index line for "
        "docs/decisions/0004-four.md"]


def test_research_with_no_index_line_fails_check(tmp_path):
    root = _tree(tmp_path)
    (root / df.RESEARCH_DIR / "0002-two.md").write_bytes(b"# 0002 - Two\n")
    proc = _cli("index", "--check", "--root", str(root))
    assert proc.returncode == 1
    assert "docs/research/0002-two.md" in proc.stdout


def test_write_adds_the_missing_line_and_nothing_else(tmp_path):
    root = _tree(tmp_path)
    (root / df.DECISIONS_DIR / "0004-four.md").write_bytes(
        b"# 0004 - Four, the new one\n")
    (root / df.DECISIONS_DIR / "0007-seven.md").write_bytes(b"# 0007 - Seven\n")
    (root / df.RESEARCH_DIR / "0002-two.md").write_bytes(b"# 0002 - Two\n")
    proc = _cli("index", "--write", "--root", str(root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    dec = (root / df.DECISIONS_DIR / "README.md").read_text(encoding="utf-8")
    res = (root / df.RESEARCH_DIR / "README.md").read_text(encoding="utf-8")
    assert _added_only(DEC_README, dec) == ["- 0007: Seven.",
                                            "- 0004: Four, the new one."]
    # Placed in the list's own (descending) order.
    assert dec.index("- 0007:") < dec.index("- 0005:")
    assert dec.index("- 0005:") < dec.index("- 0004:") < dec.index("- 0003:")
    assert _added_only(RES_README, res) == [
        "- 0002 Two ([0002-two.md](0002-two.md))"]
    assert res.index("- 0001 ") < res.index("- 0002 ") < res.index("- 0003 ")
    assert _cli("index", "--check", "--root", str(root)).returncode == 0
    # A second write is a no-op.
    assert df.index_write(root) == []
    assert (root / df.DECISIONS_DIR / "README.md").read_text(
        encoding="utf-8") == dec


def test_write_appends_below_the_last_entry_and_wraps(tmp_path):
    root = _tree(tmp_path)
    long_title = "A long title " * 8
    (root / df.DECISIONS_DIR / "0000-zero.md").write_bytes(
        f"# 0000 - {long_title.strip()}\n".encode("ascii"))
    df.index_write(root)
    dec = (root / df.DECISIONS_DIR / "README.md").read_text(encoding="utf-8")
    added = _added_only(DEC_README, dec)
    assert added[0].startswith("- 0000: A long title")
    assert all(line.startswith("  ") for line in added[1:])
    assert all(len(line) <= 72 for line in added)
    assert dec.index("- 0001:") < dec.index("- 0000:") < dec.index("Trailing")


def test_write_on_a_copy_of_the_tree_indexes_every_file(tmp_path):
    for rel_dir in df.INDEX_DIRS:
        shutil.copytree(ROOT / rel_dir, tmp_path / rel_dir)
    before = {d: (tmp_path / d / "README.md").read_text(encoding="utf-8")
              for d in df.INDEX_DIRS}
    df.index_write(tmp_path)
    tree = df.Tree(tmp_path)
    assert df.index_problems(tree, expected=()) == []
    for d in df.INDEX_DIRS:
        after = (tmp_path / d / "README.md").read_text(encoding="utf-8")
        _added_only(before[d], after)
        after.encode("ascii")


def test_index_check_exits_0_on_the_tree():
    proc = _cli("index", "--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_expected_stale_is_shrink_only():
    expected = df.EXPECTED_STALE
    assert len(expected) == len(set(expected))
    assert len(expected) <= BASE_EXPECTED
    assert all(rel.startswith(df.DECISIONS_DIR + "/") for rel in expected)
    tree = df.Tree(ROOT)
    missing = set()
    for rel_dir in df.INDEX_DIRS:
        missing.update(df.index_missing(tree, rel_dir))
    # Nothing new may go missing: the missing set only shrinks.
    assert missing <= set(expected), sorted(missing - set(expected))


def _stale_fixture(tmp_path, today):
    docs = tmp_path / "docs" / "research"
    docs.mkdir(parents=True)
    old = (today - datetime.timedelta(days=31)).isoformat()
    young = (today - datetime.timedelta(days=29)).isoformat()
    (docs / "0001-a.md").write_bytes(
        (f"# 0001 - A\n\n- verdict=PENDING since {old}\n"
         f"- UNVERIFIED as of {young}\n"
         f"- PENDING with no date\n"
         f"- plain line {old}\n").encode("ascii"))
    return tmp_path, old, young


def test_stale_lists_a_31_day_old_marker_only(tmp_path):
    today = datetime.date(2026, 11, 20)
    root, old, young = _stale_fixture(tmp_path, today)
    proc = _cli("stale", "--root", str(root), "--today", today.isoformat())
    assert proc.returncode == 1
    lines = proc.stdout.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("docs/research/0001-a.md:3: " + old)
    assert "31 days" in lines[0]
    assert young not in proc.stdout


def test_stale_prints_nothing_for_a_29_day_old_marker(tmp_path):
    today = datetime.date(2026, 11, 20)
    docs = tmp_path / "docs"
    docs.mkdir()
    young = (today - datetime.timedelta(days=29)).isoformat()
    (docs / "x.md").write_bytes(f"PENDING since {young}\n".encode("ascii"))
    proc = _cli("stale", "--root", str(tmp_path), "--today", today.isoformat())
    assert proc.returncode == 0
    assert proc.stdout == ""


def test_stale_uses_the_newest_date_on_the_line(tmp_path):
    today = datetime.date(2026, 11, 20)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x.md").write_bytes(
        b"UNVERIFIED 2026-01-01, re-checked 2026-11-19\n")
    assert df.stale_markers(tmp_path, today) == []


def test_stale_bad_today_exits_2(tmp_path):
    assert df.main(["stale", "--root", str(tmp_path),
                    "--today", "yesterday"]) == 2
