"""PRICE-1 / PRICE-TRADE-LINK (decision 0017): one item-hotkey press builds
an offline trade-search link (decision 0016 card status "link" with `url`)
and publishes it in the state with the press time. The core calls no trade
endpoint and never opens the link; UA-CONTACT gates poe.ninja and GGG
fetches only.

Mocked fetch only; nothing reaches the network. Tmp runtime. The contact
used here is a plain token, never an address.
"""

import http.client
import json
import threading
import urllib.parse
from pathlib import Path

import pytest

from server.al import price, trade, webfetch
from server.al.core import Core
from server.al.http import serve
from server.al.theorycraft import item as item_mod
from server.al.theorycraft import snapshot
from tc_eval_fixtures import ADVANCED_RING, UNIQUE_STAFF

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "p" * 48
CONTACT = "test-contact"
ITEM = {"name": "N", "base": "B", "rarity": "RARE"}
KEYS = {"status", "wait_s", "item", "league", "count", "listings", "error", "url"}


class FakeNet:
    """Records every request; answers poe.ninja with an empty list and
    fails the test on anything else."""

    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, method, url, headers, body=None):
        with self.lock:
            self.calls.append((method, url, dict(headers), body))
        if url.startswith("https://poe.ninja/"):
            return 200, {}, b"[]"
        raise AssertionError("unexpected URL " + url)

    def non_ninja(self):
        return [u for _, u, _, _ in self.calls if not u.startswith("https://poe.ninja/")]


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def _checker(league=None, clock=None):
    st = {"published": [], "cards": []}

    def card(c, at=None, keep_time=False):
        st["cards"].append((c, at, keep_time))

    c = price.PriceChecker(league=lambda: league, publish=st["published"].append,
                           clock=clock or Clock(), card=card)
    return c, st


# -- the press -----------------------------------------------------------------

def test_press_builds_the_link_card_offline():
    c, st = _checker(league="Example League")
    doc = c.request(ADVANCED_RING, at=1234.5)
    assert doc["status"] == "link" and doc["league"] == "Example League"
    card, at, keep = st["cards"][-1]
    assert set(card) == KEYS and at == 1234.5 and keep is False
    assert card["status"] == "link" and card["error"] is None
    assert card["item"] == {"name": item_mod.parse(ADVANCED_RING).name,
                            "base": "Example Ring", "rarity": "RARE"}
    assert card["url"] == trade.search_link(item_mod.parse(ADVANCED_RING), "Example League")
    assert card["league"] == "Example League" and card["listings"] == []
    assert card["count"] is None and card["wait_s"] is None
    assert len(st["cards"]) == 1  # one card per press, no later updates


def test_league_defaults_to_standard():
    for league in (None, "", "  "):
        c, st = _checker(league=league)
        c.request(UNIQUE_STAFF, at=1.0)
        card = st["cards"][-1][0]
        assert card["league"] == "Standard"
        assert "/trade2/search/poe2/Standard?q=" in card["url"]


def test_not_an_item_and_no_base_type():
    c, st = _checker()
    c.request("hello there")
    card, at, _ = st["cards"][-1]
    assert card["status"] == "error" and card["error"] == "not an item"
    assert card["url"] is None and at == 1_800_000_000.0  # no press time: the clock
    assert c.request(5) is None


def test_every_press_is_one_card():
    c, st = _checker()
    c.request(ADVANCED_RING, at=10.0)
    c.request(ADVANCED_RING, at=11.0)
    assert [x[1] for x in st["cards"]] == [10.0, 11.0]
    assert c.latest()["price"]["at"] == 11.0


# -- card_of ---------------------------------------------------------------------

def _doc(status, **kw):
    return dict({"id": 1, "status": status, "reason": None, "item": ITEM, "league": "L",
                 "url": None, "at": 5.0}, **kw)


def test_card_of_link():
    c = price.card_of(_doc("link", url="https://www.pathofexile.com/trade2/search/poe2/L?q=%7B%7D"))
    assert set(c) == KEYS
    assert c["status"] == "link" and c["url"].endswith("?q=%7B%7D") and c["item"] == ITEM
    assert c["error"] is None and c["league"] == "L"


def test_card_of_link_without_a_url_is_an_error():
    for bad in (None, "", "http://www.pathofexile.com/trade2/search/poe2/L?q=1",
                "https://evil.example/trade2/search/poe2/L?q=1", 5):
        c = price.card_of(_doc("link", url=bad))
        assert c["status"] == "error" and c["url"] is None


def test_card_of_skips_and_errors():
    c = price.card_of(_doc("skipped", reason="not an item", item=None))
    assert c["status"] == "error" and c["error"] == "not an item"
    assert c["item"] == {"name": None, "base": None, "rarity": None}
    c = price.card_of(_doc("skipped", reason="item has no base type"))
    assert c["error"] == "no base type" and c["item"] == ITEM
    c = price.card_of(_doc("skipped", reason="some other skip"))
    assert c["status"] == "error" and c["error"] == "some other skip"
    assert price.card_of(_doc("error"))["error"] == "price check failed"
    assert price.card_of(None)["status"] == "error"


def test_price_module_has_no_network_code():
    src = (ROOT / "server" / "al" / "price.py").read_text(encoding="ascii")
    for gone in ("webfetch", "submit(", "TradeClient", "STATS_URL", "LEAGUES_URL"):
        assert gone not in src, gone


# -- UA-CONTACT (poe.ninja / GGG fetches) -------------------------------------

def test_user_agent_contact():
    base = webfetch.user_agent("x")
    assert "contact" not in base
    assert webfetch.user_agent("x", CONTACT) == base + f" (contact: {CONTACT})"
    for bad in ("", "   ", "a\r\nb", "a(b", "a)b", "a\\b", "x" * 200, 5, None,
                "caf" + chr(0xE9)):
        assert webfetch.clean_contact(bad) is None
        assert webfetch.user_agent("x", bad) == base
    assert webfetch.blocked_reason(lambda: False, CONTACT) == "web data off"
    assert webfetch.blocked_reason(True, None) == "contact not set"
    assert webfetch.blocked_reason(True, CONTACT) is None


def test_snapshot_user_agent_and_ggg_gate(tmp_path):
    calls = []

    def fake(url, headers):
        calls.append((url, dict(headers)))
        return 200, {}, b"{}"

    src = {"mods": "https://repoe-fork.github.io/poe2/mods.json",
           "skilltree": "https://repoe-fork.github.io/poe2/tree.json"}
    out = snapshot.run(tmp_path, fetch=fake, sources=src, now=1_800_000_000)
    assert out["mods"] == "fetched" and out["skilltree"] == "off: contact not set"
    assert [u for u, _ in calls] == [src["mods"]]
    assert "contact" not in calls[0][1]["User-Agent"]
    out = snapshot.run(tmp_path / "b", fetch=fake, sources=src, now=1_800_000_000,
                       contact=CONTACT)
    assert out["skilltree"] == "fetched"
    assert calls[-1][1]["User-Agent"].endswith(f"(contact: {CONTACT})")
    assert snapshot.needs_contact("x", "https://www.pathofexile.com/a")
    assert snapshot.needs_contact("x", "https://raw.githubusercontent.com/grindinggear/x")
    assert not snapshot.needs_contact("mods", src["mods"])


# -- API ----------------------------------------------------------------------

def _req(server, method, path, body=None, token=TOKEN):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": f"127.0.0.1:{server.port}"}
    if token:
        h["X-AL-Token"] = token
    data = None
    if body is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    conn.request(method, path, body=data, headers=h)
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    return r.status, (json.loads(raw) if raw[:1] == b"{" else raw)


def _api(tmp_path, cfg):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "local.json").write_text(json.dumps(cfg), encoding="ascii")
    net = FakeNet()
    core = Core(runtime=rt, log_path=str(log), poll_s=0.05, web_fetch=net)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    return server, core, net


@pytest.fixture(params=[
    {"web_data": True, "contact": CONTACT, "league": "Example League"},
    {"web_data": False},
    {"web_data": True},
], ids=["on-with-contact", "off", "on-no-contact"])
def api(tmp_path, request):
    server, core, net = _api(tmp_path, request.param)
    yield server, core, net, request.param
    server.stop()
    core.close()


@pytest.mark.server
def test_price_endpoint_removed(api):
    srv, _core, net, _cfg = api
    assert _req(srv, "GET", "/api/price")[0] == 404
    assert net.non_ninja() == []


@pytest.mark.server
def test_eval_press_publishes_the_link_and_sends_nothing_to_the_trade_site(api):
    from server.al import state as state_mod
    srv, core, net, cfg = api
    assert _req(srv, "POST", "/api/eval", {"item": ADVANCED_RING})[0] == 200
    snap = _req(srv, "GET", "/api/state")[1]
    card = snap["price"]
    assert card["status"] == "link", card
    assert card["at"] == snap["eval"]["at"]  # one press, one time
    league = cfg.get("league", "Standard")
    assert card["league"] == league
    parts = urllib.parse.urlsplit(card["url"])
    assert (parts.scheme, parts.netloc) == ("https", "www.pathofexile.com")
    assert urllib.parse.unquote(parts.path) == "/trade2/search/poe2/" + league
    q = json.loads(urllib.parse.parse_qs(parts.query)["q"][0])
    assert q["query"]["type"] == "Example Ring"
    assert card["text"]["line"] == "Trade link ready"
    oc = state_mod.overlay_card(snap["eval"], card, card["at"] + 1)
    assert oc is not None and "Trade link ready" in (oc["line2"], oc["line3"]) \
        or oc["kind"] == "eval"
    assert net.non_ninja() == []  # no trade request, whatever the settings
    wd = _req(srv, "GET", "/api/web-data")[1]
    assert CONTACT not in json.dumps(wd)  # the value is never echoed
    assert not any("trade" in u.lower() or "price" in u.lower() for u in wd["uses"])
