"""TC-EVAL API: POST /api/eval, GET / PUT /api/weights behind the token.

Ephemeral port and tmp runtime only; a running AshLight is never touched.
The item text is posted by the test; the server never reads the clipboard.
"""

import http.client
import json
import socket
import threading
from pathlib import Path

import pytest

from server.al.core import Core
from server.al.http import serve
from server.al.theorycraft import codec
from server.al.theorycraft import weights as wm
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML, RARE_GLOVES

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "e" * 48

pytestmark = pytest.mark.server


@pytest.fixture
def env(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    started = []

    def start():
        core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
        server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                       tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True).start()
        started.append((core, server))
        return server
    yield start, tmp_path / "rt"
    for core, server in started:
        server.stop()
        core.close()


def req(server, method, path, body=None, token=TOKEN, ctype="application/json",
        host=None, origin=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": host or f"127.0.0.1:{server.port}"}
    if token:
        h["X-AL-Token"] = token
    if origin:
        h["Origin"] = origin
    if body is not None:
        h["Content-Type"] = ctype
        if not isinstance(body, bytes):
            body = json.dumps(body).encode("ascii")
    conn.request(method, path, body=body, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, (json.loads(data) if data[:1] == b"{" else data)


def test_endpoints_need_token_host_origin(env):
    start, _ = env
    srv = start()
    for method, path, body in (("POST", "/api/eval", {"item": "x"}),
                               ("GET", "/api/weights", None),
                               ("PUT", "/api/weights", {"weights": {}})):
        assert req(srv, method, path, body, token=None)[0] == 401
        assert req(srv, method, path, body, token="nope")[0] == 401
        assert req(srv, method, path, body, host="evil.example:80")[0] == 400
        assert req(srv, method, path, body, origin="http://evil.example")[0] == 403
        assert req(srv, method, path, body, origin="null")[0] == 403
    assert req(srv, "PUT", "/api/build-code", {"code": "x"})[0] == 405
    assert req(srv, "DELETE", "/api/weights")[0] == 405


def _early_reject_roundtrip(srv, host, extra_head=""):
    """FLAKY-EVAL-API: send the headers, wait for the first reply byte (or
    for the server to wait on the body), then send the body and read to EOF.
    A server that answers and closes with the body still unread makes
    Windows send a reset, and the client loses the reply (WinError 10053 /
    10054). Event-ordered, no sleep: the reply cannot come before the body
    once the server drains it, so the recv times out harmlessly first."""
    body = b'{"item": "x"}'
    s = socket.create_connection(("127.0.0.1", srv.port), timeout=5)
    try:
        s.sendall(("POST /api/eval HTTP/1.1\r\nHost: %s\r\n%s"
                   "Content-Type: application/json\r\nContent-Length: %d\r\n\r\n"
                   % (host, extra_head, len(body))).encode("ascii"))
        s.settimeout(0.2)
        try:
            data = s.recv(65536)
        except socket.timeout:
            data = b""
        s.settimeout(5)
        s.sendall(body)
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
        return data
    finally:
        s.close()


def test_early_reject_drains_body_no_reset(env):
    start, _ = env
    srv = start()
    good = f"127.0.0.1:{srv.port}"
    assert _early_reject_roundtrip(srv, good).startswith(b"HTTP/1.0 401")
    assert _early_reject_roundtrip(srv, "evil.example:80").startswith(b"HTTP/1.0 400")
    assert _early_reject_roundtrip(
        srv, good, "X-AL-Token: %s\r\nOrigin: null\r\n" % TOKEN).startswith(b"HTTP/1.0 403")


def test_eval_against_loaded_build(env):
    start, _ = env
    srv = start()
    status, doc = req(srv, "POST", "/api/eval", {"item": RARE_GLOVES})
    assert status == 200 and doc["error"] == "no build loaded" and doc["score"] == 81
    assert req(srv, "POST", "/api/build-code", {"code": codec.encode(EVAL_BUILD_XML)})[0] == 200
    status, doc = req(srv, "POST", "/api/eval", {"item": ADVANCED_RING})
    assert status == 200 and doc["ok"]
    assert doc["slot"] == "Ring 1" and doc["verdict"] == "upgrade"
    assert len(doc["comparisons"]) == 2
    status, doc = req(srv, "POST", "/api/eval", {"item": RARE_GLOVES, "slot": "Ring 2"})
    assert status == 200 and doc["slot"] == "Ring 2"


def test_eval_bad_inputs(env):
    start, _ = env
    srv = start()
    assert req(srv, "POST", "/api/eval", {})[0] == 400
    assert req(srv, "POST", "/api/eval", {"item": 5})[0] == 400
    assert req(srv, "POST", "/api/eval", {"item": "x", "slot": 3})[0] == 400
    assert req(srv, "POST", "/api/eval", b"{}", ctype="text/plain")[0] == 415
    big = b'{"item": "' + b"A" * (100 * 1024) + b'"}'
    assert req(srv, "POST", "/api/eval", big)[0] == 413
    status, doc = req(srv, "POST", "/api/eval", {"item": "just some text"})
    assert status == 200 and doc["ok"] is False and doc["error"] == "not an item"


def test_weights_get_put_persist(env):
    start, rt = env
    srv = start()
    status, doc = req(srv, "GET", "/api/weights")
    assert status == 200 and doc["weights"] == wm.DEFAULT_WEIGHTS and doc["load_error"] is None
    assert wm.default_path(rt).is_file()
    new = {"weights": {"+# to maximum Life": 5}, "sidegrade": {"abs": 0, "pct": 0}}
    status, doc = req(srv, "PUT", "/api/weights", new)
    assert status == 200 and doc["weights"] == {"+# to maximum Life": 5}
    assert req(srv, "PUT", "/api/weights", {"weights": {"a": "x"}})[0] == 400
    assert req(srv, "PUT", "/api/weights", {"weights": {"a": 1}}, ctype="text/plain")[0] == 415
    # the score uses the stored weights at once, and a fresh core reloads them
    status, doc = req(srv, "POST", "/api/eval", {"item": RARE_GLOVES})
    assert doc["score"] == 350
    srv2 = start()
    status, doc = req(srv2, "GET", "/api/weights")
    assert doc["weights"] == {"+# to maximum Life": 5}
