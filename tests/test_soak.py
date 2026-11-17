"""TEST-SOAK: a time-compressed soak of a RUNNING core.

A real core (tailer thread + HTTP / SSE server on an ephemeral port, runtime
in tmp_path) reads hours of synthetic Client.txt play (tools/synth_client.py
play(): five-minute rounds of game time with zones, level-ups, deaths,
whispers, trades, party joins and restarts) written in hour-long chunks,
while SSE clients connect and drop every round (reconnect churn), one SSE
client stays connected throughout, and the dashboard's /api/state is polled.

Asserted after the run, against a warmed-up baseline:
- Python heap growth (tracemalloc, whole process) stays bounded;
- the event history stays bounded (bus ring, recent events / whispers,
  trade cards) and the tailer keeps no partial line;
- no thread, socket, subscriber or SSE-slot leak (thread count, Windows
  process handle count, bus subscribers, the SSE semaphore);
- the long-lived SSE client still receives events at the end.

Short variant: 48 simulated hours (about 4 s), in every suite. Long variant
(opt-in, AL_SOAK=1; AL_SOAK_HOURS sets the length, default 500): the same
run, plus a check that the second half grows no more than the first.
"""

import ctypes
import gc
import http.client
import json
import os
import socket
import sys
import threading
import time
import tracemalloc
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import synth_client  # noqa: E402
from server.al import bus as bus_mod  # noqa: E402
from server.al import http as al_http  # noqa: E402
from server.al import state as state_mod  # noqa: E402
from server.al.core import Core  # noqa: E402
from server.al.http import serve  # noqa: E402

pytestmark = pytest.mark.server
TOKEN = "s" * 48
LONG = os.environ.get("AL_SOAK") == "1"
HOURS = float(os.environ.get("AL_SOAK_HOURS", "500")) if LONG else 48.0
CHURN_PER_HOUR = 4
HEAP_BUDGET_MB = 2.5  # whole-process growth after warm-up (measured ~0.7 MB, flat)


def handle_count():
    """This process's open kernel handles (Windows), else open fds, else None."""
    if os.name == "nt":
        k32 = ctypes.windll.kernel32
        n = ctypes.c_ulong(0)
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        if k32.GetProcessHandleCount(ctypes.c_void_p(k32.GetCurrentProcess()),
                                     ctypes.byref(n)):
            return n.value
        return None
    try:
        return len(os.listdir("/proc/self/fd"))
    except OSError:
        return None


class Reader(threading.Thread):
    """A long-lived SSE client that keeps only counters (its buffer would
    otherwise count as heap growth)."""

    def __init__(self, port):
        super().__init__(daemon=True, name="soak-sse-reader")
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.sock.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{port}"
                           "\r\nAccept: text/event-stream\r\n\r\n").encode())
        self.events_blocks = 0
        self.bytes = 0
        self.closed = False
        self._tail = b""
        self._stop = threading.Event()

    def run(self):
        self.sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            self.bytes += len(chunk)
            data = self._tail + chunk
            self.events_blocks += data.count(b"event: events\n")
            self._tail = data[-32:]
        self.closed = True

    def stop(self):
        self._stop.set()
        self.sock.close()
        self.join(3)


def churn_once(port):
    """One dashboard tab opening the stream, reading the first state, leaving."""
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        s.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{port}"
                   "\r\nAccept: text/event-stream\r\n\r\n").encode())
        buf = b""
        end = time.monotonic() + 5
        while b"event: state" not in buf and time.monotonic() < end:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        return b"event: state" in buf
    finally:
        s.close()


def get_state(port):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", "/api/state",
                     headers={"Host": f"127.0.0.1:{port}", "X-AL-Token": TOKEN})
        r = conn.getresponse()
        body = r.read()
        assert r.status == 200
        return json.loads(body)
    finally:
        conn.close()


def wait_caught_up(core, log, timeout=20.0):
    size = log.stat().st_size
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        t = core.tailer
        if t is not None and t._offset >= size and not t._partial:
            return
        time.sleep(0.02)
    pytest.fail(f"tailer never caught up: offset {core.tailer and core.tailer._offset} "
                f"of {size}")


def settle(pred, timeout=25.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.05)
    return pred()


def measure():
    gc.collect()
    return {"heap": tracemalloc.get_traced_memory()[0], "threads": threading.active_count(),
            "handles": handle_count()}


@pytest.mark.slow
def test_soak_core_stays_bounded(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    sess = synth_client.Session(seed=4242)
    sess.marker()

    def write_play(minutes):
        synth_client.play(sess, minutes)
        with open(log, "ab") as fh:
            fh.write(sess.text().encode("utf-8"))
        sess.lines.clear()

    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.02, start_at_end=False)
    server = serve(core, TOKEN, port=0)
    th = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                          daemon=True)
    th.start()
    port = server.port
    reader = None
    tracemalloc.start(1)
    try:
        core.record_consent(True, str(log))
        assert core.start_tailing() or core.tailer is not None
        reader = Reader(port)
        reader.start()
        # warm-up: one hour of play, a full churn round, caches filled
        for _ in range(2):
            write_play(60)
            for _ in range(CHURN_PER_HOUR):
                assert churn_once(port)
            wait_caught_up(core, log)
            get_state(port)
        settle(lambda: core.bus.subscriber_count == 1)
        base = measure()
        mid = None
        hours = int(HOURS)
        for h in range(hours):
            write_play(60)
            for _ in range(CHURN_PER_HOUR):
                assert churn_once(port), f"SSE reconnect failed in hour {h}"
            wait_caught_up(core, log)
            snap = get_state(port)
            assert snap["tailer"]["reading"] is True
            if h == hours // 2:
                settle(lambda: core.bus.subscriber_count == 1)
                mid = measure()
        blocks_before = reader.events_blocks
        write_play(30)
        wait_caught_up(core, log)
        assert settle(lambda: reader.events_blocks > blocks_before, 10), \
            "the long-lived SSE client stopped receiving events"
        # dropped tabs: their stream threads exit on the next write
        assert settle(lambda: core.bus.subscriber_count == 1), core.bus.subscriber_count
        assert settle(lambda: server.sse_slots._value == al_http.MAX_SSE_CLIENTS - 1)
        assert settle(lambda: threading.active_count() <= base["threads"])
        end = measure()

        snap = get_state(port)
        assert snap["events_seen"] > hours * 12 * 5  # thousands of events, not a stub
        assert len(core.bus.recent()) <= bus_mod.RING_SIZE
        assert len(snap["recent_events"]) <= state_mod.RECENT_EVENTS
        assert len(snap["recent_whispers"]) <= state_mod.RECENT_WHISPERS
        assert len(snap["trade_requests"]) <= state_mod.TRADE_REQUESTS
        assert len(json.dumps(snap)) < 256 * 1024
        assert core.tailer.dropped_lines == 0 and not core.tailer._partial
        assert not reader.closed

        growth_mb = (end["heap"] - base["heap"]) / 1e6
        assert growth_mb < HEAP_BUDGET_MB, (
            f"heap grew {growth_mb:.2f} MB over {hours} simulated hours")
        if base["handles"] is not None:
            assert end["handles"] - base["handles"] < 40, (base, end)
        if LONG and mid is not None:
            first, second = mid["heap"] - base["heap"], end["heap"] - mid["heap"]
            assert second <= max(first, 0) + 1_000_000, (
                f"heap keeps growing: first half {first} B, second half {second} B")
    finally:
        tracemalloc.stop()
        if reader is not None:
            reader.stop()
        server.stop()
        core.close()


def test_dropped_sse_clients_free_their_slots_promptly(tmp_path):
    # SOAK-1: a dashboard tab that closed its stream kept its SSE slot, its
    # bus subscription and its thread until two writes failed - with a quiet
    # log that is the 15 s heartbeat twice, ~30 s. Reloading the dashboard a
    # few times filled MAX_SSE_CLIENTS and the overlay got "busy" for 30 s.
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, TOKEN, port=0)
    th = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                          daemon=True)
    th.start()
    try:
        threads0 = threading.active_count()
        for _ in range(al_http.MAX_SSE_CLIENTS):
            assert churn_once(server.port)
        assert settle(lambda: core.bus.subscriber_count == 0, 4.0), \
            f"{core.bus.subscriber_count} dropped streams still subscribed"
        assert settle(lambda: server.sse_slots._value == al_http.MAX_SSE_CLIENTS, 2.0)
        assert settle(lambda: threading.active_count() <= threads0, 2.0)
        assert churn_once(server.port)  # a new tab is served, not "busy"
    finally:
        server.stop()
        core.close()
