"""DATA-LEAGUE-PICKER-API (folded into DATA-DIAG-SEAM, unit F-141, research
0056 F10 / R10): POST /api/web-data sets or clears the "league" key from
poe.ninja's cached leagues list, GET /api/web-data names the setting, the
auto league, the league prices come from and the cached names, and a solo
league prices and links from its trade league.

Mocked fetch only; no request reaches the network. Tmp runtime and config.
"""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import leagues, ninja
from server.al.core import Core
from server.al.http import serve

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "p" * 48
LISTED = [{"id": "conquerors", "name": "Conquerors of Wraeclast"},
          {"id": "Standard", "name": "Standard"}]
OVERVIEW = json.dumps({"core": {"primary": "divine", "items": []},
                       "lines": [{"id": "divine", "primaryValue": 1}],
                       "items": [{"id": "divine", "name": "Divine Orb"}]}).encode()
UNIQUE_TEXT = "\n".join(["Item Class: Rings", "Rarity: Rare", "Doom Loop",
                         "Example Ring", "--------", "Item Level: 70"])


class FakeNet:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append(url)
        if url.endswith(ninja.LEAGUES_PATH):
            return 200, {}, json.dumps(LISTED).encode()
        return 200, {}, OVERVIEW


def _core(tmp_path, cfg, net):
    p = tmp_path / "local.json"
    p.write_text(json.dumps(cfg), encoding="ascii")
    core = Core(runtime=tmp_path / "rt", tail=False, config_path=p, web_fetch=net)
    core.rates.doc["leagues"] = [dict(e) for e in LISTED]
    core.rates.doc["league_auto"] = "conquerors"
    return core


def _serve(core):
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    return server


def _req(server, method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": f"127.0.0.1:{server.port}", "X-AL-Token": TOKEN}
    data = None
    if body is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    conn.request(method, path, body=data, headers=h)
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    return r.status, json.loads(raw)


@pytest.fixture
def api(tmp_path):
    net = FakeNet()
    core = _core(tmp_path, {"web_data": False}, net)
    server = _serve(core)
    yield server, core, net
    server.stop()
    core.close()


def _cfg(core):
    return json.loads(core.config_path.read_text(encoding="utf-8"))


@pytest.mark.server
def test_post_league_writes_the_league_key_and_survives_a_restart(api, tmp_path):
    srv, core, net = api
    status, doc = _req(srv, "GET", "/api/web-data")
    assert status == 200 and doc["league"] is None
    assert doc["league_auto"] == "Conquerors of Wraeclast"
    assert doc["leagues"] == ["Conquerors of Wraeclast", "Standard"]
    # an id or a name of the cached list; the display name is stored
    status, doc = _req(srv, "POST", "/api/web-data", {"league": "standard"})
    assert status == 200 and doc["league"] == "Standard"
    assert doc["prices_from"] == "Standard" and doc["web_data"] is False
    assert _cfg(core) == {"web_data": False, "league": "Standard"}
    assert core.configured_league() == "Standard" and core.trade_league() == "Standard"
    status, doc = _req(srv, "POST", "/api/web-data", {"league": "conquerors"})
    assert status == 200 and _cfg(core)["league"] == "Conquerors of Wraeclast"
    # a restart reads the key back
    core.close()
    again = Core(runtime=tmp_path / "rt", tail=False, config_path=core.config_path,
                 web_fetch=net)
    try:
        assert again.league_setting() == "Conquerors of Wraeclast"
        assert again.trade_league() == "Conquerors of Wraeclast"
    finally:
        again.close()
    # '' clears it: the auto league is followed again; enabled and league together
    status, doc = _req(srv, "POST", "/api/web-data", {"league": "", "enabled": False})
    assert status == 200 and doc["league"] is None and "league" not in _cfg(core)
    assert core.configured_league() is None


@pytest.mark.server
def test_a_league_outside_the_cached_list_is_refused(api):
    srv, core, net = api
    _req(srv, "POST", "/api/web-data", {"league": "Standard"})
    before = core.config_path.read_bytes()
    for bad in ("Not A League", "SSF Nowhere", 7, None, ["Standard"], "x" * 65,
                "Stan\ndard"):
        status, doc = _req(srv, "POST", "/api/web-data", {"league": bad, "enabled": True})
        assert status == 400, bad
        assert "league" in doc["error"] and "Pick one" in doc["error"]
    # nothing written, not even the enabled switch sent with it
    assert core.config_path.read_bytes() == before
    with pytest.raises(ValueError):
        core.set_league("Not A League")
    # no cached list (web data never on): only clearing is accepted
    core.rates.doc.pop("leagues")
    assert _req(srv, "POST", "/api/web-data", {"league": "Standard"})[0] == 400
    assert _req(srv, "POST", "/api/web-data", {"league": ""})[0] == 200
    assert _req(srv, "POST", "/api/web-data", {})[0] == 400


def test_solo_league_prices_and_links_from_its_trade_league(tmp_path):
    net = FakeNet()
    core = _core(tmp_path, {"web_data": True, "contact": "test-contact",
                            "league": "SSF Conquerors of Wraeclast"}, net)
    try:
        assert core.league_setting() == "SSF Conquerors of Wraeclast"
        assert core.configured_league() == "Conquerors of Wraeclast"
        assert core.trade_league() == "Conquerors of Wraeclast"
        assert core.rates.refresh(force=True) == "fetched"
        overviews = [u for u in net.calls if "/overview?" in u]
        assert overviews and all("league=conquerors&" in u for u in overviews)
        assert not any(u.endswith(ninja.LEAGUES_PATH) for u in net.calls)
        core.eval_press(UNIQUE_TEXT)
        card = core.state.snapshot()["price"]
        assert card["league"] == "Conquerors of Wraeclast"
        assert "/trade2/search/poe2/Conquerors%20of%20Wraeclast?" in card["url"]
        assert "SSF" not in card["url"]
        server = _serve(core)
        try:
            doc = _req(server, "GET", "/api/web-data")[1]
        finally:
            server.stop()
        assert doc["league"] == "SSF Conquerors of Wraeclast"
        assert doc["prices_from"] == "Conquerors of Wraeclast"
    finally:
        core.close()
    # the mapping is inert unless the rest is a cached league
    listed = [dict(e) for e in LISTED]
    assert leagues.trade_league_of("ssf standard", listed) == "Standard"
    assert leagues.trade_league_of("SSF Unknown", listed) == "SSF Unknown"
    assert leagues.trade_league_of("SSF Standard", None) == "SSF Standard"
    assert leagues.trade_league_of("Standard", listed) == "Standard"
    assert leagues.trade_league_of("Hardcore Standard", listed) == "Hardcore Standard"
    # a solo name that is itself in the cached list is never mapped
    assert leagues.trade_league_of("SSF Standard",
                                   listed + [{"id": "ssf", "name": "SSF Standard"}]) \
        == "SSF Standard"
    assert leagues.SOLO_FORMS == ("SSF ",)


@pytest.mark.server
def test_no_request_is_added(api):
    srv, core, net = api
    assert _req(srv, "POST", "/api/web-data", {"league": "Standard"})[0] == 200
    assert _req(srv, "GET", "/api/web-data")[0] == 200
    core.set_league("")
    core.league_names(), core.league_auto(), core.configured_league()
    assert net.calls == []
    # web data on: picking a league starts no fetch of its own (the next due
    # refresh prices it; the hourly gates decide)
    core.config_path.write_text(json.dumps({"web_data": True, "contact": "test-contact"}),
                                encoding="ascii")
    core.rates.doc.update({"checked_at": core.rates.clock(),
                           "overview_attempt_at": core.rates.clock()})
    if core.rates.book is not None:
        core.rates.book.due = lambda now: False
    assert _req(srv, "POST", "/api/web-data", {"league": "Conquerors of Wraeclast"})[0] == 200
    assert net.calls == []
    src = (ROOT / "server" / "al" / "leagues.py").read_text(encoding="utf-8")
    assert "import urllib" not in src and "webfetch" not in src
