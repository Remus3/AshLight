"""DATA-NINJA-SHAPE-WATCH (F-140 layers 1 and 3): poe.ninja bodies checked
against the tracked read-key baseline, the SHAPE_DRIFT flag, the league
list invariant and the 'League changed to X' note.

Synthetic bodies in the real shape (research 0036 evidence base: the
exchange body's keys); mocked fetch only, tmp dirs only, no network.
"""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.al import diag, hotreload, ninja, ninjashape, pricebook

ROOT = Path(__file__).resolve().parents[1]
NOW = 1_800_000_000.0
DAY = 86400.0


def _exchange(n=6, line_extra=None, top_extra=None, rename=None):
    """An exchange overview in the real shape: n lines, n items, core with
    the reference currency. `rename` = (old key, new key) on every line."""
    lines, items = [], []
    for i in range(n):
        lid = "divine" if i == 0 else f"item-{i}"
        line = {"id": lid, "primaryValue": 1 if i == 0 else 0.1 * i,
                "volumePrimaryValue": 10.0 + i, "maxVolumeCurrency": "divine",
                "maxVolumeRate": 2.0, "sparkline": {"totalChange": 1.5, "data": [1, 2]}}
        if line_extra:
            line.update(line_extra)
        if rename:
            line[rename[1]] = line.pop(rename[0])
        lines.append(line)
        items.append({"id": lid, "name": f"Item {i}", "image": "/x.png",
                      "category": "Test", "detailsId": f"item-{i}"})
    doc = {"core": {"items": [{"id": "divine", "name": "Divine Orb"}],
                    "rates": {"x": 1.0}, "primary": "divine", "secondary": "chaos"},
           "lines": lines, "items": items}
    if top_extra:
        doc.update(top_extra)
    return json.dumps(doc).encode()


def _leagues(entries):
    return json.dumps(entries).encode()


HDR = {"ETag": '"v1"', "Cache-Control": "no-cache"}


def _flag(d):
    p = Path(d) / ninjashape.FLAG_NAME
    return json.loads(p.read_text(encoding="ascii")) if p.exists() else None


def _kept(body, kind="exchange"):
    parse = pricebook.parse_exchange_overview if kind == "exchange" \
        else pricebook.parse_item_overview
    try:
        return len(parse(body)["entries"])
    except ValueError:
        return None


class Clock:
    def __init__(self, t=NOW):
        self.t = t

    def __call__(self):
        return self.t


# -- the five named tests ----------------------------------------------------

def test_body_missing_a_read_key_raises_the_flag_with_family_type_and_keys(tmp_path):
    w = ninjashape.Watch(tmp_path / "ninja", clock=Clock())
    good = _exchange()
    assert w.record("exchange", "Essences", 200, HDR, good, _kept(good), _kept(good)) \
        == ninjashape.PASS
    assert _flag(tmp_path / "ninja") is None
    bad = _exchange(rename=("primaryValue", "price"))
    assert w.record("exchange", "Essences", 200, HDR, bad, _kept(bad), 0) == ninjashape.BREAK
    flag = _flag(tmp_path / "ninja")
    assert flag["family"] == "exchange" and flag["type"] == "Essences"
    assert flag["missing"] == ["lines.primaryValue"]
    assert flag["first_seen"] == "2027-01-15T08:00:00Z"
    assert set(flag) == {"family", "type", "missing", "first_seen", "reason"}
    # key names and a time only: no price, no item name
    text = json.dumps(flag)
    assert "Item " not in text and "0.1" not in text
    # a list that is not a list breaks, missing names every lines key
    w2 = ninjashape.Watch(tmp_path / "n2", clock=Clock())
    body = json.dumps({"core": {"primary": "divine"}, "lines": {"a": 1}}).encode()
    assert w2.record("item", "UniqueWeapons", 200, {}, body, None, None) == ninjashape.BREAK
    flag = _flag(tmp_path / "n2")
    assert flag["family"] == "item" and "lines.name" in flag["missing"]
    assert "lines.primaryValue" in flag["missing"]
    # a missing core.primary is a missing read key too
    w3 = ninjashape.Watch(tmp_path / "n3", clock=Clock())
    doc = json.loads(_exchange())
    del doc["core"]["primary"]
    body = json.dumps(doc).encode()
    assert w3.record("exchange", "Currency", 200, {}, body, 6, 6) == ninjashape.BREAK
    assert _flag(tmp_path / "n3")["missing"] == ["core.primary"]
    # only 200 bodies are looked at
    w4 = ninjashape.Watch(tmp_path / "n4", clock=Clock())
    assert w4.record("exchange", "Runes", 404, {}, b"{}", None, None) == ninjashape.PASS
    assert _flag(tmp_path / "n4") is None

    # end to end: the refresh paths hand their 200 bodies to the watch
    class Net:
        def __call__(self, method, url, headers, body=None):
            if url.endswith(ninja.LEAGUES_PATH):
                return 200, {}, _leagues([{"id": "L1", "name": "L1"}])
            if "type=Essences" in url:
                return 200, {}, _exchange(rename=("primaryValue", "price"))
            if "/item/" in url:
                return 200, {}, json.dumps({"core": {"primary": "divine"},
                                            "lines": []}).encode()
            return 200, {}, _exchange()

    d = tmp_path / "rates"
    rates = ninja.RatesClient(d, enabled=lambda: True, league=lambda: None, fetch=Net(),
                              clock=Clock(), contact=lambda: "c",
                              book=pricebook.PriceBook(d))
    core = SimpleNamespace(rates=rates, runtime=tmp_path / "rt")
    ninjashape.attach(core)
    assert rates.shape_watch is rates.book.shape_watch is core.ninja_shape
    assert rates.refresh() == "fetched"
    flag = _flag(tmp_path / "rt" / "ninja")
    assert (flag["family"], flag["type"]) == ("exchange", "Essences")
    assert flag["missing"] == ["lines.primaryValue"]
    seen = set(core.ninja_shape.results)
    assert ("leagues", "leagues") in seen and ("exchange", "Currency") in seen
    assert ("item", "UniqueWeapons") in seen and ("exchange", "Runes") in seen
    # an empty type (league start) is no alarm
    assert core.ninja_shape.results[("item", "UniqueWeapons")]["verdict"] == ninjashape.PASS


def test_body_with_an_extra_unknown_key_raises_nothing(tmp_path):
    w = ninjashape.Watch(tmp_path / "ninja", clock=Clock())
    good = _exchange()
    assert w.record("exchange", "Runes", 200, HDR, good, 6, 6) == ninjashape.PASS
    more = _exchange(line_extra={"lowConfidence": True}, top_extra={"meta": {}})
    got = w.record("exchange", "Runes", 200, HDR, more, _kept(more), 6)
    assert got == ninjashape.CHANGE  # information only
    assert "lowConfidence" in w.results[("exchange", "Runes")]["reason"]
    assert _flag(tmp_path / "ninja") is None
    assert w.view()["broken"] == [] and w.view()["changed"] == ["exchange Runes"]
    # the same body again is a plain pass
    assert w.record("exchange", "Runes", 200, HDR, more, 6, 6) == ninjashape.PASS
    # a first body with an extra key passes outright (nothing to compare)
    w2 = ninjashape.Watch(tmp_path / "n2", clock=Clock())
    assert w2.record("exchange", "Runes", 200, HDR, more, 6, 6) == ninjashape.PASS
    # a vanished ETag or another cache class is a change, never a break
    assert w2.record("exchange", "Runes", 200, {"Cache-Control": "max-age=60"}, more,
                     6, 6) == ninjashape.CHANGE
    assert _flag(tmp_path / "n2") is None
    # an item body missing only soft keys is a change (no real item body yet)
    w3 = ninjashape.Watch(tmp_path / "n3", clock=Clock())
    body = json.dumps({"core": {"primary": "divine", "items": []},
                       "lines": [{"name": f"U{i}", "primaryValue": 2.0}
                                 for i in range(6)]}).encode()
    assert w3.record("item", "UniqueJewels", 200, {}, body, 6, 6) == ninjashape.CHANGE
    assert _flag(tmp_path / "n3") is None


def test_flag_clears_when_every_type_passes_again(tmp_path):
    clock = Clock()
    d = tmp_path / "ninja"
    w = ninjashape.Watch(d, clock=clock)
    bad = _exchange(rename=("id", "itemKey"))
    good = _exchange()
    assert w.record("exchange", "Runes", 200, {}, bad, 0, 0) == ninjashape.BREAK
    clock.t += 60
    assert w.record("exchange", "Idols", 200, {}, bad, 0, 0) == ninjashape.BREAK
    flag = _flag(d)
    assert flag["type"] == "Runes"  # the first break is the flag
    assert "lines.id" in flag["missing"]
    first = flag["first_seen"]
    w.record("exchange", "Runes", 200, {}, good, 6, 6)
    flag = _flag(d)
    assert flag["type"] == "Idols"  # the next open break takes over
    assert flag["first_seen"] > first
    # a restart keeps the flag until its own type passes
    w2 = ninjashape.Watch(d, clock=clock)
    assert w2.view()["broken"] == [{"family": "exchange", "type": "Idols",
                                    "missing": flag["missing"]}]
    w2.record("exchange", "Runes", 200, {}, good, 6, 6)
    assert _flag(d) == flag
    w2.record("exchange", "Idols", 200, {}, good, 6, 6)
    assert _flag(d) is None and w2.view()["broken"] == []
    # a body that breaks again later raises a fresh flag
    clock.t += 3600
    w2.record("exchange", "Idols", 200, {}, bad, 0, 0)
    assert _flag(d)["first_seen"] > first


def test_league_list_invariants_and_changed_line_for_7_days(tmp_path):
    p = ninjashape.league_list_problem
    assert p([{"id": "A", "name": "A"}, {"id": "B", "name": "B"}]) is None
    assert p([]) == "empty"
    assert p({"id": "A"}) == "not a list"
    assert p([{"id": "A"}, {"id": "A"}]) == "an id appears twice"
    assert p([{"id": 3}]) == "an entry has no text id"
    w = ninjashape.Watch(tmp_path / "ninja", clock=Clock())
    ok = _leagues([{"id": "A", "name": "A"}, {"id": "B", "name": "B"}])
    assert w.record("leagues", "leagues", 200, {}, ok, 2, 2) == ninjashape.PASS
    dup = _leagues([{"id": "A", "name": "A"}, {"id": "A", "name": "A2"}])
    assert w.record("leagues", "leagues", 200, {}, dup, 1, 1) == ninjashape.BREAK
    flag = _flag(tmp_path / "ninja")
    assert flag["family"] == "leagues" and flag["missing"] == ["id"]
    assert w.record("leagues", "leagues", 200, {}, b"[]", None, None) == ninjashape.BREAK
    assert w.record("leagues", "leagues", 200, {}, ok, 2, 2) == ninjashape.PASS
    assert _flag(tmp_path / "ninja") is None

    # layer 3: the facts from the rates cache, the rows from the facts
    rates = SimpleNamespace(doc={"league": "Rise", "league_id": "rise",
                                 "league_changed_at": NOW - DAY,
                                 "leagues": [{"id": "rise", "name": "Rise"}]},
                            shape_watch=None)
    f = dict(ninjashape.diag_facts(SimpleNamespace(rates=rates)),
             web_data=True, contact_set=True)
    rows = ninjashape.diag_rows(f, NOW)
    assert rows == [{"id": "league_changed", "label": "League", "status": diag.NOTE,
                     "detail": "League changed to Rise.", "fix": None}]
    assert ninjashape.diag_rows(f, NOW + 5.9 * DAY)[0]["id"] == "league_changed"
    assert ninjashape.diag_rows(f, NOW + 6 * DAY) == []  # 7 days after the change, gone
    assert ninjashape.diag_rows(dict(f, web_data=False), NOW) == []
    # a bad cached list is a failing row; no cached list is no row
    rates.doc["leagues"] = [{"id": "rise"}, {"id": "rise"}]
    rates.doc.pop("league_changed_at")
    f = dict(ninjashape.diag_facts(SimpleNamespace(rates=rates)),
             web_data=True, contact_set=True)
    rows = ninjashape.diag_rows(f, NOW)
    assert [r["id"] for r in rows] == ["ninja_leagues"]
    assert rows[0]["status"] == diag.FAIL and "appears twice" in rows[0]["detail"]
    assert rows[0]["fix"] == ninjashape.LEAGUES_FIX
    rates.doc.pop("leagues")
    f = dict(ninjashape.diag_facts(SimpleNamespace(rates=rates)),
             web_data=True, contact_set=True)
    assert ninjashape.diag_rows(f, NOW) == []

    # end to end: ninja.py records league_changed_at on a new league id
    class Net:
        def __init__(self):
            self.first = "old"

        def __call__(self, method, url, headers, body=None):
            if url.endswith(ninja.LEAGUES_PATH):
                return 200, {}, _leagues([{"id": self.first, "name": self.first.title()}])
            return 200, {}, _exchange()

    clock, net = Clock(), Net()
    rc = ninja.RatesClient(tmp_path / "r", enabled=lambda: True, league=lambda: None,
                           fetch=net, clock=clock, contact=lambda: "c")
    core = SimpleNamespace(rates=rc, runtime=tmp_path / "rt")
    ninjashape.attach(core)
    assert rc.refresh() == "fetched"
    net.first = "new"
    clock.t += ninja.LEAGUE_INTERVAL_S + 1
    assert rc.refresh() in ("fetched", "unchanged")
    f = dict(ninjashape.diag_facts(core), web_data=True, contact_set=True)
    assert [r["detail"] for r in ninjashape.diag_rows(f, clock.t)] == [
        "League changed to New."]


def test_baseline_holds_key_names_only(tmp_path, monkeypatch):
    path = ROOT / "server" / "al" / "data" / "ninja_read_keys.json"
    raw = path.read_bytes()
    assert raw.isascii() and b"\r" not in raw
    doc = json.loads(raw)
    assert set(doc["families"]) == {"leagues", "exchange", "item"}
    key = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*$")
    for fam, spec in doc["families"].items():
        assert set(spec) == {"read", "soft"}
        for value in spec["read"] + spec["soft"]:
            assert isinstance(value, str) and key.match(value), (fam, value)
        assert set(spec["soft"]) <= set(spec["read"])
    loaded = ninjashape.load_baseline(path)
    assert "lines.primaryValue" in loaded["exchange"]["read"]
    assert loaded["leagues"]["read"] == ["id", "name"]
    # a price, an item name or an unknown family is refused
    for bad in ({"families": {"item": {"read": ["Divine Orb"], "soft": []}}},
                {"families": {"item": {"read": [12.5], "soft": []}}},
                {"families": {"other": {"read": ["id"], "soft": []}}},
                {"families": {"item": {"read": ["id"], "soft": ["name"]}}},
                {"nope": 1}):
        f = tmp_path / "bad.json"
        f.write_text(json.dumps(bad), encoding="ascii")
        with pytest.raises(ValueError):
            ninjashape.load_baseline(f)
    # hot reloaded (decision 0042): a bad edit keeps the last good copy
    f = tmp_path / "keys.json"
    f.write_bytes(raw)
    watched = hotreload.Watched(f, ninjashape.load_baseline, name="poe.ninja read keys",
                                default=dict, registry=False)
    monkeypatch.setattr(ninjashape, "_baseline_watch", watched)
    assert "item" in ninjashape.baseline()
    f.write_text('{"families": {"item": {"read": ["a b"]}}}', encoding="ascii")
    assert "exchange" in ninjashape.baseline() and watched.error
    small = {"families": {"exchange": {"read": ["lines.id"], "soft": []}}}
    f.write_text(json.dumps(small) + "\n" * 3, encoding="ascii")
    assert set(ninjashape.baseline()) == {"exchange"} and watched.error is None
    # the shipped baseline joins the hot reload registry
    monkeypatch.setattr(ninjashape, "_baseline_watch", None)
    ninjashape.baseline()
    assert ninjashape._baseline_watch in hotreload.REGISTRY.watches()


# -- the seam and the guard rails --------------------------------------------

def test_observe_never_raises_and_a_missing_watch_checks_nothing(tmp_path):
    assert ninjashape.observe(None, "exchange", "Runes", 200, {}, b"{}") is None

    class Broken:
        def record(self, *a):
            raise RuntimeError("boom")

    assert ninjashape.observe(Broken(), "exchange", "Runes", 200, {}, b"{}") is None
    w = ninjashape.Watch(tmp_path / "ninja", clock=Clock())
    assert ninjashape.observe(w, "exchange", "Runes", 200, {}, b"not json") \
        == ninjashape.BREAK
    # a hostile key never reaches the signature as text
    body = _exchange(line_extra={"Mirror of X": 2})
    assert w.record("exchange", "Odd", 200, {}, body, 6, 6) == ninjashape.PASS
    assert "Mirror of X" not in json.dumps(w.signatures[("exchange", "Odd")])
    assert w.signatures[("exchange", "Odd")]["line_other"] == 6


def test_shape_row_names_the_type_and_the_missing_count(tmp_path):
    w = ninjashape.Watch(tmp_path / "ninja", clock=Clock())
    bad = _exchange(rename=("primaryValue", "price"))
    w.record("exchange", "Essences", 200, {}, bad, 0, 0)
    w.record("exchange", "Runes", 200, {}, bad, 0, 0)
    rates = SimpleNamespace(shape_watch=w, doc={})
    f = dict(ninjashape.diag_facts(SimpleNamespace(rates=rates)),
             web_data=True, contact_set=True)
    rows = ninjashape.diag_rows(f, NOW)
    assert [r["id"] for r in rows] == ["ninja_shape"]
    assert rows[0]["status"] == diag.FAIL and rows[0]["fix"] == ninjashape.SHAPE_FIX
    assert rows[0]["detail"] == ("poe.ninja changed the layout of its Essences prices. "
                                 "AshLight no longer finds 1 field it reads there. "
                                 "1 other price type changed too.")
    assert rows[0]["detail"].isascii()
    assert ninjashape.diag_rows(dict(f, contact_set=False), NOW) == []
