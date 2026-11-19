"""LOOP-FAILED-PARK (F-024, AUTO-01, OPEN-29, OPEN-36): a failed loop item is
parked visibly (checklist line, parked list, keep ref on its WIP commit); a
failed plan record whose row is no longer open reads superseded; a red gate
naming only tests outside the lane's diff ends the fix rounds at round 0.
Every side effect is injected; git worlds live under tmp_path."""

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402
import loop_gatefail  # noqa: E402

from al_loopkit import FakeSpawn, deps, git, git_world, isolate_git, make_root, real_git  # noqa: E402

NOW = 1_790_000_000.0
FOREIGN = ("python -m pytest -q rc=1\n"
           "........F..\n"
           "FAILED tests/test_other.py::test_x - AssertionError: boom\n"
           "FAILED tests/test_other.py::test_y[a-b]\n"
           "2 failed, 9 passed in 1.23s\n")


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)


def review_deps(root, sp, **kw):
    return deps(root, spawn=sp, git=real_git,
                lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                    for i, n in enumerate(("build", "data", "review"))],
                **kw)


def row(doc, iid):
    return next((r for r in doc["checklist"] if r["id"] == iid), None)


def test_failed_item_prints_a_checklist_line_and_is_parked(tmp_path):
    root = make_root(tmp_path, handoff="")
    al_loop.Items(root).put({"id": "012", "kind": "plan", "state": "failed", "lane": "build",
                             "title": "Grind spot recommender", "label": "l",
                             "finished": al_loop.iso(NOW - 7200)})
    assert "failed" not in al_loop.DONE_STATES and "failed" in al_loop.ATTENTION_STATES
    assert "superseded" in al_loop.DONE_STATES
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    r = row(doc, "012")
    assert r is not None and r["state"] == "failed" and r["eta_s"] == 0
    assert "012" not in d.seen["launch"]  # parked, never re-sent
    assert al_loop.Items(root).get("012")["state"] == "failed"
    parked = al_loop.parked_items(root, None, NOW)
    assert parked == [{"id": "012", "why": "failed", "age_h": 2.0}]
    # an order whose lane failed is still answered once (finished, not done)
    src = (ROOT / "tools" / "loop_inbox.py").read_text(encoding="utf-8")
    assert 'DONE_STATES + ("adjudicate", "failed")' in src


@pytest.mark.git
def test_failed_wip_commit_gets_a_keep_ref(tmp_path):
    root, wt = git_world(tmp_path)
    items = al_loop.Items(root)
    rec = items.get("012")
    rec["rounds"] = al_loop.MAX_ROUNDS  # no fix round left: red gates end in failed
    items.put(rec)
    head = git(root, "rev-parse", "main")
    sp = FakeSpawn()
    doc = al_loop.tick(deps=review_deps(root, sp, gates=lambda cwd: (False, "1 failed")),
                       no_push=True)
    rec = al_loop.Items(root).get("012")
    assert sp.calls == [] and rec["state"] == "failed"
    assert rec["keep_ref"] == "refs/al/keep/012"
    assert git(root, "rev-parse", "refs/al/keep/012") == rec["commit"]
    assert git(root, "rev-parse", "main") == head  # unmerged
    assert row(doc, "012")["state"] == "failed"


@pytest.mark.git
def test_failed_record_of_a_done_row_becomes_superseded(tmp_path):
    root = make_root(tmp_path, handoff="")
    items = al_loop.Items(root)
    base = {"state": "failed", "lane": "build", "label": "l",
            "finished": al_loop.iso(NOW - 3600)}
    items.put(dict(base, id="001", kind="plan", title="Skeleton"))  # row [x]
    items.put(dict(base, id="GONE-ROW", kind="resolve", base_kind="plan",
                   title="Gone", keep_ref="refs/al/keep/GONE-ROW", commit="abc"))  # no row
    items.put(dict(base, id="012", kind="plan", title="Grind spot recommender"))  # open
    items.put(dict(base, id="N0000001", kind="order", title="An order"))  # no ROADMAP row
    doc = al_loop.tick(deps=deps(root), no_push=True)
    recs = al_loop.Items(root).all()
    assert recs["001"]["state"] == "superseded"
    assert recs["GONE-ROW"]["state"] == "superseded"
    assert recs["GONE-ROW"]["keep_ref"] == "refs/al/keep/GONE-ROW"  # WIP never dropped
    assert recs["012"]["state"] == "failed" and recs["N0000001"]["state"] == "failed"
    assert any("001: failed record superseded" in s for s in doc["log"])
    assert row(doc, "001") is None and row(doc, "GONE-ROW") is None
    assert row(doc, "012")["state"] == "failed"
    assert {p["id"] for p in al_loop.parked_items(root, None, NOW)} == {"012", "N0000001"}
    # an unreadable ROADMAP (no rows) supersedes nothing
    step = importlib.import_module("loop_steps.failed_supersede")
    items.put(dict(base, id="013", kind="plan", title="Season pass tracker"))

    class T:
        pass

    t = T()
    t.items = items
    assert step.post_work(t, [], [], []) is None
    assert items.get("013")["state"] == "failed"


@pytest.mark.git
def test_gate_log_naming_only_foreign_tests_ends_at_round_0(tmp_path):
    root, wt = git_world(tmp_path)
    items = al_loop.Items(root)
    items.put(dict(items.get("012"), finished=al_loop.iso(NOW - 3600)))
    head = git(root, "rev-parse", "main")
    sp = FakeSpawn()
    doc = al_loop.tick(deps=review_deps(root, sp, gates=lambda cwd: (False, FOREIGN)),
                       no_push=True)
    rec = al_loop.Items(root).get("012")
    assert sp.calls == []  # no fix spawn, no verifier
    assert rec["state"] == "adjudicate" and rec["rounds"] == 0
    assert rec["error"] == ("gate failure outside the lane diff: "
                            "tests/test_other.py::test_x, tests/test_other.py::test_y[a-b]")
    assert rec["keep_ref"] == "refs/al/keep/012"
    assert git(root, "rev-parse", "refs/al/keep/012") == rec["commit"]
    assert git(root, "rev-parse", "main") == head
    assert "outside the lane diff" in git(root, "log", "-1", "--format=%s", rec["commit"])
    assert row(doc, "012")["state"] == "adjudicate"
    assert [p["id"] for p in al_loop.parked_items(root, None, NOW)] == ["012"]
    # the parser: doubt means "not foreign" (the fix rounds run)
    changed = {"feature.txt"}
    assert loop_gatefail.foreign_only(FOREIGN, changed) == [
        "tests/test_other.py::test_x", "tests/test_other.py::test_y[a-b]"]
    assert loop_gatefail.foreign_only(FOREIGN, {"tests\\test_other.py"}) == []
    cut = FOREIGN.replace("FAILED tests/test_other.py::test_x - AssertionError: boom\n", "")
    assert loop_gatefail.foreign_only(cut, changed) == []  # tail cut a FAILED line
    assert loop_gatefail.foreign_only(FOREIGN.replace("2 failed, 9 passed in 1.23s\n", ""),
                                      changed) == []  # no counts line
    assert loop_gatefail.foreign_only("1 failed", changed) == []
    assert loop_gatefail.foreign_only("npm test --prefix app rc=1\nnot ok 1", changed) == []
    err = ("ERROR tests/test_feature.py - ImportError\n"
           "FAILED tests/test_other.py::test_x\n"
           "== 1 failed, 1 error in 0.50s ==\n")
    assert loop_gatefail.foreign_only(err, {"tests/test_feature.py"}) == []
    assert loop_gatefail.foreign_only(err, changed) == [
        "tests/test_feature.py", "tests/test_other.py::test_x"]


@pytest.mark.git
def test_gate_failure_in_the_lane_diff_still_gets_fix_rounds(tmp_path):
    root, wt = git_world(tmp_path)
    (wt / "tests").mkdir()
    (wt / "tests" / "test_feature.py").write_text("def test_a():\n    pass\n", newline="\n")
    red = ("python -m pytest -q rc=1\n"
           "FAILED tests/test_feature.py::test_a - assert 0\n"
           "FAILED tests/test_other.py::test_x\n"
           "2 failed, 3 passed in 0.40s\n")

    def fix(kw):  # a real fix changes the tree (the gate cache keys on it)
        (Path(kw["cwd"]) / "fixed.txt").write_text("fix\n", newline="\n")
        return {"rc": 0}

    sp = FakeSpawn([fix, {"rc": 0, "error": None, "result": "fine\nVERDICT: PASS"}])
    calls = {"n": 0}

    def gates(cwd):
        calls["n"] += 1
        return (False, red) if calls["n"] == 1 else (True, "green")

    al_loop.tick(deps=review_deps(root, sp, gates=gates), no_push=True)
    rec = al_loop.Items(root).get("012")
    assert sp.calls[0]["writes_code"] is True  # a fix round ran
    assert rec["rounds"] == 1 and "gate_foreign" not in rec
    assert rec["state"] == "merged" and rec["verdict"] == "PASS"
