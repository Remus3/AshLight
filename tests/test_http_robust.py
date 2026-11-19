"""TEST-HTTP: robustness of the HTTP / SSE surface beyond the security floor
(tests/test_http_security.py): malformed and oversized requests, idle and
short-body clients, deep JSON, many SSE clients and slow SSE readers.

Ephemeral port, runtime in tmp_path; a running AshLight is never touched.
"""

import http.client
import json
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
TOKEN = "r" * 48


@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.setattr(alhttp.Handler, "timeout", 0.5)
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web")
    errors = []
    real = server.handle_error

    def spy(request, addr):
        import sys
        errors.append(repr(sys.exc_info()[1]))
        real(request, addr)

    server.handle_error = spy
    server.errors = errors
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def raw(server, data, wait=3.0):
    """Send bytes, read until the server closes; returns (bytes, closed)."""
    s = socket.create_connection(("127.0.0.1", server.port), timeout=wait)
    try:
        if data:
            s.sendall(data)
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


def head(server):
    return f"Host: 127.0.0.1:{server.port}\r\nX-AL-Token: {TOKEN}\r\n"


def post(server, path, body):
    return raw(server, (f"POST {path} HTTP/1.1\r\n{head(server)}Content-Type: "
                        f"application/json\r\nContent-Length: {len(body)}\r\n\r\n").encode()
               + body)


def status(reply):
    return int(reply.split(b" ", 2)[1]) if reply.startswith(b"HTTP/") else None


def test_idle_connection_is_dropped(srv):
    out, closed = raw(srv, b"", wait=3.0)
    assert closed and out == b""


def test_short_body_is_dropped_not_hung(srv):
    out, closed = raw(srv, (f"POST /api/consent HTTP/1.1\r\n{head(srv)}Content-Type: "
                            "application/json\r\nContent-Length: 100\r\n\r\n{").encode())
    assert closed
    assert not srv.core.consented()


def test_garbage_request_line_gets_400(srv):
    out, closed = raw(srv, b"\x16\x03\x01\x00\xff garbage\r\n\r\n")
    # no parsable version, so the stdlib answers HTTP/0.9 style (body only)
    assert b"Error code: 400" in out and closed
    assert not [e for e in srv.errors if "AttributeError" in e]


def test_overlong_uri_gets_414(srv):
    out, _ = raw(srv, b"GET /" + b"a" * 70000 + b" HTTP/1.1\r\n\r\n")
    assert status(out) == 414
    assert not [e for e in srv.errors if "AttributeError" in e]


@pytest.mark.parametrize("path,body", [
    ("/api/consent", b"[" * 4000),
    ("/api/build-code", b'{"code":' + b"[" * 100000 + b"}"),
    ("/api/eval", b'{"item":' + b'{"a":' * 7000 + b"1" + b"}" * 7000 + b"}"),
])
def test_deeply_nested_json_gets_400(srv, path, body):
    out, _ = post(srv, path, body)
    assert status(out) == 400, out[:80]
    assert not [e for e in srv.errors if "RecursionError" in e]


@pytest.mark.parametrize("body", [b"", b"{", b"null", b"[]", b'"x"', b"\xff\xfe",
                                  b'{"consent": "yes"}', b'{"consent": NaN}'])
def test_malformed_consent_bodies_never_consent(srv, body):
    out, _ = post(srv, "/api/consent", body)
    assert status(out) in (200, 400) and not srv.core.consented()


def test_bad_content_length_values(srv):
    for value in ("abc", "-5", "99999999999"):
        out, _ = raw(srv, (f"POST /api/consent HTTP/1.1\r\n{head(srv)}Content-Type: "
                           f"application/json\r\nContent-Length: {value}\r\n\r\n").encode())
        assert status(out) == 413, (value, out[:60])


def test_token_edge_cases(srv):
    host = f"Host: 127.0.0.1:{srv.port}\r\n"
    for line in (f"GET /api/health?token=\u00e9 HTTP/1.1\r\n{host}\r\n",
                 f"GET /api/health HTTP/1.1\r\n{host}X-AL-Token: \u00e9\u00e9\r\n\r\n",
                 f"GET /api/health HTTP/1.1\r\n{host}X-AL-Token: {TOKEN[:-1]}\r\n\r\n",
                 f"GET /api/health HTTP/1.1\r\n{host}X-AL-Token: {TOKEN}x\r\n\r\n",
                 f"GET /api/health HTTP/1.1\r\n{host}Authorization: Basic {TOKEN}\r\n\r\n",
                 f"GET /api/health?token= HTTP/1.1\r\n{host}\r\n"):
        out, _ = raw(srv, line.encode("utf-8"))
        assert status(out) == 401, line


def test_host_and_origin_edge_cases(srv):
    p = srv.port
    t = f"X-AL-Token: {TOKEN}\r\n"
    cases = [(f"Host: 127.0.0.1:{p}.evil.example\r\n", 400),
             (f"Host: 127.0.0.1\r\n", 400),
             (f"Host: [::1]:{p}\r\n", 400),
             (f"Host: LOCALHOST:{p}\r\n", 200),
             (f"Host: 127.0.0.1:{p}\r\nOrigin: http://127.0.0.1:{p}.evil\r\n", 403),
             # SEC-CROSS-SITE: Origin null opens only GET /events (the overlay)
             (f"Host: 127.0.0.1:{p}\r\nOrigin: null\r\n", 403),
             ]
    for hdr, want in cases:
        out, _ = raw(srv, f"GET /api/health HTTP/1.1\r\n{hdr}{t}\r\n".encode())
        assert status(out) == want, (hdr, out[:60])
    # "Origin: null" never reaches a write endpoint
    body = b'{"consent": true}'
    out, _ = raw(srv, (f"POST /api/consent HTTP/1.1\r\nHost: 127.0.0.1:{p}\r\n{t}Origin: "
                       f"null\r\nContent-Type: application/json\r\nContent-Length: "
                       f"{len(body)}\r\n\r\n").encode() + body)
    assert status(out) == 403 and not srv.core.consented()


def open_sse(server):
    s = socket.create_connection(("127.0.0.1", server.port), timeout=5)
    s.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{server.port}"
               "\r\n\r\n").encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += s.recv(65536)
    return s, buf


def test_sse_client_cap_and_slot_release(srv):
    socks = []
    try:
        for _ in range(alhttp.MAX_SSE_CLIENTS):
            s, buf = open_sse(srv)
            assert status(buf) == 200
            socks.append(s)
        s, buf = open_sse(srv)
        s.settimeout(3)
        while True:  # read to the close: the refusal is a short, closed stream
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        s.close()
        # 200 + a long retry, not 503: an EventSource gives up for good on a
        # non-200 reply, but reconnects by itself after a closed 200 stream
        assert status(buf) == 200 and b"retry: 30000" in buf and b"event: busy" in buf
        assert b"event: state" not in buf
        # the API still answers while every stream slot is taken
        out, _ = raw(srv, f"GET /api/health HTTP/1.1\r\n{head(srv)}\r\n".encode())
        assert status(out) == 200
        socks.pop().close()
        srv.core.bus.publish({"type": "death", "character": "Me", "suicide": False})
        end = time.monotonic() + 20  # generous: a deadline, not a budget
        while True:  # the closed stream's slot frees once its write fails
            s, buf = open_sse(srv)
            while b"event: state" not in buf and b"event: busy" not in buf:
                buf += s.recv(65536)
            if b"event: state" in buf:
                socks.append(s)
                break
            s.close()
            assert time.monotonic() < end, "slot never released"
            srv.core.bus.publish({"type": "death", "character": "Me", "suicide": False})
            time.sleep(0.1)
    finally:
        for s in socks:
            s.close()


def test_slow_sse_reader_is_dropped_and_does_not_stall_others(srv):
    """A stalled SSE client (never reads, tiny receive buffer) is cut by its
    write timeout; no publish blocks on it and a reading client keeps up.

    TEST-FLAKE-SSE: the old version let the "fast" client sit unread while
    1.6 MB was published, so it survived only while Windows loopback
    buffering (~3 MB default, ~400 KB at SO_RCVBUF 4096) outran the 0.5 s
    write timeout, with a fixed 400-event count and wall-clock budgets on
    top. Now the fast client really reads (a thread), publishing runs until
    the slow subscription is gone, and every wait is a condition with a
    generous deadline - load only makes it slower, never red."""
    slow = socket.socket()
    slow.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    slow.connect(("127.0.0.1", srv.port))
    slow.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{srv.port}"
                  "\r\n\r\n").encode())
    fast, got = open_sse(srv)
    got = bytearray(got)
    lock = threading.Lock()
    stop = threading.Event()
    closed = threading.Event()

    def read_fast():
        fast.settimeout(0.2)
        while not stop.is_set():
            try:
                chunk = fast.recv(1 << 20)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            with lock:
                got.extend(chunk)
        closed.set()

    reader = threading.Thread(target=read_fast, daemon=True)
    try:
        end = time.monotonic() + 30
        while srv.core.bus.subscriber_count < 2:
            assert time.monotonic() < end, "streams never subscribed"
            time.sleep(0.02)
        reader.start()
        big = "x" * 4000
        worst = 0.0
        n = 0
        end = time.monotonic() + 60
        while srv.core.bus.subscriber_count > 1:  # until the slow one is cut
            assert time.monotonic() < end, "slow reader was never dropped"
            assert not closed.is_set(), "fast stream closed while reading"
            t0 = time.perf_counter()
            srv.core.bus.publish({"type": "chat", "channel": "#", "name": "Spam",
                                  "text": big, "i": n})
            worst = max(worst, time.perf_counter() - t0)
            n += 1
            if n % 10 == 0:
                time.sleep(0.02)  # ~2 MB/s: fills the slow socket, not the fast
        # a publish is a deque append per subscriber; seconds would mean it
        # waited on a socket (generous: it is ~microseconds unloaded)
        assert worst < 2.0, f"a publish blocked for {worst:.2f} s"
        srv.core.bus.publish({"type": "chat", "channel": "#", "name": "Marker",
                              "text": "end"})
        end = time.monotonic() + 30
        while True:
            with lock:
                if b'"name":"Marker"' in got:
                    break
            assert not closed.is_set(), "fast stream closed"
            assert time.monotonic() < end, "fast stream stalled"
            time.sleep(0.05)
        assert srv.core.bus.subscriber_count == 1  # the fast one is still live
    finally:
        stop.set()
        slow.close()
        fast.close()
        reader.join(timeout=5) if reader.is_alive() else None


def test_default_socket_timeout_is_finite():
    """The srv fixture shortens it to 0.5 s; the shipped value must be finite,
    or idle, short-body and slow SSE clients pin a thread forever."""
    assert alhttp.Handler.timeout == alhttp.REQUEST_TIMEOUT_S
    assert 1.0 <= alhttp.REQUEST_TIMEOUT_S <= 30.0


def test_many_sequential_requests_leak_no_threads(srv):
    before = threading.active_count()
    for _ in range(100):
        conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
        conn.request("GET", "/api/state", headers={"Host": f"127.0.0.1:{srv.port}",
                                                   "X-AL-Token": TOKEN})
        r = conn.getresponse()
        assert r.status == 200 and json.loads(r.read())["version"] >= 0
        conn.close()
    time.sleep(0.3)
    assert threading.active_count() <= before + 2
