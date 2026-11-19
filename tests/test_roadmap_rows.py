"""AUTO-03 ROW-FILES (finding F-029): tools/roadmap.py composes ROADMAP.md
with docs/roadmap/new/<ID>.md (a filed row) and docs/roadmap/done/<ID>.md
(a closed row); new and done are the only writers and only ever add a file,
so two branches that each file and close rows merge with no conflict."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import roadmap  # noqa: E402

GIT_TIMEOUT_S = 60
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}

ROADMAP = """# AshLight ROADMAP

Open work only.

## Lane: build

- [ ] ALPHA (build) First open row. ACCEPT: alpha works.
  ZERO-CLICK: automatic.
- [ ] BETA (data) Second open row. DEPENDS: ALPHA. ACCEPT: beta.
- [x] GAMMA (review) A done row. -- done 2026-11-17 (session)
- [ ] DELTA (build) Blocked row. BLOCKED: session wave 2.
"""

NEW_ROW = ("- [ ] EPSILON (build) A filed row. DEPENDS: BETA, DELTA. ACCEPT: it\n"
           "  holds a continuation line.\n")


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)


def _git(cwd, *args):
    r = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
                        "-c", "core.autocrlf=false", *args], cwd=str(cwd),
                       capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _root(tmp_path, text=ROADMAP):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ROADMAP.md").write_text(text, encoding="ascii", newline="\n")
    return root


def _by_id(rows):
    return {r["id"]: r for r in rows}


def _cli(root, *args, stdin=None):
    return subprocess.run([sys.executable, str(ROOT / "tools" / "roadmap.py"),
                           "--root", str(root), *args], capture_output=True,
                          text=True, input=stdin, timeout=60)


def test_loader_composes_roadmap_new_and_done_files(tmp_path):
    root = _root(tmp_path)
    before = (root / "ROADMAP.md").read_bytes()
    assert roadmap.write_new(root, NEW_ROW) == "docs/roadmap/new/EPSILON.md"
    assert roadmap.write_done(root, "ALPHA", "session wave 1; verified",
                              date="2026-11-18") == "docs/roadmap/done/ALPHA.md"
    assert (root / "docs/roadmap/done/ALPHA.md").read_bytes() == \
        b" -- done 2026-11-18 (session wave 1; verified)\n"
    assert (root / "docs/roadmap/new/EPSILON.md").read_bytes() == NEW_ROW.encode("ascii")
    assert (root / "ROADMAP.md").read_bytes() == before  # never edited

    rows = roadmap.load_rows(root)
    assert [r["id"] for r in rows] == ["ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON"]
    by = _by_id(rows)
    # the done line is appended to the row's first line and marks it done
    a = by["ALPHA"]
    assert not a["open"] and a["status"] == "[x] done" and a["source"] == "roadmap"
    assert a["text"] == ("First open row. ACCEPT: alpha works. -- done 2026-11-18 "
                         "(session wave 1; verified) ZERO-CLICK: automatic.")
    assert a["lane"] == "build" and a["title"] == "First open row."
    assert by["BETA"]["open"] and by["BETA"]["depends"] == ["ALPHA"]
    assert by["GAMMA"]["status"] == "[x] done"
    e = by["EPSILON"]
    assert e["source"] == "new" and e["open"] and e["lane"] == "build"
    assert e["depends"] == ["BETA", "DELTA"]
    assert e["text"].endswith("holds a continuation line.")
    # a done file closes a filed row the same way
    roadmap.write_done(root, "EPSILON", "watch: launch 20261211", date="2026-12-11")
    e = _by_id(roadmap.load_rows(root))["EPSILON"]
    assert not e["open"] and "-- done 2026-12-11 (watch: launch 20261211)" in e["text"]
    assert roadmap.lint(root) == []

    # the CLI lists ids; --open drops done rows, --untagged drops BLOCKED rows
    r = _cli(root, "rows")
    assert r.returncode == 0 and r.stdout.split() == ["ALPHA", "BETA", "GAMMA", "DELTA",
                                                     "EPSILON"]
    assert _cli(root, "rows", "--open").stdout.split() == ["BETA", "DELTA"]
    assert _cli(root, "rows", "--open", "--untagged").stdout.split() == ["BETA"]
    r = _cli(root, "lint")
    assert r.returncode == 0 and r.stdout.strip() == "roadmap lint: ok 5 rows"

    # briefs match on the exact id, never on a hyphen prefix
    briefs = root / "docs/plan/briefs"
    briefs.mkdir(parents=True)
    (briefs / "BETA.md").write_text("brief\n", encoding="ascii", newline="\n")
    (briefs / "LIVE-1.md").write_text("brief\n", encoding="ascii", newline="\n")
    assert roadmap.brief_path(root, "BETA") == briefs / "BETA.md"
    assert roadmap.brief_path(root, "LIVE-1-ITEM") is None
    assert roadmap.brief_path(root, "LIVE") is None
    assert roadmap.brief_path(root, "../x") is None


def test_two_branches_adding_row_files_merge_clean(tmp_path):
    root = _root(tmp_path)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "--", "ROADMAP.md")
    _git(root, "commit", "-q", "-m", "init")

    paths = {}
    for branch, row, done in (("a", "ZETA", "ALPHA"), ("b", "ETA", "BETA")):
        _git(root, "checkout", "-q", "-b", branch, "main")
        new = roadmap.write_new(root, f"- [ ] {row} (data) Row from branch {branch}.\n")
        closed = roadmap.write_done(root, done, f"branch {branch}", date="2026-11-18")
        paths[branch] = (new, closed)
        _git(root, "add", "--", new, closed)
        _git(root, "commit", "-q", "-m", f"rows from {branch}", "--", new, closed)
        assert _git(root, "status", "--short") == ""
    _git(root, "checkout", "-q", "main")
    head0 = _git(root, "rev-parse", "HEAD")
    _git(root, "merge", "-q", "--no-ff", "-m", "merge a", "a")
    _git(root, "merge", "-q", "--no-ff", "-m", "merge b", "b")  # no conflict
    assert _git(root, "status", "--short") == ""
    assert _git(root, "diff", "--name-only", head0, "HEAD", "--", "ROADMAP.md") == ""
    changed = set(_git(root, "diff", "--name-only", head0, "HEAD").split())
    assert changed == {p for pair in paths.values() for p in pair}

    by = _by_id(roadmap.load_rows(root))
    assert by["ZETA"]["source"] == "new" and by["ZETA"]["open"]
    assert by["ETA"]["source"] == "new" and by["ETA"]["open"]
    assert not by["ALPHA"]["open"] and "(branch a)" in by["ALPHA"]["text"]
    assert not by["BETA"]["open"] and "(branch b)" in by["BETA"]["text"]
    assert roadmap.lint(root) == []
    assert [r["id"] for r in roadmap.load_rows(root) if r["open"]] == ["DELTA", "ETA", "ZETA"]


def test_depends_and_unknown_dependency_wait(tmp_path):
    assert roadmap.depends("x DEPENDS: A-1, B2 and C-3. Also ZED.") == ["A-1", "B2", "C-3"]
    assert roadmap.depends("DEPENDS: none. ACCEPT: X") == []
    assert roadmap.depends("no line") == []
    assert roadmap.depends("DEPENDS: A, A.") == ["A"]

    root = _root(tmp_path, ROADMAP + "- [ ] THETA (build) Waits. DEPENDS: BETA, NOPE-9. "
                                      "ACCEPT: NOT-A-DEP.\n")
    rows = roadmap.load_rows(root)
    assert _by_id(rows)["THETA"]["depends"] == ["BETA", "NOPE-9"]
    w = roadmap.waits(rows)
    assert w["THETA"] == ["waits on BETA", "waits on NOPE-9 (no such row)"]
    assert w["BETA"] == ["waits on ALPHA"]
    assert "ALPHA" not in w and "GAMMA" not in w

    # a done file clears the wait on that row; the unknown id keeps waiting
    roadmap.write_done(root, "BETA", "session", date="2026-11-18")
    roadmap.write_done(root, "ALPHA", "session", date="2026-11-18")
    w = roadmap.waits(roadmap.load_rows(root))
    assert w == {"THETA": ["waits on NOPE-9 (no such row)"]}

    # a filed row may be the dependency that is waited on
    roadmap.write_new(root, "- [ ] NOPE-9 (data) Now it exists.\n")
    w = roadmap.waits(roadmap.load_rows(root))
    assert w == {"THETA": ["waits on NOPE-9"]}

    r = _cli(root, "rows", "--open", "--json")
    assert r.returncode == 0
    got = {x["id"]: x["waits"] for x in json.loads(r.stdout)}
    assert got["THETA"] == ["waits on NOPE-9"] and got["NOPE-9"] == []


def test_new_and_done_refuse_an_existing_path_or_a_bad_id(tmp_path):
    root = _root(tmp_path)
    archive = root / "docs/roadmap/archive"
    archive.mkdir(parents=True)
    (archive / "2026-11.md").write_text("- [x] OLD-ROW (build) History.\n",
                                        encoding="ascii", newline="\n")
    rel = roadmap.write_new(root, "- [ ] IOTA (build) Filed.\n")
    snapshot = (root / rel).read_bytes()

    bad_new = [
        "- [ ] IOTA (build) Filed again.\n",          # existing path
        "- [ ] ALPHA (build) Already in ROADMAP.md.\n",  # id used in ROADMAP.md
        "- [ ] OLD-ROW (build) Used in the archive.\n",  # id used in the archive
        "- [ ] UTIL-1.0-POST (build) Dotted id.\n",   # does not parse
        "- [ ] 012 (build) A digits id has no row file.\n",
        "- [ ] lower (build) Lower case.\n",
        "- [x] KAPPA (build) A done row is a done file.\n",
        "- [ ] KAPPA (docs) Unknown lane hint.\n",
        "- [ ] KAPPA (build) One.\n- [ ] LAMBDA (build) Two.\n",
        "- [ ] KAPPA (build) Stray.\n\nnot a continuation\n",
        "- [ ] KAPPA (build) " + "x" * 700 + "\n",
        "- [ ] KAPPA (build) Not ASCII \u2014 dash.\n",
        "KAPPA (build) Not a bullet.\n",
    ]
    for text in bad_new:
        with pytest.raises(roadmap.RowFileError):
            roadmap.write_new(root, text)
    assert (root / rel).read_bytes() == snapshot
    assert sorted(p.name for p in (root / "docs/roadmap/new").iterdir()) == ["IOTA.md"]

    first = roadmap.write_done(root, "ALPHA", "session", date="2026-11-18")
    done_bytes = (root / first).read_bytes()
    for row_id, note, date in (
        ("ALPHA", "again", "2026-11-19"),  # existing path
        ("GAMMA", "session", "2026-11-18"),  # row already done
        ("NO-SUCH", "session", "2026-11-18"),  # no row
        ("OLD-ROW", "session", "2026-11-18"),  # archive is history, not a row
        ("UTIL-1.0-POST", "session", "2026-11-18"),
        ("../ALPHA", "session", "2026-11-18"),
        ("beta", "session", "2026-11-18"),
        ("012", "session", "2026-11-18"),
        ("", "session", "2026-11-18"),
        ("BETA", "", "2026-11-18"),
        ("BETA", "two\nlines", "2026-11-18"),
        ("BETA", "dash \u2014", "2026-11-18"),
        ("BETA", "session", "2026-13-40"),
        ("BETA", "session", "tomorrow"),
    ):
        with pytest.raises(roadmap.RowFileError):
            roadmap.write_done(root, row_id, note, date=date)
    assert (root / first).read_bytes() == done_bytes
    assert sorted(p.name for p in (root / "docs/roadmap/done").iterdir()) == ["ALPHA.md"]
    assert not (root / "docs/roadmap/ALPHA.md").exists()

    # the CLI refuses with exit 1 and leaves the files alone
    r = _cli(root, "done", "ALPHA", "again")
    assert r.returncode == 1 and "refused" in r.stderr
    r = _cli(root, "new", stdin="- [ ] IOTA (build) Again.\n")
    assert r.returncode == 1 and "refused" in r.stderr
    r = _cli(root, "new", stdin="- [ ] MU (review) Via stdin.\n")
    assert r.returncode == 0 and r.stdout.strip() == "docs/roadmap/new/MU.md"
    r = _cli(root, "done", "MU", "session wave 1; verified", "--date", "2026-11-18")
    assert r.returncode == 0 and r.stdout.strip() == "docs/roadmap/done/MU.md"
    assert roadmap.lint(root) == []
