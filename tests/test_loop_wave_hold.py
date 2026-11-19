"""LOOP-WAVE-HOLD (F-033, AUTO-06): a loop merge whose diff touches a folder
a session's wave holds (ops/loop/control/wave_owned.json) parks as
wave-hold and merges once the hold file is gone; a hold file older than 48 h
is one checklist row and is not obeyed; `python tools/loop_merge.py hold --
<command>` runs a wave merge agent's command under the loop's merge lock."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402
import loop_base  # noqa: E402
import loop_merge  # noqa: E402

from al_loopkit import FakeSpawn, deps, git, isolate_git, make_root, real_git  # noqa: E402

A, B = "GRIND-012", "SEASON-013"
RM = f"""# AshLight roadmap

- [x] SKEL Skeleton -- done 2026-10-04
- [ ] {A} Grind spot recommender
- [ ] {B} Season pass tracker
"""
NOW = 1_790_000_000.0  # the al_loopkit deps clock


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)  # TESTS-A-19


def _running():
    return [{"index": i, "state": "RUNNING", "lane": n}
            for i, n in enumerate(("build", "data", "review"))]


def _passing(n=1):
    return FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}] * n)


def _world(tmp_path):
    """One finished lane for row A whose work is src/feature.txt."""
    root = make_root(tmp_path, roadmap=RM, handoff="")
    git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("ops/\n", newline="\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    wt = tmp_path / "al-worktrees" / "lane-1"
    git(root, "worktree", "add", "-q", "--detach", str(wt))
    (wt / "src").mkdir()
    (wt / "src" / "feature.txt").write_text("work\n", newline="\n")
    al_loop.Items(root).put({"id": A, "kind": "plan", "title": "Grind spot recommender",
                             "label": f"plan {A}: Grind spot recommender", "state": "ran",
                             "worktree": str(wt), "rc": 0, "lane": "build", "rounds": 0})
    return root, wt


def _hold(root, prefixes, age_s, wave=4):
    p = root / al_loop.CONTROL_REL / "wave_owned.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"wave": wave, "prefixes": prefixes,
                             "time": al_loop.iso(NOW - age_s)}), newline="\n")
    return p


def _checklist(root, d):
    doc = json.loads((root / d.kit.PROGRESS_REL / "loop.json").read_text(encoding="utf-8"))
    return doc["checklist"]


@pytest.mark.git
def test_diff_in_a_held_prefix_parks_as_wave_hold_then_merges(tmp_path):
    root, wt = _world(tmp_path)
    hold = _hold(root, ["src/", "server/al"], age_s=3600)
    head0 = git(root, "rev-parse", "main")
    sp = _passing(2)
    d = deps(root, spawn=sp, git=real_git, lane_state=_running)
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get(A)
    assert rec["state"] == "wave-hold" and rec["commit"]
    assert rec["wave_hold"] == {"wave": 4, "paths": ["src/feature.txt"]}
    assert git(root, "rev-parse", "main") == head0  # main did not move
    assert not (root / "docs" / "roadmap" / "done" / f"{A}.md").exists()
    rows = {r["id"]: r for r in _checklist(root, d)}
    assert rows[A]["state"] == "wave-hold" and rows[A]["eta_s"] == 0
    n_spawn = len(sp.calls)

    al_loop.tick(deps=d, no_push=True)  # still held: parked again, no spawn
    assert al_loop.Items(root).get(A)["state"] == "wave-hold"
    assert git(root, "rev-parse", "main") == head0

    hold.unlink()  # the session ends the wave
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get(A)
    assert rec["state"] == "merged" and "wave_hold" not in rec
    assert git(root, "rev-parse", "main") != head0
    assert (root / "src" / "feature.txt").exists()
    assert len(sp.calls) == n_spawn  # a held item only merges: no verifier rerun


@pytest.mark.git
def test_hold_file_older_than_48_h_is_reported_not_obeyed(tmp_path):
    root, wt = _world(tmp_path)
    _hold(root, ["src"], age_s=49 * 3600, wave=7)
    d = deps(root, spawn=_passing(), git=real_git, lane_state=_running)
    al_loop.tick(deps=d, no_push=True)
    assert al_loop.Items(root).get(A)["state"] == "merged"  # not obeyed
    notice = al_loop.Items(root).get(loop_base.WAVE_HOLD_NOTICE_ID)
    assert notice["state"] == "wave-hold-stale"
    assert notice["title"] == "Remove stale wave 7 hold file (49 h old), not obeyed"
    al_loop.tick(deps=d, no_push=True)  # the row is printed every tick
    rows = [r for r in _checklist(root, d) if r["id"] == loop_base.WAVE_HOLD_NOTICE_ID]
    assert len(rows) == 1 and rows[0]["state"] == "wave-hold-stale"
    assert "not obeyed" in rows[0]["task"] and rows[0]["eta_s"] == 0
    # a hold with no readable time cannot be aged: reported, not obeyed
    (root / al_loop.CONTROL_REL / "wave_owned.json").write_text(
        json.dumps({"wave": 7, "prefixes": ["src"]}), newline="\n")
    h = loop_merge.read_wave_hold(root, NOW)
    assert h["stale"] and h["why"] == "no readable time"
    # just under 48 h is still obeyed; a missing file is no hold
    _hold(root, ["src"], age_s=47 * 3600)
    assert loop_merge.read_wave_hold(root, NOW)["stale"] is False
    (root / al_loop.CONTROL_REL / "wave_owned.json").unlink()
    assert loop_merge.read_wave_hold(root, NOW) is None
    # the next merge that finds no stale file drops the row
    t = al_loop.Tick(d)
    t.wave_hold_notice(None)
    assert al_loop.Items(root).get(loop_base.WAVE_HOLD_NOTICE_ID) is None
    assert loop_merge.held_names(["src/a.py", "srcx/b.py", "src"], ["src"]) == [
        "src/a.py", "src"]


def test_two_holders_of_the_merge_lock_run_one_after_the_other(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    log = tmp_path / "order.log"
    body = ("import sys, time; p, n = sys.argv[1], sys.argv[2]; "
            "open(p, 'a').write('start ' + n + '\\n'); time.sleep(1.5); "
            "open(p, 'a').write('end ' + n + '\\n')")

    def holder(name):
        return subprocess.Popen(
            [sys.executable, str(ROOT / "tools" / "loop_merge.py"), "hold", "--root",
             str(root), "--wait-s", "60", "--poll-s", "0.2", "--",
             sys.executable, "-c", body, str(log), name],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    first = holder("a")
    deadline = time.monotonic() + 30
    while not (log.exists() and "start a" in log.read_text()):
        assert time.monotonic() < deadline and first.poll() is None
        time.sleep(0.05)
    second = holder("b")
    assert first.wait(timeout=60) == 0
    assert second.wait(timeout=60) == 0
    assert log.read_text().splitlines() == ["start a", "end a", "start b", "end b"]
    assert not (root / al_loop.MERGE_LOCK_REL).exists()

    # a lock still busy past --wait-s: exit 3, the command never runs
    class Busy(Exception):
        pass

    def busy_lock(path):
        raise Busy("held by live pid 1")

    clock = iter(range(0, 100, 10))
    ran = []
    rc = loop_merge.hold(["x"], root, wait_s=30, poll_s=1, lock=busy_lock, busy=Busy,
                         run=lambda c: ran.append(c) or 0, sleep=lambda s: None,
                         clock=lambda: next(clock))
    assert rc == 3 and ran == []
    assert loop_merge.main(["hold", "--root", str(root)]) == 2  # no `--`


def test_wave_hold_record_is_relaunched_by_finished(tmp_path):
    assert "wave-hold" in al_loop.HOLD_STATES and "wave-hold" in al_loop.IN_FLIGHT
    root = make_root(tmp_path, roadmap=RM, handoff="")
    launched = []
    d = deps(root, launch_review=lambda iid: launched.append(iid) or 4243)
    items = al_loop.Items(root)
    items.put({"id": A, "kind": "plan", "title": "t", "state": "wave-hold",
               "worktree": str(tmp_path / "wt"), "commit": "abc", "lane": "build"})
    items.put({"id": B, "kind": "plan", "title": "t", "state": "merged"})
    al_loop.Tick(d).finished()
    assert launched == [A]
    rec = items.get(A)
    assert rec["state"] == "wave-hold" and rec["review_launch"]
    # the worker's process() routes a wave-hold record to merge, like committed
    called = []
    t = al_loop.Tick(d)
    t.merge = lambda r: called.append(r["id"])
    t.process(dict(rec))
    assert called == [A]
