"""LOOP-TESTS-CARVE: the tools/al_loop.py tests of plan_depends and
blocked-on-dependency records (the plan 019 dependency gate section), moved
from tests/test_al_loop.py. LOOP-ROWFILES-WORK rewrote the dependency tests
to DEPENDS rows: a row waits on the `DEPENDS: <ids>` in its own text (F-029),
plan docs are no longer read, and an unknown id is a visible wait, not a
fail-open dispatch. progress, _lane, _two_lane_world and T0 are copied
unchanged; they stay in tests/test_al_loop.py too."""

import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402
import loop_roadmap  # noqa: E402
import roadmap  # noqa: E402

from al_loopkit import (  # noqa: E402
    GIT_TIMEOUT_S, FakeSpawn, deps, git, git_world, isolate_git, make_root, real_git)


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)  # TESTS-A-19


def progress(root):
    return json.loads((root / "ops/loop/control/progress/loop.json").read_text())


def _lane(root, tmp_path, name, iid, edit):
    wt = tmp_path / "al-worktrees" / name
    git(root, "worktree", "add", "-q", "--detach", str(wt))
    edit(wt)
    al_loop.Items(root).put({"id": iid, "kind": "plan", "title": f"plan {iid}",
                             "label": f"plan {iid}: t", "state": "ran", "worktree": str(wt),
                             "rc": 0, "lane": name, "rounds": 0})
    return wt


def _two_lane_world(tmp_path, edit_a, edit_b):
    root = make_root(tmp_path, handoff="")
    git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("ops/\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    _lane(root, tmp_path, "lane-0", "012", edit_a)
    _lane(root, tmp_path, "lane-1", "013", edit_b)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}] * 2)
    d = deps(root, spawn=sp, git=real_git,
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    return root


# ---------------------------------------------------------------- plan 019: dependency gate

DEP_ROADMAP = """# AshLight roadmap

- [x] 001 Skeleton -- done 2026-10-04
- [ ] 012 Grind spot recommender
- [ ] 013 Season pass tracker
- [ ] 014 Coupon check
"""

T0 = 1_790_000_000.0
ALL_RUNNING = [{"index": i, "state": "RUNNING", "lane": n}
               for i, n in enumerate(("build", "data", "review"))]


def with_depends(text, deps_of):
    """ROADMAP text with a `  DEPENDS: <line>` continuation line under the row
    of each id in deps_of (None: no line)."""
    out = []
    for line in text.split("\n"):
        out.append(line)
        m = al_loop.ROW_RX.match(line)
        if m and deps_of.get(m.group(2)) is not None:
            out.append(f"  DEPENDS: {deps_of[m.group(2)]}")
    return "\n".join(out)


def dep_root(tmp_path, deps_of, roadmap=DEP_ROADMAP):
    """make_root with a DEPENDS: line in the row of each id in deps_of."""
    return make_root(tmp_path, roadmap=with_depends(roadmap, deps_of), handoff="")


def test_plan_depends_parser():
    assert al_loop.plan_depends("# Plan 1\n\nDepends on: none.\n") == []
    assert al_loop.plan_depends("Depends on: 021.\n") == ["021"]
    assert al_loop.plan_depends("x\nDepends on: 035, 028.\n") == ["035", "028"]
    assert al_loop.plan_depends("Depends on: 027 (net proceeds) and 031\n") == ["027", "031"]
    assert al_loop.plan_depends("# Plan 2\nno such line, mentions 027\n") == []
    # only the first matching line, only at a line start
    assert al_loop.plan_depends("carry `Depends on:` 010\nDepends on: 022.\n"
                                "Depends on: 023.\n") == ["022"]
    assert al_loop.plan_depends("Depends on: 1234, 12, 05x\n") == []


@pytest.mark.git
def test_work_list_skips_rows_waiting_on_open_dependencies(tmp_path):
    root = dep_root(tmp_path, {"012": "013.", "013": "none.", "014": "001."})
    d = deps(root)
    rows, work, skipped = al_loop.Tick(d).work_list()
    assert [w["id"] for w in work] == ["013", "014"]
    wait = next(s for s in skipped if s["id"] == "012")
    assert wait["reason"] == "waits on 013"
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["013", "014"]
    row = next(r for r in progress(root)["checklist"] if r["id"] == "012")
    assert row["state"] == "waits on 013"
    assert al_loop.render_checklist(progress(root)).count(" 012: ") == 1


@pytest.mark.git
def test_done_dependency_dispatches_and_priority_stays_first(tmp_path):
    rm = DEP_ROADMAP.replace("- [ ] 013 Season pass tracker",
                             "- [x] 013 Season pass tracker -- done")
    rm = rm.replace("- [ ] 014 Coupon check",
                    "- [ ] 014 Coupon check (priority)")
    root = dep_root(tmp_path, {"012": "013.", "014": "001."}, roadmap=rm)
    d = deps(root)
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["014", "012"]


@pytest.mark.git
def test_dependency_cycle_leaves_both_skipped_and_is_logged(tmp_path):
    root = dep_root(tmp_path, {"012": "013.", "013": "012.", "014": "none."})
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["014"]
    assert any("dependency cycle" in s for s in doc["log"])


@pytest.mark.git
def test_unknown_dependency_waits_and_a_plan_doc_gates_nothing(tmp_path):
    root = dep_root(tmp_path, {"012": "077.", "014": "none."})  # 013 has no line
    # a legacy plan doc's Depends-on line is no longer read (F-029)
    (root / "docs" / "plans").mkdir()
    (root / "docs" / "plans" / "013-x.md").write_text("Depends on: 012.\n", newline="\n")
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["013", "014"]
    row = next(r for r in doc["checklist"] if r["id"] == "012")
    assert row["state"] == "waits on 077 (no such row)"
    assert not any("no ROADMAP row" in s for s in doc["log"])


# -- 4a blocked markers

def blocked_world(tmp_path, dispatched=T0 - 600):
    root, wt = git_world(tmp_path)
    (wt / "feature.txt").unlink()  # a clean worktree: the lane changed nothing
    items = al_loop.Items(root)
    rec = items.get("012")
    rec["dispatched"] = al_loop.iso(dispatched)
    items.put(rec)
    return root, wt


def marker(tree, updated, status="blocked", needs=("013",)):
    p = Path(tree) / "ops/loop/control/progress/p012-build.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"task": "p012-build", "status": status, "updated": updated}
    if needs is not None:
        doc["needs"] = list(needs)
    p.write_text(json.dumps(doc))


def finish(root):
    d = deps(root, git=real_git, lane_state=lambda: ALL_RUNNING)
    doc = al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    # plan 098: the review worker's steps land in the record, not the tick log
    doc["log"] = doc["log"] + rec.get("review_log", [])
    return rec, doc


@pytest.mark.git
def test_fresh_blocked_marker_sets_blocked_not_no_change(tmp_path):
    root, wt = blocked_world(tmp_path)
    marker(wt, al_loop.iso(T0 - 60))
    rec, doc = finish(root)
    assert rec["state"] == "blocked" and rec["needs"] == ["013"] and rec["blocked_runs"] == 1
    assert "012: blocked on 013" in doc["log"]
    row = next(r for r in doc["checklist"] if r["id"] == "012")
    assert row["state"] == "blocked on 013"


@pytest.mark.git
def test_stale_marker_in_a_reused_worktree_is_plain_no_change(tmp_path):
    root, wt = blocked_world(tmp_path)
    marker(wt, al_loop.iso(T0 - 7200))
    rec, doc = finish(root)
    assert rec["state"] == "no-change" and "blocked_runs" not in rec
    assert "012: stale blocked marker ignored" in doc["log"]


@pytest.mark.git
def test_worktree_marker_is_preferred_over_main_checkout(tmp_path):
    root, wt = blocked_world(tmp_path)
    marker(wt, al_loop.iso(T0 - 60), needs=("013",))
    marker(root, al_loop.iso(T0 - 60), needs=("014",))
    rec, _ = finish(root)
    assert rec["needs"] == ["013"]
    root2, _ = blocked_world(tmp_path / "b")
    marker(root2, al_loop.iso(T0 - 60), needs=("014",))
    rec2, _ = finish(root2)
    assert rec2["state"] == "blocked" and rec2["needs"] == ["014"]


@pytest.mark.slow
@pytest.mark.git
def test_malformed_markers_are_plain_no_change_with_a_step_line(tmp_path):
    cases = [{"updated": al_loop.iso(T0 - 60), "needs": None},
             {"updated": al_loop.iso(T0 - 60), "needs": ("13", "abc")},
             {"updated": al_loop.iso(T0 - 60), "needs": ()},
             {"updated": "yesterday", "needs": ("013",)}]
    for i, kw in enumerate(cases):
        root, wt = blocked_world(tmp_path / str(i))
        marker(wt, **kw)
        rec, doc = finish(root)
        assert rec["state"] == "no-change", kw
        assert any(s.startswith("012: malformed blocked marker") for s in doc["log"]), kw
    root, wt = blocked_world(tmp_path / "done")
    marker(wt, al_loop.iso(T0 - 60), status="done")
    rec, doc = finish(root)
    assert rec["state"] == "no-change" and not any("marker" in s for s in doc["log"])


# -- 4b blocked dispatch

def test_blocked_dispatchable_only_once_needs_are_done():
    rec = {"state": "blocked", "needs": ["013"], "blocked_runs": 1}
    assert not al_loop.dispatchable(rec, {"013"})
    assert al_loop.dispatchable(rec, set())
    assert al_loop.dispatchable(rec, {"099"})
    assert not al_loop.dispatchable(dict(rec, blocked_runs=al_loop.MAX_ATTEMPTS), set())
    assert "blocked" not in al_loop.DONE_STATES


@pytest.mark.git
def test_blocked_record_waits_then_redispatches_after_need_flips(tmp_path):
    root = dep_root(tmp_path, {"012": "none."}, roadmap=DEP_ROADMAP.replace(
        "- [ ] 014 Coupon check\n", ""))
    al_loop.Items(root).put({"id": "012", "kind": "plan", "state": "blocked", "needs": ["013"],
                             "blocked_runs": 1, "attempts": 1,
                             "title": "Grind spot recommender", "label": "l"})
    d = deps(root, lane_state=lambda: ALL_RUNNING[:1])
    doc = al_loop.tick(deps=d, no_push=True)
    assert "012" not in d.seen["launch"]
    assert next(r for r in doc["checklist"] if r["id"] == "012")["state"] == "blocked on 013"
    rm = root / "ROADMAP.md"
    rm.write_text(al_loop.flip_roadmap(rm.read_text(), "013", "done"), newline="\n")
    (al_loop.Items(root).dir / "013.json").unlink()
    d = deps(root)
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["012"]
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "dispatched" and rec["blocked_runs"] == 1 and rec["attempts"] == 2


@pytest.mark.git
def test_blocked_runs_cap_becomes_gave_up(tmp_path):
    root = dep_root(tmp_path, {"012": "none."})
    al_loop.Items(root).put({"id": "012", "kind": "plan", "state": "blocked", "needs": ["013"],
                             "blocked_runs": al_loop.MAX_ATTEMPTS, "attempts": 2,
                             "title": "Grind spot recommender", "label": "l"})
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "gave-up" and rec["error"] == "blocked 2 times on 013"
    assert "012" not in d.seen["launch"]
    assert next(r for r in doc["checklist"] if r["id"] == "012")["state"] == "gave-up"


# -- 4c re-arm

def rearm_world(tmp_path, dep_merged_at, dep_row_done=True, own_deps="013."):
    rm = DEP_ROADMAP.replace("- [ ] 014 Coupon check\n", "")
    if dep_row_done:
        rm = rm.replace("- [ ] 013 Season pass tracker",
                        "- [x] 013 Season pass tracker -- done")
    root = dep_root(tmp_path, {"012": own_deps}, roadmap=rm)
    items = al_loop.Items(root)
    items.put({"id": "012", "kind": "plan", "state": "no-change", "attempts": 1,
               "dispatched": al_loop.iso(T0 - 3600), "title": "Grind spot recommender",
               "label": "l"})
    if dep_merged_at is not None:
        items.put({"id": "013", "kind": "plan", "state": "merged", "title": "t", "label": "l",
                   "merged_at": al_loop.iso(dep_merged_at)})
    return root, items


@pytest.mark.git
def test_no_change_rearms_once_when_dependency_flipped_after_dispatch(tmp_path):
    root, items = rearm_world(tmp_path, T0 - 1800)
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["012"]
    assert any("012: re-armed" in s for s in doc["log"])
    rec = items.get("012")
    assert rec["rearmed"] is True and rec["state"] == "dispatched"
    rec.update(state="no-change", pid=None)  # the re-run changed nothing either
    items.put(rec)
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"].count("012") == 1 and items.get("012")["state"] == "no-change"


@pytest.mark.git
def test_no_change_with_dependencies_done_before_dispatch_stays(tmp_path):
    root, items = rearm_world(tmp_path, T0 - 7200)
    d = deps(root)
    for _ in range(3):
        al_loop.tick(deps=d, no_push=True)
    rec = items.get("012")
    assert "012" not in d.seen["launch"] and rec["state"] == "no-change"
    assert rec["rearmed"] is False


@pytest.mark.git
def test_no_change_untouched_with_own_row_done_or_no_dependencies(tmp_path):
    root, items = rearm_world(tmp_path / "a", T0 - 1800, own_deps="none.")
    d = deps(root)
    al_loop.tick(deps=d, no_push=True)
    assert "012" not in d.seen["launch"] and "rearmed" not in items.get("012")
    root, items = rearm_world(tmp_path / "b", T0 - 1800)
    rm = root / "ROADMAP.md"
    rm.write_text(al_loop.flip_roadmap(rm.read_text(), "012", "done"), newline="\n")
    d = deps(root)
    al_loop.tick(deps=d, no_push=True)
    assert "012" not in d.seen["launch"] and "rearmed" not in items.get("012")


@pytest.mark.git
def test_no_change_with_dependency_still_open_is_reconsidered_later(tmp_path):
    root, items = rearm_world(tmp_path, None, dep_row_done=False)
    d = deps(root)
    al_loop.tick(deps=d, no_push=True)
    assert "rearmed" not in items.get("012") and d.seen["launch"] == ["013"]


@pytest.mark.slow
@pytest.mark.git
def test_merge_records_merged_at_only_when_it_flips_and_succeeds(tmp_path):
    root, wt = git_world(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}])
    d = deps(root, spawn=sp, git=real_git, lane_state=lambda: ALL_RUNNING)
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "merged" and rec["merged_at"] == al_loop.iso(d.clock())
    root2 = _two_lane_world(tmp_path / "c", lambda w: (w / "f.txt").write_text("a\n"),
                            lambda w: (w / "f.txt").write_text("b\n"))
    states = []
    for iid in ("012", "013"):
        r = al_loop.Items(root2).get(iid)
        states.append(r["state"])
        assert ("merged_at" in r) == (r["state"] == "merged")
    assert sorted(states) == ["merge-conflict", "merged"]


def _git_at(cwd, when, *args):
    env = dict(os.environ, GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when)
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                        "-c", "core.hooksPath=/dev/null", *args], cwd=str(cwd),
                       capture_output=True, text=True, env=env, timeout=GIT_TIMEOUT_S)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.mark.git
def test_flip_time_fallback_finds_the_no_ff_merge_commit(tmp_path):
    root = make_root(tmp_path, roadmap=DEP_ROADMAP, handoff="")
    day = "2026-10-0{}T10:00:00+00:00".format
    _git_at(root, day(1), "init", "-q", "-b", "main")
    _git_at(root, day(1), "add", "-A")
    _git_at(root, day(1), "commit", "-q", "-m", "add rows")
    _git_at(root, day(2), "checkout", "-q", "-b", "lane")
    rm = root / "ROADMAP.md"
    rm.write_text(al_loop.flip_roadmap(rm.read_text(), "013", "done"), newline="\n")
    _git_at(root, day(2), "commit", "-q", "-am", "flip on lane")
    _git_at(root, day(2), "checkout", "-q", "main")
    (root / "other.txt").write_text("x\n")
    _git_at(root, day(3), "add", "-A")
    _git_at(root, day(3), "commit", "-q", "-m", "main moves")
    _git_at(root, day(4), "merge", "--no-ff", "-q", "-m", "merge", "lane")
    when = al_loop.roadmap_flip_time(real_git, root, "013")
    assert when is not None
    assert _dt.datetime.fromisoformat(when) == _dt.datetime.fromisoformat(day(4))
    assert al_loop.roadmap_flip_time(real_git, root, "012") is None


def test_current_roadmap_dispatches_only_ready_rows(tmp_path):
    # acceptance on the real ROADMAP + row files (read-only): every open row is
    # either ready (no open or unknown DEPENDS id) or waits on exactly those
    d = deps(make_root(tmp_path), main_tree=ROOT)
    rows, work, skipped = al_loop.Tick(d, dry_run=True).work_list()
    open_ids = {r["id"] for r in rows if r["open"]}
    known = {r["id"] for r in rows} | {r["id"] for r in loop_roadmap.archived_rows(ROOT)}
    by_id = {r["id"]: r for r in rows}

    def expected(iid):
        dep = roadmap.depends(by_id[iid]["text"])
        why = [x for x in dep if x in open_ids]
        out = ["waits on " + ", ".join(why)] if why else []
        return out + [f"waits on {x} (no such row)" for x in dep if x not in known]

    for w in work:
        if w["kind"] == "plan":
            assert expected(w["id"]) == [], w["id"]
    for s in skipped:
        if s.get("reason") and s.get("skip") != "blocked":
            want = expected(s["id"])
            assert want and s["reason"] == "; ".join(want)
    plans = [w["id"] for w in work if w["kind"] == "plan"]
    waits = [s["id"] for s in skipped if s.get("reason")]
    assert sorted(plans + waits) == sorted(open_ids)


@pytest.mark.git
def test_work_list_never_dispatches_blocked_rows(tmp_path):
    rm = DEP_ROADMAP.replace("- [ ] 013 Season pass tracker",
                             "- [ ] 013 Season pass tracker BLOCKED (operator plays once)")
    root = dep_root(tmp_path, {"014": "none."}, roadmap=rm)
    d = deps(root)
    rows, work, skipped = al_loop.Tick(d).work_list()
    assert "013" not in [w["id"] for w in work]
    hit = next(s for s in skipped if s["id"] == "013")
    assert hit["skip"] == "blocked" and hit["reason"].startswith("BLOCKED")
    # lower-case "blocked" in a title is prose, not the marker
    assert not al_loop.BLOCKED_RX.search("unblocked or blocked rows")


def test_rearm_falls_back_to_git_when_dependency_has_no_merged_at(tmp_path):
    root, items = rearm_world(tmp_path, None)
    calls = []

    def g(args, cwd, input=None):
        calls.append(list(args))
        out = al_loop.iso(T0 - 1800) if args and args[0] == "log" else ""
        return subprocess.CompletedProcess(args, 0, out, "")

    d = deps(root, git=g)
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["012"] and items.get("012")["rearmed"] is True
    assert any(a[0] == "log" and "--first-parent" in a for a in calls)
