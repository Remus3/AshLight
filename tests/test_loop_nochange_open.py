"""LOOP-NOCHANGE-OPEN (decision 0055 amendment 2026-11-24): an empty plan run
(rc 0, clean worktree, no blocked marker) on a ROADMAP row that is still open
is refused, retried up to MAX_ATTEMPTS and then a listed gave-up, never the
silent done state no-change; an old no-change record on an open row is listed
in the checklist; the lane allow-list grants tools/docs_fresh.py only."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_lane  # noqa: E402
import al_loop  # noqa: E402

from al_loopkit import (  # noqa: E402
    deps, git_world, isolate_git, make_root, real_git, stub_git)

BUSY = [{"index": i, "state": "RUNNING", "lane": n}
        for i, n in enumerate(("build", "data", "review"))]


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)
    stub_git(monkeypatch)


def _empty_run(tmp_path, attempts=None, kind="plan"):
    root, wt = git_world(tmp_path, kind=kind)
    (wt / "feature.txt").unlink()
    if attempts is not None:
        items = al_loop.Items(root)
        items.put(dict(items.get("012"), attempts=attempts))
    return root


def _close_row(root):
    rm = root / "ROADMAP.md"
    rm.write_text(al_loop.flip_roadmap(rm.read_text(), "012", "done"), newline="\n")


def _row(doc, iid):
    return next((r for r in doc["checklist"] if r["id"] == iid), None)


@pytest.mark.git
def test_empty_run_on_an_open_row_is_refused_not_no_change(tmp_path):
    root = _empty_run(tmp_path, attempts=1)
    d = deps(root, git=real_git, lane_state=lambda: BUSY)
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "refused" and rec["error"] == "no change, row still open"
    assert al_loop.dispatchable(rec, {"012"})


@pytest.mark.git
def test_empty_run_on_an_open_row_is_redispatched(tmp_path):
    root = _empty_run(tmp_path, attempts=1)
    d = deps(root, git=real_git)
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert "012" in d.seen["launch"] and rec["state"] == "dispatched"
    assert rec["attempts"] == 2


@pytest.mark.git
def test_empty_runs_out_of_attempts_give_up_and_are_listed(tmp_path):
    root = _empty_run(tmp_path, attempts=al_loop.MAX_ATTEMPTS)
    d = deps(root, git=real_git)
    al_loop.tick(deps=d, no_push=True)
    doc = al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get("012")
    assert rec["state"] == "gave-up" and "012" not in d.seen["launch"]
    assert _row(doc, "012")["state"] == "gave-up"


@pytest.mark.git
def test_empty_run_on_a_closed_row_stays_no_change(tmp_path):
    root = _empty_run(tmp_path, attempts=1)
    _close_row(root)
    d = deps(root, git=real_git)
    doc = al_loop.tick(deps=d, no_push=True)
    assert al_loop.Items(root).get("012")["state"] == "no-change"
    assert _row(doc, "012") is None


@pytest.mark.git
def test_empty_non_plan_run_stays_no_change(tmp_path):
    root = _empty_run(tmp_path, kind="order")
    d = deps(root, git=real_git, lane_state=lambda: BUSY)
    al_loop.tick(deps=d, no_push=True)
    assert al_loop.Items(root).get("012")["state"] == "no-change"


def _old_record(tmp_path):
    root = make_root(tmp_path, handoff="")
    al_loop.Items(root).put({"id": "012", "kind": "plan", "state": "no-change",
                             "attempts": 1, "title": "Grind spot recommender",
                             "label": "l", "rearmed": False})
    return root


def test_old_no_change_record_on_an_open_row_is_listed(tmp_path):
    root = _old_record(tmp_path)
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    row = _row(doc, "012")
    assert row is not None and row["state"] == al_loop.NO_CHANGE_OPEN
    assert row["state"] == "no-change, row still open"
    assert "012" not in d.seen["launch"]  # listed for a session, not retried


def test_old_no_change_record_on_a_closed_row_is_not_listed(tmp_path):
    root = _old_record(tmp_path)
    _close_row(root)
    doc = al_loop.tick(deps=deps(root), no_push=True)
    assert _row(doc, "012") is None


def test_lane_tools_grant_docs_fresh_but_not_electron_pin():
    assert "Bash(python tools/docs_fresh.py:*)" in al_lane.GATE_TOOLS.split(",")
    assert not any("electron_pin" in t for t in al_lane.CODE_EXTRA)
