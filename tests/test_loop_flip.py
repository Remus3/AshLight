"""LOOP-TESTS-CARVE: the tools/al_loop.py tests that call flip_roadmap or
assert a '- [x] ' ROADMAP.md line after a merge, moved unchanged from
tests/test_al_loop.py. Owner later: LOOP-ROWFILES-MERGE, which edits this file
and never tests/test_al_loop.py. The git-world helpers these tests share with
tests that stay in tests/test_al_loop.py are copied here unchanged."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402

from al_loopkit import (  # noqa: E402
    ROADMAP, FakeSpawn, deps, git, git_world, isolate_git, make_root, real_git)


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)  # TESTS-A-19


def test_roadmap_rows_and_flip():
    rows = al_loop.roadmap_rows(ROADMAP)
    assert [(r["id"], r["open"]) for r in rows] == [("001", False), ("012", True),
                                                     ("013", True)]
    out = al_loop.flip_roadmap(ROADMAP, "012", "done 2026-10-05 (loop; refute 1/3 PASS)")
    assert "- [x] 012 Grind spot recommender -- done 2026-10-05 (loop; refute 1/3 PASS)" in out
    assert "- [ ] 013 Season pass tracker" in out
    assert al_loop.flip_roadmap(out, "001", "x") == out  # done rows never touched


@pytest.mark.git
def test_finished_lane_is_verified_committed_merged_and_flipped(tmp_path):
    root, wt = git_world(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "fine\nVERDICT: PASS"}])
    d = deps(root, spawn=sp, git=real_git,
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "merged" and rec["verdict"] == "PASS"
    v = sp.calls[0]
    assert v["cwd"] == wt and v["governor"] == "queued" and v["writes_code"] is False
    assert "refute round 1/3" in v["prompt"]
    log = git(root, "log", "-1", "--format=%P%n%B", "main")
    assert len(log.splitlines()[0].split()) == 2  # --no-ff merge commit
    lane_msg = git(root, "log", "-1", "--format=%B", rec["commit"])
    assert "refute-rounds: 0/3" in lane_msg and "verifier: PASS" in lane_msg
    rm = (root / "ROADMAP.md").read_text()
    assert "- [x] 012 Grind spot recommender -- done" in rm and "refute 0/3 PASS" in rm
    assert (root / "feature.txt").exists()


def test_resolve_roadmap_takes_both_sides_row_changes():
    base = ROADMAP
    ours = ROADMAP.replace("- [ ] 012 Grind spot recommender",
                           "- [x] 012 Grind spot recommender -- done A")
    theirs = ROADMAP.replace("- [ ] 013 Season pass tracker",
                             "- [x] 013 Season pass tracker -- done B") + \
        "- [ ] 020 New idea\n"
    out = al_loop.resolve_roadmap(base, ours, theirs)
    assert "- [x] 012 Grind spot recommender -- done A" in out
    assert "- [x] 013 Season pass tracker -- done B" in out
    assert "- [ ] 020 New idea" in out
    assert out.index("] 013 ") < out.index("] 020 ")
    # both sides changed one row: main (ours) wins
    both = theirs.replace("- [ ] 012 Grind spot recommender\n",
                          "- [x] 012 Grind spot recommender -- lane says\n")
    assert "-- done A" in al_loop.resolve_roadmap(base, ours, both)
    # a non-row (prose) change on both sides is not auto-resolved
    assert al_loop.resolve_roadmap(base, ours + "prose A\n", theirs + "prose B\n") is None


def _lane(root, tmp_path, name, iid, edit):
    wt = tmp_path / "al-worktrees" / name
    git(root, "worktree", "add", "-q", "--detach", str(wt))
    edit(wt)
    al_loop.Items(root).put({"id": iid, "kind": "plan", "title": f"plan {iid}",
                             "label": f"plan {iid}: t", "state": "ran", "worktree": str(wt),
                             "rc": 0, "lane": name, "rounds": 0})
    return wt


def _flip_in(wt, iid):
    rm = wt / "ROADMAP.md"
    rm.write_text(al_loop.flip_roadmap(rm.read_text(), iid, "done by lane"), newline="\n")


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


@pytest.mark.git
def test_lane_commit_never_flips_roadmap_merge_does(tmp_path):
    root, wt = git_world(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}])
    d = deps(root, spawn=sp, git=real_git,
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "merged"
    lane_files = git(root, "show", "--name-only", "--format=", rec["commit"]).split()
    assert "ROADMAP.md" not in lane_files
    assert "- [x] 012 Grind spot recommender -- done" in git(root, "show", "main:ROADMAP.md")
    assert len(git(root, "log", "-1", "--format=%P", "main").split()) == 2
    assert git(root, "status", "--porcelain") == ""


@pytest.mark.slow
@pytest.mark.git
def test_parallel_lanes_flipping_adjacent_rows_both_merge(tmp_path):
    # the Nfa7953 / 013 / 014 shape: two lanes from one base, adjacent ROADMAP rows
    def a(wt):
        (wt / "a.txt").write_text("a\n")
        _flip_in(wt, "012")

    def b(wt):
        (wt / "b.txt").write_text("b\n")
        _flip_in(wt, "013")

    root = _two_lane_world(tmp_path, a, b)
    items = al_loop.Items(root)
    assert items.get("012")["state"] == "merged" and items.get("013")["state"] == "merged"
    rm = (root / "ROADMAP.md").read_text()
    assert "<<<<" not in rm and rm.count("] 012 ") == 1 and rm.count("] 013 ") == 1
    assert "- [x] 012 Grind spot recommender -- done" in rm
    assert "- [x] 013 Season pass tracker -- done" in rm
    assert (root / "a.txt").exists() and (root / "b.txt").exists()
    assert git(root, "status", "--porcelain") == ""


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
def test_roadmap_only_conflict_never_keeps_a_ref(tmp_path):
    def a(wt):
        (wt / "a.txt").write_text("a\n")
        _flip_in(wt, "012")

    def b(wt):
        (wt / "b.txt").write_text("b\n")
        _flip_in(wt, "013")

    root = _two_lane_world(tmp_path, a, b)
    assert keep_refs(root) == ""
    d = _free(root, tmp_path)
    al_loop.tick(deps=d, no_push=True)
    assert not {"012", "013"} & set(d.seen["launch"])  # idle deep-dive only
    assert all(r.get("kind") != "resolve" for r in al_loop.Items(root).all().values())


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
def test_resolve_lane_merges_through_the_normal_path_and_drops_the_ref(tmp_path):
    root, items = _conflict_world(tmp_path)
    kept = items.get("013")["commit"]
    al_loop.tick(deps=_free(root, tmp_path), no_push=True)
    saw = _run_resolve(root, tmp_path, items, "lane-2", "a\nb\n")
    assert saw == {"merging": True, "markers": True}
    al_loop.tick(deps=_review(root), no_push=True)
    rec = items.get("013")
    assert rec["state"] == "merged" and rec["verdict"] == "PASS"
    assert "keep_ref" not in rec and keep_refs(root) == ""
    assert (root / "f.txt").read_text() == "a\nb\n"
    assert git(root, "merge-base", "--is-ancestor", kept, "main") == ""
    assert git(root, "log", "-1", "--format=%s", "main") == "merge: plan 013 (plan-013)"
    assert "- [x] 013 Season pass tracker -- done" in (root / "ROADMAP.md").read_text()
    assert git(root, "status", "--porcelain") == ""


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
def test_refused_lane_commit_is_salvaged_and_merged_in_main(tmp_path):
    root, wt = git_world(tmp_path)
    d = deps(root, spawn=_passing(), git=_refusing_git(wt, {"on": True}),
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "merged" and "leak-sweep" in rec["error"]
    assert (root / "feature.txt").exists() and keep_refs(root) == ""
    assert git(wt, "status", "--porcelain") == ""  # lane index usable again
    assert "refute-rounds: 0/3" in git(root, "log", "-1", "--format=%B", rec["commit"])
    assert "- [x] 012 Grind spot recommender -- done" in (
        root / "ROADMAP.md").read_text()
