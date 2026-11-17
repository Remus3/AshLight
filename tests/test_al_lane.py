import contextlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_lane  # noqa: E402


def test_roster_and_cap():
    assert al_lane.LANES == ("build", "data", "review") and al_lane.lane_cap() == 3
    with pytest.raises(SystemExit):
        al_lane.check_lane("rogue")


def test_suite_pins_fleet_sidecar_root_off():
    """Kit v14 3.4: the suite never depends on the machine FLEET_SIDECAR_ROOT."""
    import os
    assert os.environ.get("FLEET_SIDECAR_ROOT") == ""


def test_kit_worktree_layout_is_per_lane_index(tmp_path):
    fl = al_lane.lanes()
    assert fl.LANE_CAP_MAX == 3
    paths = {fl.worktree_path(ROOT, "AL", i) for i in range(3)}
    assert len(paths) == 3
    assert all(p.parent.name == "al-worktrees" for p in paths)


def test_seed_config_copies_missing_only(tmp_path):
    root, wt = tmp_path / "repo", tmp_path / "wt"
    (root / "config").mkdir(parents=True)
    (root / "config" / "local.json").write_text("{}")
    assert al_lane.seed_config(wt, root) == ["config/local.json"]
    assert al_lane.seed_config(wt, root) == []


def _fakes(tmp_path, rc=0):
    seen = {"progress": [], "spawn": [], "lane": [], "record": []}
    wt = tmp_path / "al-worktrees" / "lane-1"

    @contextlib.contextmanager
    def lane_ctx(root, code, name, run_id, cap):
        seen["lane"].append((code, name, run_id, cap))
        yield {"worktree": wt, "index": 1}

    def spawn(root, code, prompt, **kw):
        seen["spawn"].append((code, kw))
        return {"rc": rc, "error": None}

    def progress(root, task, pct, step, eta_s, status):
        seen["progress"].append((task, pct, status))
        seen.setdefault("progress_root", []).append(root)
        seen.setdefault("step", []).append(step)

    def record(kind, secs, ok=True):
        seen["record"].append((kind, ok))

    return seen, wt, dict(lane_ctx=lane_ctx, spawn=spawn, progress=progress, record=record)


def test_run_lane_claims_lane_one_governor_slot_at_spawn(tmp_path):
    seen, wt, f = _fakes(tmp_path)
    line = al_lane.run_lane("data", "do x", root=tmp_path, **f)
    assert line["rc"] == 0 and line["worktree"] == str(wt)
    assert seen["lane"] == [("AL", "data", "lane-data", 3)]
    code, kw = seen["spawn"][0]
    assert code == "AL" and kw["cwd"] == wt and kw["governor"] == "queued"
    assert kw["kind"] == "build"
    # kit v18: lanes label the usage row's slot and hand the progress row over
    assert kw["slot_id"] == "data" and kw["progress_task"] == "lane-1"
    assert seen["record"] == [("lane-data-read", True)]
    assert seen["progress"] == [("lane-1", al_lane.PCT_START, "running"),
                                ("lane-1", 100, "done")]
    assert all(s.startswith("data: ") for s in seen["step"])


def test_progress_file_is_lane_index_in_main_tree(tmp_path):
    # FLEET item 13 d: progress/lane-<i>.json (i = lane-lock index) in the MAIN
    # checkout, even when root is a linked worktree.
    main = tmp_path / "main"
    (main / ".git" / "worktrees" / "lane-1").mkdir(parents=True)
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / ".git").write_text(f"gitdir: {main / '.git' / 'worktrees' / 'lane-1'}\n")
    seen, _, f = _fakes(tmp_path)
    al_lane.run_lane("build", "x", root=linked, **f)
    assert {Path(r).resolve() for r in seen["progress_root"]} == {main.resolve()}
    assert al_lane.progress_task(2) == "lane-2"
    with pytest.raises(ValueError):
        al_lane.progress_task(10)


def test_refused_claim_writes_no_progress(tmp_path):
    seen, _, f = _fakes(tmp_path)

    @contextlib.contextmanager
    def refused(root, code, name, run_id, cap):
        raise RuntimeError("lanes_full")
        yield

    with pytest.raises(RuntimeError):
        al_lane.run_lane("data", "x", root=tmp_path, **dict(f, lane_ctx=refused))
    assert seen["progress"] == [] and seen["record"] == [("lane-data-read", False)]


def test_failed_run_marks_failed(tmp_path):
    seen, _, f = _fakes(tmp_path, rc=1)
    al_lane.run_lane("build", "x", writes_code=True, root=tmp_path, **f)
    assert seen["record"] == [("lane-build-code", False)]
    assert seen["progress"][-1][2] == "failed"


def test_dry_run_spawns_nothing(tmp_path):
    seen, _, f = _fakes(tmp_path)
    out = al_lane.run_lane("review", "x", dry_run=True, root=tmp_path, **f)
    assert out["dry_run"] and seen["spawn"] == [] and seen["lane"] == []
    assert seen["progress"] == []


def test_code_lane_runs_accept_edits_read_lane_does_not(tmp_path):
    seen, _, f = _fakes(tmp_path)
    al_lane.run_lane("build", "do x", writes_code=True, root=tmp_path, **f)
    al_lane.run_lane("review", "look", root=tmp_path, **f)
    extra = seen["spawn"][0][1]["extra"]
    assert extra[:2] == ("--permission-mode", "acceptEdits")
    assert "Bash(python -m pytest:*)" in extra[3]
    # plan 163: git add / status / diff only; the loop commits, merges and pushes
    tools = extra[3].split(",")
    git = sorted(t for t in tools if t.startswith("Bash(git"))
    assert git == ["Bash(git add:*)", "Bash(git diff:*)", "Bash(git status:*)"]
    assert seen["spawn"][1][1]["extra"] == ()


def test_item_kind_records_its_own_eta_row(tmp_path):
    # session 29: one lane mixes plan (~15 m) and resolve (~4 m) items, so the
    # loop worker passes the item kind; the run records under both kinds.
    seen, _, f = _fakes(tmp_path)
    al_lane.run_lane("build", "x", writes_code=True, root=tmp_path,
                     eta_kind="item-plan", **f)
    assert seen["record"] == [("lane-build-code", True), ("item-plan", True)]


# ---------------------------------------------------------------- LANE-CHECKLIST

def _kw_progress(seen):
    def progress(root, task, pct, step, eta_s, status, **kw):
        seen.append(dict(kw, task=task, pct=pct, eta_s=eta_s, status=status))
    return progress


def test_lane_eta_has_a_floor_and_uses_history(tmp_path, monkeypatch):
    log = tmp_path / "t.jsonl"
    monkeypatch.setattr(al_lane.eta, "LOG", log)
    assert al_lane.lane_eta(True, "lane-build-code") == 900.0  # default 416 floored
    assert al_lane.lane_eta(False, "lane-review-read") == 300.0
    for s in (1500, 1600, 1700):
        al_lane.eta.record("lane-build-code", s, log=log)
    assert al_lane.lane_eta(True, "lane-build-code") == 1600.0
    # an item kind without history falls back to the lane history
    assert al_lane.lane_eta(True, "lane-build-code", "item-plan") == 1600.0
    al_lane.eta.record("item-resolve", 200, log=log)
    assert al_lane.lane_eta(True, "lane-build-code", "item-resolve") == 900.0


def test_running_pct_and_remaining_are_bounded():
    assert al_lane.running_pct(0, 900) == al_lane.PCT_START
    assert al_lane.running_pct(450, 900) == 50
    assert al_lane.running_pct(5000, 900) == al_lane.PCT_CAP < 100
    assert al_lane.remaining_s(100, 900) == 800
    assert al_lane.remaining_s(5000, 900) == al_lane.REMAIN_MIN_S


def test_checklist_reaches_every_progress_write(tmp_path):
    _, _, f = _fakes(tmp_path)
    writes = []
    rows = [{"id": "LANE-CHECKLIST", "task": "fix lane progress", "state": "running",
             "eta_s": None}, {"id": "OPS-OVL-PID", "task": "pid", "state": "queued",
                              "eta_s": 60}]
    al_lane.run_lane("build", "x", writes_code=True, root=tmp_path, checklist=rows,
                     **dict(f, progress=_kw_progress(writes)))
    assert [w["status"] for w in writes] == ["running", "done"]
    first = writes[0]
    assert first["eta_s"] >= 900 and first["pct"] == al_lane.PCT_START
    assert [r["id"] for r in first["checklist"]] == ["LANE-CHECKLIST", "OPS-OVL-PID"]
    assert first["checklist"][0]["eta_s"] == first["eta_s"]  # None = live lane ETA
    assert first["checklist"][1]["eta_s"] == 60
    assert writes[-1]["checklist"] == []  # done: nothing of the run remains


def test_failed_run_keeps_its_checklist_rows(tmp_path):
    _, _, f = _fakes(tmp_path, rc=1)
    writes = []
    al_lane.run_lane("build", "x", root=tmp_path,
                     checklist=[{"id": "A", "task": "t", "state": "running", "eta_s": 5}],
                     **dict(f, progress=_kw_progress(writes)))
    assert writes[-1]["status"] == "failed" and writes[-1]["checklist"][0]["id"] == "A"


def test_no_checklist_passes_no_checklist_kwarg(tmp_path):
    seen, _, f = _fakes(tmp_path)  # the fake progress takes no kwargs
    al_lane.run_lane("data", "x", root=tmp_path, **f)
    assert len(seen["progress"]) == 2


def test_bad_checklist_fails_before_the_claim(tmp_path):
    seen, _, f = _fakes(tmp_path)
    with pytest.raises(ValueError):
        al_lane.run_lane("data", "x", root=tmp_path, checklist=[{"id": "", "task": "t"}], **f)
    assert seen["lane"] == [] and seen["spawn"] == []
    assert al_lane.norm_checklist([{"id": "a b/c", "task": " t  u "}])[0] == \
        {"id": "a-b-c", "task": "t u", "state": None, "eta_s": None}


def test_heartbeat_rewrites_while_the_spawn_runs(tmp_path):
    import threading
    _, _, f = _fakes(tmp_path)
    writes = []
    pause = threading.Event()

    def spawn(root, code, prompt, **kw):
        # hold the run until a few heartbeats landed (bounded wait)
        for _ in range(500):
            if sum(1 for w in writes if w["status"] == "running") >= 3:
                break
            pause.wait(0.01)
        return {"rc": 0, "error": None}

    t = {"now": 1000.0}

    def clock():
        t["now"] += 100.0
        return t["now"]

    al_lane.run_lane("build", "x", writes_code=True, root=tmp_path, heartbeat_s=0.01,
                     clock=clock, checklist=[{"id": "A", "task": "t"}],
                     **dict(f, spawn=spawn, progress=_kw_progress(writes)))
    running = [w for w in writes if w["status"] == "running"]
    assert len(running) >= 3 and writes[-1]["status"] == "done"
    assert all(w["status"] == "running" for w in writes[:-1])  # none after the final
    pcts = [w["pct"] for w in running]
    assert pcts == sorted(pcts) and max(pcts) <= al_lane.PCT_CAP
    assert all("checklist" in w for w in running)


def test_heartbeat_write_error_never_breaks_the_run():
    def boom(pct, rem):
        raise OSError("disk")
    al_lane.Heartbeat(boom, lambda: 10.0, 0.0, 900.0, 60).beat()  # suppressed


def test_real_kit_progress_file_carries_checklist(tmp_path):
    import json
    _, _, f = _fakes(tmp_path)
    f.pop("progress")
    seen = []
    real = al_lane.kit().write_progress

    def spy(*a, **kw):
        doc = real(*a, **kw)
        seen.append(doc)
        return doc

    al_lane.run_lane("build", "x", writes_code=True, root=tmp_path, progress=spy,
                     checklist=al_lane.parse_items(["LANE-CHECKLIST: lane rows"]), **f)
    assert seen[0]["checklist"][0]["id"] == "LANE-CHECKLIST"
    assert seen[0]["eta_s"] >= 900 and seen[0]["status"] == "running"
    doc = json.loads((tmp_path / "ops/loop/control/progress/lane-1.json").read_text())
    assert doc["status"] == "done" and doc["checklist"] == []


def test_cli_item_and_checklist_file(tmp_path, monkeypatch):
    import json
    seen = {}

    def fake(lane, prompt, *a, checklist=None, **kw):
        seen["checklist"] = checklist
        return {"rc": 0, "error": None, "worktree": "wt"}

    monkeypatch.setattr(al_lane, "run_lane", fake)
    pf = tmp_path / "p.txt"
    pf.write_text("p")
    cf = tmp_path / "c.json"
    cf.write_text(json.dumps([{"id": "B", "task": "second", "state": "queued", "eta_s": 9}]))
    assert al_lane.main(["run", "build", "--prompt-file", str(pf), "--item", "A: first",
                         "--checklist-file", str(cf)]) == 0
    assert [r["id"] for r in seen["checklist"]] == ["A", "B"]
    assert al_lane.main(["run", "build", "--prompt-file", str(pf), "--item", "nocolon"]) == 64
    with pytest.raises(ValueError):
        al_lane.parse_items(["A:"])
