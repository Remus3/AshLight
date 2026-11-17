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


def test_large_real_sized_code_accepted(env):
    srv = env()
    filler = "".join(f'\t\t<PlayerStat stat="S{i}" value="{i * 7919 % 100003}"/>\n'
                     for i in range(6000))
    xml = FULL_XML.replace('\t</Build>', filler + '\t</Build>', 1)
    code = codec.encode(xml)
    assert len(code) > 4096
    status, doc = req(srv, "POST", "/api/build-code", {"code": code})
    assert status == 200 and doc["build"]["stats"]["S5999"] == 5999 * 7919 % 100003
