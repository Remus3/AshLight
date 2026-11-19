"""LOOP-TESTS-CARVE: the tools/al_loop.py tests that call flip_roadmap or
check how a merge closes a row, moved from tests/test_al_loop.py.
LOOP-ROWFILES-MERGE (F-029): a merge closes its row with a done file,
docs/roadmap/done/<ID>.md, inside the merge commit and never edits
ROADMAP.md; the gate verdict carries over a merge that added only done files.
Row files take upper-case ids, so the merge worlds here use RM (file ids)
instead of the al_loopkit ROADMAP (numeric ids)."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402
import roadmap  # noqa: E402

from al_loopkit import (  # noqa: E402
    ROADMAP, FakeSpawn, deps, git, isolate_git, make_root, real_git)

A, B = "GRIND-012", "SEASON-013"
RM = f"""# AshLight roadmap

- [x] SKEL Skeleton -- done 2026-10-04
- [ ] {A} Grind spot recommender
- [ ] {B} Season pass tracker
"""
DAY = "2026-09-21"
NOW = 1_790_000_000.0  # the al_loopkit deps clock


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)  # TESTS-A-19


def _done(iid):
    return f"docs/roadmap/done/{iid}.md"


def _done_line(root, iid):
    p = root / _done(iid)
    return p.read_text(encoding="ascii") if p.exists() else None


def _running():
    return [{"index": i, "state": "RUNNING", "lane": n}
            for i, n in enumerate(("build", "data", "review"))]


def _passing(n=1):
    return FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}] * n)


def git_world(tmp_path, kind="plan", iid=A):
    """al_loopkit.git_world on RM: one finished lane for row iid."""
    root = make_root(tmp_path, roadmap=RM, handoff="")
    git(root, "init", "-q", "-b", "main")
    # LF on every host (al_loopkit.git_world)
    (root / ".gitignore").write_text("ops/\n", newline="\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    wt = tmp_path / "al-worktrees" / "lane-1"
    git(root, "worktree", "add", "-q", "--detach", str(wt))
    (wt / "feature.txt").write_text("work\n", newline="\n")
    al_loop.Items(root).put({"id": iid, "kind": kind, "title": "Grind spot recommender",
                             "label": f"plan {iid}: Grind spot recommender", "state": "ran",
                             "worktree": str(wt), "rc": 0, "lane": "build", "rounds": 0})
    return root, wt


def test_roadmap_rows_and_flip():
    rows = al_loop.roadmap_rows(ROADMAP)
    assert [(r["id"], r["open"]) for r in rows] == [("001", False), ("012", True),
                                                     ("013", True)]
    out = al_loop.flip_roadmap(ROADMAP, "012", "done 2026-10-05 (loop; refute 1/3 PASS)")
    assert "- [x] 012 Grind spot recommender -- done 2026-10-05 (loop; refute 1/3 PASS)" in out
    assert "- [ ] 013 Season pass tracker" in out
    assert al_loop.flip_roadmap(out, "001", "x") == out  # done rows never touched


@pytest.mark.git
def test_finished_lane_is_verified_committed_merged_and_closed_by_a_done_file(tmp_path):
    root, wt = git_world(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "fine\nVERDICT: PASS"}])
    d = deps(root, spawn=sp, git=real_git, lane_state=_running)
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get(A)
    assert rec["state"] == "merged" and rec["verdict"] == "PASS"
    assert rec["merged_at"]
    v = sp.calls[0]
    assert v["cwd"] == wt and v["governor"] == "queued" and v["writes_code"] is False
    assert "refute round 1/3" in v["prompt"]
    log = git(root, "log", "-1", "--format=%P%n%B", "main")
    assert len(log.splitlines()[0].split()) == 2  # --no-ff merge commit
    lane_msg = git(root, "log", "-1", "--format=%B", rec["commit"])
    assert "refute-rounds: 0/3" in lane_msg and "verifier: PASS" in lane_msg
    assert (root / "ROADMAP.md").read_text() == RM  # the row stays open in ROADMAP.md
    line = _done_line(root, A)
    assert line is not None and line.startswith(" -- done 20") and line.count("\n") == 1
    assert line.endswith(" (loop; refute 0/3 PASS)\n")
    assert _done(A) in git(root, "show", "--name-only", "--format=", "main").split()
    assert (root / "feature.txt").exists()
    rows = {r["id"]: r for r in roadmap.load_rows(root)}
    assert rows[A]["open"] is False and rows[B]["open"] is True
    assert roadmap.lint(root) == []


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
    root = make_root(tmp_path, roadmap=RM, handoff="")
    git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("ops/\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    _lane(root, tmp_path, "lane-0", A, edit_a)
    _lane(root, tmp_path, "lane-1", B, edit_b)
    al_loop.tick(deps=deps(root, spawn=_passing(2), git=real_git, lane_state=_running),
                 no_push=True)
    return root


@pytest.mark.git
def test_lane_commit_never_flips_roadmap_merge_does(tmp_path):
    root, wt = git_world(tmp_path)
    al_loop.tick(deps=deps(root, spawn=_passing(), git=real_git, lane_state=_running),
                 no_push=True)
    rec = al_loop.Items(root).get(A)
    assert rec["state"] == "merged"
    lane_files = git(root, "show", "--name-only", "--format=", rec["commit"]).split()
    assert "ROADMAP.md" not in lane_files and _done(A) not in lane_files
    assert "refute 0/3 PASS" in git(root, "show", f"main:{_done(A)}")
    assert len(git(root, "log", "-1", "--format=%P", "main").split()) == 2
    assert git(root, "status", "--porcelain") == ""


@pytest.mark.slow
@pytest.mark.git
def test_parallel_lanes_closing_adjacent_rows_both_merge(tmp_path):
    # the Nfa7953 / 013 / 014 shape: two lanes from one base, adjacent rows;
    # each merge adds its own done file, so the rows can never conflict
    root = _two_lane_world(tmp_path, lambda wt: (wt / "a.txt").write_text("a\n"),
                           lambda wt: (wt / "b.txt").write_text("b\n"))
    items = al_loop.Items(root)
    assert items.get(A)["state"] == "merged" and items.get(B)["state"] == "merged"
    assert (root / "ROADMAP.md").read_text() == RM
    assert _done_line(root, A).endswith(" (loop; refute 0/3 PASS)\n")
    assert _done_line(root, B).endswith(" (loop; refute 0/3 PASS)\n")
    assert not any(r["open"] for r in roadmap.load_rows(root))
    assert (root / "a.txt").exists() and (root / "b.txt").exists()
    assert git(root, "status", "--porcelain") == ""


def _conflict_world(tmp_path):
    """A merges, B conflicts on f.txt (finished() runs ids in order)."""
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
    # a session-style ROADMAP.md edit in each lane: resolve_roadmap_conflict
    def a(wt):
        (wt / "a.txt").write_text("a\n")
        _flip_in(wt, A)

    def b(wt):
        (wt / "b.txt").write_text("b\n")
        _flip_in(wt, B)

    root = _two_lane_world(tmp_path, a, b)
    assert keep_refs(root) == ""
    d = _free(root, tmp_path)
    al_loop.tick(deps=d, no_push=True)
    assert not {A, B} & set(d.seen["launch"])  # idle deep-dive only
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

    assert al_loop.lane_worker(B, deps=deps(root, spawn=sp, git=real_git),
                               run_lane=run_lane) == 0
    assert items.get(B)["state"] == "ran"
    return saw


@pytest.mark.slow
@pytest.mark.git
def test_resolve_lane_merges_through_the_normal_path_and_drops_the_ref(tmp_path):
    root, items = _conflict_world(tmp_path)
    kept = items.get(B)["commit"]
    al_loop.tick(deps=_free(root, tmp_path), no_push=True)
    saw = _run_resolve(root, tmp_path, items, "lane-2", "a\nb\n")
    assert saw == {"merging": True, "markers": True}
    al_loop.tick(deps=deps(root, spawn=_passing(), git=real_git, lane_state=_running),
                 no_push=True)
    rec = items.get(B)
    assert rec["state"] == "merged" and rec["verdict"] == "PASS"
    assert "keep_ref" not in rec and keep_refs(root) == ""
    assert (root / "f.txt").read_text() == "a\nb\n"
    assert git(root, "merge-base", "--is-ancestor", kept, "main") == ""
    assert git(root, "log", "-1", "--format=%s", "main") == \
        f"merge: plan {B} (plan-{B.lower()})"
    assert _done_line(root, B).endswith(" (loop; refute 0/3 PASS)\n")
    assert (root / "ROADMAP.md").read_text() == RM
    assert git(root, "status", "--porcelain") == ""


def _refusing_git(wt, refuse):
    """real_git, but `commit` in the lane worktree is refused (a pre-commit hook)
    while refuse["on"] holds."""
    def g(args, cwd, input=None):
        if args[:1] == ["commit"] and Path(cwd) == Path(wt) and refuse["on"]:
            return subprocess.CompletedProcess(args, 1, "", "[leak-sweep] HALT t.py:1 drive-path")
        return real_git(args, cwd, input=input)
    return g


@pytest.mark.git
def test_refused_lane_commit_is_salvaged_and_merged_in_main(tmp_path):
    root, wt = git_world(tmp_path)
    d = deps(root, spawn=_passing(), git=_refusing_git(wt, {"on": True}),
             lane_state=_running)
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get(A)
    assert rec["state"] == "merged" and "leak-sweep" in rec["error"]
    assert (root / "feature.txt").exists() and keep_refs(root) == ""
    assert git(wt, "status", "--porcelain") == ""  # lane index usable again
    assert "refute-rounds: 0/3" in git(root, "log", "-1", "--format=%B", rec["commit"])
    assert _done_line(root, A) is not None
    assert (root / "ROADMAP.md").read_text() == RM


def _main_commit_refused(root):
    """real_git, but `commit` in the main checkout is refused (main's hook)."""
    def g(args, cwd, input=None):
        if args[:1] == ["commit"] and Path(cwd) == Path(root):
            return subprocess.CompletedProcess(args, 1, "", "[leak-sweep] HALT x")
        return real_git(args, cwd, input=input)
    return g


@pytest.mark.git
def test_merge_never_edits_roadmap_md(tmp_path):
    root, wt = git_world(tmp_path)
    before = (root / "ROADMAP.md").read_bytes()
    al_loop.tick(deps=deps(root, spawn=_passing(), git=real_git, lane_state=_running),
                 no_push=True)
    assert al_loop.Items(root).get(A)["state"] == "merged"
    assert (root / "ROADMAP.md").read_bytes() == before
    changed = git(root, "diff", "--name-status", "main^1", "main").splitlines()
    assert sorted(changed) == sorted([f"A\t{_done(A)}", "A\tfeature.txt"])
    assert git(root, "status", "--porcelain") == ""
    # a refused merge commit leaves neither the done file nor a dirty main
    root2, _ = git_world(tmp_path / "two")
    al_loop.tick(deps=deps(root2, spawn=_passing(), git=_main_commit_refused(root2),
                           lane_state=_running), no_push=True)
    rec = al_loop.Items(root2).get(A)
    assert rec["state"] == "merge-refused" and "merged_at" not in rec
    assert not (root2 / _done(A)).exists()
    assert (root2 / "ROADMAP.md").read_text() == RM
    assert git(root2, "status", "--porcelain") == ""
    # a row already done gets no done file; the merge still goes on
    root3, _ = git_world(tmp_path / "three", iid="SKEL")
    al_loop.tick(deps=deps(root3, spawn=_passing(), git=real_git, lane_state=_running),
                 no_push=True)
    rec = al_loop.Items(root3).get("SKEL")
    assert rec["state"] == "merged" and "merged_at" not in rec
    assert not (root3 / "docs" / "roadmap" / "done").exists()
    assert (root3 / "ROADMAP.md").read_text() == RM


def _carry_repo(tmp_path):
    root = make_root(tmp_path, roadmap=RM, handoff="")
    git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("ops/\n", newline="\n")
    (root / "a.py").write_text("x = 1\n", newline="\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def _commit_file(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, newline="\n")
    git(root, "add", "--", rel)
    git(root, "commit", "-q", "-m", "c")
    return git(root, "rev-parse", "HEAD^{tree}")


@pytest.mark.git
def test_verdict_carries_over_a_done_file_only_merge(tmp_path):
    root = _carry_repo(tmp_path / "unit")
    c = al_loop.GateCache(root)
    t0 = git(root, "rev-parse", "HEAD^{tree}")
    c.put(t0, True, "green", "lane", NOW)
    t1 = _commit_file(root, _done(A), f" -- done {DAY} (loop; refute 0/3 PASS)\n")
    assert c.carry(t0, t1, real_git, root, NOW) and c.get(t1, NOW)["via"] == t0
    t2 = _commit_file(root, "ROADMAP.md", RM.replace("- [ ] " + B, "- [x] " + B))
    assert c.carry(t1, t2, real_git, root, NOW)  # a ROADMAP.md-only change still carries
    t3 = _commit_file(root, _done(B), f" -- done {DAY} (loop)\n")
    assert c.carry(t0, t3, real_git, root, NOW)  # done files plus ROADMAP.md
    # anything beside them refuses: a new row file, a non-row file in done/, code
    for n, rel in enumerate(("docs/roadmap/new/NEW-1.md", "docs/roadmap/done/notes.txt",
                             "docs/roadmap/done/sub/X.md", "a.py")):
        sub = _carry_repo(tmp_path / f"refuse{n}")
        cs = al_loop.GateCache(sub)
        s0 = git(sub, "rev-parse", "HEAD^{tree}")
        cs.put(s0, True, "green", "lane", NOW)
        _commit_file(sub, _done(A), f" -- done {DAY} (loop)\n")
        s1 = _commit_file(sub, rel, "x = 2\n")
        assert not cs.carry(s0, s1, real_git, sub, NOW), rel
        assert cs.get(s1, NOW) is None
    # end to end: the merge's own done file does not cost main a second gate
    root2, wt = git_world(tmp_path / "e2e")
    al_loop.tick(deps=deps(root2, spawn=_passing(), git=real_git, lane_state=_running),
                 no_push=True)
    rec = al_loop.Items(root2).get(A)
    assert rec["state"] == "merged"
    lane_tree = git(root2, "rev-parse", f"{rec['commit']}^{{tree}}")
    main_tree = git(root2, "rev-parse", "main^{tree}")
    assert lane_tree != main_tree
    e = al_loop.GateCache(root2).get(main_tree, NOW)
    assert e is not None and e["ok"] and e["via"] == lane_tree


@pytest.mark.git
def test_legacy_numeric_row_keeps_the_roadmap_flip(tmp_path):
    # a \d{3} row id has no row-file form (roadmap.FILE_ID): only it flips
    root = make_root(tmp_path, handoff="")
    git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("ops/\n", newline="\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    _lane(root, tmp_path, "lane-1", "012", lambda wt: (wt / "f.txt").write_text("f\n"))
    al_loop.tick(deps=deps(root, spawn=_passing(), git=real_git, lane_state=_running),
                 no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "merged" and rec["merged_at"]
    rm = (root / "ROADMAP.md").read_text()
    assert "- [x] 012 Grind spot recommender -- done" in rm and "refute 0/3 PASS" in rm
    assert not (root / "docs" / "roadmap").exists()
    assert git(root, "status", "--porcelain") == ""
