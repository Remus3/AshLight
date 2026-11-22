"""DATA-PRICE-CADENCE (F-046, decision 0072): poe.ninja polling tiers and
the release polling gate.

Currency refreshes hourly, the other 21 overview types every 3 h, and a
type a press matched in the last 24 h hourly; a day with no press makes at
most 200 overview GETs. An installed (release) copy sends poe.ninja nothing
while ninja.RELEASE_POLLING is off, and the press still builds its offline
trade link. Mocked fetch only; nothing reaches the network. Tmp cache dirs.
"""

import json
import types

from server.al import ninja, paths, price, pricebook, trade
from server.al.theorycraft import item as item_mod
from tc_eval_fixtures import ADVANCED_RING

CORE = {"items": [{"id": "divine", "name": "Divine Orb", "category": "Currency"}],
        "primary": "divine"}
CURRENCY = json.dumps({
    "core": CORE, "items": [{"id": "chaos", "name": "Chaos Orb"}],
    "lines": [{"id": "chaos", "primaryValue": 0.01}]}).encode()
UNIQUES = json.dumps({
    "core": CORE,
    "lines": [{"name": "Ember Veil", "baseType": "Silk Robe", "primaryValue": 12.5,
               "listingCount": 300}]}).encode()
EMPTY = json.dumps({"core": CORE, "lines": []}).encode()
DAY = 24 * 3600
START = 1_800_000_000.0
N_BOOK = len(pricebook.UNIQUE_TYPES) + len(pricebook.EXCHANGE_TYPES)


class Net:
    """Records every request; answers 200 with a fresh body (no ETag)."""

    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append(url)
        if "type=Currency" in url:
            return 200, {}, CURRENCY
        if "type=UniqueArmours" in url:
            return 200, {}, UNIQUES
        return 200, {}, EMPTY

    def overviews(self, key="/overview"):
        return [u for u in self.calls if key in u]


class Clock:
    def __init__(self, t=START):
        self.t = t

    def __call__(self):
        return self.t


def _client(tmp_path, net, clock, installed=lambda: False):
    d = tmp_path / "ninja"
    return ninja.RatesClient(d, enabled=lambda: True, league=lambda: "Example League",
                             fetch=net, clock=clock, contact=lambda: "test-contact",
                             book=pricebook.PriceBook(d), installed=installed)


def _run(c, clock, start, end, step=60):
    """One refresh check a minute from start up to (not incl.) end."""
    t = start
    while t < end:
        clock.t = t
        c.refresh()
        t += step


def _press(c, name="Ember Veil", base="Silk Robe"):
    item = types.SimpleNamespace(rarity="UNIQUE", name=name, base=base, flags={})
    return c.lookup(item)


def test_unpressed_day_makes_at_most_200_overview_gets(tmp_path):
    net, clock = Net(), Clock()
    c = _client(tmp_path, net, clock)
    _run(c, clock, START, START + DAY)
    over = net.overviews()
    assert len(over) <= 200
    assert len(net.overviews("type=Currency")) == 24  # Currency hourly
    for name in pricebook.UNIQUE_TYPES + pricebook.EXCHANGE_TYPES:
        assert sum(1 for u in over if u.endswith("type=" + name)) == 8, name
    assert len(over) == 24 + N_BOOK * 8 <= 200
    assert pricebook.INTERVAL_S == 3 * 3600 and pricebook.PRESSED_INTERVAL_S == 3600
    # a price watch re-read (a plain dict) is no press: the cadence holds
    clock.t = START + DAY
    assert c.lookup({"rarity": "UNIQUE", "name": "Ember Veil",
                     "base": "Silk Robe"})["value"] == 12.5
    assert c.book.pressed("UniqueArmours", clock.t) is False


def test_pressed_type_refreshes_hourly_for_24_h(tmp_path):
    net, clock = Net(), Clock()
    c = _client(tmp_path, net, clock)
    clock.t = START
    assert c.refresh() == "fetched"  # the first round fills the cache
    hit = _press(c)
    assert hit is not None and hit["type"] == "UniqueArmours"
    # the press wrote nothing: the press time is in memory until a refresh
    on_disk = json.loads(c.book.path.read_text(encoding="ascii"))
    assert "UniqueArmours" not in (on_disk.get("pressed") or {})
    net.calls.clear()

    def asked(name):
        return sum(1 for u in net.calls if u.endswith("type=" + name))

    _run(c, clock, START + 60, START + DAY)
    # hourly from START: 23 more in the first day; an unpressed type 7 more
    assert asked("UniqueArmours") == 23 and asked("UniqueWeapons") == 7
    assert asked("Currency") == 23
    # the next refresh saved the press time with the round, and a restart
    # on the same cache keeps it
    on_disk = json.loads(c.book.path.read_text(encoding="ascii"))
    assert on_disk["pressed"]["UniqueArmours"] == START
    again = pricebook.PriceBook(tmp_path / "ninja")
    assert again.pressed("UniqueArmours", START + DAY - 1) is True
    # 24 h after the press the type falls back to 3 h
    net.calls.clear()
    _run(c, clock, START + DAY, START + 2 * DAY)
    assert asked("UniqueArmours") == 8 and asked("UniqueWeapons") == 8
    assert c.book.pressed("UniqueArmours", clock.t) is False
    assert "UniqueArmours" not in c.book.doc["pressed"]
    # a Currency hit or an unknown type never marks a book type
    c.book.note_press("NotAType", clock.t)
    c.book.note_press("Currency", clock.t)
    assert not c.book.pressed("NotAType", clock.t)


def test_release_build_makes_no_ninja_request_and_still_builds_the_trade_link(
        tmp_path, monkeypatch):
    assert ninja.RELEASE_POLLING is False
    net, clock = Net(), Clock()
    c = _client(tmp_path, net, clock, installed=lambda: True)
    assert c.refresh() == "off: " + ninja.REASON_RELEASE
    assert c.refresh(force=True) == "off: " + ninja.REASON_RELEASE
    assert c.refresh_async() is False and c.any_due() is True
    _run(c, clock, START, START + 3 * 3600, step=600)
    assert net.calls == []
    snap = c.snapshot()
    assert snap["blocked"] == ninja.REASON_RELEASE == "release build"
    assert snap["next_refresh_in_s"] is None
    # web data off still reads as off first
    off = ninja.RatesClient(tmp_path / "off", enabled=lambda: False, fetch=net,
                            installed=lambda: True)
    assert off.refresh() == "off" and off.snapshot()["blocked"] == "web data off"
    # the default reads paths.install_mode (DEP-05)
    monkeypatch.setattr(paths, "install_mode", lambda environ=None: "installed")
    d = ninja.RatesClient(tmp_path / "def", enabled=lambda: True, fetch=net,
                          contact=lambda: "test-contact", clock=clock)
    assert d.refresh() == "off: release build" and net.calls == []
    # the press still builds its offline trade link, no ninja price
    cards = []
    checker = price.PriceChecker(league=lambda: "Example League", lookup=c.lookup,
                                 card=lambda card, at=None, keep_time=False:
                                 cards.append(card))
    doc = checker.request(ADVANCED_RING, at=START)
    assert doc["status"] == "link" and doc["ninja"] is None
    assert doc["url"] == trade.search_link(item_mod.parse(ADVANCED_RING),
                                           "Example League")
    assert cards and cards[-1]["url"] == doc["url"]
    assert net.calls == []


def test_source_checkout_polls_with_the_constant_off(tmp_path, monkeypatch):
    assert ninja.RELEASE_POLLING is False
    net, clock = Net(), Clock()
    c = _client(tmp_path, net, clock, installed=lambda: False)
    assert c.release_blocked() is False and c.snapshot()["blocked"] is None
    assert c.refresh() == "fetched"
    assert len(net.overviews()) == 1 + N_BOOK
    # the default in a checkout: install_mode() says "checkout"
    monkeypatch.setattr(paths, "install_mode", lambda environ=None: "checkout")
    d = ninja.RatesClient(tmp_path / "def", enabled=lambda: True, fetch=net,
                          league=lambda: "Example League",
                          contact=lambda: "test-contact", clock=clock)
    assert d.release_blocked() is False and d.refresh() == "fetched"
    # without install_mode (DEP-05 missing) the default is a checkout too
    monkeypatch.delattr(paths, "install_mode")
    assert ninja._installed_default() is False
    # flipping the constant lets an installed copy poll
    monkeypatch.setattr(ninja, "RELEASE_POLLING", True)
    e = _client(tmp_path / "e", net, clock, installed=lambda: True)
    assert e.release_blocked() is False and e.refresh() == "fetched"
