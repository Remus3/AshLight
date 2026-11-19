"""LOOP-DONE-FOLD (F-028, F-029): the /done ritual folds the row files into
ROADMAP.md with tools/roadmap_fold.py, and the round trip holds: rows filed
and closed as files (tools/roadmap.py new / done) on two branches merge with
no ROADMAP.md conflict, and one fold leaves no row file behind and the same
row set the loader read before it. Scratch git repositories under tmp_path
only; the live tree is read, never written."""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import roadmap  # noqa: E402
import roadmap_fold  # noqa: E402
from loop_roadmap import roadmap_rows  # noqa: E402

GIT_TIMEOUT_S = 60
DATE = "2026-11-18"
ARCHIVE = "docs/roadmap/archive/2026-11.md"
DONE_MD = ROOT / ".claude" / "commands" / "done.md"

ROADMAP = """# AshLight ROADMAP

Open work only.

## Lane: build

- [ ] ALPHA (build) First open row. ACCEPT: alpha works.
  ZERO-CLICK: automatic.
- [ ] BETA (build) Second open row. ACCEPT: beta.
- [x] GAMMA (review) Done before the fold. -- done 2026-11-17 (session)

## Lane: data

- [ ] ZETA (data) Open data row. ACCEPT: zeta.

## Lane: review

- [ ] ETA (review) Open review row.
"""


def _quiet(*_a, **_k):
    return None


def _git(cwd, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="")
    r = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
                        "-c", "core.autocrlf=false", "-c", "init.defaultBranch=main",
                        "-c", "commit.gpgsign=false", *args],
                       cwd=str(cwd), env=env, capture_output=True, text=True,
                       timeout=GIT_TIMEOUT_S)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ROADMAP.md").write_bytes(ROADMAP.encode("ascii"))
    _git(root, "init", "-q")
    _git(root, "add", "ROADMAP.md")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _commit(root, rel, msg):
    _git(root, "add", "--", rel)
    _git(root, "commit", "-q", "-m", msg)


def _row_set(root):
    """{id: open} of every row the loader composes (ROADMAP.md, new files,
    done files applied), plus the archived rows (all done)."""
    out = {r["id"]: r["open"] for r in roadmap.load_rows(root)}
    arch = Path(root) / ARCHIVE
    if arch.is_file():
        for r in roadmap_rows(arch.read_text(encoding="ascii")):
            out.setdefault(r["id"], r["open"])
    return out


def _row_files(root):
    return sorted(p.relative_to(root).as_posix()
                  for sub in ("new", "done")
                  for p in (Path(root) / "docs/roadmap" / sub).glob("*.md"))


def test_fold_leaves_no_fragment_and_the_same_row_set(tmp_path):
    root = _repo(tmp_path)
    for text in ("- [ ] KAPPA (data) Filed row. ACCEPT: kappa.\n"
                 "  ZERO-CLICK: automatic.\n",
                 "- [ ] LAMBDA (review) Filed then closed.\n"):
        rel = roadmap.write_new(root, text)
        _commit(root, rel, "file " + rel)
    for iid in ("ALPHA", "LAMBDA"):
        rel = roadmap.write_done(root, iid, "session wave 3", date=DATE)
        _commit(root, rel, "close " + iid)
    before = _row_set(root)
    assert before == {"ALPHA": False, "BETA": True, "GAMMA": False, "ZETA": True,
                      "ETA": True, "KAPPA": True, "LAMBDA": False}
    assert len(_row_files(root)) == 4

    assert roadmap_fold.fold(root, date=DATE, write=True, out=_quiet) == 4
    # no fragment: no row file on disk, none in the index
    assert _row_files(root) == []
    assert _git(root, "ls-files", "docs/roadmap/new", "docs/roadmap/done") == ""
    # the same row set, now held by ROADMAP.md (open) and the archive (done)
    assert _row_set(root) == before
    text = (root / "ROADMAP.md").read_text(encoding="ascii")
    assert [r["id"] for r in roadmap_rows(text) if not r["open"]] == []
    assert {r["id"] for r in roadmap_rows(text)} == {"BETA", "ZETA", "ETA", "KAPPA"}
    data = text[text.index("## Lane: data"):text.index("## Lane: review")]
    assert "- [ ] KAPPA (data) Filed row. ACCEPT: kappa.\n  ZERO-CLICK: automatic.\n" in data
    arch = (root / ARCHIVE).read_text(encoding="ascii")
    assert "- [x] LAMBDA (review) Filed then closed. -- done 2026-11-18 (session wave 3)\n" in arch
    assert arch.count("- [x] GAMMA ") == 1
    assert roadmap.lint(root) == []
    # one commit takes ROADMAP.md, the archive and the removed row files
    _git(root, "add", "--", "ROADMAP.md", ARCHIVE)
    _git(root, "commit", "-q", "-m", "fold")
    assert _git(root, "status", "--porcelain") == ""
    names = _git(root, "show", "--name-status", "--format=", "HEAD").splitlines()
    assert sorted(names) == sorted(
        ["M\tROADMAP.md", "A\t" + ARCHIVE,
         "D\tdocs/roadmap/done/ALPHA.md", "D\tdocs/roadmap/done/LAMBDA.md",
         "D\tdocs/roadmap/new/KAPPA.md", "D\tdocs/roadmap/new/LAMBDA.md"])
    # a second fold is a no-op
    rm1 = (root / "ROADMAP.md").read_bytes()
    assert roadmap_fold.fold(root, date=DATE, write=True, out=_quiet) == 0
    assert (root / "ROADMAP.md").read_bytes() == rm1
    assert _git(root, "status", "--porcelain") == ""


def test_two_branches_with_row_files_merge_then_fold(tmp_path):
    root = _repo(tmp_path)
    _git(root, "branch", "side")
    # main files one row and closes one
    rel = roadmap.write_new(root, "- [ ] MU (build) Filed on main.\n")
    _commit(root, rel, "file MU")
    rel = roadmap.write_done(root, "BETA", "main", date=DATE)
    _commit(root, rel, "close BETA")
    # side files another row and closes others, never touching ROADMAP.md
    _git(root, "checkout", "-q", "side")
    rel = roadmap.write_new(root, "- [ ] NU (review) Filed on side.\n")
    _commit(root, rel, "file NU")
    rel = roadmap.write_done(root, "ZETA", "side", date=DATE)
    _commit(root, rel, "close ZETA")
    rel = roadmap.write_done(root, "NU", "side", date=DATE)
    _commit(root, rel, "close NU")
    _git(root, "checkout", "-q", "main")
    # the merge is clean: no branch edited ROADMAP.md
    _git(root, "merge", "-q", "--no-ff", "--no-edit", "side")
    assert _git(root, "diff", "--name-only", "HEAD~1", "HEAD", "--", "ROADMAP.md") == ""
    assert _row_files(root) == [
        "docs/roadmap/done/BETA.md", "docs/roadmap/done/NU.md",
        "docs/roadmap/done/ZETA.md", "docs/roadmap/new/MU.md",
        "docs/roadmap/new/NU.md"]
    before = _row_set(root)
    assert before == {"ALPHA": True, "BETA": False, "GAMMA": False, "ZETA": False,
                      "ETA": True, "MU": True, "NU": False}

    assert roadmap_fold.fold(root, date=DATE, write=True, out=_quiet) == 5
    assert _row_files(root) == []
    assert _row_set(root) == before
    text = (root / "ROADMAP.md").read_text(encoding="ascii")
    assert {r["id"] for r in roadmap_rows(text)} == {"ALPHA", "ETA", "MU"}
    assert all(r["open"] for r in roadmap_rows(text))
    build = text[text.index("## Lane: build"):text.index("## Lane: data")]
    assert "- [ ] MU (build) Filed on main.\n" in build


def test_done_ritual_names_the_fold_command():
    text = DONE_MD.read_text(encoding="ascii")
    assert "\r" not in text
    assert text.count("roadmap_fold.py fold") == 1
    paper = text[text.index("### 4. Paperwork"):text.index("### 5.")]
    assert "python tools/roadmap_fold.py fold --write" in paper
    assert "flip finished rows" not in paper
    for word in ("ROADMAP.md", "archive", "row files", "one", "git lock"):
        assert word in paper
    # the hand-off template: the LOOP: rule and the SESSION line shape
    hand = text[text.index("### 6. Hand-off"):text.index("### 7.")]
    assert "LOOP:" in hand
    tpl = hand[hand.index("```"):hand.rindex("```")]
    m = re.search(r"^SESSION: <n\+1>   \(", tpl, re.M)
    assert m, "SESSION line shape changed"
    sys.path.insert(0, str(ROOT / "tools"))
    import al_loop  # noqa: E402
    import loop_roadmap  # noqa: E402
    filled = tpl.replace("```\n", "").replace("<n+1>", "8")
    assert al_loop.handoff_session(filled) == 8
    items = loop_roadmap.handoff_items(filled)
    assert len(items) == 1 and items[0]["text"].startswith("<an item the loop")
