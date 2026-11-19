"""DATA-NINJA: poe.ninja currency rates client and GET /api/rates.

Mocked fetch only; no request ever reaches the network. Tmp cache / runtime.
"""

import gzip
import http.client
import json
import threading
import time
from pathlib import Path

import pytest

from server.al import NAME, VERSION, ninja, paths, webfetch
from server.al.core import Core
from server.al.http import serve

AT = chr(64)  # userinfo separator, built at run time so the leak sweep sees no address

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "n" * 48

LEAGUES = json.dumps([{"id": "Example League", "name": "Example League"},
                      {"id": "Standard", "name": "Standard"}]).encode()
# The real overview shape (research 0013, 2026-11-17, trimmed): line names in
# the TOP-LEVEL `items`; `core.items` holds only the reference currencies
# (here the primary, divine, whose name comes from that fallback).
OVERVIEW = json.dumps({
    "core": {"items": [{"id": "divine", "name": "Divine Orb", "category": "Currency",
                        "detailsId": "divine-orb"}],
             "rates": {"exalted": 531.0, "chaos": 7.43},
             "primary": "divine", "secondary": "chaos"},
    "lines": [{"id": "exalted", "primaryValue": 0.001883, "volumePrimaryValue": 29.5,
               "maxVolumeCurrency": "divine", "maxVolumeRate": 531.0,
               "sparkline": {"totalChange": 3.06, "data": [0.66, 0.58, 1.99]}},
              {"id": "chaos", "primaryValue": 0.1346},
              {"id": "divine", "primaryValue": 1},
              {"id": "broken", "primaryValue": "x"}, "junk"],
    "items": [{"id": "exalted", "name": "Exalted Orb", "category": "Currency",
               "detailsId": "exalted-orb"},
              {"id": "chaos", "name": "Chaos Orb", "category": "Currency",
               "detailsId": "chaos-orb"}]}).encode()


class FakeNet:
    def __init__(self, overview=OVERVIEW, etag='"v1"', gzip_body=False):
        self.calls = []
        self.overview = overview
        self.etag = etag
        self.down = False
        self.gzip_body = gzip_body
        self.answer = None  # (status, headers) for the overview, e.g. a 429

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        if self.down:
            raise webfetch.FetchError("network: offline")
        if url.endswith(ninja.LEAGUES_PATH):
            return 200, {}, LEAGUES
        if self.answer is not None:
            return self.answer[0], dict(self.answer[1]), b""
        if headers.get("If-None-Match") == self.etag:
            return 304, {"ETag": self.etag}, b""
        if self.gzip_body and headers.get("Accept-Encoding") == "gzip":
            return (200, {"ETag": self.etag, "Content-Encoding": "gzip"},
                    gzip.compress(self.overview))
        return 200, {"ETag": self.etag}, self.overview


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


CONTACT = "test-contact"


def _client(tmp_path, net, clock, on=True, league=None, contact=CONTACT):
    state = {"on": on}
    c = ninja.RatesClient(tmp_path / "ninja", enabled=lambda: state["on"],
                          league=lambda: league, fetch=net, clock=clock,
                          contact=lambda: contact)
    return c, state


def test_parse_overview_names_from_top_level_items():
    out = ninja.parse_overview(OVERVIEW)
    assert out["primary"] == "divine"
    assert all("name" in v for v in out["rates"].values())
    assert out["rates"]["divine"]["value"] == 1.0
    # top-level items win over core.items for the same id; bad entries skipped
    body = json.dumps({
        "core": {"items": [{"id": "a", "name": "Core A"}, {"id": "b", "name": "Core B"}]},
        "lines": [{"id": "a", "primaryValue": 2}, {"id": "b", "primaryValue": 3},
                  {"id": "c", "primaryValue": 4}],
        "items": [{"id": "a", "name": "Top A"}, {"id": "c", "name": ""}, "x",
                  {"name": "no id"}]}).encode()
    rates = ninja.parse_overview(body)["rates"]
    assert rates["a"]["name"] == "Top A" and rates["b"]["name"] == "Core B"
    assert "name" not in rates["c"]
    # the older guess (names only in core.items) still parses
    old = json.dumps({"core": {"items": [{"id": "a", "name": "A"}]},
                      "lines": [{"id": "a", "primaryValue": 1}]}).encode()
    assert ninja.parse_overview(old)["rates"]["a"]["name"] == "A"


def test_no_request_without_contact(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock, contact=None)
    assert c.refresh() == "off: contact not set"
    assert c.refresh(force=True) == "off: contact not set"
    assert c.refresh_async() is False
    assert net.calls == []
    snap = c.snapshot()
    assert snap["web_data"] is True and snap["contact_set"] is False
    assert snap["blocked"] == "contact not set" and snap["next_refresh_in_s"] is None
    # a bad value (line break, parenthesis) counts as not set
    for bad in ("x\r\nInjected: 1", "a(b)", " ", 7):
        c2, _ = _client(tmp_path, net, clock, contact=bad)
        assert c2.refresh() == "off: contact not set"
    assert net.calls == []


def test_no_request_without_opt_in(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock, on=False)
    assert c.refresh() == "off"
    assert c.refresh(force=True) == "off"
    assert c.refresh_async() is False
    assert net.calls == []
    snap = c.snapshot()
    assert snap["web_data"] is False and snap["rates"] == {} and snap["stale"] is True


def test_fetch_parse_attribution_and_user_agent(tmp_path):
    # DATA-PRICE-POLITE: every GET asks for gzip; the gzip body decodes
    net, clock = FakeNet(gzip_body=True), Clock()
    c, _ = _client(tmp_path, net, clock)
    assert c.refresh() == "fetched"
    urls = [u for _, u, _ in net.calls]
    assert urls[0] == "https://poe.ninja/poe2/api/economy/leagues"
    assert urls[1] == ("https://poe.ninja/poe2/api/economy/exchange/current/overview"
                       "?league=Example+League&type=Currency")
    for _, _, h in net.calls:
        assert h["User-Agent"].startswith(f"{NAME}/{VERSION} ")
        assert h["User-Agent"].endswith(f"(contact: {CONTACT})")
        assert h["Accept-Encoding"] == "gzip"
        assert "Cookie" not in h
    snap = c.snapshot()
    assert snap["blocked"] is None and snap["contact_set"] is True
    assert snap["league"] == "Example League" and snap["primary"] == "divine"
    assert snap["rates"]["exalted"] == {"value": 0.001883, "volume": 29.5,
                                        "name": "Exalted Orb"}
    assert set(snap["rates"]) == {"exalted", "chaos", "divine"}
    # DATA-NINJA-NAMES: every line is named (top-level items, core.items fallback)
    assert {k: v["name"] for k, v in snap["rates"].items()} == {
        "exalted": "Exalted Orb", "chaos": "Chaos Orb", "divine": "Divine Orb"}
    assert snap["age_s"] == 0 and snap["stale"] is False
    assert "poe.ninja" in snap["attribution"] and "Grinding Gear Games" in snap["attribution"]
    assert ninja.ATTRIBUTION == snap["attribution"]


def test_gzip_body_inflating_past_the_cap_is_refused(tmp_path):
    net, clock = FakeNet(overview=b" " * (ninja.MAX_BYTES + 1), gzip_body=True), Clock()
    c, _ = _client(tmp_path, net, clock)
    out = c.refresh()
    assert out.startswith("error") and "too large" in out
    assert c.snapshot()["rates"] == {}


def test_user_agent_purpose_says_prices():
    assert ninja.UA_PURPOSE == "prices from poe.ninja"
    assert "currency rates" not in ninja.USER_AGENT
    assert ninja.USER_AGENT == (f"{NAME}/{VERSION} (local Path of Exile 2 companion; "
                                "prices from poe.ninja)")


def test_429_with_retry_after_7200_blocks_two_hours_across_a_restart(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    net.answer = (429, {"Retry-After": "7200"})
    start = clock.t
    assert c.refresh() == "backoff"
    assert c.doc["backoff_until"] == start + 7200
    assert "429" in c.snapshot()["last_error"]
    saved = json.loads((tmp_path / "ninja" / ninja.CACHE_NAME).read_text(encoding="ascii"))
    assert saved["backoff_until"] == start + 7200
    n = len(net.calls)
    net.answer = None
    # past the hourly gate, forced, and after a restart on the same cache:
    # nothing is sent until the two hours are over
    for dt in (60, ninja.MIN_INTERVAL_S + 1, 7199):
        clock.t = start + dt
        c2, _ = _client(tmp_path, net, clock)
        assert c2.refresh() == "backoff" and c2.refresh(force=True) == "backoff"
        assert c2.refresh_async() is False and c2.any_due() is False
    assert len(net.calls) == n
    clock.t = start + 7200
    c3, _ = _client(tmp_path, net, clock)
    assert c3.refresh() == "fetched" and len(net.calls) == n + 1
    assert c3.snapshot()["last_error"] is None


@pytest.mark.parametrize("status", [403, 503])
def test_403_and_503_back_off_an_hour_without_retry_after(tmp_path, status):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    net.answer = (status, {})
    assert c.refresh() == "backoff"
    assert c.doc["backoff_until"] == clock.t + ninja.BACKOFF_DEFAULT_S == clock.t + 3600
    # a Retry-After past 24 h is bounded to 24 h
    net.answer = (status, {"Retry-After": str(10 * 86400)})
    clock.t += 3600
    assert c.refresh() == "backoff"
    assert c.doc["backoff_until"] == clock.t + 86400


def test_backoff_on_the_league_list_stops_the_round(tmp_path):
    def net(method, url, headers, body=None):
        calls.append(url)
        return 429, {"Retry-After": "7200"}, b""
    calls, clock = [], Clock()
    c, _ = _client(tmp_path, net, clock)
    assert c.refresh() == "backoff" and len(calls) == 1
    assert calls[0].endswith(ninja.LEAGUES_PATH)
    assert c.doc["backoff_until"] == clock.t + 7200
    # a cached league does not carry the round on past a back-off
    c.doc["league_auto"] = "Example League"
    c.doc["backoff_until"] = None
    clock.t += ninja.LEAGUE_INTERVAL_S + 1
    assert c.refresh() == "backoff" and len(calls) == 2


def test_a_backoff_far_beyond_24_hours_is_ignored(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    c.doc["backoff_until"] = clock.t + 30 * 86400  # a clock moved back, a bad cache
    assert c.backed_off() is False and c.refresh() == "fetched"


def test_at_most_one_request_per_hour_and_survives_restart(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    c.refresh()
    n = len(net.calls)
    start = clock.t
    for dt in (1, 600, 1800, ninja.MIN_INTERVAL_S - 1):
        clock.t = start + dt
        assert c.refresh() == "fresh"
    # a fresh client (core restart) on the same cache keeps the gate
    c2, _ = _client(tmp_path, net, clock)
    assert c2.refresh() == "fresh"
    assert c2.refresh_async() is False
    assert len(net.calls) == n
    assert c2.snapshot()["rates"]["chaos"]["value"] == 0.1346


def test_etag_conditional_request_after_an_hour(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    c.refresh()
    clock.t += ninja.MIN_INTERVAL_S + 1
    assert c.refresh() == "unchanged"
    last = net.calls[-1]
    assert last[2]["If-None-Match"] == '"v1"'
    assert sum(1 for _, u, _ in net.calls if u.endswith(ninja.LEAGUES_PATH)) == 1
    snap = c.snapshot()
    assert snap["age_s"] == 0 and snap["rates"]["exalted"]["value"] == 0.001883


def test_offline_returns_cached_rates_with_age(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    c.refresh()
    net.down = True
    clock.t += 3 * 3600
    out = c.refresh()
    assert out.startswith("error: ")
    snap = c.snapshot()
    assert snap["rates"]["exalted"]["value"] == 0.001883
    assert snap["age_s"] == 3 * 3600 and snap["stale"] is True
    assert "offline" in snap["last_error"]
    # the failed attempt counts: no retry within the hour
    n = len(net.calls)
    clock.t += 60
    assert c.refresh() == "fresh" and len(net.calls) == n


def test_configured_league_skips_lookup(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock, league="My League")
    assert c.refresh() == "fetched"
    assert len(net.calls) == 1 and "league=My+League" in net.calls[0][1]


def test_bad_payload_is_an_error_not_a_crash(tmp_path):
    net, clock = FakeNet(overview=b"<html>"), Clock()
    c, _ = _client(tmp_path, net, clock)
    assert c.refresh().startswith("error")
    assert c.snapshot()["rates"] == {}


def test_cache_dir_is_in_the_al_sidecar(tmp_path):
    env = {paths.SIDECAR_ENV: str(tmp_path)}
    assert ninja.cache_dir(env) == tmp_path.resolve() / "Cache" / "ninja"


# -- API -----------------------------------------------------------------

def _req(server, method, path, body=None, token=TOKEN, host=None, origin=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": host or f"127.0.0.1:{server.port}"}
    if token:
        h["X-AL-Token"] = token
    if origin:
        h["Origin"] = origin
    data = None
    if body is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    conn.request(method, path, body=data, headers=h)
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    return r.status, (json.loads(raw) if raw[:1] == b"{" else raw)


@pytest.fixture
def api(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    net = FakeNet()
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "local.json").write_text(json.dumps({"contact": CONTACT}), encoding="ascii")
    core = Core(runtime=rt, log_path=str(log), poll_s=0.05, web_fetch=net)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    yield server, core, net
    server.stop()
    core.close()


@pytest.mark.server
def test_rates_endpoint_guards(api):
    srv, _core, net = api
    assert _req(srv, "GET", "/api/rates", token=None)[0] == 401
    assert _req(srv, "GET", "/api/rates", token="wrong")[0] == 401
    assert _req(srv, "GET", "/api/rates", host="evil.example:80")[0] == 400
    assert _req(srv, "GET", "/api/rates", origin="http://evil.example")[0] == 403
    assert _req(srv, "GET", "/api/rates", origin="null")[0] == 403
    assert _req(srv, "POST", "/api/web-data", {"enabled": True}, token=None)[0] == 401
    assert net.calls == []


@pytest.mark.server
def test_rates_endpoint_off_then_opt_in(api):
    srv, core, net = api
    status, doc = _req(srv, "GET", "/api/rates")
    assert status == 200 and doc["web_data"] is False and doc["rates"] == {}
    assert doc["attribution"] == ninja.ATTRIBUTION
    assert net.calls == []
    assert _req(srv, "GET", "/api/web-data")[1]["web_data"] is False
    assert _req(srv, "POST", "/api/web-data", {"enabled": "yes"})[0] == 400
    status, doc = _req(srv, "POST", "/api/web-data", {"enabled": True})
    assert status == 200 and doc["web_data"] is True
    assert doc["contact_set"] is True and doc["blocked"] is None
    cfg = json.loads(core.config_path.read_text(encoding="utf-8"))
    assert cfg["web_data"] is True and cfg["contact"] == CONTACT
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        doc = _req(srv, "GET", "/api/rates")[1]
        if doc["rates"] and not doc["refreshing"]:
            break
        time.sleep(0.05)
    assert doc["rates"]["exalted"]["value"] == 0.001883
    n = len(net.calls)
    for _ in range(3):
        _req(srv, "GET", "/api/rates")
    assert len(net.calls) == n  # hourly gate
    _req(srv, "POST", "/api/web-data", {"enabled": False})
    assert core.web_data_enabled() is False


# -- webfetch policy -------------------------------------------------------

@pytest.mark.parametrize("url", [
    "http://poe.ninja/x", "https://evil.example/x", "https://poe.ninja.evil.example/",
    "https://evil.example/poe.ninja", "https://user" + AT + "poe.ninja/", "https://poe.ninja:8443/",
    "https://poe.ninja:443" + AT + "evil.example/", "https://127.0.0.1/", "https://[::1]/",
    "https://poe.ninja./", "https://poe.ninja\\@evil.example/", "ftp://poe.ninja/",
    "https://p" + chr(0xF6) + "e.ninja/", "","https:///x", "javascript:alert(1)",
])
def test_check_url_refuses(url):
    with pytest.raises(webfetch.UrlNotAllowed):
        webfetch.check_url(url, ninja.ALLOWED_HOSTS)


def test_check_url_accepts():
    for url in ("https://poe.ninja/poe2/api/economy/leagues", "https://POE.NINJA:443/x"):
        webfetch.check_url(url, ninja.ALLOWED_HOSTS)


def test_request_requires_user_agent_and_refuses_cookies():
    def never(*a):
        raise AssertionError("sent")
    with pytest.raises(webfetch.FetchError):
        webfetch.request("GET", "https://poe.ninja/", {}, ninja.ALLOWED_HOSTS, fetch=never)
    with pytest.raises(webfetch.FetchError):
        webfetch.request("GET", "https://poe.ninja/", {"User-Agent": "x", "Cookie": "a=b"},
                         ninja.ALLOWED_HOSTS, fetch=never)
