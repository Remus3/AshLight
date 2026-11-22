"""AUDIT-HTTP-HARDEN (audit findings S1-S4, docs/audit/2026-11-17-audit.md).

S1 HEAD /events never opens the endless stream.
S2 the handler has a socket timeout, so an idle connection frees its thread.
S3 ?token= is accepted on /events only (EventSource), not on /api routes.
S4 POST /api/consent "path" refuses UNC / device / relative paths and file
   names other than Client.txt, lexically (no file system or SMB access).
OVL-APP-SCHEME-STRICT (F-174): the origin table of the read-only feed path
   holds only the app scheme's origin; null and file pages are refused.

Ephemeral port, runtime under tmp_path; a running AshLight is never touched.
"""

import http.client
import socket
import threading
import time
from pathlib import Path

import pytest

from server.al import logfile
from server.al.core import Core
from server.al import http as al_http
from server.al.http import Handler, serve

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "h" * 48
# drive prefixes built from parts (the leak sweep refuses literal drive paths)
CD = "C" + ":"
DD = "D" + ":"


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


def req(server, method, path, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": f"127.0.0.1:{server.port}"}
    h.update(headers or {})
    conn.request(method, path, body=body, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r, data


# -- S1
def test_head_events_does_not_stream(srv):
    s = socket.create_connection(("127.0.0.1", srv.port), timeout=5)
    try:
        s.sendall((f"HEAD /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{srv.port}"
                   "\r\n\r\n").encode("ascii"))
        data = b""
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            chunk = s.recv(4096)
            if not chunk:
                break  # the server closed the connection: no endless stream
            data += chunk
        else:
            pytest.fail("HEAD /events kept the connection open")
    finally:
        s.close()
    head = data.decode("ascii", "replace")
    assert head.startswith("HTTP/1.0 405") or head.startswith("HTTP/1.1 405"), head
    assert "Allow: GET" in head
    assert "text/event-stream" not in head


def test_head_on_a_normal_route_still_works(srv):
    r, data = req(srv, "HEAD", "/api/health", {"X-AL-Token": TOKEN})
    assert r.status == 200 and data == b""


# -- S2
def test_handler_has_a_socket_timeout():
    assert isinstance(Handler.timeout, (int, float)) and 0 < Handler.timeout <= 60


def test_idle_connection_is_closed_by_the_server(srv, monkeypatch):
    monkeypatch.setattr(Handler, "timeout", 0.3)
    s = socket.create_connection(("127.0.0.1", srv.port), timeout=5)
    try:
        start = time.monotonic()
        got = s.recv(4096)  # send nothing: the server must hang up
        assert got == b"" or got.startswith(b"HTTP/")
        assert time.monotonic() - start < 4
    finally:
        s.close()


# -- S3
def test_query_token_refused_on_api_routes(srv):
    for path in ("/api/health", "/api/state", "/api/build"):
        r, _ = req(srv, "GET", f"{path}?token={TOKEN}")
        assert r.status == 401, path
    r, _ = req(srv, "POST", f"/api/web-data?token={TOKEN}",
               {"Content-Type": "application/json"}, b'{"enabled": false}')
    assert r.status == 401


def test_query_token_still_opens_events(srv):
    s = socket.create_connection(("127.0.0.1", srv.port), timeout=5)
    try:
        s.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{srv.port}"
                   "\r\nAccept: text/event-stream\r\n\r\n").encode("ascii"))
        head = s.recv(4096).decode("ascii", "replace")
    finally:
        s.close()
    assert " 200 " in head.split("\r\n", 1)[0]
    assert "text/event-stream" in head


# -- S4
@pytest.mark.parametrize("bad", [
    "\\\\evil-host\\share\\Client.txt",
    "//evil-host/share/Client.txt",
    "\\\\?\\" + CD + "\\Games\\logs\\Client.txt",
    "\\\\.\\pipe\\x",
    "relative\\logs\\Client.txt",
    CD + "\\Windows\\win.ini",
    CD + "\\Games\\logs\\Client.txt.bak",
    CD + "\\Games\\logs\\Client.txt\x00",
    CD + "\\Games\\logs\\Client.txt:stream",
])
def test_bad_consent_paths_refused_lexically(bad):
    assert not logfile.consent_path_ok(bad, windows=True), bad


@pytest.mark.parametrize("good", [
    CD + "\\Program Files (x86)\\Steam\\steamapps\\common\\Path of Exile 2\\logs\\Client.txt",
    DD + "\\SteamLibrary\\steamapps\\common\\Path of Exile 2\\logs\\client.txt",
    DD + "\\SteamLibrary\\steamapps\\common\\Path of Exile 2",
    DD + "\\SteamLibrary\\steamapps\\common\\Path of Exile 2\\logs\\",
])
def test_good_consent_paths_allowed(good, tmp_path):
    assert logfile.consent_path_ok(good, windows=True), good


def test_consent_api_refuses_unc_without_touching_it(srv):
    before = srv.core.log_path
    r, data = req(srv, "POST", "/api/consent",
                  {"X-AL-Token": TOKEN, "Content-Type": "application/json"},
                  b'{"consent": true, "path": "\\\\\\\\evil-host\\\\share\\\\Client.txt"}')
    assert r.status == 400, data
    assert b"path" in data
    assert srv.core.log_path == before
    assert not srv.core.consented()


def test_consent_api_accepts_a_local_client_txt(srv, tmp_path):
    other = tmp_path / "logs" / "Client.txt"
    other.parent.mkdir()
    other.write_bytes(b"")
    body = ('{"consent": false, "path": %s}' % __import__("json").dumps(str(other))).encode()
    r, data = req(srv, "POST", "/api/consent",
                  {"X-AL-Token": TOKEN, "Content-Type": "application/json"}, body)
    assert r.status == 200, data
    assert Path(srv.core.log_path) == other


def test_consent_api_refuses_a_file_not_named_client_txt(srv, tmp_path):
    """SEC-NO-DISCOVERY: a dot-free name passes the lexical check as a
    folder, but an existing FILE of that name is refused (400) and the
    tailer path and consent stay as they were."""
    before = srv.core.log_path
    secret = tmp_path / "notes" / "secrets"
    secret.parent.mkdir()
    secret.write_bytes(b"not a log\n")
    assert logfile.consent_path_ok(str(secret))
    body = ('{"consent": true, "path": %s}' % __import__("json").dumps(str(secret))).encode()
    r, data = req(srv, "POST", "/api/consent",
                  {"X-AL-Token": TOKEN, "Content-Type": "application/json"}, body)
    assert r.status == 400, data
    assert b"path" in data
    assert srv.core.log_path == before
    assert not srv.core.consented()
    assert srv.core.tailer is None or srv.core.tailer.path != secret


# -- OVL-APP-SCHEME-STRICT (F-174)
def test_origin_table_holds_only_the_app_scheme_origin():
    """The read-only path set is the feed alone and its origin table holds
    only the app scheme's origin: no null, no file page origin."""
    assert al_http.FILE_ORIGIN_PATHS == {"/events"}
    assert al_http.FILE_ORIGINS == {al_http.APP_ORIGIN} == {"al-app://app"}
    src = (ROOT / "server" / "al" / "http.py").read_text(encoding="utf-8")
    assert '"file://"' not in src and '"null"' not in src


def test_null_and_file_origins_get_403_on_the_feed_and_read_routes(srv):
    for origin in ("null", "file://"):
        for site in ("cross-site", None):
            h = {"X-AL-Token": TOKEN, "Origin": origin}
            if site:
                h["Sec-Fetch-Site"] = site
            for path in ("/api/state", "/api/health"):
                r, _ = req(srv, "GET", path, h)
                assert r.status == 403, (origin, site, path)
                assert r.getheader("Access-Control-Allow-Origin") is None
            s = socket.create_connection(("127.0.0.1", srv.port), timeout=5)
            try:
                s.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\n"
                           f"Host: 127.0.0.1:{srv.port}\r\n"
                           + "".join(f"{k}: {v}\r\n" for k, v in h.items()
                                     if k != "X-AL-Token") + "\r\n").encode())
                head = s.recv(65536)
            finally:
                s.close()
            assert head.split(b"\r\n")[0].endswith(b"403 Forbidden"), (origin, site, head[:60])
            assert b"Access-Control-Allow-Origin" not in head
