"""PRICE-1 server side and UA-CONTACT: one price check per hotkey press
through the shared trade limiter, the contact gate, and PRICE-1-WIRE: the
decision 0016 card in the state with the press time (GET /api/price was
removed, decisions 0015 / 0016 amendment).

Mocked fetch only; nothing reaches the network. Tmp cache / runtime. The
contact used here is a plain token, never an address.
"""

import http.client
import json
import threading
import time
from pathlib import Path

import pytest

from server.al import NAME, VERSION, price, trade, webfetch
from server.al.core import Core
from server.al.http import serve
from server.al.theorycraft import snapshot
from tc_eval_fixtures import ADVANCED_RING, CURRENCY, RARE_GLOVES

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "p" * 48
CONTACT = "test-contact"

STATS = json.dumps({"result": [
    {"label": "Pseudo", "entries": [{"id": "pseudo.life", "text": "+# to maximum Life",
                                     "type": "pseudo"}]},
    {"label": "Explicit", "entries": [
        {"id": "explicit.stat_life", "text": "+# to maximum Life", "type": "explicit"},
        {"id": "explicit.stat_light", "text": "+#% to Lightning Resistance",
         "type": "explicit"}, "junk"]}]}).encode()
LEAGUES = json.dumps({"result": [
    {"id": "Standard", "realm": "poe2", "text": "Standard"},
    {"id": "Hardcore Example", "realm": "poe2", "text": "HC"},
    {"id": "Example League", "realm": "poe2", "text": "Example League"}]}).encode()
IDS = [f"r{i}" for i in range(14)]
SEARCH = json.dumps({"id": "Q1", "result": IDS, "total": 40}).encode()
LISTINGS = [5, 3, 4, 1, 2, 9, 7]


def _fetch_body():
    rows = [{"id": f"r{i}", "listing": {"price": {"type": "~price", "amount": a,
                                                  "currency": "exalted"}}}
            for i, a in enumerate(LISTINGS)]
    rows.append({"id": "x", "listing": {"price": {"amount": 1, "currency": "divine"}}})
    rows.append({"id": "y", "listing": {}})
    return json.dumps({"result": rows}).encode()


HDRS = {"X-Rate-Limit-Policy": "trade-search-request-limit", "X-Rate-Limit-Rules": "Ip",
        "X-Rate-Limit-Ip": "8:10:60", "X-Rate-Limit-Ip-State": "1:10:0"}


class FakeNet:
    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, method, url, headers, body=None):
        with self.lock:
            self.calls.append((method, url, dict(headers), body))
        if url.endswith("/api/trade2/data/stats"):
            return 200, HDRS, STATS
        if url.endswith("/api/trade2/data/leagues"):
            return 200, HDRS, LEAGUES
        if "/api/trade2/search/" in url:
            return 200, HDRS, SEARCH
        if "/api/trade2/fetch/" in url:
            return 200, HDRS, _fetch_body()
        if url.startswith("https://poe.ninja/"):
            return 200, {}, b"[]"
        raise AssertionError("unexpected URL " + url)

    def kinds(self):
        out = []
        for _, url, _, _ in self.calls:
            for k in ("data/stats", "data/leagues", "search/", "fetch/"):
                if k in url:
                    out.append(k.rstrip("/"))
        return out


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def _checker(tmp_path, net, on=True, contact=CONTACT, league=None, clock=None,
             client=None):
    state = {"on": on, "contact": contact, "published": [], "cards": []}
    client = client or trade.TradeClient(enabled=lambda: state["on"], fetch=net,
                                         contact=lambda: state["contact"])

    def card(c, at=None, keep_time=False):
        state["cards"].append((c, at, keep_time))

    c = price.PriceChecker(client, tmp_path / "trade", enabled=lambda: state["on"],
                           contact=lambda: state["contact"], league=lambda: league,
                           publish=state["published"].append, clock=clock or Clock(),
                           spawn=lambda fn, *a: fn(*a), poll_s=0.01, card=card)
    return c, state


# -- gates ------------------------------------------------------------------

def test_opt_in_off_means_zero_requests(tmp_path):
    net = FakeNet()
    c, _ = _checker(tmp_path, net, on=False)
    doc = c.request(ADVANCED_RING)
    assert doc["status"] == "off" and doc["reason"] == "web data off"
    assert c.latest()["blocked"] == "web data off"
    assert net.calls == []


def test_no_contact_means_zero_requests(tmp_path):
    net = FakeNet()
    for bad in (None, "", "two\nlines", "a(b)"):
        c, _ = _checker(tmp_path, net, contact=bad)
        doc = c.request(ADVANCED_RING)
        assert doc["status"] == "off" and doc["reason"] == "contact not set"
    assert net.calls == []


def test_not_an_item_is_skipped(tmp_path):
    net = FakeNet()
    c, _ = _checker(tmp_path, net)
    assert c.request("")["reason"] == "not an item"
    assert c.request("hello there")["status"] == "skipped"
    assert net.calls == []


# -- the flow ---------------------------------------------------------------

def test_end_to_end_stats_league_search_fetch_summary(tmp_path):
    net = FakeNet()
    c, st = _checker(tmp_path, net)
    first = c.request(ADVANCED_RING)
    assert first["status"] == "queued" and first["item"]["base"] == "Example Ring"
    doc = c.latest()["price"]
    assert doc["status"] == "done", doc
    assert net.kinds() == ["data/stats", "data/leagues", "search", "fetch"]
    method, url, headers, body = net.calls[2]
    assert method == "POST"
    assert url == "https://www.pathofexile.com/api/trade2/search/poe2/Example%20League"
    q = json.loads(body)
    filters = q["query"]["stats"][0]["filters"]
    assert {"id": "explicit.stat_life", "value": {"min": 49.5}} in filters
    assert net.calls[3][1] == ("https://www.pathofexile.com/api/trade2/fetch/"
                               + ",".join(IDS[:10]) + "?query=Q1")
    for _, _, h, _ in net.calls:
        assert h["User-Agent"].startswith(f"{NAME}/{VERSION} ")
        assert h["User-Agent"].endswith(f"(contact: {CONTACT})")
        assert "Cookie" not in h
    s = doc["summary"]
    assert s["currency"] == "exalted" and s["min"] == 1 and s["median"] == 3
    assert s["listings"] == 8 and s["total"] == 40
    assert s["currencies"] == {"exalted": 7, "divine": 1}
    assert doc["league"] == "Example League" and doc["query_id"] == "Q1"
    assert st["published"][-1]["status"] == "done"


def test_one_search_per_press_and_duplicate_text_reuses(tmp_path):
    net = FakeNet()
    clock = Clock()
    c, _ = _checker(tmp_path, net, clock=clock)
    c.request(ADVANCED_RING)
    again = c.request(ADVANCED_RING)
    assert again["reused"] is True and again["status"] == "done"
    assert net.kinds().count("search") == 1
    clock.t += price.DEDUPE_S + 1
    c.request(ADVANCED_RING)
    assert net.kinds().count("search") == 2
    c.request(RARE_GLOVES)
    assert net.kinds().count("search") == 3
    # the stat table and the league list were fetched once (daily gate)
    assert net.kinds().count("data/stats") == 1
    assert net.kinds().count("data/leagues") == 1


def test_stat_table_cached_daily_and_across_restarts(tmp_path):
    net = FakeNet()
    clock = Clock()
    c, _ = _checker(tmp_path, net, clock=clock)
    c.request(ADVANCED_RING)
    c2, _ = _checker(tmp_path, net, clock=clock)  # a core restart
    c2.request(RARE_GLOVES)
    assert net.kinds().count("data/stats") == 1
    cached = json.loads((tmp_path / "trade" / price.CACHE_NAME).read_text(encoding="ascii"))
    assert cached["stats"]["+# to maximum Life"] == "explicit.stat_life"
    clock.t += price.DATA_INTERVAL_S + 1
    c2.request(ADVANCED_RING)
    assert net.kinds().count("data/stats") == 2


def test_configured_league_skips_lookup(tmp_path):
    net = FakeNet()
    c, _ = _checker(tmp_path, net, league="My League")
    c.request(ADVANCED_RING)
    assert "data/leagues" not in net.kinds()
    assert net.calls[1][1].endswith("/search/poe2/My%20League")


def test_unique_and_currency(tmp_path):
    net = FakeNet()
    c, _ = _checker(tmp_path, net)
    doc = c.request(CURRENCY)
    assert doc["status"] in ("queued", "skipped")
    assert net.kinds().count("search") <= 1


def test_limiter_wait_is_reported_then_search_runs(tmp_path):
    clock = Clock(1000.0)
    seen = []
    holder = {}

    def sleep(s):
        seen.append(holder["c"].latest())
        clock.t += s

    net = FakeNet()
    client = trade.TradeClient(enabled=lambda: True, fetch=net, contact=lambda: CONTACT,
                               sleep=sleep, clock=clock)
    client.limiter.update("search", 429, dict(HDRS, **{"Retry-After": "12"}))
    c, _ = _checker(tmp_path, net, client=client, league="L")
    holder["c"] = c
    c.request(ADVANCED_RING)
    assert seen, "the limiter never deferred"
    first = seen[0]
    assert first["price"]["status"] == "waiting" and first["price"]["wait_s"] == 12
    assert first["limiter_wait_s"]["search"] == pytest.approx(12.0)
    assert c.latest()["price"]["status"] == "done"
    assert net.kinds().count("search") == 1


def test_opt_out_mid_check_stops_before_the_search(tmp_path):
    net = FakeNet()
    holder = {}

    def gated(method, url, headers, body=None):
        out = net(method, url, headers, body)
        if "data/leagues" in url:
            holder["st"]["on"] = False  # the user turns web data off
        return out

    c, st = _checker(tmp_path, gated)
    holder["st"] = st
    c.request(ADVANCED_RING)
    doc = c.latest()["price"]
    assert doc["status"] == "off" and doc["reason"] == "web data off"
    assert "search" not in net.kinds()


def test_search_error_is_reported(tmp_path):
    def broken(method, url, headers, body=None):
        if "/search/" in url:
            return 400, {}, b'{"error": {"code": 2, "message": "bad query"}}'
        return FakeNet()(method, url, headers, body)

    c, _ = _checker(tmp_path, broken, league="L")
    c.request(ADVANCED_RING)
    doc = c.latest()["price"]
    assert doc["status"] == "error" and "400" in doc["error"]


def test_summarize_edges():
    s = price.summarize({"result": []}, 0)
    assert s["listings"] == 0 and s["min"] is None and s["total"] == 0
    s = price.summarize({"result": [{"listing": {"price": {"amount": -1, "currency": "x"}}},
                                    {"listing": {"price": {"amount": True,
                                                           "currency": "x"}}}]})
    assert s["listings"] == 0
    assert price.parse_leagues({"result": [{"id": "Standard"}]}) is None
    assert price.parse_stats({"result": "x"}) == {}


# -- PRICE-1-WIRE: the decision 0016 card ------------------------------------

ITEM = {"name": "Doom Loop", "base": "Example Ring", "rarity": "Rare"}


def _doc(status, **kw):
    return dict({"id": 1, "status": status, "reason": None, "item": ITEM, "league": "L",
                 "wait_s": 0, "summary": None, "error": None, "at": 5.0}, **kw)


def test_card_of_status_mapping():
    keys = {"status", "wait_s", "item", "league", "count", "listings", "error"}
    for st in ("queued", "searching"):
        c = price.card_of(_doc(st))
        assert set(c) == keys
        assert c["status"] == "searching" and c["wait_s"] is None and c["item"] == ITEM
    c = price.card_of(_doc("waiting", wait_s=7.2))
    assert c["status"] == "waiting" and c["wait_s"] == 8
    rows = [{"amount": a, "currency": "exalted"} for a in range(1, 13)]
    c = price.card_of(_doc("done", summary={"prices": rows, "total": 40, "min": 1}))
    assert c["status"] == "done" and c["count"] == 40 and c["error"] is None
    assert c["listings"] == rows[:10] and c["league"] == "L"
    c = price.card_of(_doc("done", summary={"prices": rows[:3], "total": None}))
    assert c["count"] == 3
    c = price.card_of(_doc("done", summary=None))
    assert c["status"] == "done" and c["count"] == 0 and c["listings"] == []
    for reason in ("web data off", "contact not set"):
        c = price.card_of(_doc("off", reason=reason))
        assert c["status"] == "off" and c["error"] is None
    for reason in ("not an item", "item has no base type"):
        c = price.card_of(_doc("skipped", reason=reason, item=None))
        assert c["status"] == "error" and c["error"] == "not an item"
        assert c["item"] == {"name": None, "base": None, "rarity": None}
    assert price.card_of(_doc("error", error="league required"))["error"] == "no league"
    c = price.card_of(_doc("error", error="trade2 search: HTTP 400"))
    assert c["status"] == "error" and c["error"] == "trade2 search: HTTP 400"
    assert price.card_of(_doc("error"))["error"] == "price check failed"
    assert price.card_of(None)["status"] == "error"


def test_card_publish_uses_press_time(tmp_path):
    net = FakeNet()
    clock = Clock(2000.0)
    c, st = _checker(tmp_path, net, clock=clock)
    c.request(ADVANCED_RING, at=1234.5)
    cards = st["cards"]
    assert cards[0][0]["status"] == "searching" and cards[0][1:] == (1234.5, False)
    assert all(at == 1234.5 and keep for _, at, keep in cards[1:])
    last = cards[-1][0]
    assert last["status"] == "done" and last["count"] == 40
    assert [r["amount"] for r in last["listings"]] == LISTINGS + [1]
    assert last["item"]["base"] == "Example Ring" and last["league"] == "Example League"
    # the same text again within the window: one new card at the new press
    n = len(cards)
    c.request(ADVANCED_RING, at=1240.0)
    assert len(cards) == n + 1 and cards[-1][1:] == (1240.0, False)
    assert cards[-1][0]["status"] == "done"
    assert net.kinds().count("search") == 1
    # no press time given: the checker's clock
    c.request("hello there")
    assert cards[-1][0]["error"] == "not an item" and cards[-1][1] == 2000.0


def test_card_off_and_waiting(tmp_path):
    net = FakeNet()
    c, st = _checker(tmp_path, net, on=False)
    c.request(ADVANCED_RING, at=10.0)
    card, at, keep = st["cards"][-1]
    assert card["status"] == "off" and at == 10.0 and keep is False
    assert card["item"]["base"] == "Example Ring"
    c2, st2 = _checker(tmp_path, net, contact=None)
    c2.request(ADVANCED_RING, at=11.0)
    assert st2["cards"][-1][0]["status"] == "off"
    assert net.calls == []


def test_cache_dir_is_in_the_al_sidecar(tmp_path):
    from server.al import paths
    env = {paths.SIDECAR_ENV: str(tmp_path)}
    assert price.cache_dir(env) == tmp_path.resolve() / "Cache" / "trade"


# -- UA-CONTACT ---------------------------------------------------------------

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


@pytest.fixture
def api_on(tmp_path):
    server, core, net = _api(tmp_path, {"web_data": True, "contact": CONTACT,
                                        "league": "Example League"})
    yield server, core, net
    server.stop()
    core.close()


@pytest.fixture
def api_no_contact(tmp_path):
    server, core, net = _api(tmp_path, {"web_data": True})
    yield server, core, net
    server.stop()
    core.close()


def _wait_price(srv, done=("done", "error")):
    deadline = time.monotonic() + 5
    snap = None
    while time.monotonic() < deadline:
        snap = _req(srv, "GET", "/api/state")[1]
        if snap.get("price") and snap["price"]["status"] in done:
            break
        time.sleep(0.05)
    return snap


@pytest.mark.server
def test_price_endpoint_removed(api_on):
    # decisions 0015 / 0016 amendment: the result lives only in the state
    srv, _core, net = api_on
    assert _req(srv, "GET", "/api/price")[0] == 404
    assert net.calls == []


@pytest.mark.server
def test_eval_post_queues_one_price_check(api_on):
    srv, core, net = api_on
    status, _ = _req(srv, "POST", "/api/eval", {"item": ADVANCED_RING})
    assert status == 200
    snap = _wait_price(srv)
    card = snap["price"]
    assert card["status"] == "done", card
    assert card["listings"][0] == {"amount": 5, "currency": "exalted"}
    assert card["league"] == "Example League"
    assert card["at"] == snap["eval"]["at"]  # one press, one time
    assert core.price.latest()["price"]["summary"]["min"] == 1  # 0015 doc kept inside
    assert _req(srv, "POST", "/api/eval", {"item": ADVANCED_RING})[0] == 200
    assert net.kinds().count("search") == 1  # duplicate press within the window
    snap = core.state.snapshot()
    assert snap["price"]["at"] == snap["eval"]["at"]  # re-stamped with the new press
    assert "data/leagues" not in net.kinds()  # league from local config
    wd = _req(srv, "GET", "/api/web-data")[1]
    assert wd["contact_set"] is True and wd["blocked"] is None
    assert CONTACT not in json.dumps(wd)  # the value is never echoed


@pytest.mark.server
def test_end_to_end_contact_set_at_run_time(api_no_contact):
    """PRICE-1-WIRE ACCEPT: web_data on, the contact added to local.json
    while the core runs, one press -> the card in the state with the item
    name, count and listings; the overlay / dashboard words carry them."""
    from server.al import state as state_mod
    from server.al.theorycraft import item as item_mod
    srv, core, net = api_no_contact
    cfg = json.loads(core.config_path.read_text(encoding="ascii"))
    cfg.update(contact=CONTACT, league="Example League")
    core.config_path.write_text(json.dumps(cfg), encoding="ascii")
    assert _req(srv, "POST", "/api/eval", {"item": ADVANCED_RING})[0] == 200
    snap = _wait_price(srv)
    card = snap["price"]
    name = item_mod.parse(ADVANCED_RING).name
    assert name and card["status"] == "done", card
    assert card["item"]["name"] == name and card["count"] == 40
    assert [r["amount"] for r in card["listings"]] == LISTINGS + [1]
    assert card["text"]["item"] == name
    assert card["text"]["line"].startswith("40 listed, ~")
    assert card["text"]["detail"] == "Lowest 5 exalted"  # the first (cheapest) row
    words = state_mod.price_card_text(card)
    assert name in words["head"] and "1 divine" in " ".join(words["rows"])
    oc = state_mod.overlay_card(snap["eval"], card, card["at"] + 1)
    assert oc is not None and "listed" in oc["line2"]
    if oc["kind"] == "price":  # no build loaded: the price-only card
        assert name in oc["head"]
    assert snap["card"] is not None
    assert net.kinds() == ["data/stats", "search", "fetch"]
    assert all(h["User-Agent"].endswith(f"(contact: {CONTACT})") for _, _, h, _ in net.calls)


@pytest.mark.server
def test_no_contact_api_says_why_and_sends_nothing(api_no_contact):
    srv, core, net = api_no_contact
    assert _req(srv, "POST", "/api/eval", {"item": ADVANCED_RING})[0] == 200
    snap = core.state.snapshot()
    assert snap["price"]["status"] == "off" and snap["price"]["at"] == snap["eval"]["at"]
    doc = core.price.latest()
    assert doc["price"]["status"] == "off" and doc["price"]["reason"] == "contact not set"
    assert doc["blocked"] == "contact not set"
    rates = _req(srv, "GET", "/api/rates")[1]
    assert rates["blocked"] == "contact not set" and rates["contact_set"] is False
    wd = _req(srv, "GET", "/api/web-data")[1]
    assert wd["web_data"] is True and wd["blocked"] == "contact not set"
    time.sleep(0.2)
    assert net.calls == []
    assert core.state.snapshot()["price"]["status"] == "off"
