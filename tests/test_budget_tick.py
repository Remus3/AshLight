"""RUN-BUDGET-TESTS-DET (F-108, research 0048 R6): the cost of one core
loop pass, Core.tick_all (RUN-SEAMS), on two fixtures.

- worst case: 500 saved maps plus 200 session maps and an open one (the
  RUN-LADDER-TICK fixture);
- campaign: a four-hour levelling session from tools/synth_client.py fed
  through Core.feed_line.

B2 (timed): one full tick under 2 ms on the worst case, under 0.3 ms on
the campaign. The cost is the best of five medians of 20 ticks (noise on a
shared box only adds time, a real regression raises every round), widened
by fleet_test_guard.budget() while other suites hold the gate; under
AL_CI=1 the assert skips with the value printed (decision 0080).

B3 (deterministic): one idle tick makes at most 20 stat calls and opens no
file. Each core gets its own hot reload registry, so watches left by other
tests' cores (held weakly until a collection) are not counted.

Both fixtures have a local.json and the two cached data files (written an
hour ago), so a stat finds a real file and a re-read would show.
"""

import json
import os
import sys
import time
from pathlib import Path

import pytest

import fleet_test_guard
from ci_timing import skip_if_ci_timing
from server.al import acts, hotreload, runs
from server.al.core import Core
from server.al.theorycraft import basetypes

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import synth_client  # noqa: E402

STAT_MAX = 20  # B3
WORST_S = 0.002  # B2, worst case
CAMPAIGN_S = 0.0003  # B2, campaign

# One audit hook for the module (hooks cannot be removed): it records the
# "open" events only while a counted tick runs.
_OPENS = []
_COUNTING = [False]


def _audit(event, args):
    if _COUNTING[0] and event == "open":
        _OPENS.append(str(args[0])[-80:])


sys.addaudithook(_audit)


def _data_files(tmp):
    """local.json and small world_areas / base_items snapshots, all with an
    mtime an hour back (a settled config is never re-read)."""
    rt = tmp / "rt"
    gd = rt / "gamedata"
    gd.mkdir(parents=True)
    areas = {aid: {"name": name, "area_level": lvl, "is_town": "town" in aid,
                   "has_waypoint": True, "connections": []}
             for aid, lvl, name in synth_client.ZONES}
    bases = {f"Metadata/Items/Synthetic/Base{i}": {
        "name": f"Synthetic Base {i}", "item_class": "Ring", "drop_level": 1 + i % 80,
        "release_state": "released"} for i in range(200)}
    cfg = tmp / "local.json"
    files = ((gd / acts.FILE_NAME, areas), (gd / basetypes.FILE_NAME, bases), (cfg, {}))
    old = time.time() - 3600
    for path, doc in files:
        path.write_text(json.dumps(doc) + "\n", encoding="ascii")
        os.utime(path, (old, old))
    return rt, cfg


def _worst_core(tmp):
    """RUN-LADDER-TICK's 200 + 500 fixture; the open map's clock moves 0.5 s
    a tick (the returned step function)."""
    rt, cfg = _data_files(tmp)
    core = Core(runtime=rt, config_path=cfg, tail=False)
    clock = [1000.0]
    core.state._clock = lambda: clock[0]

    def feed(ev):
        clock[0] = ev["recv_ts"]
        core.state.apply(ev)

    feed({"type": "level_up", "character": "Quill", "level": 80, "class": "Witch",
          "recv_ts": 1000.0})
    old = [{"area_id": f"MapOld{i % 40}", "seed": i, "opened_at": float(i),
            "area_level": 60 + i % 20, "time_s": 300.0, "deaths": i % 3,
            "level_ups": 0} for i in range(500)]
    core.ladder.record("Quill", old)
    at = 2000.0
    for i in range(runs.MAX_MAPS + 1):  # the last one stays open
        feed({"type": "area_generated", "area_id": f"MapNew{i % 30}",
              "area_level": 65 + i % 15, "seed": 10_000 + i, "recv_ts": at})
        feed({"type": "scene_changed", "scene": f"New{i % 30}", "is_hideout": False,
              "recv_ts": at + 1})
        at += 400.0

    def step():
        clock[0] += 0.5
    assert len(core.ladder.by["Quill"]) == 500
    return core, step


def _campaign_core(tmp):
    """A four-hour levelling session (synth_client, seed 7) through the
    core's own line path."""
    rt, cfg = _data_files(tmp)
    core = Core(runtime=rt, config_path=cfg, tail=False)
    s = synth_client.standard_session(seed=7)
    synth_client.play(s, 240)
    for line in s.lines:
        core.feed_line(line)
    assert core.state.snapshot()["level"] > 1
    return core, lambda: None


FIXTURES = {"worst": (_worst_core, WORST_S), "campaign": (_campaign_core, CAMPAIGN_S)}


def _make(make, tmp, monkeypatch):
    """A fixture core on a hot reload registry of its own."""
    monkeypatch.setattr(hotreload, "REGISTRY", hotreload.Registry())
    return make(tmp)


def _settle(core, step, n=5):
    for _ in range(n):
        step()
        core.tick_all()


class _Stats:
    """os.stat wrapped: the paths stat-ed while `on` (the call still runs)."""

    def __init__(self, monkeypatch):
        self.real = os.stat
        self.on = False
        self.paths = []
        monkeypatch.setattr(os, "stat", self._stat)

    def _stat(self, path, *args, **kwargs):
        if self.on:
            self.paths.append(path)
        return self.real(path, *args, **kwargs)

    def tick(self, core):
        """One counted tick_all; returns the paths it stat-ed."""
        del self.paths[:]
        self.on = True
        try:
            core.tick_all()
        finally:
            self.on = False
        return list(self.paths)

    def cost(self, paths):
        """Seconds the real os.stat takes for `paths` once each."""
        t0 = time.perf_counter()
        for path in paths:
            try:
                self.real(path)
            except OSError:
                pass
        return time.perf_counter() - t0


def _median(values):
    values = sorted(values)
    return values[len(values) // 2]


def test_full_tick_under_2_ms_worst_and_0_3_ms_campaign(tmp_path, monkeypatch):
    """The tick's own work, net of its stat calls: B3 bounds their number
    deterministically, while one call's latency is the disk stack's (10 to
    20 us on Windows with an on-access scanner), not AshLight's. Each round
    takes the median of 20 ticks and the median cost of the same stat calls
    timed right after them; the worst case also holds its 2 ms gross."""
    stats = _Stats(monkeypatch)
    got = {}
    for name, (make, limit) in FIXTURES.items():
        core, step = _make(make, tmp_path / name, monkeypatch)
        try:
            _settle(core, step)
            names = {n for n, _ in core.ticks}
            assert set(core.tick_ms) == names  # every tick of the list ran
            step()
            paths = stats.tick(core)
            assert 0 < len(paths) <= STAT_MAX, (name, len(paths))
            rounds = []
            for _ in range(5):
                times = []
                for _ in range(20):
                    step()
                    t0 = time.perf_counter()
                    core.tick_all()
                    times.append(time.perf_counter() - t0)
                gross = _median(times)
                stat_s = _median([stats.cost(paths) for _ in range(20)])
                rounds.append((gross - stat_s, gross))
            net = min(r[0] for r in rounds)
            gross = min(r[1] for r in rounds)
            got[name] = (net, gross, limit, dict(core.tick_ms))
        finally:
            core.close()
    text = ", ".join(f"{n} {v[0] * 1000:.3f} ms net, {v[1] * 1000:.3f} ms gross"
                     for n, v in got.items())
    print(f"full tick: {text}")
    skip_if_ci_timing("full core tick", text)
    for name, (net, gross, limit, ticks) in got.items():
        slow = sorted(ticks.items(), key=lambda kv: -kv[1])[:3]
        assert net < fleet_test_guard.budget(limit), (
            f"{name}: {net * 1000:.3f} ms net (budget {limit * 1000:g} ms); slowest {slow}")
    worst_gross = got["worst"][1]
    assert worst_gross < fleet_test_guard.budget(WORST_S), f"{worst_gross * 1000:.3f} ms gross"


def test_idle_tick_at_most_20_stats_and_no_read(tmp_path, monkeypatch):
    stats = _Stats(monkeypatch)
    for name, (make, _limit) in FIXTURES.items():
        core, step = _make(make, tmp_path / name, monkeypatch)
        try:
            _settle(core, step)
            step()
            del _OPENS[:]
            _COUNTING[0] = True
            try:
                paths = stats.tick(core)
            finally:
                _COUNTING[0] = False
            shown = [str(p)[-60:] for p in paths]
            assert paths, f"{name}: the counter saw no stat (os.stat not used?)"
            assert len(paths) <= STAT_MAX, (name, len(paths), shown)
            assert _OPENS == [], (name, _OPENS)
        finally:
            core.close()
