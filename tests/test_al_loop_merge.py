"""Loop tests, merge side: finish + merge (refute rounds, gates, WIP), the push
worker gate, the AL gate list (ops/loop/gates.txt and the ci.yml fallback),
ROADMAP collisions between lanes and the Conventional Commits subjects.
Moved verbatim from tests/test_al_loop.py (TEST-LOOP-SPLIT-MERGE, F-196);
every side effect is injected and merge tests use a throwaway local git repo
under tmp_path."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402

from al_loopkit import (  # noqa: E402 (shared with the sibling loop tests)
    FakeGit, FakeSpawn, _two_lane_world, deps, git, git_world, isolate_git, make_root,
    real_git, stub_git)

# Plan 097 / 156 (TESTS-A-18): only the tests that build a real git world under
# tmp_path are marked git, one by one, so the fast tier runs the pure ones.


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)  # TESTS-A-19
    stub_git(monkeypatch)  # TEST-LOOP-STUB-GIT: no-spawn deps() defaults


# ---------------------------------------------------------------- finish + merge

@pytest.mark.git
def test_refute_rounds_cap_at_three_then_adjudicate_unmerged(tmp_path):
    root, wt = git_world(tmp_path)
    fail = {"rc": 0, "error": None, "result": "VERDICT: FAIL\n1. nit"}
    sp = FakeSpawn([fail, {"rc": 0}, fail, {"rc": 0}, fail, {"rc": 0}, fail])
    d = deps(root, spawn=sp, git=real_git,
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "adjudicate" and rec["rounds"] == 3
    assert rec["verdict"] == "adjudicate"
    fixes = [c for c in sp.calls if c["writes_code"]]
    assert len(fixes) == 3 and all("1. nit" in c["prompt"] for c in fixes)
    verifies = [c for c in sp.calls if not c["writes_code"]]
    # plan 129: one review-only verifier pass after fix round 3, never a round 4
    assert len(verifies) == 4 and "refute round 3/3" in verifies[-1]["prompt"]
    assert not sp.calls[-1]["writes_code"]  # no producer answer follows the pass
    assert not (root / "feature.txt").exists()  # never merged into main
    assert "refute-rounds: 3/3" in git(root, "log", "-1", "--format=%B", rec["commit"])
    log = rec["round_log"]
    assert [(e["round"], e["source"]) for e in log] == [
        (1, "verifier"), (2, "verifier"), (3, "verifier"), (3, "verifier")]
    assert all("1. nit" in e["findings"][0] for e in log)


def round3_world(tmp_path, kind="plan"):
    """Plan 129: an item that already spent its 3 fix rounds, now gated."""
    root, wt = git_world(tmp_path, kind=kind)
    items = al_loop.Items(root)
    rec = items.get("012")
    rec.update(rounds=3, round_log=[{"round": 3, "source": "verifier",
                                     "findings": ["VERDICT: FAIL\n1. nit"]}])
    items.put(rec)
    return root, wt


def review_deps(root, sp, **kw):
    return deps(root, spawn=sp, git=real_git,
                lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                    for i, n in enumerate(("build", "data", "review"))],
                **kw)


@pytest.mark.git
def test_round3_clean_gets_one_verifier_pass_and_pass_merges(tmp_path):
    root, wt = round3_world(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "fine\nVERDICT: PASS"}])
    al_loop.tick(deps=review_deps(root, sp), no_push=True)
    rec = al_loop.Items(root).get("012")
    assert len(sp.calls) == 1 and sp.calls[0]["writes_code"] is False
    assert "refute round 3/3" in sp.calls[0]["prompt"]
    assert rec["state"] == "merged" and rec["verdict"] == "PASS" and rec["rounds"] == 3
    assert (root / "feature.txt").exists()
    assert "refute-rounds: 3/3" in git(root, "log", "-1", "--format=%B", rec["commit"])
    assert rec["round_log"][-1] == {"round": 3, "source": "verifier", "findings": [],
                                    "final": True}


@pytest.mark.git
def test_round3_clean_non_pass_is_adjudicated_without_round_4(tmp_path):
    root, wt = round3_world(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: FAIL\n1. still off"}])
    al_loop.tick(deps=review_deps(root, sp), no_push=True)
    rec = al_loop.Items(root).get("012")
    assert len(sp.calls) == 1 and sp.calls[0]["writes_code"] is False
    assert rec["state"] == "adjudicate" and rec["verdict"] == "adjudicate"
    assert rec["rounds"] == 3 and not (root / "feature.txt").exists()
    last = rec["round_log"][-1]
    assert last["source"] == "verifier" and last["final"] is True
    assert "1. still off" in last["findings"][0]
    al_loop.tick(deps=review_deps(root, sp), no_push=True)
    assert len(sp.calls) == 1  # parked: nothing more runs


@pytest.mark.git
def test_round3_with_findings_is_adjudicated_without_a_spawn(tmp_path):
    root, wt = round3_world(tmp_path, kind="deep-dive")
    items = al_loop.Items(root)
    rec = items.get("012")
    rec["date"] = "20261012"  # no research doc in the worktree: an extra_checks finding
    items.put(rec)
    sp = FakeSpawn()
    al_loop.tick(deps=review_deps(root, sp), no_push=True)
    rec = al_loop.Items(root).get("012")
    assert sp.calls == [] and rec["state"] == "adjudicate" and rec["rounds"] == 3
    last = rec["round_log"][-1]
    assert last["round"] == 3 and last["source"] == "extra_checks"
    assert "missing docs/research/" in last["findings"][0]


@pytest.mark.git
def test_round_log_records_gates_and_caps_findings(tmp_path):
    root, wt = git_world(tmp_path)
    def fix(kw):  # a real fix changes the tree (the gate cache keys on it)
        (Path(kw["cwd"]) / "fixed.txt").write_text("fix\n")
        return {"rc": 0}

    sp = FakeSpawn([fix, {"rc": 0, "error": None,
                          "result": "x" * 9000 + chr(0x2014) + "\nVERDICT: FAIL"}])
    calls = {"n": 0}

    def gates(cwd):
        calls["n"] += 1
        return (False, "1 failed") if calls["n"] == 1 else (True, "")

    al_loop.tick(deps=review_deps(root, sp, gates=gates), no_push=True)
    log = al_loop.Items(root).get("012")["round_log"]
    assert log[0] == {"round": 1, "source": "gates", "findings": ["gates failed: 1 failed"]}
    assert log[1]["round"] == 2 and log[1]["source"] == "verifier"
    text = log[1]["findings"][0]
    assert len(text) <= al_loop.ROUND_LOG_CAP and text.isascii()


@pytest.mark.slow
def _fix_changes_tree(n):
    """A fix lane that changes the tree (an unchanged tree parks, LOOP-TRUNC)."""
    def fix(kw):
        (Path(kw["cwd"]) / f"fix{n}.txt").write_text(f"fix {n}\n", newline="\n")
        return {"rc": 0}
    return fix


@pytest.mark.git
def test_red_gates_after_three_rounds_keep_wip_unmerged(tmp_path):
    root, wt = git_world(tmp_path)
    sp = FakeSpawn([_fix_changes_tree(n) for n in range(3)])  # LOOP-TRUNC: real fixes
    d = deps(root, spawn=sp, git=real_git, gates=lambda cwd: (False, "1 failed"),
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    head = git(root, "rev-parse", "main")
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "failed" and git(root, "rev-parse", "main") == head
    assert git(wt, "status", "--porcelain") == ""  # lane unblocked
    assert len(sp.calls) == 3 and all(c["writes_code"] for c in sp.calls)


@pytest.mark.git
def test_clean_worktree_is_no_change(tmp_path):
    # LOOP-NOCHANGE-OPEN: true no-change only once the row is closed; the
    # open-row case is tests/test_loop_nochange_open.py
    root, wt = git_world(tmp_path)
    (wt / "feature.txt").unlink()
    rm = root / "ROADMAP.md"
    rm.write_text(al_loop.flip_roadmap(rm.read_text(), "012", "done"), newline="\n")
    d = deps(root, git=real_git)
    al_loop.tick(deps=d, no_push=True)
    assert al_loop.Items(root).get("012")["state"] == "no-change"


@pytest.mark.git
def test_dirty_main_defers_merge(tmp_path):
    root, wt = git_world(tmp_path)
    (root / "stray.txt").write_text("x")
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}])
    d = deps(root, spawn=sp, git=real_git)
    al_loop.tick(deps=d, no_push=True)
    assert al_loop.Items(root).get("012")["state"] == "committed"
    (root / "stray.txt").unlink()
    al_loop.tick(deps=d, no_push=True)
    assert al_loop.Items(root).get("012")["state"] == "merged"


# ---------------------------------------------------------------- push

@pytest.mark.git
def test_push_once_when_clean_green_and_leak_clean(tmp_path):
    root = make_root(tmp_path, roadmap="", handoff="", local={"loop_push": True})
    g = FakeGit()
    leak = []
    d = deps(root, git=g, leak_pre_push=lambda cwd, line: leak.append(line) or True)
    al_loop.tick(deps=d)
    assert [c for c in g.calls if c[0] == "push"] == [["push", "origin", "main"]]
    assert leak == ["refs/heads/main abc refs/heads/main abc"]


@pytest.mark.git
def test_push_skipped_no_push_red_gates_leak_or_nothing_ahead(tmp_path):
    root = make_root(tmp_path, roadmap="", handoff="")
    for kw, over in (({"no_push": True}, {}),
                     ({}, {"gates": lambda cwd: (False, "red")}),
                     ({}, {"leak_pre_push": lambda cwd, line: False}),
                     ({}, {"git": FakeGit(ahead="0")}),
                     ({}, {"git": FakeGit(dirty=" M x")})):
        g = over.pop("git", FakeGit())
        d = deps(root, git=g, **over)
        al_loop.tick(deps=d, **kw)
        assert not [c for c in g.calls if c[0] == "push"]


# ---------------------------------------------------------------- AL gates (ops/loop/gates.txt)

GATES_TXT = ROOT / "ops" / "loop" / "gates.txt"
CI_TEXT = """name: ci
jobs:
  check:
    steps:
      - name: install
        run: python -m pip install --quiet -r requirements.txt
      - name: lint
        run: python -m ruff check server tools tests
      - name: pytest
        run: python -m pytest -q
      - name: node
        run: npm test --prefix app
"""


def test_tracked_gate_list_matches_the_claude_md_gates():
    cmds = al_loop.gate_file_commands(GATES_TXT.read_text(encoding="utf-8"))
    # TEST-GATE-CALLERS: the first gate is the one whole-suite runner
    assert cmds[0] == "python tools/suite_run.py" and "npm test --prefix app" in cmds
    assert "python -m pytest -q" not in cmds
    assert "python tools/leak_sweep.py --tree" in cmds
    assert not any(c.startswith("#") for c in cmds)
    assert all(al_loop._shell_operator(c) is None for c in cmds)


def test_ci_gate_commands_are_read_from_a_ci_workflow():
    cmds = al_loop.ci_gate_commands(CI_TEXT)
    assert "python -m ruff check server tools tests" in cmds
    assert "python -m pytest -q" in cmds and "npm test --prefix app" in cmds
    assert not any("pip install" in c for c in cmds)  # environment setup, not a gate
    assert cmds.index("python -m ruff check server tools tests") < cmds.index("python -m pytest -q")


def _ci_tree(tmp_path, text=None):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(text if text is not None else CI_TEXT, newline="\n")
    return tmp_path


def _gates_tree(tmp_path, text=None):
    d = tmp_path / "ops" / "loop"
    d.mkdir(parents=True)
    (d / "gates.txt").write_text(text if text is not None else
                                 GATES_TXT.read_text(encoding="utf-8"), newline="\n")
    return tmp_path


def test_loop_gates_run_exactly_the_gate_list(tmp_path):
    cwd, ran = _gates_tree(tmp_path), []
    _ci_tree(tmp_path, "jobs:\n  chk:\n    steps:\n      - run: python other.py\n")

    def run(argv, cwd):
        ran.append(argv)
        return 0, ""

    ok, detail = al_loop._gates(cwd, run=run)
    assert ok and "gates.txt" in detail, detail
    want = al_loop.gate_file_commands(GATES_TXT.read_text(encoding="utf-8"))
    assert len(ran) == len(want)  # gates.txt wins over ci.yml
    for argv, cmd in zip(ran, want):
        words = cmd.split()
        if words[0] == "python" and al_loop._whole_suite(words):
            # kit v12: the whole suite runs through fleet_suite_gate.py
            i = argv.index("--")
            assert argv[0] == al_loop._python() and "fleet_suite_gate.py" in argv[1]
            assert argv[i + 1] == al_loop._python() and argv[i + 2:] == words[1:]
        elif words[0] == "python":
            assert argv[0] == al_loop._python() and argv[1:] == words[1:]
        elif words[0] == "npm":
            assert Path(argv[0]).stem == "npm" and argv[1:] == words[1:]
        else:
            assert argv == words


def test_loop_gates_fall_back_to_the_ci_workflow_and_stop_red(tmp_path):
    cwd, ran = _ci_tree(tmp_path), []

    def run(argv, cwd):
        ran.append(argv)
        return (1, "F401 unused import") if "ruff" in argv else (0, "")

    ok, detail = al_loop._gates(cwd, run=run)
    assert not ok and "ruff" in detail and "F401" in detail
    assert not any("pytest" in a for a in ran)


def test_empty_gate_list_fails_closed(tmp_path):
    cwd = _gates_tree(tmp_path, "# nothing\n\n")
    ok, detail = al_loop._gates(cwd, run=lambda argv, cwd: (0, ""))
    assert not ok and "no gate command" in detail


def test_loop_gates_fail_closed_without_ci_workflow(tmp_path):
    ok, detail = al_loop._gates(tmp_path, run=lambda argv, cwd: (0, ""))
    assert not ok and "ci.yml" in detail
    _ci_tree(tmp_path / "x", "name: ci\njobs: {}\n")
    ok, detail = al_loop._gates(tmp_path / "x", run=lambda argv, cwd: (0, ""))
    assert not ok


def test_loop_gates_fail_closed_on_shell_operators(tmp_path):
    # the loop runs argv without a shell: `a && b` would hand "&&" to a as an
    # argument and never run b, so the loop could merge what ci rejects
    for i, op in enumerate(("&&", "||", "|", ";", ">", "<", "2>&1", "a&&b")):
        cwd, ran = _ci_tree(tmp_path / str(i),
                            f"jobs:\n  check:\n    steps:\n      - run: python a.py {op} python b.py\n"), []
        ok, detail = al_loop._gates(cwd, run=lambda argv, cwd: ran.append(argv) or (0, ""))
        assert not ok and "shell operator" in detail and not ran, op
    assert al_loop._shell_operator("python a.py 'x|y' \"a && b\"") is None  # quoted: plain args
    assert al_loop._shell_operator("python -m pytest -q") is None


# ---------------------------------------------------------------- fix-0130: ROADMAP collisions

@pytest.mark.slow
@pytest.mark.git
def test_real_code_conflict_still_aborts_cleanly(tmp_path):
    root = _two_lane_world(tmp_path, lambda wt: (wt / "f.txt").write_text("a\n"),
                           lambda wt: (wt / "f.txt").write_text("b\n"))
    states = sorted(al_loop.Items(root).get(i)["state"] for i in ("012", "013"))
    assert states == ["merge-conflict", "merged"]
    assert git(root, "status", "--porcelain") == ""
    assert not (root / ".git" / "MERGE_HEAD").exists()


def test_plan_and_handoff_prompts_keep_lanes_off_roadmap_and_name_the_leak_sweep():
    item = {"id": "012", "title": "t", "text": "x"}
    for prompt in (al_loop.plan_prompt(item), al_loop.handoff_prompt(item)):
        assert "Do NOT edit ROADMAP.md" in prompt
        assert "python tools/leak_sweep.py --staged" in prompt
        assert "ruff" not in prompt  # AL gates: pytest, npm test, leak sweep


def test_lane_prompts_give_scratch_scripts_a_task_unique_name():
    # session 9: two agents' generic prog.py clobbered each other's progress file
    item = {"id": "012", "title": "t", "text": "x"}
    assert "(p012-build_*.py)" in al_loop.plan_prompt(item)
    assert "(012_*.py)" in al_loop.handoff_prompt(item)


@pytest.mark.git
def test_merge_rerun_of_an_already_merged_commit_is_a_no_op(tmp_path):
    root, wt = git_world(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}])
    d = deps(root, spawn=sp, git=real_git,
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    items = al_loop.Items(root)
    rec = items.get("012")
    assert rec["state"] == "merged"
    head = git(root, "rev-parse", "main")
    rec["state"] = "committed"  # crash between the merge commit and the record write
    items.put(rec)
    al_loop.tick(deps=d, no_push=True)
    assert items.get("012")["state"] == "merged" and git(root, "rev-parse", "main") == head


def test_ci_gate_commands_block_run_with_blank_line():
    text = "steps:\n  - name: a\n    run: |\n      echo one\n\n      echo two\n  - name: b\n    run: echo three\n"
    assert al_loop.ci_gate_commands(text) == ["echo one", "echo two", "echo three"]


# ---------------------------------------------------------------- commit subjects
# PUBREPO order (MAIN 2026-10-15, item 1b): lane commits carry Conventional
# Commits subjects for outsiders (the item id in the scope, session detail in
# the body); merge subjects read `merge: <topic>`, never a lane or worktree name.

CC_RX = re.compile(r"^(feat|fix|docs|chore)\([a-z0-9-]+\): \S")


def test_conventional_commit_subjects_by_item_kind():
    cs = al_loop.commit_subject
    plan = {"id": "132", "kind": "plan", "label": "plan 132: My Info XP OCR",
            "title": "My Info XP OCR: absolute samples (plan doc docs/plans/132-x.md;"
                     " depends on 116, 063)"}
    assert cs(plan) == "feat(plan-132): My Info XP OCR: absolute samples"
    fixp = dict(plan, id="133", title="Fix stale gate cache on rename")
    assert cs(fixp) == "fix(plan-133): stale gate cache on rename"
    order = {"id": "N3018ab", "kind": "order", "title": "PUBREPO posture"}
    assert cs(order) == "chore(order-n3018ab): PUBREPO posture"
    ho = {"id": "H7", "kind": "handoff", "text": "rerun the OCR fixture sweep"}
    assert cs(ho) == "chore(handoff-h7): rerun the OCR fixture sweep"
    dd = {"id": "DD-2026-10-15", "kind": "deep-dive", "date": "2026-10-15",
          "title": "idle deep-dive"}
    assert cs(dd) == "docs(research): idle deep-dive 2026-10-15"
    res = dict(plan, kind="resolve", base_kind="plan")
    assert cs(res) == cs(plan)
    for rec in (plan, fixp, order, ho, dd):
        s = cs(rec)
        assert CC_RX.match(s) and len(s) <= 100 and s.isascii(), s
        assert "lane" not in s and "worktree" not in s
    assert len(cs(dict(plan, title="word " * 60))) <= 100


def test_wip_subjects_stay_conventional():
    rec = {"id": "012", "kind": "plan", "title": "Grind spot recommender"}
    s = al_loop.commit_subject(rec, wip="gates failed, not merged")
    assert s == "chore(plan-012): WIP (gates failed, not merged) Grind spot recommender"
    assert CC_RX.match(s)


def test_merge_subject_names_the_topic_never_the_lane():
    rec = {"id": "132", "kind": "plan", "label": "plan 132: My Info XP OCR",
           "title": "My Info XP OCR (plan doc docs/plans/132-x.md)", "lane": "build"}
    s = al_loop.merge_subject(rec)
    assert s == "merge: My Info XP OCR (plan-132)"
    assert "lane" not in s and "worktree" not in s and "build" not in s


@pytest.mark.git
def test_lane_and_merge_commits_use_the_generated_subjects(tmp_path):
    root, wt = git_world(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "fine\nVERDICT: PASS"}])
    d = deps(root, spawn=sp, git=real_git,
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "merged"
    assert git(root, "log", "-1", "--format=%s", rec["commit"]) == \
        "feat(plan-012): Grind spot recommender"
    assert git(root, "log", "-1", "--format=%s", "main") == \
        "merge: Grind spot recommender (plan-012)"
    body = git(root, "log", "-1", "--format=%B", rec["commit"])
    assert "loop item: 012" in body and "plan 012: Grind spot recommender" in body
