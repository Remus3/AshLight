"""DEP-04 (F-101, decision 0062): release notes and the changelog.

`release.py notes` drafts a version's notes from first-parent commit
subjects joined to ROADMAP row titles. The fixture history is a fresh git
repo under tmp_path (no hooks, fixed dates), so the checkout is never read
for history and never written.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "tools" / "release.py"


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, str(ROOT / "tools" / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rn = _load("rel_notes")

_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")


def _git(repo, *args):
    proc = subprocess.run(["git", "-c", "core.hooksPath=", *args], cwd=str(repo),
                          capture_output=True, text=True, env=_env_now(),
                          check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


_CLOCK = [0]


def _env_now():
    # a fixed, increasing date per git call: two runs give the same history
    _CLOCK[0] += 1
    stamp = "2026-11-%02dT12:%02d:00+00:00" % (1 + _CLOCK[0] // 60, _CLOCK[0] % 60)
    return dict(_ENV, GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)


def _write(repo, rel, text):
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("ascii"))


def _commit(repo, message, rel="ROADMAP.md", text=None):
    if text is not None:
        _write(repo, rel, text)
        _git(repo, "add", "--", rel)
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)


def _merge(repo, branch, subject, body_subject="feat: branch work"):
    _git(repo, "checkout", "-q", "-b", branch)
    _commit(repo, body_subject, "work/%s.txt" % branch, branch + "\n")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", subject, branch)


ROADMAP_V1 = """# ROADMAP

- [ ] A-ONE (build) Item check reads the pasted build. ACCEPT: tests pass.
- [ ] DATA-TWO (data) Old title of the data row. ACCEPT: tests pass.
- [ ] SEC-THREE (build) Electron pin: a hash-pinned runtime
  download. ACCEPT: tests pass.
- [ ] DEP-07 (build) Players can install from a release. ACCEPT: tests pass.
"""

# A-ONE pruned (done rows leave ROADMAP.md at /done); DATA-TWO retitled
ROADMAP_V2 = """# ROADMAP

- [ ] DATA-TWO (data) Fresh league data on launch day. ACCEPT: tests pass.
- [ ] SEC-THREE (build) Electron pin: a hash-pinned runtime
  download. ACCEPT: tests pass.
- [ ] DEP-07 (build) Players can install from a release. ACCEPT: tests pass.
"""

# after the tag: docs x2, test, chore, ops, release, git's own Merge branch
# and a merge without a row id
INTERNAL = 8


@pytest.fixture(scope="module")
def history(tmp_path_factory):
    repo = tmp_path_factory.mktemp("relnotes")
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "docs: start the roadmap", text=ROADMAP_V1)
    _git(repo, "tag", "v0.0.1")
    _merge(repo, "w-a", "merge: A-ONE Item check reads the pasted build (wave 1)")
    _merge(repo, "w-d", "merge: DATA-TWO data row (wave 1)")
    _merge(repo, "w-s", "merge: SEC-THREE Electron pin (wave 1)")
    _commit(repo, "feat(DEP-07): release install path")
    _commit(repo, "docs: notes")
    _commit(repo, "test: more tests")
    _commit(repo, "chore(integrate): wave 1 batch 1\n\n"
                  "feat(EVIL-9): a body line that must never be read\n\n"
                  "Co-Authored-By: someone")
    _commit(repo, "ops: lane tweak")
    _commit(repo, "release: 0.1.0")
    _merge(repo, "w-x", "Merge branch 'w-x'")
    _merge(repo, "w-y", "merge: idle deep-dive 20261119 (research)")
    _commit(repo, "docs(roadmap): prune done rows", text=ROADMAP_V2)
    return repo


def _draft(repo, version="0.1.0", **kw):
    return rn.draft(version, root=repo, **kw)


def _section(text, name):
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("### "):
            inside = line == "### " + name
            continue
        if inside and line.startswith("- "):
            lines.append(line)
        elif inside and not line.strip():
            inside = False
    return lines


@pytest.mark.git
def test_three_merges_give_three_grouped_lines(history):
    text = _draft(history)
    assert _section(text, "Changed") == ["- Fresh league data on launch day (DATA-TWO)"]
    assert _section(text, "Security") == [
        "- Electron pin: a hash-pinned runtime download (SEC-THREE)"]
    added = _section(text, "Added")
    assert "- Item check reads the pasted build (A-ONE)" in added
    rows = [ln for g in rn.GROUPS for ln in _section(text, g)
            if ln.endswith(("(A-ONE)", "(DATA-TWO)", "(SEC-THREE)"))]
    assert len(rows) == 3


@pytest.mark.git
def test_dep_prefix_with_feat_lands_under_added_not_security(history):
    text = _draft(history)
    assert "- Players can install from a release (DEP-07)" in _section(text, "Added")
    assert not any("DEP-07" in ln for ln in _section(text, "Security"))


@pytest.mark.git
def test_titles_come_from_the_roadmap_diffs_in_the_range(history):
    rows = rn.titles((None, "HEAD"), root=history)
    # A-ONE was pruned before HEAD: only a diff in the range still names it
    assert rows["A-ONE"] == ("Item check reads the pasted build.", "build")
    # ROADMAP.md at the end wins over the older title of the same row
    assert rows["DATA-TWO"] == ("Fresh league data on launch day.", "data")
    head = _git(history, "show", "HEAD:ROADMAP.md")
    assert "A-ONE" not in head


@pytest.mark.git
def test_internal_changes_are_counted(history):
    text = _draft(history)
    assert "Also: %d internal changes." % INTERNAL in text.splitlines()
    assert "EVIL-9" not in text
    for g in rn.GROUPS:
        assert not any("notes" in ln.lower() or "lane" in ln.lower()
                       for ln in _section(text, g))


@pytest.mark.git
def test_only_subjects_are_read(history, monkeypatch):
    calls = []
    real = rn._git

    def spy(root, *args, **kw):
        calls.append(args)
        return real(root, *args, **kw)

    monkeypatch.setattr(rn, "_git", spy)
    text = _draft(history)
    assert "EVIL-9" not in text and "Co-Authored" not in text
    logs = [a for a in calls if a[0] == "log"]
    assert logs
    for args in logs:
        fmt = [a for a in args if a.startswith("--format=")]
        assert fmt and set(fmt) <= {"--format=%H%x09%s", "--format=%x00%H",
                                    "--format=%cs"}, args


@pytest.mark.git
def test_range_starts_at_the_previous_tag(history):
    assert rn.previous_tag("0.1.0", root=history) == "v0.0.1"
    assert rn.previous_tag("0.0.1", root=history) is None
    # the tagged root commit (docs: start the roadmap) is outside the range
    assert len(rn.collect((None, "HEAD"), root=history)) == 13
    after = rn.collect(("v0.0.1", "HEAD"), root=history)
    assert len(after) == 12 and after[0][1].startswith("merge: A-ONE ")
    assert _draft(history) == _draft(history, start="v0.0.1")


@pytest.mark.git
def test_count_since_last_tag(history):
    assert rn.last_tag(root=history) == "v0.0.1"
    n, day = rn.count(("v0.0.1", "HEAD"), root=history)
    assert n == 3 and len(day) == 10 and day[4] == "-"
    first = rn.collect(("v0.0.1", "HEAD"), root=history)[0][0]
    want = _git(history, "log", "-1", "--format=%cs", first).strip()
    assert day == want
    proc = _run("--count", "--root", str(history))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ("3 %s" % want) + chr(10)


@pytest.mark.git
def test_count_from_root_without_a_tag(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "docs: start", text="# R" + chr(10))
    assert rn.last_tag(root=repo) is None
    assert rn.count((None, "HEAD"), root=repo) == (0, "")
    _merge(repo, "w-a", "merge: A-ONE first (wave 1)")
    _merge(repo, "w-b", "merge: B-TWO second (wave 1)")
    n, day = rn.count((None, "HEAD"), root=repo)
    assert n == 2 and len(day) == 10
    proc = _run("--count", "--root", str(repo))
    assert proc.returncode == 0 and proc.stdout.startswith("2 20")


@pytest.mark.git
def test_two_runs_give_the_same_bytes(history):
    a = rn.write("0.1.0", root=history).read_bytes()
    log_a = (history / rn.CHANGELOG_REL).read_bytes()
    b = rn.write("0.1.0", root=history).read_bytes()
    assert a == b and (history / rn.CHANGELOG_REL).read_bytes() == log_a
    assert a.isascii() and b"\r" not in a
    assert a.startswith(b"## [0.1.0] - 2026-11-")


@pytest.mark.git
def test_lead_paragraph_survives_a_regeneration(history):
    path = rn.write("0.1.0", root=history)
    text = path.read_text(encoding="ascii")
    assert rn.LEAD_STUB in text and rn.lead_of(text) == rn.LEAD_STUB
    lead = "The first public version, written by hand."
    path.write_bytes(text.replace(rn.LEAD_STUB, lead).encode("ascii"))
    again = rn.write("0.1.0", root=history).read_text(encoding="ascii")
    assert rn.lead_of(again) == lead
    assert again.splitlines()[1:4] == [rn.LEAD_OPEN, lead, rn.LEAD_CLOSE]


@pytest.mark.git
def test_a_bump_stub_gets_the_stub_lead(history):
    path = rn.notes_path("0.2.0", root=history)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(rn.rv.notes_stub("0.2.0").encode("ascii"))
    text = rn.write("0.2.0", root=history).read_text(encoding="ascii")
    # the STUB mark stays until the lead is written (publish refuses it)
    assert rn.rv.STUB_MARK in text and text.startswith("## [0.2.0] - ")
    path.unlink()
    rn.changelog(root=history)


@pytest.mark.git
def test_every_notes_file_ends_with_the_sentence(history):
    from server.al import DISCLAIMER
    assert rn.DISCLAIMER == DISCLAIMER
    rn.write("0.1.0", root=history)
    files = [p for _v, p in rn.notes_files(history)] + [
        p for _v, p in rn.notes_files(ROOT)]
    assert files
    for path in files:
        raw = path.read_bytes()
        assert raw.isascii() and b"\r" not in raw, path.name
        assert raw.decode("ascii").endswith(DISCLAIMER + "\n"), path.name


def test_changelog_is_the_notes_newest_first(tmp_path):
    for ver in ("0.1.0", "0.2.0-rc.1", "0.2.0", "0.10.0"):
        _write(tmp_path, "docs/releases/%s.md" % ver,
               "## [%s] - 2026-11-19\nbody\n\n%s\n" % (ver, rn.DISCLAIMER))
    _write(tmp_path, "docs/releases/README.txt", "not a notes file\n")
    assert [v for v, _p in rn.notes_files(tmp_path)] == [
        "0.10.0", "0.2.0", "0.2.0-rc.1", "0.1.0"]
    assert rn.changelog(check=True, root=tmp_path) is False
    assert not (tmp_path / "CHANGELOG.md").exists()
    rn.changelog(root=tmp_path)
    want = rn.CHANGELOG_HEAD + "".join(
        "\n" + (tmp_path / ("docs/releases/%s.md" % v)).read_text(encoding="ascii")
        for v in ("0.10.0", "0.2.0", "0.2.0-rc.1", "0.1.0"))
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="ascii") == want
    assert rn.changelog(check=True, root=tmp_path) is True


def test_checkout_changelog_equals_the_concatenation():
    want = rn.CHANGELOG_HEAD + "".join(
        "\n" + p.read_text(encoding="ascii") for _v, p in rn.notes_files(ROOT))
    assert (ROOT / "CHANGELOG.md").read_bytes() == want.encode("ascii")
    assert (ROOT / "docs/releases/0.1.0.md").is_file()
    # 0.1.0 carries its hand-written lead, not the STUB mark
    assert rn.rv.STUB_MARK not in (ROOT / "docs/releases/0.1.0.md").read_text(
        encoding="ascii")


def _run(*args, cwd=ROOT):
    return subprocess.run([sys.executable, str(RELEASE), "notes", *args],
                          cwd=str(cwd), capture_output=True, text=True, check=False)


def test_changelog_check_cli(tmp_path):
    proc = _run("--changelog", "--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    _write(tmp_path, "docs/releases/0.1.0.md", "## [0.1.0] - x\n\n%s\n" % rn.DISCLAIMER)
    _write(tmp_path, "CHANGELOG.md", "stale\n")
    proc = _run("--changelog", "--check", "--root", str(tmp_path))
    assert proc.returncode == 1 and "stale" in proc.stderr
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="ascii") == "stale\n"
    assert _run("--changelog", "--root", str(tmp_path)).returncode == 0
    assert _run("--changelog", "--check", "--root", str(tmp_path)).returncode == 0
    assert _run().returncode == 2
    assert _run("0.1.0", "--check").returncode == 2


@pytest.mark.git
def test_draft_cli_prints_and_writes_nothing(history):
    before = sorted(p.name for p in (history / "docs" / "releases").glob("*"))
    proc = _run("0.1.0", "--root", str(history))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("## [0.1.0] - ")
    assert sorted(p.name for p in (history / "docs" / "releases").glob("*")) == before
