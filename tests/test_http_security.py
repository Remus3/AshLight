"""HTTP security floor: token, Host, Origin, CSP, loopback bind, consent gate.

The server binds an ephemeral port (0) so a running AshLight is never touched;
runtime state goes to tmp_path.
"""

import http.client
import json
import re
import socket
import threading
import time
from pathlib import Path

import pytest

import srcpaths
from server.al import http as al_http, ports
from server.al.core import Core
from server.al.http import CSP, serve, tap_event

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
    # SEC-CROSS-SITE / OVL-APP-SCHEME-STRICT: Origin null and a file page's
    # origin read nothing (not /events, /api/state or /api/health), never POST.
    for origin in ("null", "file://"):
        for path in ("/api/state", "/api/health"):
            r, _ = req(srv, "GET", path, {**auth(), "Origin": origin})
            assert r.status == 403, (origin, path)
            assert r.getheader("Access-Control-Allow-Origin") is None, (origin, path)
        r, _ = req(srv, "POST", "/api/consent",
                   {**auth(), "Origin": origin, "Content-Type": "application/json"},
                   body=json.dumps({"consent": True}))
        assert r.status == 403, origin


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
    html = srcpaths.index_html()
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
    # SEC-STATIC-MAP: more shapes; every one misses the name map
    for path in ("/web/..%2fREADME.md", "/web/..\\README.md", "/web/./index.html",
                 "/web//index.html", "/web/INDEX.HTML", "/web/", "/web/%69ndex.html",
                 "/web/" + str(ROOT / "README.md"), "/web/" + str(srcpaths.path("app.js"))):
        r, _ = req(srv, "GET", path)
        assert r.status == 404, path


# A drive name, built at run time so no tracked line holds a drive path.
DRIVE = chr(67) + ":"
SEP = chr(92)

# SEC-STATIC-MAP: tails that reached the file system before the map. Each
# one carries "zzq" or is matched by its own name in the spy records.
ODD_TAILS = ("//zzqhost/share/x.js",       # two slashes: a UNC path
             "\\\\zzqhost\\share\\x.js",   # the same with backslashes
             DRIVE + "/zzq/win.ini", DRIVE + "zzq.js",  # a drive name
             "index.html::$DATA", "zzq.js:stream",  # a stream suffix
             "index.html.", "app.js. ",    # a trailing dot / space
             "CON", "nul.zzq", "COM1", "web/AUX.js")  # device names


def _spied(monkeypatch):
    """Spies on Path.resolve, os.stat and open (builtins and io); returns
    the list of the string forms of their path arguments."""
    import builtins
    import io
    import os
    import pathlib
    seen = []
    real_resolve, real_stat, real_open = pathlib.Path.resolve, os.stat, builtins.open

    def resolve(self, *a, **k):
        seen.append(str(self))
        return real_resolve(self, *a, **k)

    def stat(path, *a, **k):
        seen.append(str(path))
        return real_stat(path, *a, **k)

    def opener(file, *a, **k):
        seen.append(str(file))
        return real_open(file, *a, **k)

    monkeypatch.setattr(pathlib.Path, "resolve", resolve)
    monkeypatch.setattr(os, "stat", stat)
    monkeypatch.setattr(builtins, "open", opener)
    monkeypatch.setattr(io, "open", opener)
    return seen


def _touched(seen, tail):
    t = tail.replace("\\", "/").strip("/")
    for s in seen:
        n = s.replace("\\", "/")
        if "zzq" in n or n == t or n.endswith("/" + t):
            return True
    return False


def test_static_path_shapes_get_404_without_a_file_system_call(srv, monkeypatch):
    from urllib.parse import quote
    seen = _spied(monkeypatch)
    # the spies are live: the old code shape would be caught
    (srv.web_root / "CON").resolve()
    assert _touched(seen, "CON")
    seen.clear()
    for tail in ODD_TAILS:
        raw = ("/web/" + tail,) if " " not in tail else ()  # http.client refuses a space
        for path in raw + ("/web/" + quote(tail, safe="/:"),):
            r, _ = req(srv, "GET", path)
            assert r.status == 404, path
        assert not _touched(seen, tail), (tail, [s for s in seen if "zzq" in s][:3])
    monkeypatch.undo()
    r, _ = req(srv, "GET", "/web/index.html")
    assert r.status == 200


def test_every_web_file_loads(srv):
    files = sorted(p for p in (ROOT / "web").rglob("*") if p.is_file())
    assert len(files) >= 10
    assert set(srv.static.names()) == {p.relative_to(ROOT / "web").as_posix() for p in files}
    for p in files:
        rel = p.relative_to(ROOT / "web").as_posix()
        r, body = req(srv, "GET", "/web/" + rel)
        assert r.status == 200, rel
        assert body == p.read_bytes(), rel
    for path in ("/", "/index.html", "/favicon.ico"):
        r, _ = req(srv, "GET", path)
        assert r.status == 200, path


def test_new_web_file_is_served_after_the_next_scan(tmp_path):
    web = tmp_path / "web"
    (web / "sub").mkdir(parents=True)
    (web / "index.html").write_bytes(b"<!doctype html>\n")
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, TOKEN, port=0, web_root=web)
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    try:
        assert req(server, "GET", "/web/sub/new.js")[0].status == 404
        (web / "sub" / "new.js").write_bytes(b"var x = 1;\n")
        # not listed yet: no scan happened, the request text made none
        assert req(server, "GET", "/web/sub/new.js")[0].status == 404
        core.reload_web = getattr(core, "reload_web", 0) + 1  # the hot-reload scan
        r, body = req(server, "GET", "/web/sub/new.js")
        assert r.status == 200 and body == b"var x = 1;\n"
        assert "javascript" in r.getheader("Content-Type")
        # a file gone after the scan is a 404, never an error
        (web / "sub" / "new.js").unlink()
        assert req(server, "GET", "/web/sub/new.js")[0].status == 404
        assert req(server, "GET", "/")[0].status == 200
    finally:
        server.stop()
        core.close()


def test_static_map_lists_only_files_inside_the_root(tmp_path):
    from server.al.static import StaticMap
    web = tmp_path / "web"
    (web / "a" / "b").mkdir(parents=True)
    (web / "a" / "b" / "c.css").write_bytes(b"x")
    (web / "top.js").write_bytes(b"y")
    (tmp_path / "secret.txt").write_bytes(b"s")
    m = StaticMap(web)
    assert m.names() == ["a/b/c.css", "top.js"]
    assert m.lookup("a/b/c.css") == (web / "a" / "b" / "c.css").resolve()
    for bad in ("../secret.txt", "a\\b\\c.css", "/top.js", "TOP.JS", "", None, 5):
        assert m.lookup(bad) is None, bad
    assert StaticMap(tmp_path / "missing").names() == []


# SEC-CROSS-SITE: every route, by method; bodies are valid JSON objects
GET_ROUTES = ("/", "/index.html", "/web/app.js", "/tokens.css", "/favicon.ico",
              "/api/health", "/api/version", "/api/state", "/api/overlay-layout",
              "/api/build", "/api/filter", "/api/buildfile", "/api/settings-export",
              "/api/weights", "/api/gfx", "/api/rates", "/api/web-data", "/events",
              "/no-such-route")
POST_ROUTES = ("/api/clipboard-read", "/api/consent", "/api/overlay-layout",
               "/api/trade-dismiss", "/api/build-code", "/api/eval", "/api/web-data",
               "/api/filter-merge", "/api/settings-import", "/api/run-history",
               "/api/price-watch", "/api/hints", "/no-such-route")


def _every_request():
    for path in GET_ROUTES:
        yield "GET", path
        if path != "/events":
            yield "HEAD", path
    for path in POST_ROUTES:
        yield "POST", path
    yield "PUT", "/api/weights"
    yield "PUT", "/api/state"
    for method in ("DELETE", "PATCH", "OPTIONS"):
        yield method, "/api/state"


def test_cross_site_is_refused_on_every_route(srv):
    for site in ("cross-site", "same-site", "Cross-Site", "bogus"):
        for method, path in _every_request():
            for origin in (None, "null", "file://", "http://evil.example",
                           al_http.APP_ORIGIN):
                h = {**auth(), "Sec-Fetch-Site": site, "Content-Type": "application/json"}
                if origin:
                    h["Origin"] = origin
                if method == "GET" and path == "/events" and origin == al_http.APP_ORIGIN:
                    continue  # the one exception, test_app_scheme_origin_reads_the_feed_only
                r, _ = req(srv, method, path, h,
                           body=b'{"consent": true}' if method in ("POST", "PUT") else None)
                assert r.status == 403, (site, method, path, origin)
    # before the token check: no token still reads 403, not 401
    r, _ = req(srv, "GET", "/api/state", {"Sec-Fetch-Site": "cross-site"})
    assert r.status == 403
    assert srv.core.tailer is None and not srv.core.consented()


def test_same_origin_none_and_no_header_pass(srv):
    for site in ("same-origin", "none", "Same-Origin", None):
        h = {"Sec-Fetch-Site": site} if site else {}
        for path in ("/", "/web/app.js", "/tokens.css", "/favicon.ico"):
            r, _ = req(srv, "GET", path, h)
            assert r.status == 200, (site, path)
        for path in ("/api/health", "/api/state", "/api/version"):
            r, _ = req(srv, "GET", path, {**h, **auth()})
            assert r.status == 200, (site, path)
            r, _ = req(srv, "GET", path, h)
            assert r.status == 401, (site, path)
        r, _ = req(srv, "POST", "/api/trade-dismiss",
                   {**h, **auth(), "Content-Type": "application/json"},
                   body=json.dumps({"all": True}))
        assert r.status == 200, site
        r, _ = req(srv, "DELETE", "/api/state", {**h, **auth()})
        assert r.status == 405, site
        r, _ = req(srv, "GET", "/api/health",
                   {**h, **auth(), "Origin": "http://evil.example"})
        assert r.status == 403, site


def _raw_events(server, headers):
    s = socket.create_connection(("127.0.0.1", server.port), timeout=5)
    s.sendall((f"GET /events?token={TOKEN} HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
               + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n").encode())
    buf = b""
    try:
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        if buf.startswith(b"HTTP/1.0 200") or buf.startswith(b"HTTP/1.1 200"):
            while b"event: state" not in buf:
                buf += s.recv(65536)
    finally:
        s.close()
    return buf


def test_null_and_file_origins_are_refused_everywhere(srv):
    """OVL-APP-SCHEME-STRICT (F-174): with both local pages on the app scheme,
    Origin null and a file page's origin are refused like any foreign origin
    on the feed and the read routes, with or without Sec-Fetch-Site, and no
    Access-Control-Allow-Origin is sent, so a foreign local file reads
    nothing even with the token."""
    assert "null" not in al_http.FILE_ORIGINS
    assert not any(o.lower().startswith("file:") for o in al_http.FILE_ORIGINS)
    for origin in ("null", "file://", "file:///", "FILE://", "Null"):
        for site in ("cross-site", "same-site", "same-origin", "none", None):
            h = {"Origin": origin}
            if site:
                h["Sec-Fetch-Site"] = site
            out = _raw_events(srv, h)
            assert out.split(b"\r\n")[0].endswith(b"403 Forbidden"), (origin, site, out[:60])
            assert b"Access-Control-Allow-Origin" not in out, (origin, site)
            assert b"event: state" not in out, (origin, site)
            for path in ("/api/state", "/api/health"):
                r, _ = req(srv, "GET", path, {**auth(), **h})
                assert r.status == 403, (origin, site, path)
                assert r.getheader("Access-Control-Allow-Origin") is None, (origin, path)
    # no Origin at all (a non-browser client) still opens the feed
    out = _raw_events(srv, {})
    assert out.split(b"\r\n")[0].endswith(b"200 OK")
    assert b"Access-Control-Allow-Origin" not in out


def test_app_scheme_origin_reads_the_feed_only(srv):
    """OVL-APP-SCHEME (decision 0061 amendment 2026-11-21): the overlay page
    on the app scheme opens GET /events with Origin al-app://app; it is let
    through, with that origin echoed, on the same read-only path set as the
    null origin (FILE_ORIGIN_PATHS), and nowhere else; since
    OVL-APP-SCHEME-STRICT it is the only origin let through there."""
    origin = al_http.APP_ORIGIN
    assert origin == "al-app://app" and al_http.FILE_ORIGINS == {origin}
    assert al_http.FILE_ORIGIN_PATHS == {"/events"}
    for site in ("cross-site", "same-site", None):
        h = {"Origin": origin}
        if site:
            h["Sec-Fetch-Site"] = site
        out = _raw_events(srv, h)
        assert out.split(b"\r\n")[0].endswith(b"200 OK"), (site, out[:60])
        assert b"Access-Control-Allow-Origin: al-app://app\r\n" in out
        assert b"Access-Control-Allow-Origin: null" not in out
        assert b"event: state" in out
    # the token is still needed
    r, _ = req(srv, "GET", "/events", {"Origin": origin, "Sec-Fetch-Site": "cross-site"})
    assert r.status == 401
    # another method, a read route, the page or a write: refused, no echo
    for method, path in (("HEAD", "/events"), ("POST", "/events"), ("GET", "/api/state"),
                         ("GET", "/api/health"), ("GET", "/api/version"), ("GET", "/")):
        for site in ("cross-site", None):
            h = {**auth(), "Origin": origin}
            if site:
                h["Sec-Fetch-Site"] = site
            r, _ = req(srv, method, path, h)
            assert r.status == 403, (method, path, site)
            assert r.getheader("Access-Control-Allow-Origin") is None, (method, path)
    r, _ = req(srv, "POST", "/api/consent",
               {**auth(), "Origin": origin, "Content-Type": "application/json"},
               body=json.dumps({"consent": True}))
    assert r.status == 403
    assert not srv.core.consented()
    # a look-alike origin is not it
    for bad in ("al-app://app.evil", "al-app://evil", "AL-APP://APP", "al-app://app/",
                "al-app://app:1"):
        out = _raw_events(srv, {"Origin": bad, "Sec-Fetch-Site": "cross-site"})
        assert out.split(b"\r\n")[0].endswith(b"403 Forbidden"), bad
    # OVL-APP-SCHEME-STRICT: the null origin no longer gets its own answer
    out = _raw_events(srv, {"Origin": "null", "Sec-Fetch-Site": "cross-site"})
    assert out.split(b"\r\n")[0].endswith(b"403 Forbidden")
    assert b"Access-Control-Allow-Origin" not in out


def test_corp_and_vary_on_every_reply(srv):
    cases = [("GET", "/", {}, 200), ("GET", "/web/app.js", {}, 200),
             ("GET", "/tokens.css", {}, 200), ("GET", "/favicon.ico", {}, 200),
             ("GET", "/web/missing.js", {}, 404), ("GET", "/api/health", auth(), 200),
             ("GET", "/api/state", {}, 401), ("DELETE", "/api/state", {}, 405),
             ("PUT", "/api/state", {}, 405), ("GET", "/api/state",
                                               {"Sec-Fetch-Site": "cross-site"}, 403),
             ("GET", "/api/state", {"Origin": "http://evil.example"}, 403),
             ("HEAD", "/", {}, 200)]
    for method, path, h, want in cases:
        r, _ = req(srv, method, path, h)
        assert r.status == want, (method, path)
        assert r.getheader("Cross-Origin-Resource-Policy") == "same-origin", (method, path)
        assert r.getheader("Vary") == "Sec-Fetch-Site", (method, path)
    r, _ = req(srv, "GET", "/", host="evil.example")
    assert r.status == 400 and r.getheader("Cross-Origin-Resource-Policy") == "same-origin"
    out = _raw_events(srv, {"Origin": al_http.APP_ORIGIN, "Sec-Fetch-Site": "cross-site"})
    head = out.split(b"\r\n\r\n")[0].decode("ascii").split("\r\n")
    assert [x for x in head if x.lower().startswith("vary:")] == ["Vary: Origin, Sec-Fetch-Site"]
    assert "Cross-Origin-Resource-Policy: same-origin" in head


def test_server_header_has_no_version(srv):
    from server.al import NAME, VERSION
    for method, path, h in (("GET", "/", {}), ("GET", "/api/health", auth()),
                            ("GET", "/nope", {}), ("DELETE", "/", {})):
        r, _ = req(srv, method, path, h)
        assert r.getheader("Server") == NAME, path
        assert VERSION not in r.getheader("Server") and "Python" not in r.getheader("Server")
    out = _raw_events(srv, {})
    assert f"\r\nServer: {NAME}\r\n".encode() in out


def test_api_errors_carry_no_os_text(srv, monkeypatch):
    from server.al import layout, webfetch
    core = srv.core
    where = SEP.join((DRIVE, "zzq", "config", "local.json"))
    secret = f"[Errno 13] Permission denied: {where!r}"

    def unreadable(changes):
        try:
            raise PermissionError(13, "Permission denied", where)
        except OSError as e:
            raise layout.LayoutError(f"config/local.json is unreadable: {secret}") from e

    def unwritable(changes):
        raise PermissionError(13, "Permission denied", where)

    def fetch_fails(url):
        try:
            raise ConnectionRefusedError(10061, "[WinError 10061] zzq refused")
        except OSError as e:
            raise webfetch.FetchError(f"network: {e} at {DRIVE}{SEP}zzq?token=zzq") from e

    h = {**auth(), "Content-Type": "application/json"}
    for fn, want in ((unreadable, 500), (unwritable, 500)):
        monkeypatch.setattr(core, "set_overlay_layout", fn)
        r, body = req(srv, "POST", "/api/overlay-layout", h, body=json.dumps({"scale": 1}))
        assert r.status == want
        text = body.decode("utf-8")
        assert json.loads(text)["error"]
        for bad in ("zzq", "Errno", "Permission", DRIVE + SEP):
            assert bad not in text, (fn.__name__, text)
    monkeypatch.undo()
    # a field the player got wrong still says which one
    r, body = req(srv, "POST", "/api/overlay-layout", h, body=json.dumps({"scale": "x"}))
    assert r.status == 400 and "scale" in json.loads(body)["error"]
    monkeypatch.setattr(core, "load_share_url", fetch_fails)
    r, body = req(srv, "POST", "/api/build-code", h,
                  body=json.dumps({"code": "https://pobb.in/abc123"}))
    assert r.status == 502
    doc = json.loads(body)
    assert doc["kind"] == "url" and doc["error"]
    for bad in ("zzq", "WinError", "network", "token", DRIVE + SEP):
        assert bad not in body.decode("utf-8"), body


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


def _sse_open(server, query=""):
    s = socket.create_connection(("127.0.0.1", server.port), timeout=5)
    s.sendall((f"GET /events?token={TOKEN}{query} HTTP/1.1\r\n"
               f"Host: 127.0.0.1:{server.port}\r\n"
               "Accept: text/event-stream\r\n\r\n").encode())
    buf = b""
    while b"event: state" not in buf:
        buf += s.recv(65536)
    return s, buf


def _sse_read_for(s, seconds):
    """Every byte the stream sends within seconds."""
    buf = b""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        s.settimeout(max(0.01, end - time.monotonic()))
        try:
            chunk = s.recv(65536)
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
    return buf


def _sse_frames(buf, name):
    out = []
    head = b"event: " + name.encode() + b"\ndata: "
    for block in buf.split(b"\n\n"):
        if block.startswith(head):
            out.append(json.loads(block[len(head):]))
    return out


def _tap_events(buf):
    return [e for frame in _sse_frames(buf, "events") for e in frame]


# SEC-SSE-TAP: a fixture replay with chat-bearing events among the rest
TAP_FIXTURE = (
    {"type": "whisper_in", "from": "Buyer", "text": "hi, secret words",
     "raw": "@From Buyer: hi, secret words", "trade": False},
    {"type": "chat", "channel": "global", "from": "Someone", "text": "party talk"},
    {"type": "level_up", "character": "Me", "class": "Monk", "level": 7},
    {"type": "death", "character": "Me", "suicide": False},
)


def test_sse_stream_sends_state_then_events(srv):
    # SEC-SSE-TAP: the default stream sends state frames only; each bus
    # event still makes a state push arrive within 250 ms (events spaced
    # past the 4 Hz coalescing window, so the push is due at once).
    s, buf = _sse_open(srv)
    try:
        assert b"text/event-stream" in buf and b"Content-Security-Policy" in buf
        for ev in TAP_FIXTURE:
            buf += _sse_read_for(s, al_http.SSE_MIN_INTERVAL_S + 0.05)
            v = srv.core.state.version
            t0 = time.monotonic()
            srv.core.bus.publish(dict(ev))
            if srv.core.state.version == v:
                continue  # chat lines change no state: nothing to push
            got = b""
            while b"event: state" not in got:
                left = 0.25 - (time.monotonic() - t0)
                assert left > 0, ("no state push within 250 ms", ev["type"])
                got += _sse_read_for(s, min(left, 0.05))
            buf += got
        buf += _sse_read_for(s, 0.4)
        assert b"event: events" not in buf and _tap_events(buf) == []
        assert {f for f in re.findall(rb"^event: (\w+)$", buf, re.M)} == {b"state"}
        assert _sse_frames(buf, "state")[-1]["deaths"] == 1
    finally:
        s.close()


def _tap_read(s, n, timeout=5.0):
    buf = b""
    end = time.monotonic() + timeout
    while len(_tap_events(buf)) < n and time.monotonic() < end:
        buf += _sse_read_for(s, 0.1)
    return buf


def test_events_tap_only_in_a_source_checkout(srv):
    # SEC-SSE-TAP: the tap is on only where the repo root holds .git (the
    # suite runs in a source checkout or a worktree of one).
    assert srv.events_tap is (ROOT / ".git").exists()
    death = {"type": "death", "character": "Me", "suicide": False}
    srv.events_tap = True
    s, _ = _sse_open(srv, "&tap=1")
    try:
        srv.core.bus.publish(dict(death))
        assert [e["type"] for e in _tap_events(_tap_read(s, 1))] == ["death"]
    finally:
        s.close()
    # an installed copy (no .git): ?tap=1 is the default stream
    srv.events_tap = False
    for query in ("&tap=1", ""):
        s, _ = _sse_open(srv, query)
        try:
            srv.core.bus.publish(dict(death))
            buf = _sse_read_for(s, 0.5)
            assert b"event: state" in buf and b"event: events" not in buf, query
        finally:
            s.close()
    # in a source checkout, only tap=1 opens the tap
    srv.events_tap = True
    for query in ("&tap=yes", "&tap=0", "&tap=", ""):
        s, _ = _sse_open(srv, query)
        try:
            srv.core.bus.publish(dict(death))
            buf = _sse_read_for(s, 0.5)
            assert b"event: state" in buf and b"event: events" not in buf, query
        finally:
            s.close()


def test_tap_frames_hold_no_text_field(srv):
    srv.events_tap = True
    s, _ = _sse_open(srv, "&tap=1")
    try:
        for ev in TAP_FIXTURE:
            srv.core.bus.publish(dict(ev))
        buf = _tap_read(s, len(TAP_FIXTURE))
    finally:
        s.close()
    evs = _tap_events(buf)
    assert [e["type"] for e in evs] == [e["type"] for e in TAP_FIXTURE]
    for e in evs:
        assert all(v is None or isinstance(v, (bool, int, float))
                   for k, v in e.items() if k != "type"), e
    assert evs[0]["trade"] is False and evs[2]["level"] == 7
    assert evs[3]["suicide"] is False and all(isinstance(e["seq"], int) for e in evs)
    for word in (b"secret words", b"party talk", b"Buyer", b"Someone", b"Monk",
                 b'"Me"', b"global", b"raw"):
        assert word not in json.dumps(evs).encode(), word
    assert tap_event({"type": "x", "a": 1, "b": 2.5, "c": True, "d": None, "e": "s",
                      "f": [1], "g": {"h": 1}}) == {"type": "x", "a": 1, "b": 2.5,
                                                     "c": True, "d": None}


def test_snapshot_has_no_recent_whispers(srv):
    srv.core.bus.publish({"type": "whisper_in", "from": "Buyer", "text": "hi"})
    r, body = req(srv, "GET", "/api/state", auth())
    assert r.status == 200 and "recent_whispers" not in json.loads(body)


def test_favicon_is_the_local_brand_icon(srv):
    # BRAND-ICON: /favicon.ico and /web/favicon.svg are served from web/.
    r, body = req(srv, "GET", "/favicon.ico")
    assert r.status == 200 and r.getheader("Content-Type") == "image/x-icon"
    assert body == srcpaths.read_bytes("favicon.ico")
    r, body = req(srv, "GET", "/web/favicon.svg")
    assert r.status == 200 and r.getheader("Content-Type") == "image/svg+xml"
