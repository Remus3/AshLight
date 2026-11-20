"""TC-UPGRADE (decision 0017 item 3): an offline upgrade-search link per item
check. From the build's item in the checked slot (else the checked item's
base) trade.upgrade_link builds a trade2 search URL: base type and rarity,
plus weighted stat filters only with a trade id index (TC-UPGRADE-STATS,
tests/test_tc_upgrade_stats.py), complexity under the site's cap.
The URL comes from the same builder as the price link; nothing touches the
network and the core never opens it."""

import ast
import json
import socket
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from server.al import trade, upgrade
from server.al.core import Core
from server.al.theorycraft import codec
from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import health, model
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML, JEWEL, RARE_GLOVES

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "https://www.pathofexile.com/trade2/search/poe2/"
GLOVES_SLOT = '\t\t\t<Slot name="Gloves" itemId="1"/>\n'


def _decode(url):
    parts = urllib.parse.urlsplit(url)
    assert (parts.scheme, parts.netloc) == ("https", "www.pathofexile.com")
    league = urllib.parse.unquote(parts.path[len("/trade2/search/poe2/"):])
    qs = urllib.parse.parse_qs(parts.query, strict_parsing=True)
    assert list(qs) == ["q"] and len(qs["q"]) == 1
    return league, json.loads(qs["q"][0])


def _build(xml=EVAL_BUILD_XML):
    return model.parse(xml)


# -- trade.upgrade_query / upgrade_link: exact output -----------------------

def test_upgrade_query_exact_output():
    assert trade.upgrade_query("Example Gloves") == {
        "query": {"status": {"option": "online"}, "type": "Example Gloves",
                  "filters": {"type_filters": {"filters": {"rarity": {"option": "rare"}}}}},
        "sort": {"price": "asc"}}
    assert trade.upgrade_query("  Example Ring ")["query"]["type"] == "Example Ring"


def test_upgrade_link_exact_url():
    body = ('{"query":{"filters":{"type_filters":{"filters":{"rarity":{"option":"rare"}}}},'
            '"status":{"option":"online"},"type":"Example Gloves"},"sort":{"price":"asc"}}')
    want = PREFIX + "Example%20League?q=" + urllib.parse.quote(body, safe="")
    assert trade.upgrade_link("Example Gloves", "Example League") == want
    assert trade.is_search_link(want)


def test_upgrade_link_round_trip_and_default_league():
    url = trade.upgrade_link("Example Ring", "a/b?c#d&e")
    assert url.startswith(PREFIX + "a%2Fb%3Fc%23d%26e?q=")
    league, q = _decode(url)
    assert league == "a/b?c#d&e" and q == trade.upgrade_query("Example Ring")
    for none in (None, "", "  "):
        assert _decode(trade.upgrade_link("Example Ring", none))[0] == "Standard"
    assert url.isascii() and len(url) < 2048


def test_upgrade_query_has_no_stats_and_no_name():
    q = trade.upgrade_query("Example Gloves")["query"]
    assert "stats" not in q and "name" not in q
    assert set(q["filters"]) == {"type_filters"}
    assert set(q["filters"]["type_filters"]["filters"]) == {"rarity"}


def test_upgrade_query_refuses_missing_base():
    for bad in (None, "", "   ", 5):
        with pytest.raises(ValueError, match="^no base type$"):
            trade.upgrade_query(bad)


def test_complexity_cap():
    assert trade.complexity(trade.upgrade_query("Example Gloves")) == 0
    assert trade.MAX_COMPLEXITY == 200 and trade.STAT_FILTER_COST == 4
    many = {"query": {"stats": [{"type": "and", "filters": [{}] * 30},
                                {"type": "weight", "filters": [{}] * 21}]}}
    assert trade.complexity(many) == 204 > trade.MAX_COMPLEXITY
    assert trade.complexity({"query": {"stats": "junk"}}) == 0
    assert trade.complexity(None) == 0


def test_price_link_shares_the_builder():
    # the price link and the upgrade link come out of the one link_for
    from server.al.theorycraft import item as item_mod
    it = item_mod.parse(RARE_GLOVES)
    assert trade.search_link(it, "X") == trade.link_for(trade.build_query(it), "X")
    assert trade.upgrade_link("Example Gloves", "X") == trade.link_for(
        trade.upgrade_query("Example Gloves"), "X")
    # a rare checked item of the worn base gives the same search as its price link
    assert trade.upgrade_query("Example Gloves") == trade.build_query(it)


# -- upgrade.link: slot item from the build, else the checked item ---------

def test_link_uses_the_base_the_build_wears():
    xml = EVAL_BUILD_XML.replace("Old Grip\nExample Gloves", "Old Grip\nOther Gloves")
    result = tc_evaluate.evaluate(RARE_GLOVES, _build(xml))
    doc = upgrade.link(result, "Example League")
    assert doc == {"slot": "Gloves", "base": "Other Gloves", "source": "equipped",
                   "rarity": "rare", "league": "Example League",
                   "url": trade.upgrade_link("Other Gloves", "Example League"),
                   # TC-DELTA: the hand weights of the compared stats (no calc)
                   "weights": {"source": "hand", "top": [
                       {"key": "#% increased Attack Speed", "weight": 2},
                       {"key": "+# to maximum Life", "weight": 1},
                       {"key": "+#% to Cold Resistance", "weight": 1},
                       {"key": "+#% to Fire Resistance", "weight": 1},
                       {"key": "+#% to Lightning Resistance", "weight": 1}]},
                   # TC-UPGRADE-STATS: no trade id index given, no filters
                   "filters": []}


def test_link_ring_uses_the_best_slot():
    result = tc_evaluate.evaluate(ADVANCED_RING, _build())
    doc = upgrade.link(result, None)
    assert doc["slot"] == result["slot"] == "Ring 1"
    assert doc["base"] == "Example Ring" and doc["league"] == "Standard"
    assert _decode(doc["url"])[1] == trade.upgrade_query("Example Ring")


def test_link_empty_slot_falls_back_to_the_checked_item():
    result = tc_evaluate.evaluate(RARE_GLOVES, _build(EVAL_BUILD_XML.replace(GLOVES_SLOT, "")))
    doc = upgrade.link(result)
    assert doc["source"] == "item" and doc["base"] == "Example Gloves"
    assert doc["slot"] == "Gloves"


def test_link_none_without_a_slot_to_search():
    assert upgrade.link(tc_evaluate.evaluate(RARE_GLOVES, None)) is None  # no build
    assert upgrade.link(tc_evaluate.evaluate("hello", _build())) is None
    assert upgrade.link(tc_evaluate.evaluate(JEWEL, _build())) is None
    for junk in (None, {}, {"ok": True}, {"ok": True, "slot": "Gloves"}, "x"):
        assert upgrade.link(junk) is None


# -- TC-UPGRADE-PER-SLOT: the same builder on every "look for next" row -----

NEXT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding2>
<Build level="80" className="Monk" ascendClassName="Invoker">
<PlayerStat stat="ColdResist" value="60"/>
<PlayerStat stat="FireResist" value="75"/>
<PlayerStat stat="LightningResist" value="75"/>
</Build>
<Items activeItemSet="1">
<Item id="1">
Rarity: RARE
Doom Grip
Example Gloves
+40 to maximum Life
</Item>
<Item id="2">
Rarity: RARE
Loop Band
Example Ring
+30 to maximum Life
</Item>
<ItemSet id="1">
<Slot name="Gloves" itemId="1"/>
<Slot name="Ring 1" itemId="2"/>
</ItemSet>
</Items>
</PathOfBuilding2>
"""
COLD_ID = "explicit.stat_4220027924"
SPEED_ID = "explicit.stat_681332047"


def test_slot_link_for_a_next_look_row():
    b = model.parse(NEXT_XML)
    ids = {"#% to cold resistance": COLD_ID, "#% increased attack speed": SPEED_ID}
    weights = {"Gloves": {"#% increased Attack Speed": 2.5}}

    def rows(index):
        def link_for(base, slot, top):
            return upgrade.slot_link(base, slot, top, "Example League", index)
        return health.next_look(b, lambda build, slot: dict(weights.get(slot, {})),
                                link_for)["slots"]

    got = rows(ids)
    assert [r["slot"] for r in got] == ["Gloves", "Ring 1"]
    for r in got:
        assert r["terms"] and trade.is_search_link(r["url"])
    gloves, ring = got
    assert gloves["base"] == "Example Gloves" and ring["base"] == "Example Ring"
    league, q = _decode(gloves["url"])
    assert league == "Example League" and q["query"]["type"] == "Example Gloves"
    # the row's stats in its order: the cold gap takes the row's top PoB weight
    assert q["query"]["stats"] == [{"type": "weight", "filters": [
        {"id": COLD_ID, "value": {"weight": 2.5}},
        {"id": SPEED_ID, "value": {"weight": 2.5}}]}]
    # a row with no PoB weight at all weights its gaps evenly
    assert _decode(ring["url"])[1]["query"]["stats"] == [{"type": "weight", "filters": [
        {"id": COLD_ID, "value": {"weight": 1.0}}]}]
    # no trade id index: the same rows, links with base type and rarity only
    for r in rows({}) + rows(None):
        assert trade.is_search_link(r["url"])
        assert _decode(r["url"])[1] == trade.upgrade_query(r["base"])


def test_slot_link_matches_the_item_check_link():
    result = tc_evaluate.evaluate(RARE_GLOVES, _build())
    doc = upgrade.link(result, "Example League")
    per_slot = upgrade.slot_link(doc["base"], doc["slot"], doc["weights"]["top"],
                                 "Example League")
    assert per_slot["url"] == doc["url"]
    assert upgrade.slot_link(None, "Gloves") is None
    assert upgrade.slot_link("  ", "Gloves", [{"key": "x", "weight": 1}]) is None
    for junk in (None, "x", [None, {"key": 1, "weight": 2}, {"key": "k", "weight": True}]):
        assert upgrade.slot_link("Example Ring", "Ring 1", junk, None, {"k": COLD_ID})[
            "filters"] == []


def test_upgrade_module_imports_only_trade():
    tree = ast.parse((ROOT / "server" / "al" / "upgrade.py").read_text(encoding="ascii"))
    imports = [ast.dump(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    # TC-UPGRADE-STATS: plus the read-only trade stat id index
    assert imports == [ast.dump(ast.parse("from . import trade, tradestats").body[0])]


# -- core: built on the hotkey press, no network ----------------------------

class _NoNet:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        raise AssertionError("network call during an item check")


@pytest.fixture
def core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "local.json").write_text(json.dumps({"league": "Example League"}), encoding="ascii")
    net = _NoNet()
    c = Core(runtime=rt, log_path=str(log), poll_s=0.05, web_fetch=net)
    yield c, net
    c.close()


def test_press_builds_the_link_with_no_network_call(core, monkeypatch):
    c, net = core
    guard = _NoNet()
    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
    monkeypatch.setattr(urllib.request, "urlopen", guard)
    c.eval_press(RARE_GLOVES)
    assert c.state.eval["upgrade"] is None  # no build yet: no slot item
    c.builds.load_code(codec.encode(EVAL_BUILD_XML))  # rerun: no click
    up = c.state.eval["upgrade"]
    assert up["slot"] == "Gloves" and up["league"] == "Example League"
    assert up["url"] == trade.upgrade_link("Example Gloves", "Example League")
    c.eval_press(ADVANCED_RING)
    assert c.state.eval["upgrade"]["slot"] == "Ring 1"
    assert guard.calls == [] and net.calls == []
