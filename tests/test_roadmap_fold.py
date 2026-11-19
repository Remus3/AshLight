"""AUTO-02 ROADMAP-PRUNE (finding F-028): tools/roadmap_fold.py keeps
ROADMAP.md to open rows. prune moves every done bullet with its continuation
lines, byte for byte, into docs/roadmap/archive/<YYYY-MM>.md; fold applies
docs/roadmap/new/ and docs/roadmap/done/ row files, removes them, then
prunes. Synthetic trees under tmp_path, plus a dry run over a copy of the
tree's own ROADMAP.md (never the live file)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import roadmap_fold  # noqa: E402
from loop_base import ROW_RX  # noqa: E402
from loop_roadmap import roadmap_rows  # noqa: E402

GIT_TIMEOUT_S = 60
DATE = "2026-11-18"
ARCHIVE = "docs/roadmap/archive/2026-11.md"

ROADMAP = """# AshLight ROADMAP

Open work only.

## Lane: build

- FOLDED 2026-11-18: OLD -> ALPHA (pointer line stays).
- [ ] ALPHA (build) First open row. ACCEPT: alpha works.
  ZERO-CLICK: automatic.
- [x] GAMMA (review) A done row. -- done 2026-11-17 (session)
  ACCEPT: gamma. ZERO-CLICK: none.
    deeper continuation stays with the row.
- [ ] DELTA (build) Blocked row. BLOCKED: session wave 2.

## Lane: data

- [X] EPSILON (data) Upper-case mark. ACCEPT: eps.
- [ ] ZETA (data) Open data row. ACCEPT: zeta.
Prose line right after a row stays.
- [x] UTIL-1.0-READY (build) Dotted id. ACCEPT: dotted.
  continuation of the dotted row.
- [x] DOC-1.0-RUNBOOK (docs) Dotted id, docs hint.
- [x] UTIL-1.0-FIXTURES (build) Dotted id three.

## Lane: review

- [ ] ETA (review) Open review row.
- [x] THETA (review) Last done row, no trailing continuation.
"""


def _root(tmp_path, text=ROADMAP):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ROADMAP.md").write_bytes(text.encode("ascii"))
    return root


def _quiet(*_a, **_k):
    return None


def _open_ids(text):
    return [r["id"] for r in roadmap_rows(text) if r["open"]]


def _bullets(text, done):
    marks = ("- [x] ", "- [X] ") if done else ("- [ ] ",)
    return [ln for ln in text.splitlines() if ln.startswith(marks)]


def _git(cwd, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    r = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
                        "-c", "core.autocrlf=false", *args], cwd=str(cwd), env=env,
                       capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_prune_keeps_open_ids_and_archives_rows_byte_for_byte(tmp_path):
    root = _root(tmp_path)
    before = ROADMAP
    # dry run: nothing written
    assert roadmap_fold.prune(root, date=DATE, write=False, out=_quiet) == 6
    assert (root / "ROADMAP.md").read_text(encoding="ascii") == before
    assert not (root / ARCHIVE).exists()

    assert roadmap_fold.prune(root, date=DATE, write=True, out=_quiet) == 6
    after = (root / "ROADMAP.md").read_text(encoding="ascii")
    arch = (root / ARCHIVE).read_text(encoding="ascii")
    assert _open_ids(after) == _open_ids(before) == ["ALPHA", "DELTA", "ZETA", "ETA"]
    assert _bullets(after, done=True) == []
    # every line of the old file is in exactly one of the two: removed lines
    # are exactly the archived blocks, in order, byte for byte
    removed = before.splitlines(keepends=True)
    for ln in after.splitlines(keepends=True):
        removed.remove(ln)
    blocks = "".join(removed)
    assert "".join(ln for ln in arch.splitlines(keepends=True)
                   if ln.startswith(("- [", "  "))) == blocks
    assert ("- [x] GAMMA (review) A done row. -- done 2026-11-17 (session)\n"
            "  ACCEPT: gamma. ZERO-CLICK: none.\n"
            "    deeper continuation stays with the row.\n") in arch
    # headings, prose and the pointer line stay; the archive names the section
    for keep in ("## Lane: build", "## Lane: data", "## Lane: review", "Open work only.",
                 "- FOLDED 2026-11-18: OLD -> ALPHA", "Prose line right after a row stays."):
        assert keep in after
    assert "## Pruned 2026-11-18 from: Lane: build" in arch
    assert arch.startswith("# ROADMAP archive 2026-11\n")
    assert arch.isascii() and "\r" not in arch and after.endswith("\n")
    # the archived blocks are rows the loop parser still reads as done
    done_ids = {r["id"] for r in roadmap_rows(arch) if not r["open"]}
    assert {"GAMMA", "EPSILON", "THETA"} <= done_ids


def test_prune_moves_done_bullets_with_dotted_ids(tmp_path):
    root = _root(tmp_path)
    dotted = [ln for ln in ROADMAP.splitlines() if ln.startswith("- [x] ")
              and not ROW_RX.match(ln)]
    assert [roadmap_fold.bullet_id(ln) for ln in dotted] == [
        "UTIL-1.0-READY", "DOC-1.0-RUNBOOK", "UTIL-1.0-FIXTURES"]
    roadmap_fold.prune(root, date=DATE, write=True, out=_quiet)
    after = (root / "ROADMAP.md").read_text(encoding="ascii")
    arch = (root / ARCHIVE).read_text(encoding="ascii")
    for ln in dotted:
        assert ln not in after and ln + "\n" in arch
    assert ("- [x] UTIL-1.0-READY (build) Dotted id. ACCEPT: dotted.\n"
            "  continuation of the dotted row.\n") in arch
    assert "continuation of the dotted row." not in after


def test_prune_twice_is_a_no_op(tmp_path):
    root = _root(tmp_path)
    assert roadmap_fold.prune(root, date=DATE, write=True, out=_quiet) == 6
    rm1 = (root / "ROADMAP.md").read_bytes()
    ar1 = (root / ARCHIVE).read_bytes()
    lines = []
    assert roadmap_fold.prune(root, date=DATE, write=True, out=lines.append) == 0
    assert (root / "ROADMAP.md").read_bytes() == rm1
    assert (root / ARCHIVE).read_bytes() == ar1
    assert lines == ["prune: no done rows in ROADMAP.md"]
    # a later month appends to its own file; the old month file is untouched
    with (root / "ROADMAP.md").open("ab") as f:
        f.write(b"- [x] IOTA (review) Done in December.\n")
    assert roadmap_fold.prune(root, date="2026-12-01", write=True, out=_quiet) == 1
    assert (root / ARCHIVE).read_bytes() == ar1
    dec = (root / "docs/roadmap/archive/2026-12.md").read_text(encoding="ascii")
    assert "- [x] IOTA (review) Done in December.\n" in dec


def test_fold_applies_new_and_done_files_and_leaves_no_fragment(tmp_path):
    root = _root(tmp_path)
    new = root / "docs/roadmap/new"
    done = root / "docs/roadmap/done"
    new.mkdir(parents=True)
    done.mkdir(parents=True)
    (new / "KAPPA.md").write_bytes(b"- [ ] KAPPA (data) A filed row. ACCEPT: it\n"
                                   b"  holds a continuation line.\n")
    (new / "LAMBDA.md").write_bytes(b"- [ ] LAMBDA (build) Filed and done.\n")
    (new / "MU.md").write_bytes(b"- [ ] MU A row with no lane hint.\n")
    (done / "ALPHA.md").write_bytes(b" -- done 2026-11-18 (session wave 2)\n")
    (done / "LAMBDA.md").write_bytes(b" -- done 2026-11-18 (session wave 2)\n")
    (done / "GAMMA.md").write_bytes(b" -- done 2026-11-17 (session)\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    before = (root / "ROADMAP.md").read_bytes()

    # dry run: nothing changes
    out = []
    assert roadmap_fold.fold(root, date=DATE, write=False, out=out.append) == 6
    assert (root / "ROADMAP.md").read_bytes() == before
    assert (new / "KAPPA.md").is_file() and not (root / ARCHIVE).exists()
    assert any(x.startswith("fold: would apply 6") for x in out)

    assert roadmap_fold.fold(root, date=DATE, write=True, out=_quiet) == 6
    after = (root / "ROADMAP.md").read_text(encoding="ascii")
    arch = (root / ARCHIVE).read_text(encoding="ascii")
    # no fragment left: the files are gone from disk and from the index
    assert list(new.glob("*.md")) == [] and list(done.glob("*.md")) == []
    assert _git(root, "ls-files", "docs/roadmap") == ""
    # new rows sit under their lane heading; done rows were flipped and pruned
    assert _open_ids(after) == ["DELTA", "MU", "ZETA", "KAPPA", "ETA"]
    data = after[after.index("## Lane: data"):after.index("## Lane: review")]
    assert ("- [ ] KAPPA (data) A filed row. ACCEPT: it\n"
            "  holds a continuation line.\n") in data
    build = after[after.index("## Lane: build"):after.index("## Lane: data")]
    assert build.endswith("- [ ] MU A row with no lane hint.\n\n")  # default lane
    assert "\n\n## Lane: review" in after
    assert _bullets(after, done=True) == []
    assert ("- [x] ALPHA (build) First open row. ACCEPT: alpha works. -- done 2026-11-18 "
            "(session wave 2)\n  ZERO-CLICK: automatic.\n") in arch
    assert "- [x] LAMBDA (build) Filed and done. -- done 2026-11-18 (session wave 2)\n" in arch
    assert arch.count("- [x] GAMMA ") == 1  # already done: not flipped twice
    # a second fold finds nothing to do and changes nothing
    rm1, ar1 = (root / "ROADMAP.md").read_bytes(), (root / ARCHIVE).read_bytes()
    assert roadmap_fold.fold(root, date=DATE, write=True, out=_quiet) == 0
    assert (root / "ROADMAP.md").read_bytes() == rm1 and (root / ARCHIVE).read_bytes() == ar1


def test_fold_refuses_a_bad_file_and_changes_nothing(tmp_path):
    root = _root(tmp_path)
    done = root / "docs/roadmap/done"
    done.mkdir(parents=True)
    (done / "NOPE.md").write_bytes(b" -- done 2026-11-18 (session)\n")
    before = (root / "ROADMAP.md").read_bytes()
    with pytest.raises(roadmap_fold.FoldError, match="no row NOPE"):
        roadmap_fold.fold(root, date=DATE, write=True, out=_quiet)
    assert (root / "ROADMAP.md").read_bytes() == before
    assert (done / "NOPE.md").is_file()
    (done / "NOPE.md").unlink()
    new = root / "docs/roadmap/new"
    new.mkdir(parents=True)
    (new / "ALPHA.md").write_bytes(b"- [ ] ALPHA (build) A different row.\n")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "roadmap_fold.py"), "fold",
                        "--write", "--date", DATE, "--root", str(root)],
                       capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    assert r.returncode == 1 and "already a different row" in r.stderr
    assert (root / "ROADMAP.md").read_bytes() == before


def test_cli_dry_run_over_a_copy_of_the_tree_roadmap(tmp_path):
    """The tree's own ROADMAP.md, copied: prune keeps every open id and
    leaves no done bullet; the live file is never written."""
    live = ROOT / "ROADMAP.md"
    live_bytes = live.read_bytes()
    root = tmp_path / "copy"
    root.mkdir()
    shutil.copyfile(live, root / "ROADMAP.md")
    cmd = [sys.executable, str(ROOT / "tools" / "roadmap_fold.py"), "prune",
           "--date", DATE, "--root", str(root)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    assert r.returncode == 0, r.stderr
    assert "dry run" in r.stdout or "no done rows" in r.stdout
    assert (root / "ROADMAP.md").read_bytes() == live_bytes
    r = subprocess.run(cmd + ["--write"], capture_output=True, text=True,
                       timeout=GIT_TIMEOUT_S)
    assert r.returncode == 0, r.stderr
    before = live_bytes.decode("ascii")
    after = (root / "ROADMAP.md").read_text(encoding="ascii")
    assert _open_ids(after) == _open_ids(before)
    assert _bullets(after, done=True) == []
    arch = root / ARCHIVE
    moved = [ln for ln in arch.read_text(encoding="ascii").splitlines()
             if ln.startswith(("- [", "  "))] if arch.is_file() else []
    assert len(after.splitlines()) + len(moved) == len(before.splitlines())
    assert live.read_bytes() == live_bytes


def test_append_under_lane_adds_a_missing_heading():
    text = "# R\n\n## Lane: build\n\n- [ ] A (build) a.\n"
    got = roadmap_fold.append_under_lane(text, "review", "- [ ] B (review) b.\n")
    assert got == text + "\n## Lane: review\n\n- [ ] B (review) b.\n"
    got = roadmap_fold.append_under_lane("# R\n\n## Lane: data\n\n## Lane: build\n",
                                         "data", "- [ ] C (data) c.\n")
    assert got == "# R\n\n## Lane: data\n\n- [ ] C (data) c.\n\n## Lane: build\n"
