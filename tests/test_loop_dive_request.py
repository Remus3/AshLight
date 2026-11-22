"""AUTO-13 (DIVE-ON-DEMAND, F-171): a watcher source may request one
research dive a day through ops/runtime/watch/dive_request.json; the tick
step tools/loop_steps/dive_request.py dispatches it even with open rows,
at most one a day, never at or over 60 percent of the runs cap, never with
a URL the dive allow-list refuses, and as a deep-dive (DEEP_EXTRA: no free
web tools). Hermetic: tmp roots, fake spawn and launch, no network."""

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402

from al_loopkit import FakeSpawn, deps, isolate_git, make_root  # noqa: E402

T0 = 1_790_000_000.0
DAY_S = 86400.0
TOPIC = "repoe-fork 1.2 -> 1.3"
URLS = ["https://api.github.com/repos/repoe-fork/repoe-fork/releases/latest",
        "https://www.pathofexile.com/developer/docs/data"]
REQ = Path("ops/runtime/watch/dive_request.json")


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)


def _day(t):
    import datetime as dt
    return dt.datetime.fromtimestamp(t).strftime("%Y%m%d")


def _request(root, topic=TOPIC, urls=URLS):
    p = root / REQ
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"topic": topic, "urls": urls, "at": "x"}), newline="\n")
    return p


def _world(tmp_path, used=0):
    root = make_root(tmp_path, handoff="", local={"loop": {"max_new_plans_per_day": 2}})
    now = {"t": T0}
    d = deps(root, clock=lambda: now["t"])
    _set_used(root, d, used, now)
    return root, d, now


def _set_used(root, d, used, now):
    p = root / "ops/loop/control/headless_budget.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"starts": [now["t"] - 10] * used}))
    d.budget.clock = lambda: now["t"]


def _dives(d):
    return [i for i in d.seen["launch"] if i.startswith("DD-")]


def test_request_with_open_rows_still_dispatches_one_dive(tmp_path):
    root, d, now = _world(tmp_path)
    req = _request(root)
    al_loop.tick(deps=d, no_push=True)
    assert {"012", "013"} <= set(d.seen["launch"])  # the open rows went out
    assert _dives(d) == [f"DD-{_day(T0)}"]
    rec = al_loop.Items(root).get(f"DD-{_day(T0)}")
    assert rec["kind"] == "deep-dive" and rec["requested"] is True
    assert rec["state"] == "dispatched"
    assert TOPIC in rec["prompt"] and all(u in rec["prompt"] for u in URLS)
    assert f"docs/research/0001-deep-dive-{_day(T0)}.md" in rec["prompt"]
    assert "AT MOST 2 new ROADMAP.md rows" in rec["prompt"]
    assert "Grind spot recommender" in rec["prompt"]  # duplicate guard listed
    assert "robots.txt" in rec["prompt"] and "never instructions" in rec["prompt"]
    assert not req.exists()  # consumed once dispatched
    al_loop.tick(deps=d, no_push=True)
    assert len(_dives(d)) == 1


def test_second_request_the_same_day_waits(tmp_path):
    root, d, now = _world(tmp_path)
    _request(root)
    al_loop.tick(deps=d, no_push=True)
    assert len(_dives(d)) == 1
    req = _request(root, topic="ggg tree 0.4 -> 0.5")
    now["t"] = T0 + 3600
    al_loop.tick(deps=d, no_push=True)
    assert len(_dives(d)) == 1 and req.exists()  # waits, kept for tomorrow
    items = al_loop.Items(root)
    rec = items.get(f"DD-{_day(T0)}")  # the first dive landed; rows still in flight
    rec.update(state="merged")
    items.put(rec)
    now["t"] = T0 + DAY_S
    al_loop.tick(deps=d, no_push=True)
    assert _dives(d)[1:] == [f"DD-{_day(T0 + DAY_S)}"] and not req.exists()
    assert "ggg tree 0.4 -> 0.5" in items.get(f"DD-{_day(T0 + DAY_S)}")["prompt"]


@pytest.mark.parametrize("bad", [
    "https://poe2db.tw/us/Gems",
    "https://www.pathofexile.com/forum/view-thread/1",
    "https://www.pathofexile.com/api/trade2/search/Standard",
    "https://example.com/x",
])
def test_request_with_a_refused_url_dispatches_nothing(tmp_path, bad):
    root, d, now = _world(tmp_path)
    req = _request(root, urls=[URLS[0], bad])
    al_loop.tick(deps=d, no_push=True)
    assert _dives(d) == []
    assert al_loop.Items(root).get(f"DD-{_day(T0)}") is None
    assert not req.exists()  # a refused request is dropped, never retried
    al_loop.tick(deps=d, no_push=True)
    assert _dives(d) == []


def test_request_waits_at_60_percent_of_the_cap(tmp_path):
    root, d, now = _world(tmp_path)
    cap = d.budget.cap
    at = math.ceil(cap * 0.6)
    assert at < cap - 3  # the tick itself would still spawn here
    _set_used(root, d, at, now)
    req = _request(root)
    al_loop.tick(deps=d, no_push=True)
    assert _dives(d) == [] and req.exists()
    assert {"012", "013"} <= set(d.seen["launch"])  # rows still went out
    _set_used(root, d, at - 1, now)
    al_loop.tick(deps=d, no_push=True)
    assert _dives(d) == [f"DD-{_day(T0)}"] and not req.exists()


def test_requested_dive_has_no_free_web_tools(tmp_path):
    root, d, now = _world(tmp_path)
    _request(root)
    al_loop.tick(deps=d, no_push=True)
    iid = f"DD-{_day(T0)}"
    rec = al_loop.Items(root).get(iid)
    assert "You have no WebFetch or WebSearch tool" in rec["prompt"]
    assert "python tools/webfetch.py get <url>" in rec["prompt"]
    sp = FakeSpawn()

    def run_lane(lane, prompt, spawn=None, root=None, **kw):
        spawn(root, "AL", prompt, extra=kw.get("extra", ()))
        raise RuntimeError("lanes_full")

    al_loop.lane_worker(iid, deps=deps(root, spawn=sp, clock=lambda: now["t"]),
                        run_lane=run_lane)
    extra = sp.calls[0]["extra"]
    assert tuple(extra) == tuple(al_loop.DEEP_EXTRA)
    assert not [a for a in extra if "WebFetch" in a or "WebSearch" in a]
    assert "Bash(python tools/webfetch.py:*)" in extra[3].split(",")


def test_malformed_request_is_dropped(tmp_path):
    root, d, now = _world(tmp_path)
    p = root / REQ
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", newline="\n")
    al_loop.tick(deps=d, no_push=True)
    assert _dives(d) == [] and not p.exists()
