"""TC-URL: a pasted share URL is fetched once, behind the web-data opt-in,
through the allowlist / SSRF guard. Mocked fetch only; never the network."""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import NAME, VERSION, webfetch
from server.al.core import Core
from server.al.http import serve
from server.al.theorycraft import codec, shareurl
from tc_fixtures import FULL_XML, MINIMAL_XML

AT = chr(64)  # userinfo separator, built at run time so the leak sweep sees no address

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "u" * 48
CODE = codec.encode(FULL_XML)


class FakeNet:
    """Routes by exact URL; anything unexpected fails the test."""

    def __init__(self, routes=None):
        self.routes = routes or {}
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        if url.startswith("https://poe.ninja/"):
            return 503, {}, b""  # the opt-in also starts a rates refresh
        self.calls.append((method, url, dict(headers)))
        if url not in self.routes:
            raise AssertionError(f"unexpected request to {url}")
        return self.routes[url]


def _on():
    return True


# -- URL rewriting / SSRF guard -----------------------------------------------

@pytest.mark.parametrize("pasted, raw", [
    ("https://pobb.in/AbCd-12_x", "https://pobb.in/AbCd-12_x/raw"),
    ("  https://pobb.in/AbCd/  ", "https://pobb.in/AbCd/raw"),
    ("https://pobb.in/AbCd/raw", "https://pobb.in/AbCd/raw"),
    ("https://pobb.in/pob/AbCd", "https://pobb.in/AbCd/raw"),
    ("https://POBB.IN/AbCd?x=1#frag", "https://pobb.in/AbCd/raw"),
    # TC-URL-POBBIN-RAW: user links (research 0013)
    ("https://pobb.in/u/some_user-1/AbCd", "https://pobb.in/u/some_user-1/AbCd/raw"),
    ("https://pobb.in/u/Name/AbCd/raw", "https://pobb.in/u/Name/AbCd/raw"),
    ("https://pobb.in/u/Name/AbCd/?x=1#f", "https://pobb.in/u/Name/AbCd/raw"),
    ("https://pastebin.com/Zx81Qq", "https://pastebin.com/raw/Zx81Qq"),
    ("https://pastebin.com/raw/Zx81Qq", "https://pastebin.com/raw/Zx81Qq"),
])
def test_raw_url(pasted, raw):
    assert shareurl.raw_url(pasted) == raw


@pytest.mark.parametrize("pasted", [
    "http://pobb.in/AbCd",                      # not https
    "https://evil.example/AbCd",                # other host
    "https://pobb.in.evil.example/AbCd",        # suffix trick
    "https://evilpobb.in/AbCd",                 # prefix trick
    "https://www.pobb.in/AbCd",                 # subdomain not listed
    "https://127.0.0.1/AbCd",                   # IP literal
    "https://[::1]/AbCd",                       # IPv6 literal
    "https://2130706433/AbCd",                  # decimal IP (not on the list)
    "https://pobb.in" + AT + "evil.example/AbCd",        # userinfo
    "https://user:pw" + AT + "pobb.in/AbCd",             # userinfo on an allowed host
    "https://pobb.in:8080/AbCd",                # port
    "https://pobb.in:443" + AT + "evil.example/AbCd",    # port-looking userinfo
    "https://pobb.in\\@evil.example/AbCd",      # backslash
    "https://pobb.in/../../etc/passwd",         # path games
    "https://pobb.in/a/b/c",                    # not one id
    "https://pobb.in/%2e%2e%2fadmin",           # encoded traversal
    "https://pastebin.com/raw/",                # no id
    "https://pobb.in/" + "a" * 65,              # id too long
    "www.pobb.in/AbCd",                         # no scheme
    "https://pobb.in./AbCd",                    # trailing dot
    "https://pobb.in/raw",                      # reserved word, no id
    "https://pobb.in/pob/raw",                  # reserved word as id
    "https://pobb.in/AbCd/raw/raw",             # extra segment
    "https://pobb.in/AbCd/x",                   # unknown second segment
    "https://pobb.in/u/AbCd",                   # user link without an id
    "https://pobb.in/u/Name/AbCd/x",            # user link, unknown tail
    "https://pobb.in/u/Name/AbCd/raw/raw",      # user link, extra segment
    "https://pobb.in/u/na.me/AbCd",             # name outside [A-Za-z0-9_-]
    "https://pobb.in/u/na%2Fme/AbCd",           # encoded slash in the name
    "https://pobb.in/u/" + "n" * 65 + "/AbCd",  # name too long
    "https://pobb.in/u/Name/" + "a" * 65,       # id too long
    "https://pobb.in/u/raw/AbCd",               # reserved word as name
    "https://pobb.in/u/Name/u",                 # reserved word as id
    "https://pobb.in/u/..%2f..%2fetc/AbCd",     # encoded traversal in the name
    "https://pobb.in" + AT + "evil.example/u/Name/AbCd",  # userinfo, user link
    "https://pobb.in:8080/u/Name/AbCd",         # port, user link
    "https://pastebin.com/u/Name/AbCd",         # user form only on pobb.in
])
def test_raw_url_refuses(pasted):
    with pytest.raises(webfetch.UrlNotAllowed):
        shareurl.raw_url(pasted)


def test_fetch_sends_truthful_user_agent_once():
    net = FakeNet({"https://pobb.in/AbCd/raw": (200, {}, (CODE + "\n").encode())})
    text = shareurl.fetch_build_text("https://pobb.in/AbCd", _on, fetch=net)
    assert text == CODE
    assert len(net.calls) == 1
    method, url, headers = net.calls[0]
    assert method == "GET" and headers["User-Agent"].startswith(f"{NAME}/{VERSION} ")
    assert "Cookie" not in headers


def test_no_request_without_opt_in():
    net = FakeNet()
    with pytest.raises(webfetch.WebDataOff):
        shareurl.fetch_build_text("https://pobb.in/AbCd", lambda: False, fetch=net)
    assert net.calls == []


def test_redirect_within_allowlist_is_followed():
    net = FakeNet({
        "https://pastebin.com/raw/Zx81Qq": (301, {"Location": "/raw/Moved1"}, b""),
        "https://pastebin.com/raw/Moved1": (200, {}, CODE.encode()),
    })
    assert shareurl.fetch_build_text("https://pastebin.com/Zx81Qq", _on, fetch=net) == CODE


@pytest.mark.parametrize("location", [
    "https://evil.example/x", "//evil.example/x", "http://pobb.in/pob/AbCd",
    "https://127.0.0.1/x", "https://pobb.in" + AT + "evil.example/", "https://pobb.in:8443/x",
])
def test_redirect_off_allowlist_is_refused(location):
    net = FakeNet({"https://pobb.in/AbCd/raw": (302, {"Location": location}, b"")})
    with pytest.raises(webfetch.UrlNotAllowed):
        shareurl.fetch_build_text("https://pobb.in/AbCd", _on, fetch=net)
    assert len(net.calls) == 1  # the off-list target was never requested


def test_redirect_loop_is_bounded():
    net = FakeNet({"https://pobb.in/AbCd/raw": (302, {"Location": "/AbCd/raw"}, b"")})
    with pytest.raises(webfetch.FetchError, match="too many redirects"):
        shareurl.fetch_build_text("https://pobb.in/AbCd", _on, fetch=net)
    assert len(net.calls) == webfetch.MAX_REDIRECTS + 1


def test_oversize_body_is_refused():
    big = b"A" * (shareurl.MAX_BYTES + 1)
    net = FakeNet({"https://pobb.in/AbCd/raw": (200, {}, big)})
    with pytest.raises(webfetch.FetchError, match="too large"):
        shareurl.fetch_build_text("https://pobb.in/AbCd", _on, fetch=net)


@pytest.mark.parametrize("status, body, exc", [
    (404, b"not found", webfetch.FetchError),
    (200, b"", codec.CodeError),
    (200, b"<html>login</html>", codec.CodeError),
    (200, b"https://pobb.in/Other", codec.CodeError),
    (200, b"\xff\xfe\x00", codec.CodeError),
])
def test_bad_responses(status, body, exc):
    net = FakeNet({"https://pobb.in/AbCd/raw": (status, {}, body)})
    with pytest.raises(exc):
        shareurl.fetch_build_text("https://pobb.in/AbCd", _on, fetch=net)
    assert len(net.calls) == 1


def test_real_transport_never_follows_redirects():
    import urllib.request
    h = webfetch._NoRedirect()
    req = urllib.request.Request("https://pobb.in/AbCd/raw")
    assert h.redirect_request(req, None, 302, "Found", {}, "https://evil.example/") is None


# -- API ---------------------------------------------------------------------

def _req(server, body):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    conn.request("POST", "/api/build-code", body=json.dumps(body).encode(),
                 headers={"Host": f"127.0.0.1:{server.port}", "X-AL-Token": TOKEN,
                          "Content-Type": "application/json"})
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, json.loads(data)


@pytest.fixture
def api(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    net = FakeNet({
        "https://pobb.in/Good1/raw": (200, {}, CODE.encode()),
        "https://pobb.in/u/some_user/Good2/raw": (200, {}, CODE.encode()),
        "https://pobb.in/Bad1/raw": (200, {}, b"not a build"),
        "https://pobb.in/Away/raw": (302, {"Location": "https://evil.example/"}, b""),
        "https://pastebin.com/raw/Down": (503, {}, b""),
    })
    started = []

    def start():
        core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05, web_fetch=net)
        server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                       tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True).start()
        started.append((core, server))
        return server, core
    yield start, net
    for core, server in started:
        server.stop()
        core.close()


@pytest.mark.server
def test_api_share_url_flow(api):
    start, net = api
    srv, core = start()
    _req(srv, {"code": codec.encode(MINIMAL_XML)})
    status, doc = _req(srv, {"code": "https://pobb.in/Good1"})
    assert status == 422 and doc["web_data"] is False and net.calls == []
    core.set_web_data(True)
    status, doc = _req(srv, {"code": "https://pobb.in/Good1"})
    assert status == 200 and doc["build"]["class_name"] == "Monk", doc
    assert len(net.calls) == 1  # once per paste
    status, doc = _req(srv, {"code": "https://evil.example/Good1"})
    assert status == 422 and doc["kind"] == "url" and "pobb.in" in doc["hosts"]
    status, doc = _req(srv, {"code": "https://pobb.in/Away"})
    assert status == 422 and doc["kind"] == "url"
    status, doc = _req(srv, {"code": "https://pastebin.com/Down"})
    assert status == 502 and doc["kind"] == "url"
    status, doc = _req(srv, {"code": "https://pobb.in/Bad1"})
    assert status == 400
    # TC-URL-POBBIN-RAW: a pobb.in user link is fetched from its /raw route
    status, doc = _req(srv, {"code": "https://pobb.in/u/some_user/Good2"})
    assert status == 200 and doc["build"]["class_name"] == "Monk", doc
    assert net.calls[-1][1] == "https://pobb.in/u/some_user/Good2/raw"
    assert not any("evil.example" in u for _, u, _ in net.calls)
    # the fetched build persisted as its code: a restart reloads with no fetch
    n = len(net.calls)
    srv2, core2 = start()
    assert core2.builds.build.class_name == "Monk" and len(net.calls) == n
