"""LOOP-ROWFILES-WORK (F-029, AUTO-03): the loop's work list reads its rows
through the loader tools/roadmap.py (ROADMAP.md plus docs/roadmap/new/ and
docs/roadmap/done/ files), waits on the `DEPENDS: <ids>` in a row's own
text, shows an id with no row as 'waits on <id> (no such row)' and never
dispatches it, and matches a row's brief on the exact id under
docs/plan/briefs/."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402
import loop_roadmap  # noqa: E402
import roadmap  # noqa: E402

from al_loopkit import GIT_TIMEOUT_S, deps, isolate_git, make_root, real_git  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)


ROADMAP = """# AshLight roadmap

- [x] SKELETON (build) The skeleton. -- done 2026-10-04 (session)
- [ ] ALPHA (build) First open row. ACCEPT: alpha works.
- [ ] BETA (data) Second open row. ACCEPT: beta works.
"""


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii", newline="\n")


def _new(root, text):
    return roadmap.write_new(root, text)


def _done(root, iid):
    return roadmap.write_done(root, iid, "test", date="2026-11-18")


def _checklist_state(doc, iid):
    return next(r for r in doc["checklist"] if r["id"] == iid).get("state")


@pytest.mark.git
def test_work_list_shows_rows_filed_and_closed_by_files(tmp_path):
    root = make_root(tmp_path, roadmap=ROADMAP, handoff="")
    _new(root, "- [ ] GAMMA (review) A filed row. ACCEPT: gamma works.\n")
    _new(root, "- [ ] DELTA (build) A filed row closed again. ACCEPT: delta.\n")
    _done(root, "BETA")   # a ROADMAP.md row closed by a done file
    _done(root, "DELTA")  # a filed row closed by a done file
    d = deps(root)
    rows, work, skipped = al_loop.Tick(d).work_list()
    by_id = {r["id"]: r for r in rows}
    assert set(by_id) == {"SKELETON", "ALPHA", "BETA", "GAMMA", "DELTA"}
    assert not by_id["BETA"]["open"] and not by_id["DELTA"]["open"]
    assert by_id["GAMMA"]["source"] == "new"
    plans = [w for w in work if w["kind"] == "plan"]
    assert [w["id"] for w in plans] == ["ALPHA", "GAMMA"]
    gamma = next(w for w in plans if w["id"] == "GAMMA")
    assert gamma["lane_hint"] == "review" and gamma["title"] == "A filed row."
    assert not [s for s in skipped if s.get("skip") == "waits"]
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["ALPHA", "GAMMA"]
    # the next tick sees a row filed after the first one, with no hand edit
    _new(root, "- [ ] EPSILON (data) Filed between ticks. ACCEPT: eps.\n")
    d2 = deps(root)
    al_loop.tick(deps=d2, no_push=True)
    assert d2.seen["launch"] == ["EPSILON"]


@pytest.mark.git
def test_row_waits_on_depends_and_opens_when_the_gate_closes(tmp_path):
    rm = ROADMAP.replace("Second open row.", "Second open row. DEPENDS: ALPHA.")
    root = make_root(tmp_path, roadmap=rm, handoff="")
    _new(root, "- [ ] GAMMA (build) Waits on two. DEPENDS: ALPHA, BETA. ACCEPT: g.\n")
    d = deps(root)
    rows, work, skipped = al_loop.Tick(d).work_list()
    assert [w["id"] for w in work if w["kind"] == "plan"] == ["ALPHA"]
    why = {s["id"]: s["reason"] for s in skipped if s.get("skip") == "waits"}
    assert why == {"BETA": "waits on ALPHA", "GAMMA": "waits on ALPHA, BETA"}
    doc = al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["ALPHA"]
    assert _checklist_state(doc, "BETA") == "waits on ALPHA"
    # ALPHA closes by a done file: BETA opens on the next tick, GAMMA still waits
    _done(root, "ALPHA")
    (al_loop.Items(root).dir / "ALPHA.json").unlink()
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["BETA"]
    assert _checklist_state(doc, "GAMMA") == "waits on BETA"
    # a dependency pruned into the archive counts as done
    _write(root / "docs/roadmap/archive/2026-11.md",
           "# ROADMAP archive 2026-11\n\n- [x] OLD (build) Archived. -- done 2026-11-01\n")
    _new(root, "- [ ] ZETA (build) Needs an archived row. DEPENDS: OLD. ACCEPT: z.\n")
    d = deps(root)
    al_loop.tick(deps=d, no_push=True)
    assert "ZETA" in d.seen["launch"]


@pytest.mark.git
def test_unknown_dependency_is_a_visible_wait_not_a_dispatch(tmp_path):
    rm = ROADMAP.replace("Second open row.", "Second open row. DEPENDS: NOPE-ROW, ALPHA.")
    root = make_root(tmp_path, roadmap=rm, handoff="")
    _new(root, "- [ ] GAMMA (build) A typo in its gate. DEPENDS: TYPO. ACCEPT: g.\n")
    d = deps(root)
    rows, work, skipped = al_loop.Tick(d).work_list()
    assert [w["id"] for w in work if w["kind"] == "plan"] == ["ALPHA"]
    why = {s["id"]: s["reason"] for s in skipped if s.get("skip") == "waits"}
    assert why == {"BETA": "waits on ALPHA; waits on NOPE-ROW (no such row)",
                   "GAMMA": "waits on TYPO (no such row)"}
    for _ in range(2):  # never dispatched, on any tick
        d = deps(root)
        doc = al_loop.tick(deps=d, no_push=True)
        assert "GAMMA" not in d.seen["launch"] and "BETA" not in d.seen["launch"]
        assert _checklist_state(doc, "GAMMA") == "waits on TYPO (no such row)"
        assert al_loop.Items(root).get("GAMMA") is None
    # the CLI loader agrees with the work list
    w = roadmap.waits(roadmap.load_rows(root))
    assert w["GAMMA"] == ["waits on TYPO (no such row)"]


def test_brief_matches_the_exact_id_only(tmp_path):
    rm = ROADMAP + ("- [ ] TC-OAUTH-REG (build) Register. ACCEPT: r.\n"
                    "- [ ] TC-OAUTH-REG-OPEN (build) Open it. ACCEPT: o.\n")
    root = make_root(tmp_path, roadmap=rm, handoff="")
    briefs = root / "docs/plan/briefs"
    _write(briefs / "TC-OAUTH-REG.md", "Brief of the register row.\nDepends on: BETA.\n")
    assert loop_roadmap.plan_doc(root, "TC-OAUTH-REG").startswith("Brief of the register")
    assert loop_roadmap.plan_doc(root, "TC-OAUTH-REG-OPEN") is None
    assert al_loop.plan_doc(root, "TC-OAUTH-RE") is None
    assert loop_roadmap.plan_doc(root, "../briefs/TC-OAUTH-REG") is None
    assert loop_roadmap.plan_doc(root, "") is None
    # the old docs/plans/<id>-*.md prefix glob is gone
    _write(root / "docs/plans/TC-OAUTH-REG-OPEN-x.md", "old plan doc\n")
    assert loop_roadmap.plan_doc(root, "TC-OAUTH-REG-OPEN") is None
    # a brief is prose: its Depends-on line gates nothing (F-029)
    d = deps(root)
    rows, work, skipped = al_loop.Tick(d).work_list()
    assert {"TC-OAUTH-REG", "TC-OAUTH-REG-OPEN"} <= {w["id"] for w in work}
    assert not [s for s in skipped if s.get("skip") == "waits"]


def test_plan_titles_read_row_files_and_the_archive(tmp_path):
    root = make_root(tmp_path, roadmap=ROADMAP, handoff="")
    _new(root, "- [ ] GAMMA (review) A filed row. ACCEPT: gamma works.\n")
    _write(root / "docs/roadmap/archive/2026-11.md",
           "# ROADMAP archive 2026-11\n\n- [x] OLD (build) An archived row. -- done x\n"
           "- [x] ALPHA (build) Archived copy of an id. -- done x\n")
    titles = al_loop.plan_titles(root)
    assert titles["GAMMA"] == "A filed row."
    assert titles["OLD"] == "An archived row. -- done x"
    assert titles["ALPHA"] == "First open row."  # the loaded row wins
    assert loop_roadmap.plan_titles(tmp_path / "missing") == {}


def _git_at(cwd, when, *args):
    import os
    env = dict(os.environ, GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when)
    r = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
                        "-c", "core.autocrlf=false", *args], cwd=str(cwd),
                       capture_output=True, text=True, env=env, timeout=GIT_TIMEOUT_S)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.mark.git
def test_flip_time_sees_the_done_file_commit(tmp_path):
    import datetime as _dt
    root = make_root(tmp_path, roadmap=ROADMAP, handoff="")
    day = "2026-10-0{}T10:00:00+00:00".format
    _git_at(root, day(1), "init", "-q", "-b", "main")
    _git_at(root, day(1), "add", "-A")
    _git_at(root, day(1), "commit", "-q", "-m", "rows")
    _done(root, "ALPHA")
    _git_at(root, day(2), "add", "-A")
    _git_at(root, day(2), "commit", "-q", "-m", "close ALPHA by a file")
    # a later fold writes the [x] line into ROADMAP.md: the earlier close wins
    rm = root / "ROADMAP.md"
    rm.write_text(al_loop.flip_roadmap(rm.read_text(), "ALPHA", "done"), newline="\n")
    _git_at(root, day(3), "add", "-A")
    _git_at(root, day(3), "commit", "-q", "-m", "fold")
    when = al_loop.roadmap_flip_time(real_git, root, "ALPHA")
    assert _dt.datetime.fromisoformat(when) == _dt.datetime.fromisoformat(day(2))
    _done(root, "BETA")
    _git_at(root, day(4), "add", "-A")
    _git_at(root, day(4), "commit", "-q", "-m", "close BETA by a file")
    when = al_loop.roadmap_flip_time(real_git, root, "BETA")
    assert _dt.datetime.fromisoformat(when) == _dt.datetime.fromisoformat(day(4))
    assert al_loop.roadmap_flip_time(real_git, root, "NOPE") is None


@pytest.mark.git
def test_rearm_uses_the_row_depends_not_a_plan_doc(tmp_path):
    rm = ROADMAP.replace("Second open row.", "Second open row. DEPENDS: ALPHA.")
    root = make_root(tmp_path, roadmap=rm, handoff="")
    _done(root, "ALPHA")
    t0 = 1_790_000_000.0
    items = al_loop.Items(root)
    items.put({"id": "BETA", "kind": "plan", "state": "no-change", "attempts": 1,
               "dispatched": al_loop.iso(t0 - 3600), "title": "t", "label": "l"})
    items.put({"id": "ALPHA", "kind": "plan", "state": "merged", "title": "t", "label": "l",
               "merged_at": al_loop.iso(t0 - 1800)})
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == ["BETA"]
    assert any("BETA: re-armed" in s for s in doc["log"])
    assert items.get("BETA")["rearmed"] is True
