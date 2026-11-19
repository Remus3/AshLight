"""LOOP-TESTS-CARVE: the tools/al_loop.py tests of idle deep dives, moved
unchanged from tests/test_al_loop.py. Owners later: AUTO-04, then AUTO-13,
which edit this file and never tests/test_al_loop.py."""

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


@pytest.mark.git
def test_idle_dispatches_one_deep_dive_per_day(tmp_path):
    rm = ROADMAP.replace("- [ ] ", "- [x] ")
    root = make_root(tmp_path, roadmap=rm, handoff="",
                     local={"loop": {"max_new_plans_per_day": 1}})
    d = deps(root)
    al_loop.tick(deps=d, no_push=True)
    assert len(d.seen["launch"]) == 1 and d.seen["launch"][0].startswith("DD-")
    rec = al_loop.Items(root).get(d.seen["launch"][0])
    assert rec["kind"] == "deep-dive" and "AT MOST 1 new ROADMAP.md rows" in rec["prompt"]
    assert "robots.txt" in rec["prompt"] and "Grind spot recommender" in rec["prompt"]
    assert "docs/research/0001-deep-dive-" in rec["prompt"]
    al_loop.tick(deps=d, no_push=True)
    assert len(d.seen["launch"]) == 1


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
