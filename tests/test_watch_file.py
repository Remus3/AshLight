"""LOOP-WATCH-FILE: tools/watch_file.py turns queued watcher findings into
add-only row files, each committed alone through the injected kit git lock
(Q-12). Every test runs in a scratch git repository under tmp_path with a
real git and a fake lock; nothing touches the live tree."""

import contextlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import roadmap  # noqa: E402
import upstream_watch  # noqa: E402
import watch_file  # noqa: E402

OWNER = "al-loop.main"
SRC = "testsrc"
TOKEN = r"[A-Z][A-Z0-9-]{0,11}"
TEMPLATES = {"kinds": {
    "thing": {
        "act": "row", "id": "THING-<TAG>", "lane": "data", "priority": False,
        "blocked": None,
        "text": ("Check the <TAG> thing. ACCEPT: a test passes. ZERO-CLICK: the loop "
                 "works it. SOURCE: watch testsrc <TAG>, filed <YYYY-MM-DD>."),
        "tokens": {"TAG": TOKEN}, "sample": {"TAG": "A1"}},
    "urgent": {
        "act": "row", "id": "URGENT-<TAG>", "lane": "data", "priority": True,
        "blocked": None,
        "text": ("Fix the <TAG> break. ACCEPT: a test passes. ZERO-CLICK: the loop "
                 "works it. SOURCE: watch testsrc <TAG>, filed <YYYY-MM-DD>."),
        "tokens": {"TAG": TOKEN}, "sample": {"TAG": "A1"}},
    "flip": {
        "act": "gate", "id": "GATE-<NAME>", "lane": "data", "priority": False,
        "blocked": None, "text": "Gate <NAME> flips.",
        "tokens": {"NAME": TOKEN}, "sample": {"NAME": "POE2-10"}},
    "live": {
        "act": "gate", "id": "LIVE-<ITEM>", "lane": "data", "priority": False,
        "blocked": None, "text": "Live item <ITEM> seen.",
        "tokens": {"ITEM": TOKEN}, "sample": {"ITEM": "A"}},
    "memo": {"act": "note", "tokens": {}, "sample": {}},
}}
ROADMAP = """# Roadmap

- [ ] GATE-POE2-10 (data) Gate: PoE2 1.0 is live. BLOCKED: gate, flipped by the watcher.
- [ ] LIVE-A (data) Live item A.
- [ ] LIVE-B (data) Live item B.
- [ ] LIVE-C (data) Live item C.
- [ ] LIVE-D (data) Live item D.
- [ ] THING-RM (data) An existing row.
- [ ] THING-DONE (data) A row closed by a done file.
"""


def _env():
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return env


def _run(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          env=_env(), timeout=60)


def _ok(args, cwd):
    r = _run(args, cwd)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


class FakeLock:
    """Stands in for the kit git lock: records every acquisition."""

    def __init__(self):
        self.calls = []

    @contextlib.contextmanager
    def __call__(self, cwd, owner, verb):
        self.calls.append((Path(cwd), owner, verb))
        yield


class Git:
    """The tick's git callable: real git; commit and push under the lock
    (as al_loop._git does)."""

    def __init__(self):
        self.lock = FakeLock()

    def raw(self, args, cwd):
        return _run(args, cwd)

    def __call__(self, args, cwd, input=None):
        if not args or args[0] not in ("commit", "push"):
            return self.raw(args, cwd)
        with self.lock(cwd, OWNER, args[0]):
            return self.commit(args, cwd)

    def commit(self, args, cwd):
        return self.raw(args, cwd)


class Budget:
    def __init__(self, used=0, cap=100, readable=True):
        self._used, self.cap, self._readable = used, cap, readable

    def readable(self):
        return self._readable

    def used(self):
        return self._used


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _ok(["init", "-q", "-b", "main"], repo)
    for k, v in (("user.name", "Operator"), ("user.email", "operator@example.com"),
                 ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
        _ok(["config", k, v], repo)
    files = {
        "ROADMAP.md": ROADMAP,
        "ops/loop/watch_rows/testsrc.json": json.dumps(TEMPLATES, indent=1) + "\n",
        "docs/roadmap/new/THING-NEW.md": "- [ ] THING-NEW (data) A filed row.\n",
        "docs/roadmap/done/THING-DONE.md": " -- done 2026-11-01 (session)\n",
        "docs/roadmap/archive/2026-10.md": "- [x] THING-ARC (data) An archived row.\n",
        ".gitignore": "ops/runtime/\n",
    }
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("ascii"))
    _ok(["add", "-A"], repo)
    _ok(["commit", "-q", "-m", "base"], repo)
    return repo


def _finding(kind, key, **tokens):
    return {"source": SRC, "kind": kind, "key": key, "tokens": tokens,
            "found": "2026-11-20T10:00:00-06:00"}


def _queue(repo, *findings):
    upstream_watch.set_pending(repo, list(findings))


def _pending_keys(repo):
    return [f["key"] for f in upstream_watch.pending(repo)]


def _head(repo):
    return _ok(["rev-parse", "HEAD"], repo).strip()


def _watch_commits(repo):
    """[(subject, [paths])] of the commits after the base commit, newest first."""
    out = _ok(["log", "--format=%x00%s", "--name-only", "HEAD"], repo)
    commits = []
    for block in out.split("\x00")[1:]:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if lines[0] != "base":
            commits.append((lines[0], lines[1:]))
    return commits


def _file(repo, git=None, budget=None, **kw):
    git = git or Git()
    lines = watch_file.file_pending(repo, time.time(), git,
                                    Budget() if budget is None else budget, **kw)
    return git, lines


def _today():
    return time.strftime("%Y-%m-%d", time.localtime())


def test_finding_becomes_one_committed_row_file(tmp_path):
    repo = _repo(tmp_path)
    _queue(repo, _finding("thing", "k1", TAG="A1"))
    git, lines = _file(repo)
    rel = "docs/roadmap/new/THING-A1.md"
    assert any(f"filed {rel}" in ln for ln in lines), lines
    text = (repo / rel).read_bytes().decode("ascii")
    assert text.startswith("- [ ] THING-A1 (data) Check the A1 thing.")
    assert text.endswith("\n") and "\r" not in text
    assert f"filed {_today()}." in text
    assert roadmap.lint(repo) == []
    assert "THING-A1" in [r["id"] for r in roadmap.load_rows(repo) if r["open"]]
    commits = _watch_commits(repo)
    assert commits == [("chore(roadmap): file THING-A1 (watch testsrc)", [rel])]
    # every commit went through the injected lock, as the loop owner
    assert git.lock.calls == [(Path(repo), OWNER, "commit")]
    assert _ok(["status", "--short"], repo).strip() == ""
    assert _pending_keys(repo) == []
    assert not (repo / watch_file.FAULT_REL).exists()


def test_fourth_new_row_in_a_local_day_waits(tmp_path):
    repo = _repo(tmp_path)
    _queue(repo, *[_finding("thing", f"k{i}", TAG=f"N{i}") for i in range(1, 5)])
    git, lines = _file(repo)
    commits = _watch_commits(repo)
    assert len(commits) == 3 and len(git.lock.calls) == 3
    assert all(len(paths) == 1 and paths[0].startswith("docs/roadmap/new/")
               for _s, paths in commits)
    assert _pending_keys(repo) == ["k4"]
    assert any("1 new row(s) wait" in ln for ln in lines), lines
    assert not (repo / "docs/roadmap/new/THING-N4.md").exists()
    # the next tick counts today's commits from git log and still waits
    git2, lines2 = _file(repo)
    assert git2.lock.calls == [] and _pending_keys(repo) == ["k4"]
    assert any("1 new row(s) wait" in ln for ln in lines2), lines2
    # a done file has its own cap and still goes
    _queue(repo, *upstream_watch.pending(repo), _finding("live", "seen-a", ITEM="A"))
    _file(repo)
    assert (repo / "docs/roadmap/done/LIVE-A.md").exists()
    assert _pending_keys(repo) == ["k4"]


def test_fourth_done_file_waits_and_a_gate_flip_goes_first(tmp_path):
    repo = _repo(tmp_path)
    _queue(repo, *[_finding("live", f"seen-{c}", ITEM=c) for c in "ABCD"],
           _finding("flip", "1.0.0", NAME="POE2-10"))
    git, lines = _file(repo)
    commits = _watch_commits(repo)
    oldest_first = [paths[0] for _s, paths in reversed(commits)]
    assert oldest_first == ["docs/roadmap/done/GATE-POE2-10.md",
                            "docs/roadmap/done/LIVE-A.md", "docs/roadmap/done/LIVE-B.md"]
    assert len(git.lock.calls) == 3
    assert _pending_keys(repo) == ["seen-C", "seen-D"]
    assert any("2 done file(s) wait" in ln for ln in lines), lines
    line = (repo / "docs/roadmap/done/GATE-POE2-10.md").read_bytes().decode("ascii")
    assert line == f" -- done {_today()} (watch: testsrc 1.0.0)\n"
    rows = {r["id"]: r for r in roadmap.load_rows(repo)}
    assert not rows["GATE-POE2-10"]["open"] and rows["LIVE-C"]["open"]
    # a new row has its own cap and still goes
    _queue(repo, *upstream_watch.pending(repo), _finding("thing", "k1", TAG="A1"))
    _file(repo)
    assert (repo / "docs/roadmap/new/THING-A1.md").exists()


def test_halt_or_dry_run_files_nothing(tmp_path):
    repo = _repo(tmp_path)
    _queue(repo, _finding("thing", "k1", TAG="A1"), _finding("flip", "1.0.0", NAME="POE2-10"))
    before = _head(repo)
    git, lines = _file(repo, halted=True)
    assert lines and "HALT" in lines[0]
    git2, lines2 = _file(repo, dry=True)
    assert lines2 and "dry run" in lines2[0]
    halt = repo / "ops/loop/control/HALT"
    halt.parent.mkdir(parents=True)
    halt.write_text("halt\n")
    git3, lines3 = _file(repo)
    assert lines3 and "HALT" in lines3[0]
    assert _head(repo) == before
    assert git.lock.calls == git2.lock.calls == git3.lock.calls == []
    assert _pending_keys(repo) == ["k1", "1.0.0"]
    assert not (repo / "docs/roadmap/new/THING-A1.md").exists()
    assert not (repo / "docs/roadmap/done/GATE-POE2-10.md").exists()


class RogueGit(Git):
    """A commit that also takes another staged path with it."""

    def commit(self, args, cwd):
        extra = Path(cwd) / "extra.txt"
        extra.write_text("extra\n")
        self.raw(["add", "--", "extra.txt"], cwd)
        return self.raw([*args, "extra.txt"], cwd)


def test_commit_touching_another_path_sets_commit_fault(tmp_path):
    repo = _repo(tmp_path)
    _queue(repo, _finding("thing", "k1", TAG="A1"), _finding("thing", "k2", TAG="A2"))
    git, lines = _file(repo, git=RogueGit())
    fault = repo / watch_file.FAULT_REL
    assert fault.exists()
    assert "THING-A1" in fault.read_text()
    assert any("COMMIT_FAULT" in ln for ln in lines), lines
    # the tick never reverts, resets or amends: the rogue commit stays HEAD
    commits = _watch_commits(repo)
    assert len(commits) == 1
    assert sorted(commits[0][1]) == ["docs/roadmap/new/THING-A1.md", "extra.txt"]
    # filing stopped at once: the second finding was not touched
    assert len(git.lock.calls) == 1
    assert not (repo / "docs/roadmap/new/THING-A2.md").exists()
    assert _pending_keys(repo) == ["k2"]


def test_commit_fault_stops_all_filing(tmp_path):
    repo = _repo(tmp_path)
    fault = repo / watch_file.FAULT_REL
    fault.parent.mkdir(parents=True)
    fault.write_text("2026-11-20T09:00:00-06:00 docs/roadmap/new/X.md: test\n")
    _queue(repo, _finding("urgent", "k1", TAG="A1"), _finding("flip", "1.0.0", NAME="POE2-10"))
    before = _head(repo)
    git, lines = _file(repo)
    assert lines and "COMMIT_FAULT" in lines[0]
    assert _head(repo) == before and git.lock.calls == []
    assert _pending_keys(repo) == ["k1", "1.0.0"]
    assert not (repo / "docs/roadmap/new/URGENT-A1.md").exists()
    # only a session removes the flag; then filing resumes
    fault.unlink()
    _file(repo)
    assert _pending_keys(repo) == []


def test_soft_gate_at_60_percent_holds_all_but_priority_and_done(tmp_path):
    repo = _repo(tmp_path)
    _queue(repo, _finding("thing", "k1", TAG="A1"), _finding("urgent", "k2", TAG="A2"),
           _finding("live", "seen-a", ITEM="A"))
    git, lines = _file(repo, budget=Budget(used=60, cap=100))
    assert (repo / "docs/roadmap/new/URGENT-A2.md").exists()
    assert (repo / "docs/roadmap/done/LIVE-A.md").exists()
    assert not (repo / "docs/roadmap/new/THING-A1.md").exists()
    assert _pending_keys(repo) == ["k1"]
    assert any("1 row(s) wait: usage" in ln for ln in lines), lines
    # an unreadable budget fails closed the same way
    _file(repo, budget=Budget(readable=False))
    assert _pending_keys(repo) == ["k1"]
    # under 60 percent the row goes
    _file(repo, budget=Budget(used=59, cap=100))
    assert (repo / "docs/roadmap/new/THING-A1.md").exists()
    assert _pending_keys(repo) == []


def test_used_id_in_roadmap_new_done_or_archive_is_refused(tmp_path):
    repo = _repo(tmp_path)
    tags = ("RM", "NEW", "DONE", "ARC")
    _queue(repo, *[_finding("thing", f"k-{t}", TAG=t) for t in tags])
    before = _head(repo)
    git, lines = _file(repo)
    assert _head(repo) == before and git.lock.calls == []
    assert _pending_keys(repo) == []  # an id that is taken can never be filed
    assert len([ln for ln in lines if "dropped" in ln]) == 4, lines
    assert any("already used" in ln for ln in lines), lines
    assert _ok(["status", "--short"], repo).strip() == ""


class FailingGit(Git):
    """A commit refused by the lock (a timeout), as al_loop._git reports it."""

    def commit(self, args, cwd):
        return subprocess.CompletedProcess(["git", *args], 3, "", "git lock: Timeout")


def test_failed_commit_removes_the_file_and_keeps_the_finding(tmp_path):
    repo = _repo(tmp_path)
    _queue(repo, _finding("thing", "k1", TAG="A1"))
    before = _head(repo)
    git, lines = _file(repo, git=FailingGit())
    assert len(git.lock.calls) == 1
    assert _head(repo) == before
    assert not (repo / "docs/roadmap/new/THING-A1.md").exists()
    assert _ok(["status", "--short"], repo).strip() == ""  # no intent-to-add left
    assert _pending_keys(repo) == ["k1"]
    assert not (repo / watch_file.FAULT_REL).exists()
    assert any("finding kept" in ln for ln in lines), lines
    # the next tick files it
    _file(repo)
    assert (repo / "docs/roadmap/new/THING-A1.md").exists()
    assert _pending_keys(repo) == []


def test_commit_subject_and_no_trailer(tmp_path):
    repo = _repo(tmp_path)
    _queue(repo, _finding("flip", "1.0.0", NAME="POE2-10"))
    _file(repo)
    body = _ok(["log", "-1", "--format=%B"], repo)
    assert body.strip() == "chore(roadmap): file GATE-POE2-10 (watch testsrc)"
    assert "\n" not in body.strip()
    assert "co-authored" not in body.lower() and "signed-off" not in body.lower()
    who = _ok(["log", "-1", "--format=%an|%ae|%cn|%ce"], repo).strip()
    assert who == "Operator|operator@example.com|Operator|operator@example.com"
    assert watch_file.SUBJECT_RX.match(body.strip())
