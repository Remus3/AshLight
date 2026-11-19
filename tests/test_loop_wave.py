"""WAVE-INTERPLAY (AUTO-06, F-033, decision 0055): the loop and a session
never work the same row. A row carrying BLOCKED is listed with its reason
(the text after 'BLOCKED:' up to the next full stop, at most 60 characters)
and never dispatched; right before a dispatch the tick re-reads the row from
HEAD (git show HEAD:ROADMAP.md plus the row files) and skips it when a
session committed a BLOCKED tag after the work list was read."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402
import loop_work  # noqa: E402

from al_loopkit import deps, git, isolate_git, make_root, real_git  # noqa: E402

A, B, C = "GRIND-012", "SEASON-013", "MAPS-014"
RM = f"""# AshLight roadmap

- [x] SKEL Skeleton -- done 2026-10-04
- [ ] {A} Grind spot recommender
- [ ] {B} Season pass tracker
"""
NEW_C = f"- [ ] {C} Map tracker\n"


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)  # TESTS-A-19


def _running():
    return [{"index": i, "state": "RUNNING", "lane": n}
            for i, n in enumerate(("build", "data", "review"))]


def _checklist(root, d):
    doc = json.loads((root / d.kit.PROGRESS_REL / "loop.json").read_text(encoding="utf-8"))
    return doc["checklist"]


def _git_world(tmp_path, roadmap=RM):
    root = make_root(tmp_path, roadmap=roadmap, handoff="")
    new = root / "docs" / "roadmap" / "new"
    new.mkdir(parents=True)
    (new / f"{C}.md").write_text(NEW_C, newline="\n")
    git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("ops/\n", newline="\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def _commit_tag(root, rel, old, new):
    """A session claims a row: the tag is committed, then the working file is
    put back untagged, so only HEAD carries it (the check reads HEAD)."""
    p = root / rel
    text = p.read_text(encoding="utf-8")
    p.write_text(text.replace(old, new), newline="\n")
    git(root, "commit", "-q", "-m", f"claim {old}", "--", rel)
    p.write_text(text, newline="\n")


def test_blocked_reason_is_echoed_in_the_checklist(tmp_path):
    long_why = "operator act: " + "x" * 80
    rm = (f"# AshLight roadmap\n\n"
          f"- [ ] {A} Grind spot recommender BLOCKED: session wave 5. ACCEPT: tests pass.\n"
          f"- [ ] {B} Season pass tracker BLOCKED: {long_why}.\n"
          f"- [ ] {C} Map tracker BLOCKED (operator plays once)\n"
          f"- [ ] OPEN-015 Free row\n")
    root = make_root(tmp_path, roadmap=rm, handoff="")
    d = deps(root, lane_state=_running)
    _rows, work, skipped = al_loop.Tick(d).work_list()
    why = {s["id"]: s["reason"] for s in skipped}
    assert why[A] == "BLOCKED: session wave 5"
    assert why[B].startswith("BLOCKED: operator act: xxx")
    assert len(why[B]) - len("BLOCKED: ") <= 60 and why[B].endswith("...")
    assert why[C] == "BLOCKED: (operator plays once)"
    assert [w["id"] for w in work] == ["OPEN-015"]
    assert loop_work.blocked_reason("BLOCKED") == "BLOCKED: operator act (see ROADMAP)"
    assert loop_work.blocked_reason("unblocked row") is None
    al_loop.tick(deps=d, no_push=True)
    rows = {r["id"]: json.dumps(r) for r in _checklist(root, d)}
    assert "BLOCKED: session wave 5" in rows[A]
    assert "BLOCKED: operator act: xxx" in rows[B]
    assert "operator plays once" in rows[C]
    assert d.seen["launch"] == []


@pytest.mark.git
def test_row_tagged_between_work_list_and_dispatch_is_skipped(tmp_path):
    root = _git_world(tmp_path)
    d = deps(root, git=real_git)
    t = al_loop.Tick(d)
    _rows, work, _skipped = t.work_list()
    assert {w["id"] for w in work} == {A, B, C}
    # two sessions claim A (ROADMAP.md) and C (its row file) after the read
    _commit_tag(root, "ROADMAP.md", f"{A} Grind spot recommender",
                f"{A} Grind spot recommender BLOCKED: session wave 5.")
    _commit_tag(root, f"docs/roadmap/new/{C}.md", f"{C} Map tracker",
                f"{C} Map tracker BLOCKED: session.")
    assert "BLOCKED" not in (root / "ROADMAP.md").read_text(encoding="utf-8")
    t.dispatch(work)
    assert d.seen["launch"] == [B]
    assert any(f"{A}: not dispatched, BLOCKED: session wave 5 (at HEAD)" in s for s in t.log)
    assert any(f"{C}: not dispatched, BLOCKED: session (at HEAD)" in s for s in t.log)
    assert al_loop.Items(root).get(A) is None and al_loop.Items(root).get(C) is None
    # a row closed in between (its done file) is not dispatched either
    t2 = al_loop.Tick(deps(root, git=real_git))
    _rows, work2, _ = t2.work_list()
    done = root / "docs" / "roadmap" / "done"
    done.mkdir(parents=True)
    (done / f"{A}.md").write_text(" -- done 2026-11-18 (session)\n", newline="\n")
    git(root, "add", "--", f"docs/roadmap/done/{A}.md")
    git(root, "commit", "-q", "-m", "close A")
    t2.d.seen["launch"].clear()
    t2.dispatch([w for w in work2 if w["id"] == A])
    assert t2.d.seen["launch"] == []
    assert any(f"{A}: not dispatched" in s for s in t2.log)


@pytest.mark.git
def test_dry_run_lists_only_untagged_rows_as_would_dispatch(tmp_path):
    rm = RM + "- [ ] OPEN-015 Free row BLOCKED: gate.\n"
    root = _git_world(tmp_path, roadmap=rm)
    _commit_tag(root, f"docs/roadmap/new/{C}.md", f"{C} Map tracker",
                f"{C} Map tracker BLOCKED: session wave 5.")
    d = deps(root, git=real_git)
    doc = al_loop.tick(dry_run=True, deps=d, no_push=True)
    would = [s for s in doc["log"] if "would dispatch" in s]
    assert sorted(s.split(":")[0] for s in would) == [A, B]
    assert not any(s.startswith("OPEN-015") and "would dispatch" in s for s in doc["log"])
    assert any(f"{C}: not dispatched, BLOCKED: session wave 5 (at HEAD)" in s
               for s in doc["log"])
    assert d.spawn.calls == [] and d.seen["launch"] == []
