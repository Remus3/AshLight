"""API-TOKEN-HDR: the token is accepted as X-AL-Token, as Authorization:
Bearer and as ?token= (EventSource cannot set headers). The Host / Origin
checks run first and are not weakened by the Bearer form (decision 0002,
"API token"). Ephemeral port; runtime under tmp_path.
"""

import http.client
import socket
import threading
from pathlib import Path

import pytest

from server.al.core import Core
from server.al.http import serve

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "b" * 48


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


def req(server, method, path, headers=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": host or f"127.0.0.1:{server.port}"}
    h.update(headers or {})
    conn.request(method, path, headers=h)
    r = conn.getresponse()
    r.read()
    conn.close()
    return r


def test_bearer_header_accepted(srv):
    for path in ("/api/health", "/api/state", "/api/version"):
        assert req(srv, "GET", path, {"Authorization": f"Bearer {TOKEN}"}).status == 200
        assert req(srv, "GET", path, {"Authorization": f"bearer  {TOKEN} "}).status == 200


def test_bearer_wrong_or_other_scheme_refused(srv):
    for value in (f"Bearer {TOKEN}x", "Bearer ", "Bearer", f"Basic {TOKEN}", TOKEN,
                  f"Token {TOKEN}"):
        r = req(srv, "GET", "/api/health", {"Authorization": value})
        assert r.status == 401, value
        # a 401 never asks the browser for credentials (no auth prompt)
        assert r.getheader("WWW-Authenticate") is None


def test_query_token_still_accepted_for_eventsource(srv):
    assert req(srv, "GET", f"/api/health?token={TOKEN}").status == 200
    s = socket.create_connection(("127.0.0.1", srv.port), timeout=5)
    try:
        s.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{srv.port}"
                   "\r\nAccept: text/event-stream\r\n\r\n").encode("ascii"))
        head = s.recv(4096).decode("ascii", "replace")
    finally:
        s.close()
    assert head.startswith("HTTP/1.") and " 200 " in head.split("\r\n")[0]


def test_bearer_does_not_bypass_host_or_origin(srv):
    bearer = {"Authorization": f"Bearer {TOKEN}"}
    assert req(srv, "GET", "/api/health", bearer, host=f"evil.example:{srv.port}").status == 400
    r = req(srv, "GET", "/api/health", {**bearer, "Origin": "http://evil.example"})
    assert r.status == 403
    # no CORS preflight is granted, so a cross-origin page cannot send it
    r = req(srv, "OPTIONS", "/api/health",
            {"Origin": "http://evil.example", "Access-Control-Request-Method": "GET",
             "Access-Control-Request-Headers": "authorization"})
    assert r.status >= 400
    assert r.getheader("Access-Control-Allow-Headers") is None


def test_header_wins_over_query(srv):
    # a wrong header is not rescued by a right query token: the first form
    # given is the one checked
    r = req(srv, "GET", f"/api/health?token={TOKEN}", {"Authorization": "Bearer nope"})
    assert r.status == 401
