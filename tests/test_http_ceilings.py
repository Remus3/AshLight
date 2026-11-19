"""SEC-CEIL-HTTP (F-173): the local server runs at most MAX_HANDLER_THREADS
handler threads, SSE streams included; one more connection is closed at once
(no reply, no thread) and the dashboard loads again once idle ones time out.

Ephemeral port, runtime in tmp_path; a running AshLight is never touched.
Every wait is a condition with a generous deadline, never a budget.
"""

import socket
import threading
import time
from pathlib import Path

import pytest

from server.al import http as alhttp
from server.al.core import Core
from server.al.http import serve

pytestmark = pytest.mark.server
ROOT = Path(__file__).resolve().parents[1]
TOKEN = "c" * 48
# shortened idle timeout: long enough that 64 connects finish well inside
# it, short enough that the tests do not wait the shipped 10 s
IDLE_S = 4.0


@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.setattr(alhttp, "REQUEST_TIMEOUT_S", IDLE_S)
    # Handler.timeout is bound from REQUEST_TIMEOUT_S at import; it is the
    # value StreamRequestHandler applies to each connection
    monkeypatch.setattr(alhttp.Handler, "timeout", IDLE_S)
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web")
    # count live handler threads (test-side spy on the instance; the server
    # starts each thread with target=self.process_request_thread)
    lock = threading.Lock()
    server.live = 0
    server.started = 0
    real = server.process_request_thread

    def spy(request, addr):
        with lock:
            server.live += 1
            server.started += 1
        try:
            real(request, addr)
        finally:
            with lock:
                server.live -= 1

    server.process_request_thread = spy
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    socks = []
    server.socks = socks
    yield server
    for s in socks:
        s.close()
    server.stop()
    core.close()


def wait_for(cond, what, deadline_s=30.0):
    end = time.monotonic() + deadline_s
    while not cond():
        assert time.monotonic() < end, what
        time.sleep(0.01)


def open_idle(server):
    """A connection that sends nothing: it holds one handler thread until
    the idle timeout drops it."""
    want = server.live + 1
    s = socket.create_connection(("127.0.0.1", server.port), timeout=10)
    server.socks.append(s)
    wait_for(lambda: server.live >= want, "idle connection never got a thread")
    return s


def open_sse(server):
    s = socket.create_connection(("127.0.0.1", server.port), timeout=10)
    server.socks.append(s)
    s.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{server.port}"
               "\r\n\r\n").encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = s.recv(65536)
        assert chunk, "SSE stream closed before its headers"
        buf += chunk
    assert buf.startswith(b"HTTP/1.0 200") or buf.startswith(b"HTTP/1.1 200"), buf[:40]
    assert b"event: busy" not in buf
    return s


def get_root(server, wait=10.0):
    """GET / once; returns (reply bytes, closed by the server)."""
    s = socket.create_connection(("127.0.0.1", server.port), timeout=wait)
    try:
        try:
            s.sendall(f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n\r\n".encode())
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            return b"", True
        out = b""
        while True:
            try:
                chunk = s.recv(65536)
            except socket.timeout:
                return out, False
            except (ConnectionResetError, ConnectionAbortedError):
                return out, True
            if not chunk:
                return out, True
            out += chunk
    finally:
        s.close()


def assert_refused(server):
    """Connection 65: closed at once with no reply and no new thread."""
    started = server.started
    t0 = time.monotonic()
    out, closed = get_root(server)
    took = time.monotonic() - t0
    assert closed and out == b"", out[:60]
    # "at once": a held connection would answer only after a slot freed,
    # i.e. after the idle timeout
    assert took < IDLE_S, f"refusal took {took:.2f} s"
    assert server.started == started
    assert server.live == alhttp.MAX_HANDLER_THREADS


def fill_with_idle(server):
    while server.live < alhttp.MAX_HANDLER_THREADS:
        open_idle(server)
    assert server.live == alhttp.MAX_HANDLER_THREADS


def test_connection_65_is_refused_while_64_idle_ones_are_open(srv):
    assert alhttp.MAX_HANDLER_THREADS == 64
    fill_with_idle(srv)
    assert_refused(srv)
    # still refused on a second try: the refusal took no slot
    assert_refused(srv)


def test_dashboard_loads_again_after_the_idle_ones_time_out(srv):
    fill_with_idle(srv)
    assert_refused(srv)
    # every idle connection is dropped by its socket timeout ...
    for s in srv.socks:
        s.settimeout(IDLE_S * 5)
        try:
            assert s.recv(1) == b""
        except (ConnectionResetError, ConnectionAbortedError):
            pass
    wait_for(lambda: srv.live == 0, "handler threads never ended")
    # ... and the dashboard answers again with no restart and no click
    end = time.monotonic() + 30
    while True:
        out, _ = get_root(srv)
        if out.startswith(b"HTTP/"):
            break
        assert time.monotonic() < end, "GET / never answered again"
        time.sleep(0.05)
    assert out.split(b" ", 2)[1] == b"200", out[:60]


def test_sse_streams_count_inside_the_cap(srv):
    for _ in range(alhttp.MAX_SSE_CLIENTS):
        open_sse(srv)
    wait_for(lambda: srv.live == alhttp.MAX_SSE_CLIENTS, "SSE streams hold no thread")
    # 16 streams + 48 idle = 64 handler threads: the 65th is refused
    fill_with_idle(srv)
    assert_refused(srv)
    # once the idle ones time out the streams alone stay inside the cap and
    # a page load answers again
    wait_for(lambda: srv.live == alhttp.MAX_SSE_CLIENTS, "idle connections never dropped")
    out, _ = get_root(srv)
    assert out.split(b" ", 2)[1] == b"200", out[:60]
