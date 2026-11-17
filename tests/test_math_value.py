"""MATH-VALUE: note price -> primary currency via cached poe.ninja rates,
and score per primary unit. Synthetic rates only; no network."""

import math
import random

import pytest

from server.al.theorycraft import live
from server.al.theorycraft import model
from server.al.theorycraft import value as v
from tc_eval_fixtures import EVAL_BUILD_XML

SNAP = {"primary": "divine", "stale": False, "credit": "Prices: poe.ninja",
        "rates": {"divine": {"value": 1, "name": "Divine Orb"},
                  "exalted": {"value": 0.002, "name": "Exalted Orb"},
                  "chaos": {"value": 0.125, "name": "Chaos Orb"},
                  "broken": {"value": 0}, "nan": {"value": float("nan")}}}


@pytest.mark.parametrize("note,want", [
    ("~price 5 exalted", ("price", 5, "exalted")),
    ("~b/o 1.5 divine", ("b/o", 1.5, "divine")),
    ("~price 1/2 divine", ("price", 0.5, "divine")),
    ("  ~PRICE 10 Exalt  ", ("price", 10, "exalted")),
    ("~b/o 3 div", ("b/o", 3, "divine")),
    ("~price 40 c", ("price", 40, "chaos")),
    ("~price 2 mystery-orb", ("price", 2, "mystery-orb")),
])
def test_parse_note_price(note, want):
    p = v.parse_note_price(note)
    assert (p["kind"], p["amount"], p["currency"]) == want


@pytest.mark.parametrize("note", [None, "", "price 5 exalted", "~price exalted", "~price 0 divine",
                                  "~price 1/0 divine", "~price -3 divine", "~price 5",
                                  "~price 1e9999 divine", "~price 9999999999 divine",
                                  "~skip 5 divine", 12])
def test_parse_note_price_rejects(note):
    assert v.parse_note_price(note) is None


def test_to_primary_and_missing_rates():
    assert v.to_primary(5, "exalted", SNAP) == pytest.approx(0.01)
    assert v.to_primary(2, "divine", SNAP) == 2
    assert v.to_primary(1, "broken", SNAP) is None  # zero rate: no guess
    assert v.to_primary(1, "nan", SNAP) is None
    assert v.to_primary(1, "unknown", SNAP) is None
    assert v.to_primary(1, "divine", {"primary": "divine", "rates": {}}) == 1
    assert v.to_primary(1, "exalted", {}) is None
    assert v.to_primary(-1, "divine", SNAP) is None
    assert v.to_primary(float("inf"), "divine", SNAP) is None
    assert v.to_primary(True, "divine", SNAP) is None


def test_cross_rate_conversion():
    assert v.convert(1, "chaos", "exalted", SNAP) == pytest.approx(62.5)
    assert v.convert(62.5, "exalted", "chaos", SNAP) == pytest.approx(1)
    assert v.convert(1, "chaos", "broken", SNAP) is None


def test_cross_rates_round_trip_property():
    rng = random.Random(55)
    ids = ["divine", "exalted", "chaos"]
    for _ in range(500):
        a, b = rng.choice(ids), rng.choice(ids)
        amt = rng.uniform(0.001, 1e5)
        there = v.convert(amt, a, b, SNAP)
        assert v.convert(there, b, a, SNAP) == pytest.approx(amt, rel=1e-12)
        # transitivity through a third currency
        c = rng.choice(ids)
        assert v.convert(v.convert(amt, a, c, SNAP), c, b, SNAP) == pytest.approx(there, rel=1e-12)


def test_per_unit():
    assert v.per_unit(30, 2) == 15
    assert v.per_unit(-30, 2) == -15
    for bad in (0, -1, None, float("nan"), float("inf")):
        assert v.per_unit(30, bad) is None
    assert v.per_unit(float("nan"), 2) is None


def test_value_doc():
    doc = v.value_of("~price 5 exalted", 20, SNAP)
    assert doc["price"] == {"kind": "price", "amount": 5, "currency": "exalted",
                            "name": "Exalted Orb"}
    assert doc["primary"] == "divine" and doc["primary_name"] == "Divine Orb"
    assert doc["price_primary"] == 0.01 and doc["score_per_primary"] == 2000
    assert doc["stale"] is False and doc["credit"] == "Prices: poe.ninja"
    assert v.value_of(None, 20, SNAP) is None
    off = v.value_of("~price 5 exalted", 20, {"rates": {}, "stale": True})
    assert off["price_primary"] is None and off["score_per_primary"] is None and off["stale"]
    assert v.value_of("~price 5 exalted", None, SNAP)["score_per_primary"] is None


def test_small_prices_keep_significant_digits():
    snap = {"primary": "divine", "rates": {"exalted": {"value": 0.001883}}}
    doc = v.value_of("~price 1 exalted", 1, snap)
    assert doc["price_primary"] == 0.001883
    assert math.isclose(doc["score_per_primary"], 1 / 0.001883, rel_tol=1e-5)


class _Builds:
    def __init__(self, build):
        self.build = build


class _Weights:
    def get(self):
        return None


class _State:
    def __init__(self):
        self.card = None

    def set_eval(self, card, keep_time=False, at=None):
        self.card = card


ITEM = """Item Class: Boots
Rarity: Magic
Swift Example Boots of Warmth
--------
Item Level: 30
--------
25% increased Movement Speed
+20% to Fire Resistance
--------
Note: ~price 4 exalted
"""


def test_item_check_card_carries_value_from_cached_rates():
    state = _State()
    last = live.LastEval(_Builds(model.parse(EVAL_BUILD_XML)), _Weights(), state,
                         rates=lambda: SNAP)
    last.run(ITEM)
    val = state.card["value"]
    assert val["price_primary"] == 0.008
    assert val["score_per_primary"] == pytest.approx(state.card["score_delta"] / 0.008,
                                                     rel=1e-5)
    no_rates = _State()
    live.LastEval(_Builds(None), _Weights(), no_rates).run(ITEM)
    assert no_rates.card["value"]["price_primary"] is None
    plain = _State()
    live.LastEval(_Builds(None), _Weights(), plain, rates=lambda: SNAP).run(
        ITEM.replace("Note: ~price 4 exalted", ""))
    assert plain.card["value"] is None


def test_rates_callable_failure_never_breaks_the_item_check():
    state = _State()

    def boom():
        raise RuntimeError("cache unreadable")

    live.LastEval(_Builds(None), _Weights(), state, rates=boom).run(ITEM)
    assert state.card["value"]["price_primary"] is None
