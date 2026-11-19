"""PRICE-UNIQUE, PRICE-STACKABLES, UTIL-MOVERS and the UTIL-1.0-READY
league rollover: poe.ninja unique and stackable overviews cached by the
price book, looked up offline on the item-check press.

Mocked fetch only; no request ever reaches the network. Bodies are
synthetic, trimmed to the real shapes of research 0019 / 0013 (invented
item names). Tmp cache only."""

import json

from server.al import ninja, price, pricebook, webfetch
from server.al.state import SessionState, ninja_text, price_card_text
from server.al.theorycraft import item as item_mod

LEAGUES = json.dumps([{"id": "Example League", "name": "Example League"},
                      {"id": "Standard", "name": "Standard"}]).encode()
CORE = {"items": [{"id": "divine", "name": "Divine Orb", "category": "Currency"}],
        "rates": {"exalted": 531.0}, "primary": "divine", "secondary": "chaos"}
CURRENCY = json.dumps({
    "core": CORE,
    "lines": [{"id": "exalted", "primaryValue": 0.002, "volumePrimaryValue": 30.0},
              {"id": "divine", "primaryValue": 1}],
    "items": [{"id": "exalted", "name": "Exalted Orb"}]}).encode()
UNIQUES = json.dumps({
    "core": CORE,
    "lines": [
        {"id": 1, "itemId": 11, "detailsId": "ember-veil", "name": "Ember Veil",
         "baseType": "Silk Robe", "category": "Body Armour", "levelRequired": 40,
         "primaryValue": 12.5, "listingCount": 342, "corrupted": False,
         "sparkLine": {"totalChange": 8.2, "data": [0, 1.5, None, 8.2]}},
        {"id": 2, "name": "Ember Veil", "baseType": "Silk Robe",
         "primaryValue": 20.0, "listingCount": 3, "corrupted": True,
         "sparkLine": {"totalChange": -40.0, "data": []}},
        {"id": 3, "name": "Ember Veil", "baseType": "Runemastered Silk Robe",
         "primaryValue": 55.0, "listingCount": 30, "corrupted": False,
         "sparkLine": {"totalChange": None, "data": []}},
        {"id": 4, "name": "Hollow Crown", "baseType": "Iron Circlet",
         "primaryValue": 0.004, "listingCount": 900, "corrupted": False,
         "sparkLine": {"totalChange": -25.5, "data": []}},
        {"id": 5, "name": "", "primaryValue": 1}, {"id": 6, "name": "Bad"}, "junk"]}
).encode()
ESSENCES = json.dumps({
    "core": CORE,
    "lines": [{"id": "greater-ruin", "primaryValue": 0.35, "volumePrimaryValue": 40.0,
               "sparkline": {"totalChange": 61.0, "data": [1, 2]}},
              {"id": "lesser-ash", "primaryValue": 0.01, "volumePrimaryValue": 0.2,
               "sparkline": {"totalChange": 300.0, "data": [1, 2]}},
              {"id": "nameless", "primaryValue": 3.0}],
    "items": [{"id": "greater-ruin", "name": "Greater Essence of Ruin"},
              {"id": "lesser-ash", "name": "Lesser Essence of Ash"}]}).encode()


class FakeNet:
    def __init__(self):
        self.calls = []
        self.status = {}

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        if url.endswith(ninja.LEAGUES_PATH):
            return 200, {}, LEAGUES
        for key, code in self.status.items():
            if key in url:
                return code, {}, b""
        etag = '"e-' + url.rsplit("type=", 1)[-1] + '"'
        if headers.get("If-None-Match") == etag:
            return 304, {"ETag": etag}, b""
        if "type=Currency" in url:
            return 200, {"ETag": etag}, CURRENCY
        if "type=UniqueArmours" in url:
            return 200, {"ETag": etag}, UNIQUES
        if "type=Essences" in url:
            return 200, {"ETag": etag}, ESSENCES
        return 200, {"ETag": etag}, json.dumps({"core": CORE, "lines": []}).encode()


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def _client(tmp_path, net, clock, on=True, league=None):
    state = {"on": on, "league": league}
    d = tmp_path / "ninja"
    c = ninja.RatesClient(d, enabled=lambda: state["on"],
                          league=lambda: state["league"], fetch=net, clock=clock,
                          contact=lambda: "test-contact",
                          book=pricebook.PriceBook(d))
    return c, state


N_TYPES = len(pricebook.UNIQUE_TYPES) + len(pricebook.EXCHANGE_TYPES)


# -- parsers -----------------------------------------------------------------

def test_parse_item_overview_keeps_named_priced_lines():
    p = pricebook.parse_item_overview(UNIQUES)
    assert p["primary"] == "divine" and p["unit"] == "Divine Orb"
    assert [(e["name"], e["base"], e["corrupted"]) for e in p["entries"]] == [
        ("Ember Veil", "Silk Robe", False), ("Ember Veil", "Silk Robe", True),
        ("Ember Veil", "Runemastered Silk Robe", False),
        ("Hollow Crown", "Iron Circlet", False)]
    first = p["entries"][0]
    assert first["value"] == 12.5 and first["listings"] == 342 and first["change"] == 8.2
    assert p["entries"][2]["change"] is None


def test_parse_exchange_overview_names_from_items():
    p = pricebook.parse_exchange_overview(ESSENCES)
    assert [(e["name"], e["value"], e["volume"], e["change"]) for e in p["entries"]] == [
        ("Greater Essence of Ruin", 0.35, 40.0, 61.0),
        ("Lesser Essence of Ash", 0.01, 0.2, 300.0)]


def test_parsers_refuse_a_body_without_lines():
    for parse in (pricebook.parse_item_overview, pricebook.parse_exchange_overview):
        for body in (b"{}", b"[]", b'{"lines": 3}'):
            try:
                parse(body)
            except ValueError:
                continue
            raise AssertionError("no error for " + repr(body))


# -- refresh: opt-in, gate, ETag ---------------------------------------------

def test_no_request_while_web_data_is_off(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock, on=False)
    assert c.refresh() == "off" and c.refresh_async() is False
    assert net.calls == []
    assert c.lookup({"rarity": "UNIQUE", "name": "Ember Veil", "base": "Silk Robe"}) is None
    assert c.snapshot()["movers"] == {"up": [], "down": []}


def test_one_request_per_type_per_hour_then_etag(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    assert c.refresh() == "fetched"
    over = [u for _, u, _ in net.calls if not u.endswith(ninja.LEAGUES_PATH)]
    assert len(over) == 1 + N_TYPES and len(set(over)) == len(over)
    assert all(h["User-Agent"].startswith(webfetch.user_agent("x").split("/")[0])
               for _, _, h in net.calls)
    assert all("Cookie" not in h for _, _, h in net.calls)
    n = len(net.calls)
    clock.t += ninja.MIN_INTERVAL_S - 1
    assert c.refresh() == "fresh" and c.refresh_async() is False
    # a restart on the same cache keeps every type's gate
    c2, _ = _client(tmp_path, net, clock)
    assert c2.refresh() == "fresh" and len(net.calls) == n
    clock.t += 2
    assert c2.refresh() == "unchanged"
    again = net.calls[n:]
    assert len(again) == 1 + N_TYPES
    assert all(h.get("If-None-Match", "").startswith('"e-') for _, _, h in again)
    hit = c2.lookup({"rarity": "UNIQUE", "name": "Ember Veil", "base": "Silk Robe"})
    assert hit["value"] == 12.5


def test_one_failing_type_does_not_stop_the_others(tmp_path):
    net, clock = FakeNet(), Clock()
    net.status["type=UniqueWeapons"] = 500
    c, _ = _client(tmp_path, net, clock)
    c.refresh()
    s = c.book.summary()
    assert s["UniqueWeapons"]["last_error"] == "HTTP 500"
    assert s["UniqueArmours"]["entries"] == 4 and s["Essences"]["entries"] == 2


# -- lookup on the press ------------------------------------------------------

def test_unique_lookup_name_base_and_corrupted(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    c.refresh()
    plain = c.lookup({"rarity": "UNIQUE", "name": "Ember Veil", "base": "Silk Robe"})
    assert (plain["value"], plain["listings"], plain["few"], plain["change"]) == (
        12.5, 342, False, 8.2)
    assert plain["unit"] == "Divine Orb" and plain["league"] == "Example League"
    bad = c.lookup({"rarity": "UNIQUE", "name": "Ember Veil", "base": "Silk Robe",
                    "flags": {"corrupted": True}})
    assert bad["value"] == 20.0 and bad["few"] is True
    rune = c.lookup({"rarity": "UNIQUE", "name": "Ember Veil",
                     "base": "Runemastered Silk Robe"})
    assert rune["value"] == 55.0
    assert c.lookup({"rarity": "UNIQUE", "name": "Nope", "base": "Silk Robe"}) is None
    assert c.lookup({"rarity": "RARE", "name": "Ember Veil", "base": "Silk Robe"}) is None


def test_stackable_lookup_exchange_and_currency(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    c.refresh()
    ess = c.lookup({"rarity": "CURRENCY", "base": "Greater Essence of Ruin"})
    assert ess["kind"] == "stackable" and ess["value"] == 0.35 and ess["type"] == "Essences"
    ex = c.lookup({"rarity": "CURRENCY", "base": "Exalted Orb"})
    assert ex["value"] == 0.002 and ex["unit"] == "Divine Orb" and ex["type"] == "Currency"


def test_lookup_ignores_another_leagues_cache(tmp_path):
    net, clock = FakeNet(), Clock()
    c, st = _client(tmp_path, net, clock)
    c.refresh()
    c.book.doc["types"]["UniqueArmours"]["league"] = "Old League"
    assert c.lookup({"rarity": "UNIQUE", "name": "Ember Veil", "base": "Silk Robe"}) is None


UNIQUE_TEXT = "\n".join([
    "Item Class: Body Armours", "Rarity: Unique", "Ember Veil", "Silk Robe",
    "--------", "Energy Shield: 80", "--------", "Item Level: 70"])


def test_press_card_carries_the_ninja_price(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    c.refresh()
    st = SessionState(clock=lambda: 10.0)
    checker = price.PriceChecker(league=lambda: "Example League", card=st.set_price,
                                 lookup=c.lookup)
    doc = checker.request(UNIQUE_TEXT, at=10.0)
    assert doc["status"] == "link"
    card = st.snapshot()["price"]
    assert card["ninja"] == {"kind": "unique", "name": "Ember Veil", "value": 12.5,
                             "unit": "Divine Orb", "listings": 342, "few": False,
                             "change": 8.2, "league": "Example League"}
    assert card["text"]["line"] == "About 12.5 Divine Orb"
    assert card["text"]["detail"] == "Up 8.2% over 7 days (poe.ninja)"
    assert card["text"]["sentence"] == (
        "poe.ninja puts this at about 12.5 Divine Orb in Example League, from 342 "
        "listings; up 8.2% over 7 days. A trade site search in Example League is "
        "ready too; click the link to see who sells it.")
    assert st.snapshot()["card"]["line2"] == "About 12.5 Divine Orb"


def test_press_without_a_cached_price_keeps_the_link_card(tmp_path):
    def broken(item):
        raise RuntimeError("cache gone")
    st = SessionState(clock=lambda: 10.0)
    checker = price.PriceChecker(league=lambda: None, card=st.set_price, lookup=broken)
    checker.request(UNIQUE_TEXT, at=10.0)
    card = st.snapshot()["price"]
    assert card["ninja"] is None and card["text"]["line"] == "Trade link ready"
    assert item_mod.parse(UNIQUE_TEXT).rarity == "UNIQUE"


def test_ninja_text_exact():
    assert ninja_text(None) is None
    assert ninja_text({"value": float("nan")}) is None
    few = ninja_text({"value": 20.0, "unit": "Divine Orb", "listings": 3, "few": True,
                      "change": -40.0, "league": "L"})
    assert few == {"line": "About 20 Divine Orb", "detail": "Few listings: rough price",
                   "sentence": "poe.ninja puts this at about 20 Divine Orb in L, but "
                               "only 3 are listed. The price is rough; down 40% "
                               "over 7 days."}
    dust = ninja_text({"value": 0.0004, "unit": "Divine Orb", "listings": None,
                       "league": None})
    assert dust == {"line": "Under 0.001 Divine Orb", "detail": "From poe.ninja",
                    "sentence": "poe.ninja puts this at under 0.001 Divine Orb "
                                "in this league."}
    rough = ninja_text({"value": 2, "unit": "Divine Orb", "listings": 1, "few": True})
    assert rough["sentence"] == ("poe.ninja puts this at about 2 Divine Orb in this "
                                 "league, but only 1 is listed. The price is rough.")
    small = ninja_text({"value": 0.0347, "unit": "", "listings": 1, "change": 0.2,
                        "league": "L"})
    assert small["line"] == "About 0.0347"
    assert small["sentence"] == "poe.ninja puts this at about 0.0347 in L, from 1 listing."


def test_price_card_text_without_ninja_is_unchanged():
    t = price_card_text({"status": "link", "league": "L", "item": {"name": "X"}})
    assert t["line"] == "Trade link ready"


# -- UTIL-MOVERS ---------------------------------------------------------------

def test_movers_from_the_cache_only_thin_markets_left_out(tmp_path):
    net, clock = FakeNet(), Clock()
    c, st = _client(tmp_path, net, clock)
    c.refresh()
    n = len(net.calls)
    m = c.snapshot()["movers"]
    assert [(r["name"], r["change"]) for r in m["up"]] == [
        ("Greater Essence of Ruin", 61.0), ("Ember Veil", 8.2)]
    # the 3-listing corrupted Veil and the 0.2-volume essence are noise
    assert [(r["name"], r["change"]) for r in m["down"]] == [("Hollow Crown", -25.5)]
    assert m["up"][0] == {"name": "Greater Essence of Ruin", "type": "Essences",
                          "value": 0.35, "unit": "Divine Orb", "change": 61.0}
    assert len(net.calls) == n  # no extra request
    st["on"] = False
    assert c.snapshot()["movers"] == {"up": [], "down": []}


# -- UTIL-1.0-READY: league rollover -----------------------------------------

def test_league_rollover_on_404_picks_the_new_league_within_the_hour(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    c.refresh()
    assert c.snapshot()["league"] == "Example League"
    # 1.0 launches: the old league's overview is gone, the list has a new first
    net.status["league=Example+League&type=Currency"] = 404
    clock.t += ninja.MIN_INTERVAL_S + 1
    assert c.refresh().startswith("error")
    assert c.doc["league_stale"] is True
    global LEAGUES
    old = LEAGUES
    LEAGUES = json.dumps([{"id": "Dawn League", "name": "Dawn League"}]).encode()
    try:
        clock.t += ninja.MIN_INTERVAL_S + 1
        assert c.refresh() == "fetched"
    finally:
        LEAGUES = old
    assert c.snapshot()["league"] == "Dawn League" and c.doc["league_stale"] is False
    # the book followed: old-league entries are gone, new ones are in
    hit = c.lookup({"rarity": "UNIQUE", "name": "Ember Veil", "base": "Silk Robe"})
    assert hit["league"] == "Dawn League"


def test_league_list_is_reread_every_six_hours_not_daily(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    c.refresh()

    def lookups():
        return sum(1 for _, u, _ in net.calls if u.endswith(ninja.LEAGUES_PATH))
    assert lookups() == 1
    clock.t += ninja.MIN_INTERVAL_S + 1
    c.refresh()
    assert lookups() == 1
    clock.t += ninja.LEAGUE_INTERVAL_S
    c.refresh()
    assert lookups() == 2 and ninja.LEAGUE_INTERVAL_S == 6 * 3600


def test_configured_league_never_rolls_over(tmp_path):
    net, clock = FakeNet(), Clock()
    c, _ = _client(tmp_path, net, clock, league="Standard")
    net.status["type=Currency"] = 404
    c.refresh()
    assert not c.doc.get("league_stale")
    assert not any(u.endswith(ninja.LEAGUES_PATH) for _, u, _ in net.calls)


# -- DATA-LEAGUE-IDENTITY (F-031): the list kept whole, conditional GET ------

class ListNet(FakeNet):
    """FakeNet whose leagues list carries an ETag and answers 304 to it."""

    def __init__(self, body=LEAGUES, etag='"L1"'):
        super().__init__()
        self.list_body, self.list_etag = body, etag

    def __call__(self, method, url, headers, body=None):
        if url.endswith(ninja.LEAGUES_PATH):
            self.calls.append((method, url, dict(headers)))
            if headers.get("If-None-Match") == self.list_etag:
                return 304, {"ETag": self.list_etag}, b""
            return 200, {"ETag": self.list_etag}, self.list_body
        return super().__call__(method, url, headers, body)


def _list_calls(net):
    return [h for _, u, h in net.calls if u.endswith(ninja.LEAGUES_PATH)]


def test_league_get_sends_if_none_match_and_a_304_keeps_the_list(tmp_path):
    net, clock = ListNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    assert c.refresh() == "fetched"
    first = _list_calls(net)
    assert len(first) == 1 and "If-None-Match" not in first[0]
    whole = [{"id": "Example League", "name": "Example League"},
             {"id": "Standard", "name": "Standard"}]
    assert c.doc["leagues"] == whole and c.doc["league_list_etag"] == '"L1"'
    assert c.snapshot()["leagues"] == whole
    # 6 h later, and after a restart on the same cache: a conditional GET
    clock.t += ninja.LEAGUE_INTERVAL_S + 1
    c2, _ = _client(tmp_path, net, clock)
    c2.refresh()
    again = _list_calls(net)
    assert len(again) == 2 and again[1]["If-None-Match"] == '"L1"'
    assert c2.doc["leagues"] == whole and c2.doc["league_auto"] == "Example League"
    assert c2.snapshot()["league"] == "Example League"
    # a changed list (new ETag) answers 200 and replaces the cached one
    net.list_body = json.dumps([{"id": "dawn", "name": "Dawn League"}]).encode()
    net.list_etag = '"L2"'
    clock.t += ninja.LEAGUE_INTERVAL_S + 1
    c2.refresh()
    assert c2.doc["leagues"] == [{"id": "dawn", "name": "Dawn League"}]
    assert c2.doc["league_list_etag"] == '"L2"' and c2.doc["league_auto"] == "dawn"


def test_league_change_time_is_recorded(tmp_path):
    net, clock = ListNet(), Clock()
    c, _ = _client(tmp_path, net, clock)
    c.refresh()
    veil = {"rarity": "UNIQUE", "name": "Ember Veil", "base": "Silk Robe"}
    # the first league ever priced is not a change
    assert c.doc.get("league_changed_at") is None
    assert c.snapshot()["league_changed_at"] is None
    assert c.lookup(veil)["league_changed_at"] is None
    # 1.0 launches: the old overview 404s, the list names a new league whose
    # id differs from its name
    net.status["league=Example+League&type=Currency"] = 404
    clock.t += ninja.MIN_INTERVAL_S + 1
    assert c.refresh().startswith("error")
    assert c.doc.get("league_changed_at") is None  # nothing priced yet
    net.list_body = json.dumps([{"id": "dawn", "name": "Dawn League"}]).encode()
    net.list_etag = '"L2"'
    clock.t += ninja.MIN_INTERVAL_S + 1
    changed = clock.t
    assert c.refresh() == "fetched"
    snap = c.snapshot()
    assert c.doc["league_changed_at"] == changed
    assert snap["league_changed_at"] == ninja._utc(changed)
    assert (snap["league"], snap["league_id"]) == ("Dawn League", "dawn")
    hit = c.lookup(veil)
    assert hit["league"] == "Dawn League" and hit["league_changed_at"] == changed
    ex = c.lookup({"rarity": "CURRENCY", "base": "Exalted Orb"})
    assert ex["league"] == "Dawn League" and ex["league_changed_at"] == changed
    # the same league an hour later keeps the time
    clock.t += ninja.MIN_INTERVAL_S + 1
    c.refresh()
    assert c.doc["league_changed_at"] == changed
