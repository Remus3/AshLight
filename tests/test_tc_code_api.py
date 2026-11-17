"""TC-CODE paste-a-code API: token-gated, local decode, reload on start.

Ephemeral port and tmp runtime only; a running AshLight is never touched.
"""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al.core import Core
from server.al.http import MAX_BUILD_BODY, serve
from server.al.theorycraft import codec
from tc_fixtures import FULL_XML, MINIMAL_XML

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "b" * 48

pytestmark = pytest.mark.server


def _start(runtime, log):
    core = Core(runtime=runtime, log_path=str(log), poll_s=0.05)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    return core, server


@pytest.fixture
def env(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    started = []

    def start():
        core, server = _start(tmp_path / "rt", log)
        started.append((core, server))
        return server
    yield start
    for core, server in started:
        server.stop()
        core.close()


def req(server, method, path, body=None, token=TOKEN, ctype="application/json"):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": f"127.0.0.1:{server.port}"}
    if token:
        h["X-AL-Token"] = token
    if body is not None:
        h["Content-Type"] = ctype
        if not isinstance(body, bytes):
            body = json.dumps(body).encode("ascii")
    conn.request(method, path, body=body, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, (json.loads(data) if data[:1] == b"{" else data)


def test_build_endpoints_need_token(env):
    srv = env()
    assert req(srv, "GET", "/api/build", token=None)[0] == 401
    assert req(srv, "POST", "/api/build-code", {"code": "x"}, token=None)[0] == 401
    assert req(srv, "POST", "/api/build-code", {"code": "x"}, token="nope")[0] == 401


def test_paste_code_then_reload_on_start(env):
    srv = env()
    status, doc = req(srv, "GET", "/api/build")
    assert status == 200 and doc["loaded"] is False
    code = codec.encode(FULL_XML)
    status, doc = req(srv, "POST", "/api/build-code", {"code": "\n" + code + "\n"})
    assert status == 200, doc
    assert doc["loaded"] and doc["build"]["class_name"] == "Monk"
    assert doc["build"]["gear"]["Gloves"]["name"] == "Doom Grip"
    assert codec.decode(doc["code"]) == FULL_XML
    # a fresh core on the same runtime reloads it with no request
    srv2 = env()
    status, doc = req(srv2, "GET", "/api/build")
    assert status == 200 and doc["loaded"] and doc["build"]["ascendancy"] == "Invoker"


def test_bad_inputs(env):
    srv = env()
    req(srv, "POST", "/api/build-code", {"code": codec.encode(MINIMAL_XML)})
    status, doc = req(srv, "POST", "/api/build-code", {"code": "https://pobb.in/AbCd"})
    assert status == 422 and doc["kind"] == "url" and "not supported yet" in doc["error"]
    assert req(srv, "POST", "/api/build-code", {"code": "garbage!!"})[0] == 400
    assert req(srv, "POST", "/api/build-code", {"code": 5})[0] == 400
    assert req(srv, "POST", "/api/build-code", b"{}", ctype="text/plain")[0] == 415
    big = b'{"code": "' + b"A" * MAX_BUILD_BODY + b'"}'
    assert req(srv, "POST", "/api/build-code", big)[0] == 413
    # the good build survived every bad paste
    status, doc = req(srv, "GET", "/api/build")
    assert doc["build"]["class_name"] == "Warrior"


def test_rejected_body_drain_is_bounded(env):
    """TEST-413-FLAKE: the 413 drain never waits on a client that does not
    send its declared body (DRAIN_TIMEOUT_S), and a body past DRAIN_MAX is
    not read at all - the reply still comes."""
    import socket
    import time
    from server.al import http as alhttp
    srv = env()
    for length, send in ((MAX_BUILD_BODY + 10, b"A" * 100), (alhttp.DRAIN_MAX + 1, b"")):
        s = socket.create_connection(("127.0.0.1", srv.port), timeout=10)
        try:
            head = (f"POST /api/build-code HTTP/1.1\r\nHost: 127.0.0.1:{srv.port}\r\n"
                    f"X-AL-Token: {TOKEN}\r\nContent-Type: application/json\r\n"
                    f"Content-Length: {length}\r\n\r\n").encode("ascii")
            t0 = time.monotonic()
            s.sendall(head + send)
            data = b""
            while b"\r\n" not in data:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            assert data.startswith(b"HTTP/1.0 413") or data.startswith(b"HTTP/1.1 413")
            assert time.monotonic() - t0 < alhttp.DRAIN_TIMEOUT_S + 3
        finally:
            s.close()


def test_large_real_sized_code_accepted(env):
    srv = env()
    filler = "".join(f'\t\t<PlayerStat stat="S{i}" value="{i * 7919 % 100003}"/>\n'
                     for i in range(6000))
    xml = FULL_XML.replace('\t</Build>', filler + '\t</Build>', 1)
    code = codec.encode(xml)
    assert len(code) > 4096
    status, doc = req(srv, "POST", "/api/build-code", {"code": code})
    assert status == 200 and doc["build"]["stats"]["S5999"] == 5999 * 7919 % 100003
