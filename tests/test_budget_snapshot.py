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

from snapshot_cores import (KEY_MAX, SNAPSHOT_MAX, busy_session_core,
                            size as _size, worst_maps_core)


def test_snapshot_under_32_kb_no_key_over_8_kb(tmp_path):
    for name, make in (("session", busy_session_core), ("maps", worst_maps_core)):
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
