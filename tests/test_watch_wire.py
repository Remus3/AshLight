"""LOOP-WATCH-WIRE (F-030, AUTO-05; rulings Q-12, Q-13): the loop tick runs
tools/upstream_watch.run_due in front of the HALT return and files pending
findings after the work list through tools/loop_steps/upstream_watch.py.

Hermetic: every root is a scratch tree under tmp_path; the settled reads go
through recording Deps seams; scratch sources replace tools/watch_sources/
where a test needs a finding; git is a real git in a scratch repository.
No socket is opened and nothing touches the live tree."""

import importlib
import json
import socket
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import al_loop  # noqa: E402
import loop_steps  # noqa: E402
import upstream_watch  # noqa: E402
import watch_file  # noqa: E402
from server.al import webfetch  # noqa: E402
from al_loopkit import deps, isolate_git, make_root, real_git  # noqa: E402

step = importlib.import_module("loop_steps.upstream_watch")

NOW = 1_790_000_000.0
TEMPLATES = {"kinds": {
    "thing": {
        "act": "row", "id": "THING-<TAG>", "lane": "data", "priority": False,
        "blocked": None,
        "text": ("Check the <TAG> thing. ACCEPT: a test passes. ZERO-CLICK: the loop "
                 "works it. SOURCE: watch testsrc <TAG>, filed <YYYY-MM-DD>."),
        "tokens": {"TAG": r"[A-Z][A-Z0-9-]{0,11}"}, "sample": {"TAG": "A1"}},
}}


def _check(state, now, fetch, ctx):
    """A local test source: records each call, finds one row for all time."""
    with open(Path(ctx["root"]) / "calls.jsonl", "a", encoding="ascii") as f:
        f.write(json.dumps({"halted": ctx.get("halted"), "live": ctx.get("live")}) + "\n")
    return [{"kind": "thing", "key": "k1", "tokens": {"TAG": "A1"}}]


TEST_SOURCE = {"name": "testsrc", "home": "loop", "cadence_s": 0, "needs_web_data": True,
               "hosts": [], "urls": [], "check": _check}
ROW = "docs/roadmap/new/THING-A1.md"


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)


class Budget:
    cap = 100

    def readable(self):
        return True

    def used(self):
        return 0


def seam(line, calls, tag):
    def fn(root, now):
        calls.append((tag, Path(root), now))
        return line
    return fn


def halted_seam(line, calls, tag):
    def fn(root, now, halted=False):
        calls.append((tag, Path(root), now, halted))
        return line
    return fn


def progress(root):
    return json.loads((root / "ops/loop/control/progress/loop.json").read_text())


def halt(root):
    p = root / al_loop.HALT_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="ascii")


def git_root(tmp_path):
    """A make_root tree that is a git repository holding the test template."""
    root = make_root(tmp_path, handoff="")
    tpl = root / "ops" / "loop" / "watch_rows" / "testsrc.json"
    tpl.parent.mkdir(parents=True)
    tpl.write_text(json.dumps(TEMPLATES, indent=1) + "\n", newline="\n")
    (root / ".gitignore").write_text("ops/runtime/\nops/loop/control/\ncalls.jsonl\n",
                                     newline="\n")
    for args in (["init", "-q", "-b", "main"], ["config", "core.autocrlf", "false"],
                 ["config", "commit.gpgsign", "false"], ["add", "-A"],
                 ["commit", "-q", "-m", "base"]):
        r = real_git(args, root)
        assert r.returncode == 0, (args, r.stderr)
    return root


def head(root):
    return real_git(["rev-parse", "HEAD"], root).stdout.strip()


def scratch_sources(monkeypatch):
    """The real registry plus the local test source, last."""
    real = upstream_watch.discover
    extra = dict(upstream_watch.normalize(TEST_SOURCE), module="testsrc")
    monkeypatch.setattr(upstream_watch, "discover",
                        lambda directory=None, errors=None: real(directory, errors) + [extra])


def source_calls(root):
    p = root / "calls.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="ascii").splitlines() if ln]


class Events:
    """Orders the dispatch launches against the git commits of one tick."""

    def __init__(self):
        self.seen = []

    def git(self, args, cwd, input=None, lock=None):
        if args and args[0] == "commit":
            self.seen.append("commit")
        return real_git(args, cwd, input)

    def launch(self, iid):
        self.seen.append(("launch", iid))
        return 4242


# ---------------------------------------------------------------- the step module

def test_step_replaces_the_auto01_docs_watch_and_tc_drift_steps():
    stems = [m.__name__.rsplit(".", 1)[-1] for m in loop_steps.load()]
    assert "upstream_watch" in stems
    assert "docs_watch" not in stems and "tc_drift" not in stems
    # the step is loop_steps.upstream_watch; the frame stays tools/upstream_watch.py
    assert Path(step.watch.__file__).resolve() == (ROOT / "tools" / "upstream_watch.py").resolve()
    assert step.watch is upstream_watch


# ---------------------------------------------------------------- package tests

@pytest.mark.git
def test_halted_tick_reads_records_and_commits_nothing(tmp_path, monkeypatch):
    root = git_root(tmp_path)
    scratch_sources(monkeypatch)
    halt(root)
    before = head(root)
    calls = []
    d = deps(root, git=real_git,
             docs_watch=seam("ggg docs: 6/6", calls, "docs"),
             drift=halted_seam("tc drift: none", calls, "drift"))
    doc = al_loop.tick(deps=d, no_push=True)
    assert doc["state"] == "halted"
    # read: every source ran, the settled seams in front of the HALT return
    assert source_calls(root) == [{"halted": True, "live": False}]
    assert calls == [("docs", root, NOW), ("drift", root, NOW, True)]
    # recorded: the source's state and the queued finding
    st = upstream_watch.load_state(root)["sources"]["testsrc"]
    assert st["last_ok"] and st["seen"] == ["k1"]
    assert [f["key"] for f in upstream_watch.pending(root)] == ["k1"]
    log = progress(root)["log"]
    assert log[:2] == ["ggg docs: 6/6", "tc drift: none"]
    assert "watch: HALT: 1 finding(s) queued, nothing filed" in log
    assert log[-1] == "HALT file present"
    # nothing filed, bumped or committed
    assert head(root) == before
    assert not (root / ROW).exists()
    assert real_git(["status", "--short"], root).stdout.strip() == ""
    assert not (root / watch_file.FAULT_REL).exists()
    # a second HALTed tick reads again and still commits nothing
    al_loop.tick(deps=d, no_push=True)
    assert len(source_calls(root)) == 2 and head(root) == before
    assert len(upstream_watch.pending(root)) == 1


@pytest.mark.git
def test_running_tick_files_a_pending_finding_after_the_work_list(tmp_path, monkeypatch):
    root = git_root(tmp_path)
    scratch_sources(monkeypatch)
    halt(root)
    ev = Events()
    d = deps(root, git=ev.git, launch=ev.launch)
    al_loop.tick(deps=d, no_push=True)  # HALTed: queued only
    assert ev.seen == [] and len(upstream_watch.pending(root)) == 1
    (root / al_loop.HALT_REL).unlink()
    before = head(root)
    al_loop.tick(deps=d, no_push=True)
    # filed: one add-only commit naming only the row file
    assert (root / ROW).read_text(encoding="ascii").startswith("- [ ] THING-A1 (data) ")
    assert real_git(["rev-parse", "HEAD^"], root).stdout.strip() == before
    shown = [ln for ln in real_git(["show", "--name-only", "--format=%s", "HEAD"],
                                   root).stdout.splitlines() if ln.strip()]
    assert shown == ["chore(roadmap): file THING-A1 (watch testsrc)", ROW]
    assert upstream_watch.pending(root) == []
    # after the work list: the dispatch launched before the filing commit
    launches = [i for i, e in enumerate(ev.seen) if isinstance(e, tuple)]
    assert launches and ev.seen.count("commit") == 1
    assert max(launches) < ev.seen.index("commit")
    log = progress(root)["log"]
    assert any(ln.startswith("watch file: filed " + ROW) for ln in log), log
    # the source key is seen for all time: no second finding, no second commit
    al_loop.tick(deps=d, no_push=True)
    assert ev.seen.count("commit") == 1


@pytest.mark.git
def test_dry_run_calls_no_source(tmp_path, monkeypatch):
    root = git_root(tmp_path)
    scratch_sources(monkeypatch)
    calls = []
    d = deps(root, git=real_git,
             docs_watch=seam("ggg docs: 6/6", calls, "docs"),
             drift=halted_seam("tc drift: none", calls, "drift"))
    al_loop.tick(dry_run=True, deps=d, no_push=True)
    halt(root)
    al_loop.tick(dry_run=True, deps=d, no_push=True, ignore_halt=True)
    al_loop.tick(dry_run=True, deps=d, no_push=True)
    assert source_calls(root) == [] and calls == []
    assert not (root / upstream_watch.STATE_REL).exists()
    assert not (root / upstream_watch.PENDING_REL).exists()


@pytest.mark.git
def test_settled_sources_still_run_every_tick_through_the_seams(tmp_path):
    root = make_root(tmp_path, handoff="")
    calls = []
    d = deps(root, docs_watch=seam("ggg docs: 6/6", calls, "docs"),
             drift=seam("tc drift: none", calls, "drift"))
    for _ in range(2):  # cadence 0: every tick, the reads keep their own 24 h gates
        al_loop.tick(deps=d, no_push=True)
    assert calls == [("docs", root, NOW), ("drift", root, NOW)] * 2
    log = progress(root)["log"]
    assert log.index("ggg docs: 6/6") < log.index("tc drift: none")
    # the one-time idle line stays in the watch state, not in the tick log
    assert not any("idle: web data off" in ln for ln in log)
    st = upstream_watch.load_state(root)["sources"]
    assert st["ggg-docs"]["last_ok"] and st["pob-release"]["last_ok"]
    # HALTed: the docs read runs; a two-argument drift seam is not called on a
    # scratch root, a halted-aware one is called with halted=True
    halt(root)
    calls.clear()
    al_loop.tick(deps=d, no_push=True)
    assert calls == [("docs", root, NOW)]
    d = deps(root, docs_watch=seam(None, calls, "docs"),
             drift=halted_seam("tc drift: halted read", calls, "drift"))
    calls.clear()
    al_loop.tick(deps=d, no_push=True)
    assert calls == [("docs", root, NOW), ("drift", root, NOW, True)]
    assert progress(root)["log"] == ["tc drift: halted read", "HALT file present"]
    # a seam fault is one tick line and never stops the tick
    (root / al_loop.HALT_REL).unlink()

    def boom(r, now):
        raise RuntimeError("seam broke")
    d = deps(root, docs_watch=boom, drift=seam("tc drift: none", calls, "drift"))
    doc = al_loop.tick(deps=d, no_push=True)
    assert doc["state"] in ("running", "idle")
    log = progress(root)["log"]
    assert any(ln.startswith("watch ggg-docs: failed") and "seam broke" in ln for ln in log)
    assert "tc drift: none" in log


def test_scratch_root_tick_starts_no_process_and_makes_no_request(tmp_path, monkeypatch):
    root = make_root(tmp_path, handoff="", local={"web_data": True})
    spawned, dialled = [], []

    def no_popen(*a, **k):
        spawned.append(a)
        raise AssertionError("a process was started")

    def no_connect(self, *a, **k):
        dialled.append(a)
        raise AssertionError("a socket was opened")

    monkeypatch.setattr(subprocess, "Popen", no_popen)
    monkeypatch.setattr(socket.socket, "connect", no_connect)
    monkeypatch.setattr(socket, "create_connection", no_connect)
    fetches = []
    real_run = step.watch.run_due

    def run_due(*a, **k):
        fetches.append(k.get("fetch"))
        return real_run(*a, **k)

    monkeypatch.setattr(step.watch, "run_due", run_due)
    calls = []
    d = types.SimpleNamespace(clock=lambda: NOW, docs_watch=seam(None, calls, "docs"),
                              drift=seam(None, calls, "drift"), git=lambda a, c: None,
                              budget=Budget())
    t = types.SimpleNamespace(root=root, d=d, halted=False, dry=False)
    assert step.live(t) is False
    assert step.live(types.SimpleNamespace(root=ROOT)) is True
    step.pre_halt(t)
    step.post_work(t, [], [], [])
    assert spawned == [] and dialled == []
    assert calls == [("docs", root, NOW), ("drift", root, NOW)]
    # off the live root the frame gets a transport that refuses every request
    assert fetches == [step._refuse]
    with pytest.raises(webfetch.UrlNotAllowed):
        step._refuse("GET", "https://api.github.com/", {})
    # web data on: whichever network source was due ran without a request
    st = upstream_watch.load_state(root)["sources"]
    assert sum(1 for e in st.values() if e.get("last_run")) >= 3
    # the HALTed and dry forms are just as quiet
    t.halted = True
    step.pre_halt(t)
    t.halted, t.dry = False, True
    assert step.post_work(t, [], [], []) == []
    assert spawned == [] and dialled == []
