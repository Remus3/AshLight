"""RUN-BUDGET-TESTS-DET (F-108, research 0048 R6), B7 (deterministic): the
state snapshot the feed sends stays under 32 KB and no top-level key over
8 KB, counted as the bytes of the compact JSON the SSE frame and
/api/state carry (server/al/http.py, ensure_ascii, so one character is one
byte).

Two busy fixtures: a four-hour session from tools/synth_client.py (zones,
level-ups, deaths, whispers with non-ASCII names, trade requests and their
outcomes, chat, party joins, game restarts) fed through Core.feed_line and
ticked; and the RUN-LADDER-TICK worst case (500 saved maps, 200 session
maps and an open one).
"""

import json
import sys
from pathlib import Path

from server.al import runs
from server.al.core import Core

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import synth_client  # noqa: E402

SNAPSHOT_MAX = 32 * 1024
KEY_MAX = 8 * 1024


def _size(value):
    return len(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _busy_session_core(tmp):
    core = Core(runtime=tmp / "rt", config_path=tmp / "local.json", tail=False)
    s = synth_client.standard_session(seed=11)
    for i in range(12):  # twelve trade requests, most still open
        s.trade_whisper(f"Buyer{i}", "Grim Bane Ruby Ring", 5 + i, "exalted")
    synth_client.play(s, 240)
    for line in s.lines:
        core.feed_line(line)
    core.tick_all()
    snap = core.state.snapshot()
    assert snap["level"] > 1 and snap["recent_events"]
    return core


def _worst_maps_core(tmp):
    core = Core(runtime=tmp / "rt", config_path=tmp / "local.json", tail=False)
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
    for i in range(runs.MAX_MAPS + 1):
        feed({"type": "area_generated", "area_id": f"MapNew{i % 30}",
              "area_level": 65 + i % 15, "seed": 10_000 + i, "recv_ts": at})
        feed({"type": "scene_changed", "scene": f"New{i % 30}", "is_hideout": False,
              "recv_ts": at + 1})
        at += 400.0
    core.tick_all()
    assert core.state.snapshot()["maps"]["ladder_all"]["maps"] > 500
    return core


def test_snapshot_under_32_kb_no_key_over_8_kb(tmp_path):
    for name, make in (("session", _busy_session_core), ("maps", _worst_maps_core)):
        core = make(tmp_path / name)
        try:
            snap = core.state.snapshot()
        finally:
            core.close()
        total = _size(snap)
        keys = sorted(((_size(v), k) for k, v in snap.items()), reverse=True)
        print(f"{name}: snapshot {total} bytes, {len(snap)} keys, largest {keys[:3]}")
        assert total < SNAPSHOT_MAX, (name, total, keys[:5])
        over = [(k, n) for n, k in keys if n > KEY_MAX]
        assert not over, (name, over)
