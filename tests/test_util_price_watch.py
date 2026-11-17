"""UTIL-PRICE-WATCH: price moves of checked items from the cached price
book only (research 0028 ruling D). A fake lookup stands in for the book;
no network."""

import json

from server.al import pricewatch
from server.al.core import Core

ITEM = {"name": "Headhunter", "base": "Leather Belt", "rarity": "UNIQUE",
        "corrupted": False}


def ninja(value, unit="Divine Orb"):
    return {"kind": "unique", "name": "Headhunter", "value": value, "unit": unit}


class Book:
    def __init__(self, prices):
        self.prices = prices
        self.calls = []

    def __call__(self, item):
        self.calls.append(item)
        p = self.prices.get(item["name"])
        return {"value": p[0], "unit": p[1]} if p else None


def watch(tmp_path, value=100.0):
    w = pricewatch.PriceWatch(tmp_path / pricewatch.FILE_NAME)
    assert w.record(ITEM, ninja(value), at=1000.0) is True
    return w


def test_rise_flags(tmp_path):
    w = watch(tmp_path)
    assert w.refresh(Book({"Headhunter": (130.0, "Divine Orb")})) is True
    v = w.view(True)
    assert v["moved"] == [{"name": "Headhunter", "was": 100.0, "now": 130.0,
                           "unit": "Divine Orb", "change_pct": 30, "at": 1000.0,
                           "text": "Headhunter: up 30%, from 100 to 130 Divine Orb"}]
    assert v["text"] == "" and v["count"] == 1


def test_fall_flags(tmp_path):
    w = watch(tmp_path)
    w.refresh(Book({"Headhunter": (60.0, "Divine Orb")}))
    assert w.view(True)["moved"][0]["text"] == "Headhunter: down 40%, from 100 to 60 Divine Orb"


def test_under_threshold_no_flag(tmp_path):
    w = watch(tmp_path)
    w.refresh(Book({"Headhunter": (120.0, "Divine Orb")}))
    v = w.view(True)
    assert v["moved"] == []
    assert v["text"] == "Watching 1 item. No price moved by 25% or more since you checked."
    assert w.view(True, pct=10)["moved"][0]["change_pct"] == 20


def test_item_gone_or_unit_changed_no_flag(tmp_path):
    w = watch(tmp_path)
    w.refresh(Book({}))
    assert w.view(True)["moved"] == []
    w.refresh(Book({"Headhunter": (9000.0, "Exalted Orb")}))
    assert w.view(True)["moved"] == []


def test_web_data_off_flags_nothing(tmp_path):
    w = watch(tmp_path)
    w.refresh(Book({"Headhunter": (300.0, "Divine Orb")}))
    off = w.view(False)
    assert off["on"] is False and off["moved"] == [] and off["text"] == pricewatch.OFF_TEXT


def test_press_without_price_records_nothing_and_cap(tmp_path):
    w = pricewatch.PriceWatch(tmp_path / pricewatch.FILE_NAME)
    assert w.record(ITEM, None, at=1.0) is False
    assert w.record(ITEM, ninja(0), at=1.0) is False
    assert w.view(True)["text"] == pricewatch.EMPTY_TEXT
    for i in range(pricewatch.MAX_ITEMS + 5):
        w.record(dict(ITEM, name=f"U{i}"), dict(ninja(10.0), name=f"U{i}"), at=float(i + 1))
    assert len(w.items) == pricewatch.MAX_ITEMS and w.items[0]["name"] == "U5"
    # the same item again replaces its row (new baseline), no duplicate
    w.record(dict(ITEM, name="U10"), ninja(50.0), at=99.0)
    assert [r["name"] for r in w.items].count("U10") == 1 and w.items[-1]["value"] == 50.0
    again = pricewatch.PriceWatch(w.path)
    assert again.items == w.items
    doc = json.loads(w.path.read_text(encoding="ascii"))
    assert doc["schema"] == 1
    w.clear()
    assert pricewatch.PriceWatch(w.path).items == []


def test_pct_setting():
    assert pricewatch.pct_setting(40) == 40
    for bad in (None, 2, 900, True, "25"):
        assert pricewatch.pct_setting(bad) == pricewatch.DEFAULT_PCT


class FakeRates:
    """RatesClient stand-in: lookup reads a dict; no request ever."""

    def __init__(self, enabled):
        self.enabled = enabled
        self.prices = {"Headhunter": 100.0}
        self.doc = {"checked_at": 1.0}
        self.book = type("B", (), {"doc": {"types": {"UniqueAccessory": {"checked_at": 1.0}}}})()

    def lookup(self, item):
        if not self.enabled():
            return None
        get = item.get if isinstance(item, dict) else (lambda k, d=None: getattr(item, k, d))
        v = self.prices.get(get("name"))
        return {"kind": "unique", "name": get("name"), "value": v, "unit": "Divine Orb",
                "listings": 50, "few": False, "change": None, "league": "L"} if v else None

    def snapshot(self):
        return {}


UNIQUE_TEXT = """Item Class: Belts
Rarity: Unique
Headhunter
Leather Belt
--------
Item Level: 80
"""


def test_core_press_records_and_book_refresh_flags(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    cfg = tmp_path / "local.json"
    cfg.write_text(json.dumps({"web_data": True}), encoding="ascii")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False, config_path=cfg)
    try:
        rates = FakeRates(core.web_data_enabled)
        core.rates = rates
        core.price.lookup = rates.lookup
        core.eval_press(UNIQUE_TEXT)
        assert [r["name"] for r in core.watch.items] == ["Headhunter"]
        core.tick_watch()
        assert core.state.snapshot()["price_watch"]["moved"] == []
        # the hourly book refresh: new stamp, new price
        rates.prices["Headhunter"] = 150.0
        core.tick_watch()  # same stamp: not re-read
        assert core.state.snapshot()["price_watch"]["moved"] == []
        rates.book.doc["types"]["UniqueAccessory"]["checked_at"] = 3601.0
        assert core.tick_watch() is True
        assert core.state.snapshot()["price_watch"]["moved"][0]["change_pct"] == 50
        # web data off: nothing flagged, nothing re-read
        core.set_web_data(False)
        core.tick_watch()
        pw = core.state.snapshot()["price_watch"]
        assert pw["on"] is False and pw["moved"] == []
        assert core.clear_watch()["count"] == 0
    finally:
        core.close()
