"""OVL-OVERLAY-FEED (F-177): /events?view=overlay sends only the fields
the HUD reads (server/al/overlayview.py OVERLAY_FIELDS, small), and a
state frame only when one of them changed (change_key, the feed's own
stamp). Two overlay streams share one serialised frame
(overlayview.FeedFrames on the server object); the default view (no view)
is unchanged; an unknown view is 400. B7 (decision 0002, research 0048):
the small view of the two busy fixtures of tests/test_budget_snapshot.py
stays under SMALL_MAX.

The JS half (app/test/shared.test.js) walks app/shared/render_gate.js:
every snapshot field it reads is in SNAP_FIELDS, and hudModel gives the
same output for the small view as for the full snapshot (B13). Here the
two lists are compared, so neither side drifts alone.
"""

import json
import re
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from server.al import http as al_http, overlayview  # noqa: E402
from server.al.core import Core  # noqa: E402
from server.al.http import serve  # noqa: E402
from server.al.overlayview import (OVERLAY_FIELDS, STAMP, FeedFrames,  # noqa: E402
                                   change_key, small)

import test_budget_snapshot as budget  # noqa: E402

TOKEN = "f" * 48
RENDER_GATE = ROOT / "app" / "shared" / "render_gate.js"
OVERLAY_JS = ROOT / "app" / "overlay" / "overlay.js"
SMALL_MAX = 4 * 1024  # B7, the small view: an eighth of the full budget
QUIET_S = 0.8  # a stream that stays silent this long sent nothing


def _tops():
    return {f.partition(".")[0] for f in OVERLAY_FIELDS}


# -- the one list, two copies ---------------------------------------------------

def test_overlay_fields_equal_render_gate_snap_fields():
    text = RENDER_GATE.read_text(encoding="ascii")
    m = re.search(r"var SNAP_FIELDS = \[(.*?)\];", text, re.S)
    assert m, "render_gate.js lost SNAP_FIELDS"
    js = tuple(re.findall(r'"([^"]+)"', m.group(1)))
    assert js == OVERLAY_FIELDS
    assert len(set(OVERLAY_FIELDS)) == len(OVERLAY_FIELDS)
    assert STAMP not in _tops()


def test_overlay_page_asks_for_the_overlay_view():
    text = OVERLAY_JS.read_text(encoding="ascii")
    assert '/events?view=overlay&token="' in text
    # overlay.js reads no snapshot field outside the list ("now" only)
    assert set(re.findall(r"\bsnap\.(\w+)", text)) <= _tops()


# -- small() and change_key() ---------------------------------------------------

FULL = {
    "version": 41, "now": 5000.0, "zone": "Crypt", "in_hideout": False, "in_town": False,
    "zone_entered_at": 4400.0, "level": 71, "deaths": 4, "afk": False, "dnd": False,
    "tailer": {"consented": True, "reading": True, "path": "x", "idle": False,
               "last_line_at": 4990.0},
    "game_idle": False,
    "maps": {"count": 3, "current": {"name": "Crypt", "area_level": 65, "time_s": 600.0,
                                     "deaths": 1, "inside": True},
             "recent": [{"name": "Old"}], "ladder": {"rows": []}},
    "trade_requests": [], "underlevel": {"word": "", "gap": 3, "text": "x"},
    "campaign": {"word": "Cold res 32%", "rows": [1, 2]},
    "card": None, "eval": {"text": {"head": "h"}, "expires_at": 5015.0, "ok": True,
                           "verdict": "upgrade", "mods": ["a"] * 50, "at": 4995.0},
    "overlay": {"guide_short": "", "calm_at": None},
    "overlay_layout": {"corner": "top-right", "parts": {}},
    "sources": {"calc_on": True}, "recent_events": [{"seq": 1}], "diag": {"rows": []},
    "hotkeys": {"eval": {"key": "Alt+E"}}, "run_history": {"on": True},
}


def test_small_keeps_only_overlay_fields():
    doc = small(FULL)
    assert set(doc) == _tops() | {STAMP}
    assert doc[STAMP] == 41 and small(FULL, stamp=7)[STAMP] == 7
    assert set(doc["maps"]) == {"current"}
    assert doc["maps"]["current"] == FULL["maps"]["current"]
    assert doc["underlevel"] == {"word": ""} and doc["campaign"] == {"word": "Cold res 32%"}
    assert set(doc["eval"]) == {"text", "expires_at", "ok", "verdict"}
    for gone in ("sources", "recent_events", "diag", "hotkeys", "run_history"):
        assert gone not in doc


def test_small_keeps_absent_absent_and_none_none():
    doc = small({"version": 1, "eval": None, "maps": None, "zone": None})
    assert doc == {"version": 1, "eval": None, "maps": None, "zone": None}
    assert "card" not in doc  # the page tells an older core by the missing key


def test_change_key_ignores_the_clock_and_a_busy_log():
    base = small(FULL)
    later = small(dict(FULL, now=5030.0, version=50,
                       maps=dict(FULL["maps"], current=dict(FULL["maps"]["current"],
                                                            time_s=630.0)),
                       tailer=dict(FULL["tailer"], last_line_at=5029.0)))
    assert change_key(base) == change_key(later)
    # a map timer that jumps (another map) is a change
    other = small(dict(FULL, maps=dict(FULL["maps"], current=dict(
        FULL["maps"]["current"], time_s=10.0))))
    assert change_key(base) != change_key(other)
    # outside the map the frozen time is compared as it is
    out = dict(FULL["maps"]["current"], inside=False)
    a = small(dict(FULL, maps=dict(FULL["maps"], current=out)))
    b = small(dict(FULL, now=5100.0, maps=dict(FULL["maps"], current=dict(out, time_s=601.0))))
    assert change_key(a) != change_key(b)
    # an idle log: its last line time is read by the HUD, so it counts
    idle = dict(FULL["tailer"], idle=True)
    i1 = small(dict(FULL, tailer=idle))
    i2 = small(dict(FULL, tailer=dict(idle, last_line_at=4000.0)))
    assert change_key(i1) != change_key(i2)
    # a HUD field is a change
    assert change_key(base) != change_key(small(dict(FULL, deaths=5)))


class FakeState:
    def __init__(self, snap):
        self.snap = dict(snap)
        self.version = snap["version"]
        self.snapshots = 0

    def snapshot(self):
        self.snapshots += 1
        return dict(self.snap, version=self.version)

    def bump(self, **fields):
        self.snap.update(fields)
        self.version += 1


def _encoder():
    calls = []

    def encode(event, data):
        calls.append(event)
        return al_http.Handler._sse_msg(event, data)
    return encode, calls


def test_feed_frames_share_one_frame_per_view_per_version():
    clock = [100.0]
    state = FakeState(FULL)
    frames = FeedFrames(clock=lambda: clock[0])
    encode, calls = _encoder()
    v1, s1, t1 = frames.frame("overlay", state, encode)
    v2, s2, t2 = frames.frame("overlay", state, encode)
    assert (v1, s1) == (v2, s2) == (41, 1)
    assert t1 is t2 and state.snapshots == 1 and calls == ["state"]
    # the default view keeps its own frame: the full snapshot, stamp = version
    vd, sd, td = frames.frame(None, state, encode)
    assert (vd, sd) == (41, 41) and state.snapshots == 2
    assert json.loads(td.split("data: ", 1)[1]) == state.snapshot()
    # a dashboard-only change: a new frame, the overlay stamp stays
    state.bump(sources={"calc_on": False}, recent_events=[])
    v3, s3, _ = frames.frame("overlay", state, encode)
    assert (v3, s3) == (42, 1)
    # a HUD change moves the stamp, and the frame carries it as "version"
    state.bump(deaths=5)
    v4, s4, t4 = frames.frame("overlay", state, encode)
    assert (v4, s4) == (43, 2)
    doc = json.loads(t4.split("data: ", 1)[1])
    assert doc[STAMP] == 2 and doc["deaths"] == 5 and set(doc) == _tops() | {STAMP}
    # the same version past FRAME_REUSE_S takes a fresh snapshot (a fresh now)
    n = state.snapshots
    clock[0] += overlayview.FRAME_REUSE_S
    assert frames.frame("overlay", state, encode)[1] == 2
    assert state.snapshots == n + 1


# -- B7: the small view of the busy fixtures --------------------------------------

def test_b7_small_view_stays_small(tmp_path):
    for name, make in (("session", budget._busy_session_core),
                       ("maps", budget._worst_maps_core)):
        core = make(tmp_path / name)
        try:
            snap = core.state.snapshot()
        finally:
            core.close()
        doc = small(snap)
        total = budget._size(doc)
        print(f"{name}: small view {total} bytes of {budget._size(snap)}")
        assert set(doc) <= _tops() | {STAMP}
        assert total < SMALL_MAX, (name, total)
        assert total < budget.SNAPSHOT_MAX and all(
            budget._size(v) <= budget.KEY_MAX for v in doc.values())


# -- the live feed -----------------------------------------------------------------

@pytest.fixture
def srv(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    server = serve(core, TOKEN, port=0)
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def _open(server, query=""):
    s = socket.create_connection(("127.0.0.1", server.port), timeout=5)
    s.sendall((f"GET /events?token={TOKEN}{query} HTTP/1.1\r\n"
               f"Host: 127.0.0.1:{server.port}\r\n"
               "Accept: text/event-stream\r\n\r\n").encode())
    buf = b""
    end = time.monotonic() + 5
    while b"\n\n" not in buf.partition(b"event: state")[2] and time.monotonic() < end:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
    return s, buf


def _read_for(s, seconds):
    buf = b""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        s.settimeout(max(0.01, end - time.monotonic()))
        try:
            chunk = s.recv(65536)
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
    return buf


def _read_until_state(s, timeout=3.0):
    buf = b""
    end = time.monotonic() + timeout
    while not _frames(buf) and time.monotonic() < end:
        buf += _read_for(s, 0.05)
    return buf


def _frames(buf, name="state"):
    head = b"event: " + name.encode() + b"\ndata: "
    return [json.loads(block[len(head):]) for block in buf.split(b"\n\n")
            if block.startswith(head)]


def _raw_frames(buf):
    return [block for block in buf.split(b"\n\n") if block.startswith(b"event: state\n")]


def _dashboard_only_change(server):
    core = server.core
    assert core.state.set_sources(calc_on=not core.state.sources.get("calc_on"))
    core.bus.wake_all()


def test_overlay_frames_hold_only_overlay_fields_and_skip_dashboard_changes(srv):
    s, buf = _open(srv, "&view=overlay")
    d, dbuf = _open(srv)
    try:
        first = _frames(buf)
        assert len(first) == 1 and set(first[0]) <= _tops() | {STAMP}
        assert "sources" not in first[0] and "recent_events" not in first[0]
        stamp = first[0][STAMP]
        # a dashboard-only change: the default view gets it, the overlay nothing
        _dashboard_only_change(srv)
        assert _frames(_read_until_state(d)), "the default view missed the change"
        assert _frames(_read_for(s, QUIET_S)) == []
        # a HUD change reaches the overlay, with a moved stamp
        srv.core.bus.publish({"type": "death", "character": "Me", "suicide": False})
        got = _frames(_read_until_state(s))
        assert got and got[-1]["deaths"] == 1 and got[-1][STAMP] > stamp
        assert set(got[-1]) <= _tops() | {STAMP}
    finally:
        s.close()
        d.close()


def test_two_overlay_streams_share_one_serialised_frame(srv, monkeypatch):
    monkeypatch.setattr(overlayview, "FRAME_REUSE_S", 60.0)
    a, abuf = _open(srv, "&view=overlay")
    b, bbuf = _open(srv, "&view=overlay")
    try:
        assert _raw_frames(abuf) == _raw_frames(bbuf)
        calls = []
        real = srv.core.state.snapshot

        def counted():
            calls.append(1)
            return real()
        monkeypatch.setattr(srv.core.state, "snapshot", counted)
        srv.core.bus.publish({"type": "death", "character": "Me", "suicide": False})
        fa, fb = _raw_frames(_read_until_state(a)), _raw_frames(_read_until_state(b))
        assert fa and fa == fb  # byte-identical: one frame for both streams
        assert len(calls) == 1, calls
    finally:
        a.close()
        b.close()


def test_default_view_is_unchanged(srv):
    s, buf = _open(srv)
    try:
        snap = srv.core.state.snapshot()
        frame = _frames(buf)[0]
        assert set(frame) == set(snap)  # the whole snapshot, as before
        assert frame[STAMP] == snap[STAMP]  # the state version, not a feed stamp
    finally:
        s.close()


@pytest.mark.parametrize("query", ["&view=dashboard", "&view=Overlay",
                                   "&view=overlay&view=overlay", "&view=overlay%00"])
def test_an_unknown_view_is_400(srv, query):
    s = socket.create_connection(("127.0.0.1", srv.port), timeout=5)
    try:
        s.sendall((f"GET /events?token={TOKEN}{query} HTTP/1.1\r\n"
                   f"Host: 127.0.0.1:{srv.port}\r\n\r\n").encode())
        buf = _read_for(s, 2.0)
    finally:
        s.close()
    assert buf.startswith(b"HTTP/1.0 400") or buf.startswith(b"HTTP/1.1 400"), buf[:80]
    assert b"text/event-stream" not in buf
    # the refused request held no stream slot
    assert srv.sse_slots.acquire(blocking=False)
    srv.sse_slots.release()


def test_an_unknown_view_still_needs_the_token(srv):
    s = socket.create_connection(("127.0.0.1", srv.port), timeout=5)
    try:
        s.sendall((f"GET /events?view=dashboard HTTP/1.1\r\n"
                   f"Host: 127.0.0.1:{srv.port}\r\n\r\n").encode())
        buf = _read_for(s, 2.0)
    finally:
        s.close()
    assert b" 401 " in buf.split(b"\r\n", 1)[0], buf[:80]
