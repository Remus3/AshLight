"""LOOP-TESTS-CARVE: the tools/al_loop.py tests of idle deep dives, moved
unchanged from tests/test_al_loop.py. Owners later: AUTO-04, then AUTO-13,
which edit this file and never tests/test_al_loop.py. AUTO-13 rewrote the
idle-dive test for the weekly rule."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402

from al_loopkit import (  # noqa: E402
    ROADMAP, FakeSpawn, deps, isolate_git, make_root)


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)  # TESTS-A-19


DAY_S = 86400.0
T0 = 1_790_000_000.0


def _day(t):
    import datetime as dt
    return dt.datetime.fromtimestamp(t).strftime("%Y%m%d")


def test_idle_dive_runs_at_most_once_in_7_days(tmp_path):
    """AUTO-13: the idle dive is weekly whatever the last dive proposed: the
    first idle tick dispatches DD-<date> (prompt as before); while the newest
    dive in the history is under 7 days old no idle dive runs; on day 7 the
    next one does."""
    rm = ROADMAP.replace("- [ ] ", "- [x] ")
    root = make_root(tmp_path, roadmap=rm, handoff="",
                     local={"loop": {"max_new_plans_per_day": 1}, "web_data": True})
    now = {"t": T0}
    history = []  # dive dates the fake git log reports, oldest first

    def git(args, cwd, input=None, lock=None):
        import subprocess
        if args and args[0] == "log" and "docs/research/" in args:
            out = "".join(f"@\ndocs/research/{i + 1:04d}-deep-dive-{d}.md\nROADMAP.md\n"
                          for i, d in enumerate(reversed(history)))
            return subprocess.CompletedProcess(["git", *args], 0, out, "")
        if args and args[0] == "config":
            return subprocess.CompletedProcess(["git", *args], 1, "", "")
        return subprocess.CompletedProcess(["git", *args], 128, "", "not a repo")

    d = deps(root, clock=lambda: now["t"], git=git)
    al_loop.tick(deps=d, no_push=True)
    assert len(d.seen["launch"]) == 1 and d.seen["launch"][0] == f"DD-{_day(T0)}"
    items = al_loop.Items(root)
    rec = items.get(d.seen["launch"][0])
    assert rec["kind"] == "deep-dive" and "AT MOST 1 new ROADMAP.md rows" in rec["prompt"]
    assert "robots.txt" in rec["prompt"] and "Grind spot recommender" in rec["prompt"]
    assert "docs/research/0001-deep-dive-" in rec["prompt"]
    al_loop.tick(deps=d, no_push=True)  # same day: never a second one
    assert len(d.seen["launch"]) == 1
    # the dive lands (it proposed a row: that no longer resets to daily)
    rec.update(state="merged")
    items.put(rec)
    history.append(_day(T0))
    for n in range(1, 7):
        now["t"] = T0 + n * DAY_S
        al_loop.tick(deps=d, no_push=True)
        assert len(d.seen["launch"]) == 1, f"day {n}"
    now["t"] = T0 + 7 * DAY_S
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"][1:] == [f"DD-{_day(T0 + 7 * DAY_S)}"]


def test_next_dive_counts_an_open_dives_claimed_number(tmp_path):
    """RES-DIVE-NUMBER-COLLISION: DD-20261125..27 each claimed 0064 because
    an unmerged dive's note is not in the main tree yet. An existing 0064
    file and an open dive holding 0065 give the next dive 0066, for the
    idle dive and the requested dive alike."""
    import loop_prompts
    from loop_steps import dive_request
    rm = ROADMAP.replace("- [ ] ", "- [x] ")
    # web_data on: LOOP-DIVE-OFFLINE-SKIP skips an offline idle dive
    root = make_root(tmp_path, roadmap=rm, handoff="",
                     local={"loop": {"max_new_plans_per_day": 1}, "web_data": True})
    research = root / "docs" / "research"
    research.mkdir(parents=True, exist_ok=True)
    (research / "0064-companion-landscape.md").write_text("x\n", encoding="ascii")
    items = al_loop.Items(root)
    items.put({"id": "DD-20261125", "kind": "deep-dive", "state": "ran",
               "prompt": "Write docs/research/0065-deep-dive-20261125.md now"})
    p = loop_prompts.deep_dive_prompt(root, "20261126", 1, {})
    assert "docs/research/0066-deep-dive-20261126.md" in p
    p = dive_request.requested_dive_prompt(root, "20261126", 1, {}, "t",
                                           ["https://api.github.com/repos/a/b"])
    assert "docs/research/0066-deep-dive-20261126.md" in p
    # the tick's idle dive takes the same next free number
    def git(args, cwd, input=None, lock=None):
        import subprocess
        code = 0 if args and args[0] == "log" else (1 if args[:1] == ["config"] else 128)
        return subprocess.CompletedProcess(["git", *args], code, "", "")

    d = deps(root, clock=lambda: T0, git=git)
    # an unmerged dive that holds its note outside the main tree, not in review
    held = items.get("DD-20261125")
    held.update(state="failed", error="red gate")
    items.put(held)
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == [f"DD-{_day(T0)}"]
    rec = items.get(f"DD-{_day(T0)}")
    assert rec and f"docs/research/0066-deep-dive-{_day(T0)}.md" in rec["prompt"]


def _dive_git(history):
    """A fake git runner whose log lists the given dive dates (oldest first)."""
    def git(args, cwd, input=None, lock=None):
        import subprocess
        if args and args[0] == "log" and "docs/research/" in args:
            out = "".join(f"@\ndocs/research/{i + 1:04d}-deep-dive-{d}.md\n"
                          for i, d in enumerate(reversed(history)))
            return subprocess.CompletedProcess(["git", *args], 0, out, "")
        if args and args[0] == "config":
            return subprocess.CompletedProcess(["git", *args], 1, "", "")
        return subprocess.CompletedProcess(["git", *args], 128, "", "not a repo")
    return git


def _offline_root(tmp_path, web_data):
    rm = ROADMAP.replace("- [ ] ", "- [x] ")
    local = {"loop": {"max_new_plans_per_day": 1}}
    if web_data is not None:
        local["web_data"] = web_data
    return make_root(tmp_path, roadmap=rm, handoff="", local=local)


def _paste(root, mtime):
    import os
    p = root / "docs" / "research" / "pasted" / "client-lines.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("pasted text\n", newline="\n")
    os.utime(p, (mtime, mtime))
    return p


def test_offline_dive_with_no_newer_paste_dispatches_nothing(tmp_path):
    """LOOP-DIVE-OFFLINE-SKIP: web_data off (absent or False) and no pasted
    file newer than the last dive: no dive is dispatched, and the checklist
    names the reason on one line."""
    last = T0 - 8 * DAY_S  # past the weekly backoff
    for n, web in enumerate((None, False)):
        root = _offline_root(tmp_path / f"r{n}", web)
        _paste(root, last - DAY_S)  # older than the last dive
        d = deps(root, clock=lambda: T0, git=_dive_git([_day(last)]))
        doc = al_loop.tick(deps=d, no_push=True)
        assert d.seen["launch"] == []
        assert al_loop.Items(root).get(f"DD-{_day(T0)}") is None
        lines = [str(x) for x in doc["checklist"]]
        hits = [x for x in lines if "deep-dive" in x]
        assert len(hits) == 1, lines
        assert "web data off" in hits[0] and "pasted" in hits[0] and "skipped" in hits[0]
        assert any("deep-dive skipped: web data off" in s for s in doc["log"])


def test_offline_dive_with_no_paste_and_no_history_dispatches_nothing(tmp_path):
    root = _offline_root(tmp_path, False)
    d = deps(root, clock=lambda: T0, git=_dive_git([]))
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == []


def test_newer_paste_or_web_data_on_still_dispatches(tmp_path):
    """A pasted file newer than the last dive, or web_data on, dispatches the
    idle dive as before."""
    last = T0 - 8 * DAY_S
    root = _offline_root(tmp_path / "paste", False)
    _paste(root, last + DAY_S)
    d = deps(root, clock=lambda: T0, git=_dive_git([_day(last)]))
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == [f"DD-{_day(T0)}"]

    root = _offline_root(tmp_path / "first", False)  # no dive yet, a paste exists
    _paste(root, last)
    d = deps(root, clock=lambda: T0, git=_dive_git([]))
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == [f"DD-{_day(T0)}"]

    root = _offline_root(tmp_path / "web", True)
    d = deps(root, clock=lambda: T0, git=_dive_git([_day(last)]))
    doc = al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == [f"DD-{_day(T0)}"]
    assert not any("skipped" in str(x) and "deep-dive" in str(x) for x in doc["checklist"])


def test_dive_offline_reason_reads_research_names(tmp_path):
    """The last dive date also comes from the research folder's
    NNNN-deep-dive-<date>.md names when git has no history."""
    import loop_work
    root = _offline_root(tmp_path, False)
    (root / "docs" / "research" / "0062-deep-dive-20261121.md").write_text("x\n")
    import datetime as dt
    _paste(root, dt.datetime(2026, 11, 20, 12).timestamp())
    assert loop_work.dive_offline_reason(root, []) == loop_work.DIVE_OFFLINE_REASON
    _paste(root, dt.datetime(2026, 11, 21, 9).timestamp())  # same day as the dive
    assert loop_work.dive_offline_reason(root, []) is None


def test_dive_backoff_is_weekly_whatever_was_proposed():
    import datetime as dt
    from loop_roadmap import dive_backoff
    today = dt.date(2026, 11, 21)
    assert not dive_backoff([], today)
    assert dive_backoff([("20261120", 1)], today)  # a plan proposed: still weekly
    assert dive_backoff([("20261115", 0)], today)
    assert not dive_backoff([("20261114", 1)], today)
    assert not dive_backoff([("bad", 0)], today)


def test_deep_dive_checks_cap_and_dupes(tmp_path):
    root = make_root(tmp_path, local={"loop": {"max_new_plans_per_day": 1}})
    wt = tmp_path / "wt"
    (wt / "docs" / "research").mkdir(parents=True)
    (wt / "ROADMAP.md").write_text(ROADMAP + "- [ ] 015 (build) Grind spot recommender v2\n"
                                   "- [ ] 016 (data) Lifeskill planner\n", newline="\n")
    t = al_loop.Tick(deps(root))
    out = t.extra_checks({"kind": "deep-dive", "date": "20261005"}, wt)
    assert any("cap is 1" in f for f in out)
    assert any("row 015" in f and "duplicates" in f for f in out)
    assert any("missing docs/research" in f for f in out)


def test_lane_worker_refusal_and_deep_dive_tools(tmp_path):
    root = make_root(tmp_path)
    items = al_loop.Items(root)
    items.put({"id": "DD-1", "kind": "deep-dive", "state": "dispatched", "lane": "build",
               "prompt": "p", "title": "t", "label": "l"})
    sp = FakeSpawn()

    def run_lane(lane, prompt, spawn=None, root=None, **kw):
        spawn(root, "AL", prompt, extra=("x",))
        raise RuntimeError("lanes_full")

    assert al_loop.lane_worker("DD-1", deps=deps(root, spawn=sp), run_lane=run_lane) == 1
    tools = sp.calls[0]["extra"][3].split(",")
    # DIVE-FLOOR (decision 0050): no free web tools, only the allow-listed fetch
    assert not [a for a in sp.calls[0]["extra"] if "WebFetch" in a or "WebSearch" in a]
    assert "Bash(python tools/webfetch.py:*)" in tools
    assert items.get("DD-1")["state"] == "refused"
