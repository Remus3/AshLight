"""Loop tests, lane side: the lane worker, stalls, the lane race, resolve
lanes, refused commits and the detached review / push workers.
Moved verbatim from tests/test_al_loop.py (TEST-LOOP-SPLIT-LANES, F-196);
every side effect is injected and merge tests use a throwaway local git repo
under tmp_path."""

import contextlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402

from al_loopkit import (  # noqa: E402 (shared with the sibling loop tests)
    ROADMAP, FakeGit, FakeSpawn, _two_lane_world, deps, git, git_world, isolate_git,
    make_root, progress, real_git, stub_git)

# Plan 097 / 156 (TESTS-A-18): only the tests that build a real git world under
# tmp_path are marked git, one by one, so the fast tier runs the pure ones.


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)  # TESTS-A-19
    stub_git(monkeypatch)  # TEST-LOOP-STUB-GIT: no-spawn deps() defaults


# ---------------------------------------------------------------- lane worker

def test_lane_worker_records_result(tmp_path):
    root = make_root(tmp_path)
    items = al_loop.Items(root)
    items.put({"id": "012", "kind": "plan", "state": "dispatched", "lane": "data",
               "prompt": "implement plan 012", "title": "t", "label": "l"})
    seen = []

    def run_lane(lane, prompt, **kw):
        seen.append((lane, prompt, kw["writes_code"]))
        seen_rows.append(kw["checklist"])
        return {"rc": 0, "error": None, "worktree": "wt"}

    seen_rows = []
    assert al_loop.lane_worker("012", deps=deps(root), run_lane=run_lane) == 0
    assert seen == [("data", "implement plan 012", True)]
    assert seen_rows[0][0]["id"] == "012"
    # LANE-CHECKLIST: the dispatched item rides on the lane progress file
    assert al_loop.lane_checklist(items.get("012")) == \
        [{"id": "012", "task": "t", "state": "data running", "eta_s": None}]
    rec = items.get("012")
    assert rec["state"] == "ran" and rec["worktree"] == "wt"
    assert al_loop.lane_worker("012", deps=deps(root), run_lane=run_lane) == 0
    assert len(seen) == 1  # only a dispatched record runs


def _dispatched(root, iid="012", **extra):
    items = al_loop.Items(root)
    items.put(dict({"id": iid, "kind": "plan", "state": "dispatched", "lane": "data",
                    "prompt": "p", "title": "t", "label": "l", "attempts": 1}, **extra))
    return items


def test_lane_worker_rechecks_halt_backoff_and_cap_and_passes_halt_file(tmp_path):
    root = make_root(tmp_path)
    ran = []

    def run_lane(lane, prompt, spawn=None, root=None, **kw):
        ran.append(lane)
        spawn(root, "AL", prompt)
        return {"rc": 0, "error": None, "worktree": "wt"}

    items = _dispatched(root)
    halt = root / al_loop.HALT_REL
    halt.parent.mkdir(parents=True, exist_ok=True)
    halt.write_text("")
    assert al_loop.lane_worker("012", deps=deps(root), run_lane=run_lane) == 0
    rec = items.get("012")
    assert ran == [] and rec["state"] == "paused" and rec["attempts"] == 0
    assert al_loop.dispatchable(rec)  # a pause costs no attempt
    halt.unlink()
    d = deps(root)
    al_loop.backoff_hit(root, d.clock(), "429")
    _dispatched(root)
    al_loop.lane_worker("012", deps=d, run_lane=run_lane)
    assert ran == [] and items.get("012")["error"] == "paused: backoff"
    al_loop.backoff_clear(root)
    p = root / "ops/loop/control/headless_budget.json"
    p.write_text(json.dumps({"starts": [d.clock() - 10] * (d.budget.cap - 3)}))
    d.budget.clock = d.clock
    _dispatched(root)
    al_loop.lane_worker("012", deps=d, run_lane=run_lane)
    assert ran == [] and items.get("012")["error"] == "paused: runs cap"
    p.unlink()
    sp = FakeSpawn()
    _dispatched(root)
    al_loop.lane_worker("012", deps=deps(root, spawn=sp), run_lane=run_lane)
    assert ran == ["data"] and sp.calls[0]["halt_file"] == halt


def test_lane_worker_halt_raised_by_kit_mid_run_is_a_pause(tmp_path):
    root = make_root(tmp_path)
    items = _dispatched(root)
    halt = root / al_loop.HALT_REL

    def run_lane(lane, prompt, **kw):
        halt.parent.mkdir(parents=True, exist_ok=True)
        halt.write_text("")
        raise RuntimeError("Refused: halt file present")

    al_loop.lane_worker("012", deps=deps(root), run_lane=run_lane)
    assert items.get("012")["state"] == "paused"


def test_dirty_lane_claim_is_flagged_not_dropped(tmp_path):
    root = make_root(tmp_path, handoff="")
    items = _dispatched(root)

    wt = tmp_path / "al-worktrees" / "lane-1"
    wt.mkdir(parents=True)

    def run_lane(lane, prompt, **kw):
        raise RuntimeError(f"LaneRefused: lane worktree {wt} is dirty - resolve it by hand")

    assert al_loop.lane_worker("012", deps=deps(root), run_lane=run_lane) == 1
    rec = items.get("012")
    assert rec["state"] == "lane-dirty" and "dirty" in rec["error"]
    assert not al_loop.dispatchable(rec)
    # still dirty: it waits (recover_lane_dirty clears it once clean)
    doc = al_loop.tick(deps=deps(root, git=FakeGit(dirty=" M x")), no_push=True)
    row = next(r for r in doc["checklist"] if r["id"] == "012")
    assert row["state"] == "lane-dirty" and row["eta_s"] == 0


@pytest.mark.git
def test_exhausted_attempts_become_gave_up_with_the_error(tmp_path):
    root = make_root(tmp_path, roadmap=ROADMAP.replace("- [ ] 013 Season pass tracker\n", ""),
                     handoff="")
    al_loop.Items(root).put({"id": "012", "kind": "plan", "state": "refused", "lane": "data",
                             "attempts": al_loop.MAX_ATTEMPTS, "error": "lanes_full",
                             "title": "Grind spot recommender", "label": "l"})
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    assert al_loop.Items(root).get("012")["state"] == "gave-up"
    assert any("gave up after 2 attempts: lanes_full" in s for s in doc["log"])
    assert next(r for r in doc["checklist"] if r["id"] == "012")["state"] == "gave-up"
    assert "012" not in d.seen["launch"]


# ---------------------------------------------------------------- plan 137 stalls

def _prog(now, ago, eta_s=300, status="running"):
    return {"task": "p012-build", "pct": 40, "step": "s", "eta_s": eta_s, "status": status,
            "updated": al_loop.iso(now - ago)}


def test_stall_of_is_twice_eta_with_a_floor_and_unknown_is_not_stalled():
    now = 1_790_000_000.0
    assert al_loop.stall_of(_prog(now, 1500), now) == 1500  # 2 x 300 < floor 600 < 1500
    assert al_loop.stall_of(_prog(now, 500), now) is None  # under the 600 s floor
    assert al_loop.stall_of(_prog(now, 1500, eta_s=900), now) is None  # under 2 x eta
    assert al_loop.stall_of(_prog(now, 1900, eta_s=900), now) == 1900
    assert al_loop.stall_of(_prog(now, 700), now, floor_s=0) == 700
    assert al_loop.stall_of(_prog(now, 1500, eta_s=None), now) == 1500
    for status in ("done", "failed", "blocked"):
        assert al_loop.stall_of(_prog(now, 9999, status=status), now) is None
    assert al_loop.stall_of(dict(_prog(now, 9999), updated="garbage"), now) is None
    assert al_loop.stall_of({k: v for k, v in _prog(now, 9999).items() if k != "updated"},
                            now) is None
    assert al_loop.stall_of(None, now) is None
    assert al_loop.stall_of(dict(_prog(now, 9999), eta_s="x"), now) == 9999


def _stall_world(tmp_path, ago=1500):
    root = make_root(tmp_path, roadmap=ROADMAP.replace("- [ ] 013 Season pass tracker\n", ""),
                     handoff="")
    wt = tmp_path / "wt0"
    d = deps(root, lane_state=lambda: [{"index": 0, "state": "RUNNING", "lane": "data"},
                                       {"index": 1, "state": "FREE", "lane": None},
                                       {"index": 2, "state": "FREE", "lane": None}],
             lane_worktree=lambda i: tmp_path / f"wt{i}")
    now = d.clock()
    _dispatched(root, pid=4242, title="Grind spot recommender",
                dispatched=al_loop.iso(now - 3600))
    return root, wt, d, now


def _write_prog(tree, doc):
    p = Path(tree) / "ops/loop/control/progress/p012-build.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc))


@pytest.mark.git
def test_silent_lane_shows_stalled_never_killed_and_records_one_stall_row(tmp_path):
    root, wt, d, now = _stall_world(tmp_path)
    _write_prog(wt, _prog(now, 1500))
    doc = al_loop.tick(deps=d, no_push=True)
    row = next(r for r in doc["checklist"] if r["id"] == "012")
    assert row["state"] == "stalled, 25m silent" and row["eta_s"] is None
    assert "012: stalled 25m" in doc["log"]
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "dispatched" and rec["stalled_s"] == 1500
    assert d.seen["record"].count("lane-stall") == 1  # 1500 s > 3 x 300
    assert "012" not in d.seen["launch"]
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["record"].count("lane-stall") == 1  # once per stall
    assert al_loop.Items(root).get("012")["state"] == "dispatched"
    block = al_loop.render_checklist(progress(root))
    assert "012: Grind spot recommender (stalled, 25m silent)" in block


@pytest.mark.git
def test_stall_under_three_eta_records_no_stall_row(tmp_path):
    root, wt, d, now = _stall_world(tmp_path)
    _write_prog(wt, _prog(now, 700))
    doc = al_loop.tick(deps=d, no_push=True)
    assert next(r for r in doc["checklist"] if r["id"] == "012")["state"] == "stalled, 11m silent"
    assert "lane-stall" not in d.seen["record"]


@pytest.mark.git
def test_no_progress_file_shows_nothing_and_fresh_progress_clears_the_flag(tmp_path):
    root, wt, d, now = _stall_world(tmp_path)
    doc = al_loop.tick(deps=d, no_push=True)
    assert next(r for r in doc["checklist"] if r["id"] == "012")["state"] == "dispatched"
    assert not any(": stalled" in s for s in doc["log"])
    _write_prog(wt, _prog(now, 1500))
    al_loop.tick(deps=d, no_push=True)
    assert al_loop.Items(root).get("012")["stalled_s"] == 1500
    _write_prog(wt, _prog(now, 10))
    doc = al_loop.tick(deps=d, no_push=True)
    assert "stalled_s" not in al_loop.Items(root).get("012")
    assert next(r for r in doc["checklist"] if r["id"] == "012")["state"] == "dispatched"


def test_lane_progress_worktree_then_main_newest_wins_stale_ignored(tmp_path):
    root, wt, d, now = _stall_world(tmp_path)
    t = al_loop.Tick(d)
    rec = al_loop.Items(root).get("012")
    assert t.lane_progress(rec) is None
    _write_prog(root, _prog(now, 1500))  # main checkout only (lane could not write wt)
    assert t.lane_progress(rec)["updated"] == al_loop.iso(now - 1500)
    _write_prog(wt, _prog(now, 2000))
    assert t.lane_progress(rec)["updated"] == al_loop.iso(now - 1500)  # newest wins
    _write_prog(wt, _prog(now, 100))
    assert t.lane_progress(rec)["updated"] == al_loop.iso(now - 100)
    _write_prog(wt, _prog(now, 7200))  # before this run's dispatch: stale
    _write_prog(root, dict(_prog(now, 9000)))
    assert t.lane_progress(rec) is None
    _write_prog(root, dict(_prog(now, 50), updated="nope"))
    assert t.lane_progress(rec) is None


@pytest.mark.git
def test_launch_exception_marks_lost_and_frees_the_lane(tmp_path):
    root = make_root(tmp_path, handoff="")
    calls = []

    def launch(iid):
        calls.append(iid)
        if iid == "012":
            raise OSError("no pythonw")
        return 99

    d = deps(root, launch=launch)
    al_loop.tick(deps=d, no_push=True)
    items = al_loop.Items(root)
    r12 = items.get("012")
    assert r12["state"] == "lost" and "OSError" in r12["error"] and not r12.get("pid")
    assert items.get("013")["lane"] == "build"  # the failed launch's lane is reused
    al_loop.tick(deps=d, no_push=True)
    assert calls.count("012") == al_loop.MAX_ATTEMPTS


@pytest.mark.git
def test_dispatched_without_pid_is_reaped(tmp_path):
    root = make_root(tmp_path, roadmap="", handoff="")
    _dispatched(root, title="t")  # no pid: a tick died between its two writes
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    assert any("012: lane process gone" in s for s in doc["log"])
    assert al_loop.Items(root).get("012")["state"] == "lost"


@pytest.mark.git
def test_checklist_eta_is_lane_median_less_elapsed(tmp_path):
    root = make_root(tmp_path, roadmap="", handoff="")
    kinds = []
    d = deps(root, estimate=lambda kind, default=None: kinds.append(kind) or 2700.0)
    al_loop.Items(root).put({"id": "012", "kind": "plan", "state": "dispatched",
                             "lane": "data", "pid": 1, "title": "t", "label": "l",
                             "dispatched": al_loop.iso(d.clock() - 600)})
    doc = al_loop.tick(deps=d, no_push=True)
    assert next(r for r in doc["checklist"] if r["id"] == "012")["eta_s"] == 2100
    assert "lane-data-code" in kinds and "loop-review" not in kinds


@pytest.mark.git
def test_checklist_eta_prefers_item_kind(tmp_path):
    root = make_root(tmp_path, roadmap="", handoff="")
    d = deps(root, estimate=lambda kind, default=None: 900.0 if kind == "item-resolve"
             else 2700.0)
    al_loop.Items(root).put({"id": "012", "kind": "resolve", "state": "dispatched",
                             "lane": "data", "pid": 1, "title": "t", "label": "l",
                             "dispatched": al_loop.iso(d.clock() - 600)})
    doc = al_loop.tick(deps=d, no_push=True)
    assert next(r for r in doc["checklist"] if r["id"] == "012")["eta_s"] == 300


def test_lane_worker_passes_item_eta_kind(tmp_path):
    root = make_root(tmp_path, roadmap="", handoff="")
    seen = {}

    def run_lane(lane, prompt, **kw):
        seen.update(kw)
        return {"rc": 0, "error": None, "worktree": str(tmp_path)}

    d = deps(root)
    al_loop.Items(root).put({"id": "012", "kind": "plan", "state": "dispatched",
                             "lane": "build", "pid": 1, "title": "t", "label": "l",
                             "prompt": "p", "dispatched": al_loop.iso(d.clock())})
    al_loop.lane_worker("012", deps=d, run_lane=run_lane)
    assert seen.get("eta_kind") == "item-plan"


@pytest.mark.slow
@pytest.mark.git
def test_verifier_crash_is_counted_then_adjudicated(tmp_path):
    root, wt = git_world(tmp_path)
    crash = {"rc": 1, "error": "exit 1", "result": "boom"}
    sp = FakeSpawn([crash, crash, crash])
    d = deps(root, spawn=sp, git=real_git,
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "ran" and rec["verify_errors"] == 1
    al_loop.tick(deps=d, no_push=True)
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["verify_errors"] == 3 and rec["state"] == "adjudicate"
    assert len(sp.calls) == 3 and not (root / "feature.txt").exists()
    al_loop.tick(deps=d, no_push=True)
    assert len(sp.calls) == 3  # never retried past the cap


def test_launch_is_detached_hidden_with_breakaway_fallback(tmp_path):
    calls = []

    class P:
        pid = 7

    def popen(argv, creationflags=0, **kw):
        calls.append(creationflags)
        if len(calls) == 1 and al_loop._BREAKAWAY:
            raise PermissionError("job forbids breakaway")
        assert argv[-2:] == ["lane", "012"] and kw["stdin"] == subprocess.DEVNULL
        return P()

    assert al_loop._launch(tmp_path, "012", popen=popen) == 7
    assert all(f & al_loop._NO_WINDOW == al_loop._NO_WINDOW for f in calls)
    assert all(f & al_loop._DETACHED == al_loop._DETACHED for f in calls)


def test_no_machine_path_in_sources():
    for rel in ("tools/al_loop.py", "tests/test_al_loop.py", "tests/test_al_loop_merge.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]", src)
        assert "\\" + "Users" + "\\" not in src
        src.encode("ascii")


T0 = 1_790_000_000.0


# ---------------------------------------------------------------- lane race (fix 2026-10-05)
# An item that finished ("ran") or was committed holds its unmerged work in its
# lane worktree; the kit claims the LOWEST non-RUNNING index and refuses a
# dirty worktree, so a dispatch onto it became lane-dirty and waited forever.

ONE_ROW = ROADMAP.replace("- [ ] 013 Season pass tracker\n", "")


def lane_wt(tmp_path, i):
    return tmp_path / "al-worktrees" / f"lane-{i}"


def finishes_mid_tick(root, wt, rows, state="ran"):
    """lane_state that, like the 14:00:27 run, flips item 013 from
    dispatched to `state` between tick start and the dispatch step."""
    def lane_state():
        rec = al_loop.Items(root).get("013")
        if rec.get("state") == "dispatched":
            al_loop.Items(root).put(dict(rec, state=state, worktree=str(wt), rc=0))
        return rows
    return lane_state


@pytest.mark.git
def test_item_finishing_mid_tick_keeps_its_lane_busy(tmp_path):
    root = make_root(tmp_path, roadmap=ONE_ROW, handoff="")
    _dispatched(root, iid="013", lane="review", pid=7)
    rows = [{"index": 0, "state": "RUNNING", "lane": "build"},
            {"index": 1, "state": "RUNNING", "lane": "data"},
            {"index": 2, "state": "FREE", "lane": None}]
    for state in ("ran", "committed"):
        al_loop.Items(root).put(dict(al_loop.Items(root).get("013"), state="dispatched"))
        d = deps(root, lane_state=finishes_mid_tick(root, lane_wt(tmp_path, 2), rows, state))
        al_loop.tick(deps=d, no_push=True)
        assert d.seen["launch"] == [], state
        assert al_loop.Items(root).get("012") is None


@pytest.mark.git
def test_held_worktree_at_a_lower_index_blocks_dispatch(tmp_path):
    """The kit picks the lowest non-RUNNING index, not a lane name: a held
    index 0 under a free index 2 would still be claimed and refused."""
    root = make_root(tmp_path, roadmap=ONE_ROW, handoff="")
    _dispatched(root, iid="013", lane="build", pid=7)
    rows = [{"index": 0, "state": "FREE", "lane": None},
            {"index": 1, "state": "RUNNING", "lane": "data"},
            {"index": 2, "state": "FREE", "lane": None}]
    d = deps(root, lane_state=finishes_mid_tick(root, lane_wt(tmp_path, 0), rows))
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == []


def dirty_lane_world(tmp_path, index=0):
    root = make_root(tmp_path, roadmap=ONE_ROW, handoff="")
    git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("ops/\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    wt = lane_wt(tmp_path, index)
    git(root, "worktree", "add", "-q", "--detach", str(wt))
    (wt / "crash.txt").write_text("left by a crashed run\n")
    return root, wt


@pytest.mark.git
def test_physically_dirty_lowest_worktree_blocks_dispatch_until_clean(tmp_path):
    root, wt = dirty_lane_world(tmp_path)
    d = deps(root, git=real_git)
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == []
    (wt / "crash.txt").unlink()
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["012"]


def lane_dirty(root, wt, attempts=1):
    al_loop.Items(root).put({
        "id": "012", "kind": "plan", "state": "lane-dirty", "lane": "review", "prompt": "p",
        "title": "Grind spot recommender", "label": "plan 012: Grind spot recommender",
        "attempts": attempts, "dispatched": al_loop.iso(T0 - 600),
        "error": f"LaneRefused: lane worktree {wt} is dirty - resolve it by hand"})


@pytest.mark.git
def test_lane_dirty_recovers_once_its_worktree_is_clean_and_unheld(tmp_path):
    root, wt = dirty_lane_world(tmp_path, index=2)
    lane_dirty(root, wt)
    d = deps(root, git=real_git)
    al_loop.tick(deps=d, no_push=True)  # still dirty: waits, no attempt spent
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "lane-dirty" and "012" not in d.seen["launch"]
    # another item's unmerged work holds that worktree: still waits
    al_loop.Items(root).put({"id": "013", "kind": "plan", "state": "committed",
                             "lane": "build", "worktree": str(wt), "title": "t",
                             "label": "l", "commit": "x"})
    (wt / "crash.txt").unlink()
    al_loop.Tick(d, False, True).recover_lane_dirty()
    assert al_loop.Items(root).get("012")["state"] == "lane-dirty"
    al_loop.Items(root).put(dict(al_loop.Items(root).get("013"), state="merged"))
    doc = al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert d.seen["launch"].count("012") == 1 and rec["state"] == "dispatched"
    assert rec["attempts"] == 2  # bounded by MAX_ATTEMPTS like any retry
    assert any("012: lane-dirty cleared" in s for s in doc["log"])
    al_loop.Tick(d, False, True).recover_lane_dirty()  # idempotent: no-op now
    assert al_loop.Items(root).get("012")["state"] == "dispatched"


@pytest.mark.git
def test_lane_dirty_out_of_attempts_gives_up_with_the_error(tmp_path):
    root, wt = dirty_lane_world(tmp_path, index=2)
    (wt / "crash.txt").unlink()
    lane_dirty(root, wt, attempts=al_loop.MAX_ATTEMPTS)
    d = deps(root, git=real_git)
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "gave-up" and "dirty" in rec["error"]
    assert "012" not in d.seen["launch"]


@pytest.mark.git
def test_lane_dirty_without_a_worktree_in_its_error_stays(tmp_path):
    root = make_root(tmp_path, roadmap=ONE_ROW, handoff="")
    lane_dirty(root, "x")
    al_loop.Items(root).put(dict(al_loop.Items(root).get("012"), error="LaneRefused: dirty"))
    d = deps(root)
    al_loop.tick(deps=d, no_push=True)
    assert al_loop.Items(root).get("012")["state"] == "lane-dirty"
    assert "012" not in d.seen["launch"]


# ---------------------------------------------------------------- plan 058: resolve lanes

def _conflict_world(tmp_path):
    """012 merges, 013 conflicts on f.txt (finished() runs ids in order)."""
    root = _two_lane_world(tmp_path, lambda wt: (wt / "f.txt").write_text("a\n"),
                           lambda wt: (wt / "f.txt").write_text("b\n"))
    return root, al_loop.Items(root)


def _free(root, tmp_path, **over):
    return deps(root, git=real_git, lane_worktree=lambda i: tmp_path / "none" / str(i),
                **over)


def keep_refs(root):
    return git(root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/al/keep")


@pytest.mark.slow
@pytest.mark.git
def test_conflict_keeps_the_lane_commit_under_a_ref(tmp_path):
    root, items = _conflict_world(tmp_path)
    rec = items.get("013")
    assert rec["state"] == "merge-conflict" and rec["keep_ref"] == "refs/al/keep/013"
    assert keep_refs(root) == f"refs/al/keep/013 {rec['commit']}"
    assert items.get("012")["state"] == "merged"


@pytest.mark.slow
@pytest.mark.git
def test_next_tick_dispatches_a_resolve_lane_first(tmp_path):
    root, items = _conflict_world(tmp_path)
    rm = root / "ROADMAP.md"
    rm.write_text(rm.read_text() + "- [ ] 014 Other\n", newline="\n")
    git(root, "commit", "-q", "-am", "row 014")
    d = _free(root, tmp_path)
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"][:2] == ["013", "014"] and d.seen["launch"].count("013") == 1
    rec = items.get("013")
    assert rec["kind"] == "resolve" and rec["base_kind"] == "plan"
    assert rec["resolve_runs"] == 1 and rec["state"] == "dispatched"
    assert rec["keep_ref"] == "refs/al/keep/013" and rec["attempts"] == 1
    assert "git merge --no-ff --no-commit refs/al/keep/013" in rec["prompt"]
    assert "BOTH" in rec["prompt"] and "decision / alternatives / why" in rec["prompt"]
    assert "Do NOT edit ROADMAP.md" in rec["prompt"]
    row = [r for r in progress(root)["checklist"] if r["id"] == "013"][0]
    assert row["state"] == "resolving, run 1/2"


def _run_resolve(root, tmp_path, items, name, content):
    """The lane worker for a dispatched resolve item; the fake lane resolves
    f.txt to `content`. Returns the merge state the lane saw."""
    wt = tmp_path / "al-worktrees" / name
    git(root, "worktree", "add", "-q", "--detach", str(wt), "main")
    saw = {}

    def lane(kw):
        cwd = Path(kw["cwd"])
        saw["merging"] = real_git(["rev-parse", "-q", "--verify", "MERGE_HEAD"],
                                  cwd).returncode == 0
        saw["markers"] = "<<<<<<<" in (cwd / "f.txt").read_text()
        (cwd / "f.txt").write_text(content)
        return {"rc": 0, "error": None, "result": "resolved"}

    sp = FakeSpawn([lane])

    def run_lane(lane_name, prompt, spawn=None, root=None, **kw):
        line = spawn(root, "AL", prompt, cwd=wt)
        return dict(line, worktree=str(wt))

    assert al_loop.lane_worker("013", deps=deps(root, spawn=sp, git=real_git),
                               run_lane=run_lane) == 0
    assert items.get("013")["state"] == "ran"
    return saw


def _review(root, verdicts=1):
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}] * verdicts)
    return deps(root, spawn=sp, git=real_git,
                lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                    for i, n in enumerate(("build", "data", "review"))])


@pytest.mark.slow
@pytest.mark.git
def test_second_conflict_reenters_resolve_then_caps(tmp_path):
    root, items = _conflict_world(tmp_path)
    al_loop.tick(deps=_free(root, tmp_path), no_push=True)
    _run_resolve(root, tmp_path, items, "lane-2", "a\nb\n")
    (root / "f.txt").write_text("c\n")  # main moves on under the resolve lane
    git(root, "commit", "-q", "-am", "main moves")
    al_loop.tick(deps=_review(root), no_push=True)
    rec = items.get("013")
    assert rec["state"] == "merge-conflict" and rec["resolve_runs"] == 1
    assert keep_refs(root) == f"refs/al/keep/013 {rec['commit']}"
    d = _free(root, tmp_path)
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["013"] and items.get("013")["resolve_runs"] == 2
    items.put(dict(items.get("013"), state="merge-conflict"))
    d = _free(root, tmp_path)
    al_loop.tick(deps=d, no_push=True)
    assert "013" not in d.seen["launch"] and items.get("013")["state"] == "merge-conflict"
    row = [r for r in progress(root)["checklist"] if r["id"] == "013"][0]
    assert row["state"] == "merge-conflict"


@pytest.mark.slow
@pytest.mark.git
def test_lost_resolve_lane_is_redispatched_as_resolve(tmp_path):
    root, items = _conflict_world(tmp_path)
    al_loop.tick(deps=_free(root, tmp_path), no_push=True)
    items.put(dict(items.get("013"), state="lost"))
    d = _free(root, tmp_path)
    al_loop.tick(deps=d, no_push=True)
    rec = items.get("013")
    assert d.seen["launch"] == ["013"] and rec["kind"] == "resolve"
    assert rec["attempts"] == 2 and "refs/al/keep/013" in rec["prompt"]


@pytest.mark.slow
@pytest.mark.git
def test_hand_merged_conflict_settles_as_merged_and_drops_the_ref(tmp_path):
    root, items = _conflict_world(tmp_path)
    git(root, "merge", "-q", "--no-ff", "-X", "theirs", "-m", "by hand",
        items.get("013")["commit"])
    d = _free(root, tmp_path)
    al_loop.tick(deps=d, no_push=True)
    assert items.get("013")["state"] == "merged" and keep_refs(root) == ""
    assert "013" not in d.seen["launch"]


@pytest.mark.slow
@pytest.mark.git
def test_legacy_conflict_without_a_ref_gets_one(tmp_path):
    root, items = _conflict_world(tmp_path)
    rec = items.get("013")
    git(root, "update-ref", "-d", "refs/al/keep/013")
    rec.pop("keep_ref")
    items.put(rec)
    d = _free(root, tmp_path)
    al_loop.tick(deps=d, no_push=True)
    assert keep_refs(root) == f"refs/al/keep/013 {rec['commit']}"
    assert d.seen["launch"] == ["013"] and items.get("013")["kind"] == "resolve"


@pytest.mark.git
def test_resolve_lane_with_conflict_markers_left_fails_review(tmp_path):
    root, wt = git_world(tmp_path)
    (wt / "feature.txt").write_text("<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> abc\n")
    t = al_loop.Tick(deps(root, git=real_git))
    rec = {"id": "012", "kind": "resolve", "base_kind": "plan"}
    out = t.extra_checks(rec, wt)
    assert len(out) == 1 and "feature.txt" in out[0] and "conflict marker" in out[0]
    (wt / "feature.txt").write_text("x\ny\n")
    assert t.extra_checks(rec, wt) == []


def test_paused_resolve_gives_its_run_back(tmp_path):
    root = make_root(tmp_path)
    items = _dispatched(root, kind="resolve", base_kind="plan", resolve_runs=1,
                        keep_ref="refs/al/keep/012")
    (root / "ops/loop/control").mkdir(parents=True, exist_ok=True)
    (root / "ops/loop/control/HALT").write_text("")

    def ran_past_halt(*a, **k):  # plan 150: never the real al_lane.run_lane
        pytest.fail("lane_worker ran a lane past HALT")
    assert al_loop.lane_worker("012", deps=deps(root), run_lane=ran_past_halt) == 0
    rec = items.get("012")
    assert rec["state"] == "paused" and rec["resolve_runs"] == 0


# ---------------------------------------------------------------- fix-loop-stall: refused commits

def _refusing_git(wt, refuse):
    """real_git, but `commit` in the lane worktree is refused (a pre-commit hook)
    while refuse["on"] holds."""
    def g(args, cwd, input=None):
        if args[:1] == ["commit"] and Path(cwd) == Path(wt) and refuse["on"]:
            return subprocess.CompletedProcess(args, 1, "", "[leak-sweep] HALT t.py:1 drive-path")
        return real_git(args, cwd, input=input)
    return g


def _passing(n=1):
    return FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}] * n)


@pytest.mark.git
def test_main_hook_refused_merge_is_parked_without_resolve_runs(tmp_path):
    # a real leak main's hook refuses no longer burns MAX_ATTEMPTS blind resolve
    # runs: the merge is clean, so a resolve run could only be refused again
    root, wt = git_world(tmp_path)

    def g(args, cwd, input=None):
        if args[:1] == ["commit"] and Path(cwd) == Path(root):
            return subprocess.CompletedProcess(args, 1, "", "[leak-sweep] HALT t.py:1 email")
        return real_git(args, cwd, input=input)
    lanes = lambda: [{"index": i, "state": "RUNNING", "lane": n}  # noqa: E731
                     for i, n in enumerate(("build", "data", "review"))]
    d = deps(root, spawn=_passing(), git=g, lane_state=lanes)
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "merge-refused" and "leak-sweep" in rec["error"]
    assert keep_refs(root) == f"refs/al/keep/012 {rec['commit']}"
    assert not (root / "feature.txt").exists()  # never merged
    assert git(root, "status", "--porcelain") == ""  # merge aborted
    assert not al_loop.dispatchable(rec)
    d = deps(root, spawn=_passing(), git=g, lane_state=lanes)
    al_loop.tick(deps=d, no_push=True)
    assert "012" not in d.seen["launch"]
    assert al_loop.Items(root).get("012")["state"] == "merge-refused"


@pytest.mark.slow
@pytest.mark.git
def test_pre_fix_failed_dirty_record_is_retried(tmp_path):
    # backfill: the 031 shape - failed-dirty, verdict PASS, work staged, no counters
    root, wt = git_world(tmp_path)
    git(wt, "add", "-A")
    rec = al_loop.Items(root).get("012")
    rec.update(state="failed-dirty", verdict="PASS", error=None)
    al_loop.Items(root).put(rec)
    d = deps(root, git=real_git, lane_state=lambda: [
        {"index": i, "state": "RUNNING", "lane": n}
        for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "merged" and (root / "feature.txt").exists()
    assert "refute-rounds: 0/3" in git(root, "log", "-1", "--format=%B", rec["commit"])


@pytest.mark.slow
@pytest.mark.git
def test_refused_commit_of_red_work_is_kept_unmerged_and_frees_the_lane(tmp_path):
    root, wt = git_world(tmp_path)
    d = deps(root, git=_refusing_git(wt, {"on": True}), gates=lambda cwd: (False, "red"),
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "failed" and rec["keep_ref"] == "refs/al/keep/012"
    assert keep_refs(root) == f"refs/al/keep/012 {rec['commit']}"
    assert git(wt, "status", "--porcelain") == ""  # lane index usable again
    assert git(root, "show", f"{rec['commit']}:feature.txt") == "work"
    assert "commit refused" in git(root, "log", "-1", "--format=%B", rec["commit"])
    assert not (root / "feature.txt").exists()  # never merged
    al_loop.tick(deps=d, no_push=True)  # idempotent
    assert al_loop.Items(root).get("012")["state"] == "failed"


@pytest.mark.slow
@pytest.mark.git
def test_dirty_failed_dirty_lane_zero_no_longer_wedges_dispatch(tmp_path):
    # the stall: lane-0 held a failed-dirty item's staged work, the kit claims
    # the lowest index, so free_lanes() gave 0 slots and every tick read idle
    root, wt = dirty_lane_world(tmp_path, index=0)
    git(wt, "add", "-A")
    items = al_loop.Items(root)
    items.put({"id": "099", "kind": "plan", "state": "failed-dirty", "verdict": "PASS",
               "title": "t", "label": "plan 099: t", "lane": "build", "rc": 0,
               "worktree": str(wt), "rounds": 0})
    d = deps(root, git=real_git, lane_worktree=lambda i: lane_wt(tmp_path, i))
    al_loop.tick(deps=d, no_push=True)
    assert items.get("099")["state"] == "merged"
    assert d.seen["launch"] == ["012"]


# ---------------------------------------------------------------- plan 098: detached review worker

def _recorder(seen, key, pid=5150):
    def launch(*args):
        seen.setdefault(key, []).append(args[0] if args else None)
        return pid
    return launch


def _all_running():
    return [{"index": i, "state": "RUNNING", "lane": n}
            for i, n in enumerate(("build", "data", "review"))]


@pytest.mark.git
def test_tick_launches_a_review_worker_and_runs_no_gate_or_spawn(tmp_path):
    root, wt = git_world(tmp_path)
    seen, gated = {}, []
    sp = FakeSpawn()
    d = deps(root, spawn=sp, git=real_git, lane_state=_all_running,
             gates=lambda cwd: gated.append(cwd) or (True, "green"),
             launch_review=_recorder(seen, "review"))
    doc = al_loop.tick(deps=d, no_push=True)
    assert seen["review"] == ["012"] and gated == [] and sp.calls == []
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "ran" and rec["review_launch"]
    assert any(r["id"] == "012" and r["state"] == "reviewing" for r in doc["checklist"])
    assert isinstance(doc["tick_s"], (int, float))
    al_loop.tick(deps=d, no_push=True)  # worker in flight (startup grace): no relaunch
    assert seen["review"] == ["012"]


@pytest.mark.git
def test_two_finished_items_are_reviewed_in_parallel(tmp_path):
    root, wt = git_world(tmp_path)
    al_loop.Items(root).put({"id": "013", "kind": "plan", "title": "t", "label": "plan 013: t",
                             "state": "committed", "worktree": str(wt), "commit": "abc",
                             "lane": "data", "rounds": 0})
    seen = {}
    d = deps(root, git=real_git, lane_state=_all_running, launch_review=_recorder(seen, "review"))
    al_loop.tick(deps=d, no_push=True)
    assert sorted(seen["review"]) == ["012", "013"]


@pytest.mark.git
def test_ran_item_waits_while_spawning_is_blocked(tmp_path):
    root, wt = git_world(tmp_path)
    al_loop.backoff_hit(root, 1_790_000_000.0, "usage limit")
    seen = {}
    d = deps(root, git=real_git, lane_state=_all_running, launch_review=_recorder(seen, "review"))
    al_loop.tick(deps=d, no_push=True)
    assert "review" not in seen and "review_launch" not in al_loop.Items(root).get("012")


@pytest.mark.git
def test_dead_review_worker_is_relaunched_then_parked_at_the_cap(tmp_path):
    root, wt = git_world(tmp_path)
    items = al_loop.Items(root)
    rec = items.get("012")
    rec.update(review_launch=al_loop.iso(1_790_000_000.0), worker_pid=999)
    items.put(rec)
    seen = {}
    d = deps(root, git=real_git, lane_state=_all_running, pid_alive=lambda pid: pid != 999,
             launch_review=_recorder(seen, "review"))
    al_loop.tick(deps=d, no_push=True)
    rec = items.get("012")
    assert seen["review"] == ["012"] and rec["review_crashes"] == 1
    assert "worker_pid" not in rec
    rec["worker_pid"] = 999  # the relaunched worker died too
    items.put(rec)
    al_loop.tick(deps=d, no_push=True)
    rec = items.get("012")
    assert seen["review"] == ["012"] and rec["review_crashes"] == al_loop.MAX_ATTEMPTS
    # parked: retry_refused salvages the dirty worktree as an unmerged WIP
    assert rec["state"] in ("failed-dirty", "failed") and "review worker" in rec["error"]
    assert "review_launch" not in rec


@pytest.mark.git
def test_review_worker_that_never_started_counts_as_a_crash(tmp_path):
    root, wt = git_world(tmp_path)
    items = al_loop.Items(root)
    rec = items.get("012")
    rec["review_launch"] = al_loop.iso(1_790_000_000.0 - al_loop.REVIEW_START_S - 1)
    items.put(rec)
    seen = {}
    d = deps(root, git=real_git, lane_state=_all_running, launch_review=_recorder(seen, "review"))
    al_loop.tick(deps=d, no_push=True)
    assert seen["review"] == ["012"] and items.get("012")["review_crashes"] == 1


@pytest.mark.git
def test_review_worker_processes_its_item_and_clears_its_markers(tmp_path):
    root, wt = git_world(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}])
    d = deps(root, spawn=sp, git=real_git, lane_state=_all_running)
    assert al_loop.review_worker("012", deps=d) == 0
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "merged" and "worker_pid" not in rec and "review_launch" not in rec
    assert any("merged" in line for line in rec["review_log"])
    assert "loop-review" in d.seen["record"]
    assert al_loop.review_worker("012", deps=d) == 0  # not ran / committed: no-op
    assert len(sp.calls) == 1


@pytest.mark.git
def test_review_worker_refuses_an_item_another_live_worker_holds(tmp_path):
    root, wt = git_world(tmp_path)
    items = al_loop.Items(root)
    rec = items.get("012")
    rec["worker_pid"] = os.getpid() + 1
    items.put(rec)
    sp = FakeSpawn()
    d = deps(root, spawn=sp, git=real_git, pid_alive=lambda pid: True)
    assert al_loop.review_worker("012", deps=d) == 0
    assert sp.calls == [] and items.get("012")["worker_pid"] == os.getpid() + 1


@pytest.mark.git
def test_busy_merge_lock_defers_the_merge(tmp_path):
    root, wt = git_world(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}])
    real_lock = al_loop._load_watch().watch_lock

    @contextlib.contextmanager
    def lock(path):
        if Path(path).name == "merge.lock":
            raise d.watch.LockBusy("held")
        with real_lock(path):
            yield

    d = deps(root, spawn=sp, git=real_git, lane_state=_all_running, lock=lock)
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "committed" and not (root / "feature.txt").exists()
    d.lock = real_lock
    al_loop.tick(deps=d, no_push=True)
    assert al_loop.Items(root).get("012")["state"] == "merged"


def test_tick_launches_one_push_worker_when_main_is_ahead(tmp_path):
    root = make_root(tmp_path, roadmap="", handoff="", local={"loop_push": True})
    seen = {}
    gated = []
    d = deps(root, git=FakeGit(), launch_push=_recorder(seen, "push"),
             gates=lambda cwd: gated.append(cwd) or (True, "green"))
    al_loop.tick(deps=d)
    assert seen["push"] == [None] and gated == []  # the tick never gates main
    al_loop.tick(deps=d)  # launched, not started yet: no second worker
    assert seen["push"] == [None]
    for kw, g in (({"no_push": True}, FakeGit()), ({}, FakeGit(ahead="0"))):
        (root / al_loop.PUSH_WORKER_REL).unlink(missing_ok=True)
        seen.clear()
        al_loop.tick(deps=deps(root, git=g, launch_push=_recorder(seen, "push")), **kw)
        assert "push" not in seen


def test_launch_review_and_push_argv(tmp_path):
    argvs = []

    class P:
        pid = 9

    def popen(argv, creationflags=0, **kw):
        argvs.append(argv)
        return P()

    assert al_loop._launch(tmp_path, "012", popen=popen, cmd="review") == 9
    assert al_loop._launch(tmp_path, None, popen=popen, cmd="push") == 9
    assert argvs[0][-2:] == ["review", "012"] and argvs[1][-1] == "push"
