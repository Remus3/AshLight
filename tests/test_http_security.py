"""HTTP security floor: token, Host, Origin, CSP, loopback bind, consent gate.

The server binds an ephemeral port (0) so a running AshLight is never touched;
runtime state goes to tmp_path.
"""

import http.client
import json
import socket
import threading
from pathlib import Path

import pytest

from server.al import ports
from server.al.core import Core
from server.al.http import CSP, serve

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "t" * 48


@pytest.fixture
def srv(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def req(server, method, path, headers=None, body=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": host or f"127.0.0.1:{server.port}"}
    h.update(headers or {})
    conn.request(method, path, body=body, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r, data


def auth():
    return {"X-AL-Token": TOKEN}


def test_binds_loopback_only(srv):
    assert srv.server_address[0] == "127.0.0.1"
    assert ports.LOOPBACK == "127.0.0.1"
    assert ports.AL_PORT == 8960 and ports.in_block(ports.AL_PORT)


def test_token_required(srv):
    for path in ("/api/health", "/api/state", "/api/version"):
        r, _ = req(srv, "GET", path)
        assert r.status == 401, path
        r, _ = req(srv, "GET", path, {"X-AL-Token": "wrong"})
        assert r.status == 401, path
        r, _ = req(srv, "GET", path, auth())
        assert r.status == 200, path
    r, _ = req(srv, "GET", f"/api/health?token={TOKEN}")  # S3: /events only
    assert r.status == 401
    r, _ = req(srv, "GET", "/events")
    assert r.status == 401


def test_host_header_checked(srv):
    r, _ = req(srv, "GET", "/api/health", auth(), host="evil.example:%d" % srv.port)
    assert r.status == 400
    r, _ = req(srv, "GET", "/", host="127.0.0.1:1")
    assert r.status == 400
    r, _ = req(srv, "GET", "/api/health", auth(), host=f"localhost:{srv.port}")
    assert r.status == 200


def test_origin_checked(srv):
    r, _ = req(srv, "GET", "/api/health", {**auth(), "Origin": "http://evil.example"})
    assert r.status == 403
    r, _ = req(srv, "GET", "/api/health",
               {**auth(), "Origin": f"http://127.0.0.1:{srv.port}"})
    assert r.status == 200
    # The file:// overlay may read state; it may never POST.
    r, _ = req(srv, "GET", "/api/state", {**auth(), "Origin": "null"})
    assert r.status == 200 and r.getheader("Access-Control-Allow-Origin") == "null"
    r, _ = req(srv, "POST", "/api/consent",
               {**auth(), "Origin": "null", "Content-Type": "application/json"},
               body=json.dumps({"consent": True}))
    assert r.status == 403


def test_security_headers_on_dashboard(srv):
    r, body = req(srv, "GET", "/")
    assert r.status == 200
    csp = r.getheader("Content-Security-Policy")
    assert csp == CSP
    assert "default-src 'self'" in csp and "connect-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp and "unsafe-inline" not in csp
    assert r.getheader("X-Content-Type-Options") == "nosniff"
    assert r.getheader("Referrer-Policy") == "no-referrer"
    assert b"<script" in body and b"src=" in body
    r, _ = req(srv, "GET", "/tokens.css")
    assert r.status == 200 and "text/css" in r.getheader("Content-Type")


def test_dashboard_has_no_inline_script():
    html = (ROOT / "web" / "index.html").read_text(encoding="ascii")
    import re
    for tag in re.findall(r"<script[^>]*>", html):
        assert "src=" in tag
    assert re.search(r"<script[^>]*>\s*[^<\s]", html) is None
    for tag in re.findall(r"<[^>]+>", html):
        assert re.search(r"\son[a-z]+\s*=", tag) is None, tag
    assert "style=" not in html


def test_static_traversal_blocked(srv):
    r, _ = req(srv, "GET", "/web/../server/al/http.py")
    assert r.status == 404
    r, _ = req(srv, "GET", "/web/%2e%2e/README.md")
    assert r.status == 404


def test_consent_gate(srv):
    core = srv.core
    assert core.tailer is None
    r, _ = req(srv, "POST", "/api/consent", {"Content-Type": "application/json"},
               body=json.dumps({"consent": True}))
    assert r.status == 401 and core.tailer is None
    r, _ = req(srv, "POST", "/api/consent", {**auth(), "Content-Type": "text/plain"},
               body=json.dumps({"consent": True}))
    assert r.status == 415 and core.tailer is None
    r, _ = req(srv, "POST", "/api/consent", {**auth(), "Content-Type": "application/json"},
               body=json.dumps({"consent": "yes"}))
    assert r.status == 400 and core.tailer is None
    r, data = req(srv, "POST", "/api/consent",
                  {**auth(), "Content-Type": "application/json"},
                  body=json.dumps({"consent": True}))
    assert r.status == 200
    assert json.loads(data)["state"]["tailer"]["consented"] is True
    assert core.tailer is not None and core.tailer.running
    r, _ = req(srv, "POST", "/api/consent", {**auth(), "Content-Type": "application/json"},
               body=json.dumps({"consent": False}))
    assert r.status == 200 and core.tailer is None


def test_clipboard_read_is_a_501_stub(srv):
    r, _ = req(srv, "POST", "/api/clipboard-read", auth())
    assert r.status == 501


def test_sse_stream_sends_state_then_events(srv):
    s = socket.create_connection(("127.0.0.1", srv.port), timeout=5)
    s.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{srv.port}\r\n"
               "Accept: text/event-stream\r\n\r\n").encode())
    buf = b""
    while b"event: state" not in buf:
        buf += s.recv(65536)
    assert b"text/event-stream" in buf and b"Content-Security-Policy" in buf
    srv.core.bus.publish({"type": "death", "character": "Me", "suicide": False})
    while b"event: events" not in buf:
        buf += s.recv(65536)
    s.close()
