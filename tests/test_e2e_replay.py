"""TEST-E2E: a generated Client.txt session replayed into a RUNNING core.

The core (tailer thread + HTTP server on an ephemeral port, runtime in
tmp_path) is driven only through the file system and its public HTTP / SSE
surface, the way the game and the dashboard reach it: consent over the API,
lines appended to Client.txt in odd chunks (split mid-line and mid UTF-8
sequence), truncation, replacement, a huge unterminated line, and a file near
the 32 MB resume cap. Lines come from tools/synth_client.py.
"""

import http.client
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import synth_client  # noqa: E402
from server.al import logfile, resume  # noqa: E402
from server.al.core import Core  # noqa: E402
from server.al.http import serve  # noqa: E402

pytestmark = pytest.mark.server
TOKEN = "e" * 48
WAIT_S = 8.0


class Live:
    def __init__(self, tmp_path, log, start_at_end=True, **kw):
        self.log = log
        self.core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.02,
                         start_at_end=start_at_end, **kw)
        self.server = serve(self.core, TOKEN, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def req(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=5)
        h = {"Host": f"127.0.0.1:{self.server.port}", "X-AL-Token": TOKEN}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=h)
        r = conn.getresponse()
        out = r.read()
        conn.close()
        return r.status, json.loads(out) if out else None

    def state(self):
        return self.req("GET", "/api/state")[1]

    def consent(self):
        status, doc = self.req("POST", "/api/consent", {"consent": True})
        assert status == 200 and doc["consent"]["consented"] is True

    def wait_for(self, pred, what):
        end = time.monotonic() + WAIT_S
        snap = None
        while time.monotonic() < end:
            snap = self.state()
            if pred(snap):
                return snap
            time.sleep(0.02)
        pytest.fail(f"timed out waiting for {what}; last state: "
                    f"{ {k: snap.get(k) for k in ('zone', 'level', 'deaths', 'tailer')} }")

    def close(self):
        self.server.stop()
        self.core.close()


@pytest.fixture
def live_factory(tmp_path):
    made = []

    def make(log, **kw):
        lv = Live(tmp_path, log, **kw)
        made.append(lv)
        return lv

    yield make
    for lv in made:
        lv.close()


def append(path, data):
    with open(path, "ab") as fh:
        fh.write(data)
        fh.flush()


def odd_chunks(data, rng_seed=7):
    """Split bytes at awkward places: mid line and mid UTF-8 sequence."""
    import random
    rng = random.Random(rng_seed)
    i = 0
    while i < len(data):
        n = rng.choice((1, 2, 3, 17, 61, 255, 1024))
        yield data[i:i + n]
        i += n


class Sse:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.sock.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{port}"
                           "\r\nAccept: text/event-stream\r\n\r\n").encode())
        self.buf = b""

    def read_until(self, needle, timeout=WAIT_S):
        end = time.monotonic() + timeout
        while needle not in self.buf:
            if time.monotonic() > end:
                raise AssertionError(f"SSE never sent {needle!r}")
            self.sock.settimeout(max(0.05, end - time.monotonic()))
            chunk = self.sock.recv(65536)
            if not chunk:
                raise AssertionError("SSE stream closed")
            self.buf += chunk
        return self.buf

    def event_types(self):
        out = []
        for block in self.buf.split(b"\n\n"):
            if block.startswith(b"event: events\ndata: "):
                out += [ev["type"] for ev in json.loads(block.split(b"data: ", 1)[1])]
        return out

    def close(self):
        self.sock.close()


def test_live_session_end_to_end_over_http_and_sse(tmp_path, live_factory):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"\xef\xbb\xbf")  # a BOM-only log, as a fresh install may leave
    lv = live_factory(log)
    assert lv.state()["tailer"].get("reading") in (None, False)
    lv.consent()
    lv.wait_for(lambda s: lv.core.tailer is not None and lv.core.tailer.running, "tailer")
    sse = Sse(lv.server.port)
    try:
        sse.read_until(b"event: state")
        s = synth_client.standard_session(seed=3, character="\u00c9lodie", klass="Witch")
        for chunk in odd_chunks(s.text().encode("utf-8")):
            append(log, chunk)
        snap = lv.wait_for(lambda x: x["deaths"] == s.deaths and x["level"] == s.level,
                           "the whole session")
        assert snap["character"] == "\u00c9lodie" and snap["class"] == "Witch"
        assert snap["zone"] == s.zone and snap["area_id"] == s.area_id
        assert snap["level_ups"] == s.level - 1
        assert "Ma\u00eblle" in json.dumps(snap["recent_whispers"], ensure_ascii=False)
        assert "\u30b5\u30af\u30e9" in json.dumps(snap["recent_whispers"], ensure_ascii=False)
        assert len(snap["recent_whispers"]) == s.whispers_in
        # AUDIT pass 2 (P2-T1): exact, not <= (which passed with no card at
        # all): the session has one request and its acceptance, and decision
        # 0019 closes that one card.
        assert s.trade_requests == 1
        assert snap["trade_requests"] == []
        sse.read_until(b"\"type\":\"death\"")
        types = sse.event_types()
        for t in ("scene_changed", "area_generated", "level_up", "death", "whisper_in",
                  "trade_accepted", "chat"):
            assert t in types, (t, sorted(set(types)))
        assert "\ufffd" not in json.dumps(snap, ensure_ascii=False)  # no split UTF-8
    finally:
        sse.close()


def test_rotation_truncation_and_replacement_keep_tailing(tmp_path, live_factory):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    lv = live_factory(log)
    lv.consent()
    a = synth_client.Session(seed=1, character="Rotor", klass="Monk")
    a.marker()
    a.zone_change("G1_1", 1, "The Riverbank")
    a.level_up()
    append(log, a.text().encode())
    lv.wait_for(lambda x: x["level"] == 2, "first run")
    # The game truncates the log (a new run reuses the file).
    b = synth_client.Session(seed=2, character="Rotor", klass="Monk")
    b.level = 2
    b.marker()
    b.level_up()
    log.write_bytes(b.text().encode())
    lv.wait_for(lambda x: x["level"] == 3, "the level-up after truncation")
    # The file is replaced (rename over it), as a log cleaner would do.
    c = synth_client.Session(seed=3, character="Rotor", klass="Monk")
    c.level = 3
    c.marker()
    c.zone_change("G1_town", 15, "Clearfell Encampment")
    c.level_up()
    tmp = tmp_path / "Client.new"
    tmp.write_bytes(c.text().encode())
    os.replace(tmp, log)
    lv.wait_for(lambda x: x["level"] == 4 and x["zone"] == "Clearfell Encampment",
                "the replaced file")
    # Deleted, then recreated: read from its start.
    log.unlink()
    lv.wait_for(lambda x: lv.core.tailer._missing, "missing file noticed")
    d = synth_client.Session(seed=4, character="Rotor", klass="Monk")
    d.level = 4
    d.level_up()
    log.write_bytes(d.text().encode())
    lv.wait_for(lambda x: x["level"] == 5, "the recreated file")
    assert lv.core.tailer.running


def test_huge_unterminated_line_is_dropped_and_tailing_recovers(tmp_path, live_factory):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    lv = live_factory(log)
    lv.consent()
    # A corrupt tail (NUL padding after a crash, garbage) with no newline,
    # several MB long, must not grow the tailer's buffer without bound.
    append(log, b"\x00" * (3 * logfile.MAX_PARTIAL))
    lv.wait_for(lambda x: lv.core.tailer._offset >= 3 * logfile.MAX_PARTIAL, "garbage read")
    assert len(lv.core.tailer._partial) <= logfile.MAX_PARTIAL
    s = synth_client.Session(seed=5, character="Afterglow", klass="Ranger")
    s.level_up()
    s.death()
    append(log, b"\r\n" + s.text().encode())
    lv.wait_for(lambda x: x["deaths"] == 1 and x["level"] == 2, "lines after the garbage")


def test_partial_line_waits_for_its_newline(tmp_path, live_factory):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    lv = live_factory(log)
    lv.consent()
    s = synth_client.Session(seed=6, character="Halfline", klass="Mercenary")
    s.level_up()
    data = s.text().encode()
    append(log, data[:-2])  # no CRLF yet
    time.sleep(0.2)
    assert lv.state()["level"] is None
    append(log, data[-2:])
    lv.wait_for(lambda x: x["level"] == 2, "the completed line")


def test_resume_near_the_32mb_cap_on_core_start(tmp_path, live_factory):
    """A long-running game: the current run's history sits ~31 MB back,
    behind engine noise. A core starting at the end recovers it."""
    log = tmp_path / "Client.txt"
    s = synth_client.standard_session(seed=8, character="Longhaul", klass="Warrior")
    head = s.text().encode()
    pad = synth_client.pad_noise(resume.DEFAULT_MAX_BYTES - len(head) - 512 * 1024)
    with open(log, "wb") as fh:
        fh.write(synth_client.pad_noise(2 * 1024 * 1024))  # an older run, past the cap
        fh.write(head)
        fh.write(pad)
    assert log.stat().st_size > resume.DEFAULT_MAX_BYTES
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "consent.json").write_text('{"consented": true}\n', encoding="ascii")
    lv = live_factory(log)
    t0 = time.perf_counter()
    assert lv.core.start_tailing()
    snap = lv.wait_for(lambda x: x["tailer"].get("resume"), "resume")
    assert time.perf_counter() - t0 < 5.0
    assert snap["character"] == "Longhaul" and snap["level"] == s.level
    assert snap["deaths"] == s.deaths and snap["zone"] == s.zone
    assert snap["tailer"]["resume"]["hit_marker"] is True
    # Old bytes are never replayed as live events.
    assert not snap["recent_whispers"]
    s2 = synth_client.Session(seed=9, character="Longhaul", klass="Warrior")
    s2.level = s.level
    s2.level_up()
    append(log, s2.text().encode())
    lv.wait_for(lambda x: x["level"] == s.level + 1, "a live level-up after resume")


def test_log_found_later_starts_tailing_without_a_click(tmp_path, monkeypatch):
    """Consent was given, but at core start no Client.txt was found (the game
    not installed yet, or its Steam library moved). The core keeps looking
    and starts tailing on its own once the log appears."""
    found = {"path": None}
    monkeypatch.setattr(logfile, "discover_client_log", lambda configured=None: found["path"])
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "consent.json").write_text('{"consented": true}\n', encoding="ascii")
    core = Core(runtime=rt, poll_s=0.02)
    try:
        assert core.log_path is None and not core.start_tailing()
        assert core.ensure_tailing(now=100.0) is False
        log = tmp_path / "lib2" / "Client.txt"
        log.parent.mkdir()
        log.write_bytes(b"")
        found["path"] = log
        assert core.ensure_tailing(now=100.5) is False  # rate limited
        assert core.ensure_tailing(now=200.0) is True
        assert core.tailer is not None and core.log_path == log
        s = synth_client.Session(seed=10, character="Latecomer", klass="Huntress")
        s.level_up()
        append(log, s.text().encode())
        end = time.monotonic() + WAIT_S
        while core.state.snapshot()["level"] != 2 and time.monotonic() < end:
            time.sleep(0.02)
        assert core.state.snapshot()["level"] == 2
    finally:
        core.close()


def test_discovered_log_moving_library_follows_it(tmp_path, monkeypatch):
    """A discovered (not configured) log that vanishes and shows up in another
    Steam library is followed; a configured path is never second-guessed."""
    old = tmp_path / "lib1" / "Client.txt"
    new = tmp_path / "lib2" / "Client.txt"
    old.parent.mkdir()
    new.parent.mkdir()
    old.write_bytes(b"")
    found = {"path": old}
    monkeypatch.setattr(logfile, "discover_client_log", lambda configured=None: found["path"])
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "consent.json").write_text('{"consented": true}\n', encoding="ascii")
    core = Core(runtime=rt, poll_s=0.02)
    try:
        assert core.start_tailing() and core.log_path == old
        old.unlink()
        end = time.monotonic() + WAIT_S
        while not core.tailer._missing and time.monotonic() < end:
            time.sleep(0.02)
        new.write_bytes(b"")
        found["path"] = new
        assert core.ensure_tailing(now=1000.0) is True
        assert core.log_path == new and core.tailer.path == new
    finally:
        core.close()
