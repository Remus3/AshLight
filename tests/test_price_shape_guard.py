"""DATA-PRICE-SHAPE-GUARD (F-085): a silent poe.ninja shape change keeps the
last good prices.

An HTTP 200 answer whose lines are present but give no usable entry, or
whose kept entries are fewer than half of 5 or more lines, is a shape
error: the type keeps its last good entries and ETag, last_error says
"shape: ...", it counts as a failure, /api/rates (RatesClient.snapshot)
publishes every type's state and Checks shows a failing row naming
poe.ninja and the worst type. Zero lines is never an error.

Mocked fetch only; no request reaches the network. Bodies are synthetic
(invented item names). Tmp cache and runtime only."""

import json
import zlib

from server.al import diag, diag_data, ninja, pricebook
from server.al.core import Core

NOW = 1_800_000_000.0
LEAGUES = json.dumps([{"id": "Example League", "name": "Example League"}]).encode()
CORE = {"items": [{"id": "divine", "name": "Divine Orb"}], "primary": "divine"}


def _uniques(value_key="primaryValue", n=6):
    lines = [{"name": f"Ember Veil {i}", "baseType": "Silk Robe", value_key: 1.5 + i,
              "listingCount": 40} for i in range(n)]
    return json.dumps({"core": CORE, "lines": lines}).encode()


def _currency(value_key="primaryValue"):
    lines = [{"id": "exalted", value_key: 0.002}, {"id": "divine", value_key: 1},
             {"id": "chaos", value_key: 0.01}]
    return json.dumps({"core": CORE, "lines": lines,
                       "items": [{"id": "exalted", "name": "Exalted Orb"},
                                 {"id": "chaos", "name": "Chaos Orb"}]}).encode()


class Net:
    """poe.ninja stand-in: bodies per type key, an ETag per body."""

    def __init__(self):
        self.calls = []
        self.bodies = {"type=Currency": _currency(), "type=UniqueWeapons": _uniques()}

    def __call__(self, method, url, headers, body=None):
        self.calls.append((url, dict(headers)))
        if url.endswith(ninja.LEAGUES_PATH):
            return 200, {}, LEAGUES
        for key, data in self.bodies.items():
            if key in url:
                etag = '"%08x"' % zlib.crc32(data)
                if headers.get("If-None-Match") == etag:
                    return 304, {"ETag": etag}, b""
                return 200, {"ETag": etag}, data
        return 200, {}, json.dumps({"core": CORE, "lines": []}).encode()


class Clock:
    def __init__(self):
        self.t = NOW

    def __call__(self):
        return self.t


def _client(tmp_path, net, clock):
    d = tmp_path / "ninja"
    return ninja.RatesClient(d, enabled=lambda: True, fetch=net, clock=clock,
                             contact=lambda: "test-contact",
                             book=pricebook.PriceBook(d), installed=lambda: False)


# -- the rule ------------------------------------------------------------------

def test_shape_rule_counts():
    assert pricebook.shape_error(0, 0) is None  # an empty type stays quiet
    assert pricebook.shape_error(3, 0) == "shape: 3 lines but no usable entry"
    assert pricebook.shape_error(4, 1) is None  # under 5 lines: no share rule
    assert pricebook.shape_error(5, 2) == "shape: kept 2 of 5 lines"
    assert pricebook.shape_error(6, 3) is None  # half kept is fine
    assert pricebook.state_of(0, None) == "empty"
    assert pricebook.state_of(3, None) == "ok"
    assert pricebook.state_of(3, "HTTP 500") == "error"
    assert pricebook.state_of(3, "shape: kept 2 of 5 lines") == "shape"


def test_parsers_return_the_dict_line_count():
    p = pricebook.parse_item_overview(
        json.dumps({"lines": [{"name": "A", "primaryValue": 1}, {"name": "B"}, "junk"]}))
    assert p["lines"] == 2 and len(p["entries"]) == 1
    e = pricebook.parse_exchange_overview(json.dumps({"lines": [{"id": "x"}, 3]}))
    assert e["lines"] == 1 and e["entries"] == []
    assert ninja.parse_overview(_currency())["lines"] == 3


# -- the book --------------------------------------------------------------------

def test_renamed_value_key_keeps_yesterdays_entries_and_sets_a_shape_error(tmp_path):
    net, clock = Net(), Clock()
    c = _client(tmp_path, net, clock)
    assert c.refresh() == "fetched"
    t = c.book.doc["types"]["UniqueWeapons"]
    good, etag, fetched = list(t["entries"]), t["etag"], t["fetched_at"]
    assert len(good) == 6 and t["last_error"] is None
    # a day later poe.ninja renames primaryValue: lines present, none usable
    net.bodies["type=UniqueWeapons"] = _uniques("primaryPrice")
    net.bodies["type=Currency"] = _currency("primaryPrice")
    clock.t += 24 * 3600
    out = c.refresh()
    assert out.startswith("error: shape: ")
    t = c.book.doc["types"]["UniqueWeapons"]
    assert t["entries"] == good and t["etag"] == etag and t["fetched_at"] == fetched
    assert t["last_error"] == "shape: 6 lines but no usable entry"
    assert t["fails"] == 1  # a shape error is a failure (FAILS_DAILY applies)
    assert c.doc["last_error"] == "shape: 3 lines but no usable entry"
    assert set(c.doc["rates"]) == {"exalted", "divine", "chaos"}  # Currency kept too
    hit = c.lookup({"rarity": "UNIQUE", "name": "Ember Veil 0", "base": "Silk Robe"})
    assert hit is not None and hit["value"] == 1.5
    # the ETag kept is the old one: the next ask gets the new body again
    clock.t += pricebook.INTERVAL_S + 1
    c.refresh()
    asked = [h for u, h in net.calls if "type=UniqueWeapons" in u][-1]
    assert asked.get("If-None-Match") == etag
    assert c.book.doc["types"]["UniqueWeapons"]["fails"] == 2
    # most lines lost is a shape error too: 2 of 6 kept
    lines = json.loads(_uniques())["lines"]
    for line in lines[2:]:
        line.pop("primaryValue")
    net.bodies["type=UniqueWeapons"] = json.dumps({"core": CORE, "lines": lines}).encode()
    clock.t += pricebook.INTERVAL_S + 1
    c.refresh()
    t = c.book.doc["types"]["UniqueWeapons"]
    assert t["last_error"] == "shape: kept 2 of 6 lines" and t["entries"] == good
    assert t["fails"] == pricebook.FAILS_DAILY  # now asked once a day
    # the shape comes back: the type heals on its daily ask
    net.bodies["type=UniqueWeapons"] = _uniques(n=5)
    net.bodies["type=Currency"] = _currency()
    clock.t += pricebook.DAILY_S + 1
    c.refresh()
    t = c.book.doc["types"]["UniqueWeapons"]
    assert t["last_error"] is None and t["fails"] == 0 and len(t["entries"]) == 5
    assert c.doc["last_error"] is None


def test_empty_lines_body_raises_nothing(tmp_path):
    net, clock = Net(), Clock()
    net.bodies["type=UniqueWeapons"] = json.dumps({"core": CORE, "lines": []}).encode()
    c = _client(tmp_path, net, clock)
    assert c.refresh() == "fetched"
    s = c.book.summary()
    assert s["UniqueWeapons"] == {"entries": 0, "league": "Example League",
                                  "last_error": None, "state": "empty"}
    assert all(v["last_error"] is None for v in s.values())
    assert c.book.doc["types"]["UniqueWeapons"].get("fails") == 0
    assert c.book.worst()["state"] == "empty"
    # an empty Currency overview is no shape error either (a new league)
    net.bodies["type=Currency"] = json.dumps({"core": CORE, "lines": []}).encode()
    clock.t += ninja.MIN_INTERVAL_S + 1
    assert c.refresh() == "fetched" and c.doc["last_error"] is None
    assert c.types()["Currency"]["state"] == "empty"


# -- Checks and /api/rates ---------------------------------------------------------

def _shape_core(tmp_path, net):
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "local.json").write_text(json.dumps({"web_data": True, "contact": "test-contact"}),
                                   encoding="ascii")
    return Core(runtime=rt, tail=False, web_fetch=net)


def test_checks_row_fails_and_names_poe_ninja_and_the_worst_type(tmp_path):
    diag_data.reset()
    net = Net()
    net.bodies["type=UniqueWeapons"] = _uniques("primaryPrice")
    core = _shape_core(tmp_path, net)
    try:
        core.rates.refresh(force=True)
        f = core.diag_facts(NOW)
        v = diag.view(f, "1.0.0", now=NOW)
        # healed: the row goes
        net.bodies["type=UniqueWeapons"] = _uniques()
        core.rates.refresh(force=True)
        healed = diag.view(core.diag_facts(NOW), "1.0.0", now=NOW)
    finally:
        core.close()
        diag_data.reset()
    assert f[pricebook.FACT]["worst"]["type"] == "UniqueWeapons"
    assert f[pricebook.FACT]["shape"] == ["UniqueWeapons"]
    rows = {r["id"]: r for r in v["checks"]}
    row = rows["price_shape"]
    assert row["status"] == diag.FAIL
    assert "poe.ninja" in row["detail"] and "UniqueWeapons" in row["detail"]
    assert "last good prices" in row["detail"] and row["fix"]
    assert "price_shape" not in {r["id"] for r in healed["checks"]}
    # only a shape state fails the row; an HTTP error or an empty type never does
    for state in ("error", "empty", "ok"):
        fact = {"worst": {"type": "Runes", "state": state, "last_error": None}, "shape": []}
        assert pricebook.diag_rows({"web_data": True, "contact_set": True,
                                    pricebook.FACT: fact}, NOW) == []
    shape = {"worst": {"type": "Currency", "state": "shape", "last_error": "shape: x"},
             "shape": ["Currency", "Runes", "Idols"]}
    got = pricebook.diag_rows({"web_data": True, "contact_set": True,
                               pricebook.FACT: shape}, NOW)
    assert "Currency" in got[0]["detail"] and "2 other price types" in got[0]["detail"]
    # web data off or no contact: no row
    assert pricebook.diag_rows({"web_data": False, "contact_set": True,
                                pricebook.FACT: shape}, NOW) == []
    assert pricebook.diag_rows({"web_data": True, "contact_set": False,
                                pricebook.FACT: shape}, NOW) == []
    assert pricebook.diag_facts(object()) == {}


def test_rates_snapshot_publishes_per_type_state(tmp_path):
    net, clock = Net(), Clock()
    c = _client(tmp_path, net, clock)
    c.refresh()
    net.bodies["type=UniqueWeapons"] = _uniques("primaryPrice")
    clock.t += pricebook.INTERVAL_S + 1
    c.refresh()
    types = c.snapshot()["types"]
    assert list(types)[0] == "Currency"
    assert set(types) == {"Currency"} | set(pricebook.UNIQUE_TYPES) | set(pricebook.EXCHANGE_TYPES)
    assert types["Currency"] == {"entries": 3, "league": "Example League",
                                 "last_error": None, "state": "ok"}
    assert types["UniqueWeapons"]["state"] == "shape"
    assert types["UniqueWeapons"]["entries"] == 6
    assert types["Runes"]["state"] == "empty"
    assert all(t["state"] in pricebook.STATES for t in types.values())
    assert pricebook.worst_of(types)["type"] == "UniqueWeapons"
    assert c.book.worst() == {"type": "UniqueWeapons", "state": "shape",
                              "last_error": "shape: 6 lines but no usable entry"}
    json.dumps(c.snapshot())  # the route serialises it as is
