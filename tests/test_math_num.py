"""MATH-NUM: numeric edge cases of stat-weight scoring.

Stdlib property tests with fixed seeds. Contract: a score, delta or
verdict is always a finite JSON-safe number or a known word, whatever the
item text or weights say; the delta is antisymmetric; the sidegrade band
grows with the equipped score; rounding is stable; the ring best-slot pick
is deterministic on ties.
"""

import json
import math
import random

import pytest

from server.al.theorycraft import evaluate as ev
from server.al.theorycraft import model
from server.al.theorycraft import weights as w
from tc_eval_fixtures import EVAL_BUILD_XML

SIDE = {"abs": 2.0, "pct": 5.0}


def _ring(*lines):
    return "Item Class: Rings\nRarity: Rare\nA\nB\n--------\n" + "\n".join(lines) + "\n"


@pytest.mark.parametrize("line", ["+" + "9" * 400 + " to maximum Life",
                                  "+1e999 to maximum Life",
                                  "+99999999999999 to maximum Life",
                                  "-" + "9" * 400 + "% to Fire Resistance"])
def test_huge_numbers_never_make_a_non_finite_score(line):
    r = ev.evaluate(_ring(line), model.parse(EVAL_BUILD_XML), None)
    json.dumps(r, allow_nan=False)  # the feed must stay valid JSON
    assert math.isfinite(r["score"]) and math.isfinite(r["score_delta"])


def test_stat_key_drops_out_of_range_values():
    assert w.stat_key("+" + "9" * 400 + " to maximum Life") == ("+# to maximum Life", None)
    assert w.stat_key("+1000000000 to maximum Life")[1] == 1e9
    assert w.stat_key("+1000000001 to maximum Life")[1] is None


def test_score_skips_non_finite_terms():
    t = w.lookup({"a": 1.0, "b": 2.0})
    assert ev.score({"a": float("inf"), "b": 3}, t) == 6
    assert ev.score({"a": float("nan")}, t) == 0
    assert ev.score({"a": 1e303, "b": 1e303}, w.lookup({"a": 1e6, "b": 1e6})) == 0


def test_verdict_on_non_finite_inputs_is_sidegrade():
    for d, old in ((float("nan"), 0), (3, float("inf")), (float("inf"), float("nan"))):
        assert ev.verdict(d, old, SIDE) == ev.SIDEGRADE


def test_delta_is_antisymmetric_and_band_symmetric():
    rng = random.Random(31)
    for _ in range(2000):
        delta = rng.uniform(-500, 500)
        old = rng.uniform(-500, 500)
        a = ev.verdict(delta, old, SIDE)
        b = ev.verdict(-delta, old, SIDE)
        flip = {ev.UPGRADE: ev.DOWNGRADE, ev.DOWNGRADE: ev.UPGRADE, ev.SIDEGRADE: ev.SIDEGRADE}
        assert flip[a] == b


def test_band_grows_with_the_equipped_score():
    rng = random.Random(32)
    for _ in range(1000):
        delta = rng.uniform(0, 50)
        old = rng.uniform(0, 1000)
        if ev.verdict(delta, old * 2, SIDE) == ev.UPGRADE:
            assert ev.verdict(delta, old, SIDE) == ev.UPGRADE


def test_clean_rounding_is_stable_and_json_safe():
    rng = random.Random(33)
    for _ in range(2000):
        x = rng.uniform(-1e6, 1e6) * rng.choice([1, 1e-5, 1e-9])
        c = ev._clean(x)
        assert ev._clean(c) == c
        assert isinstance(c, (int, float)) and math.isfinite(c)
        assert abs(c - x) <= 5e-5 + 1e-9
    assert ev._clean(-0.0) == 0 and str(ev._clean(-0.00001)) == "0"
    assert ev._clean(float("inf")) == 0 and ev._clean(float("nan")) == 0


def test_random_items_and_weights_always_give_finite_json():
    rng = random.Random(34)
    build = model.parse(EVAL_BUILD_XML)
    keys = ["+# to maximum Life", "+#% to Fire Resistance", "#% increased Attack Speed"]
    for _ in range(300):
        weights = {k: rng.choice([0, -1e6, 1e6, rng.uniform(-10, 10)]) for k in keys}
        lines = []
        for _ in range(rng.randint(0, 6)):
            n = rng.choice([rng.randint(0, 200), rng.uniform(0, 1e12), 10 ** rng.randint(0, 40)])
            lines.append(rng.choice(["+{} to maximum Life", "-{}% to Fire Resistance",
                                     "{}% reduced Attack Speed"]).format(n))
        r = ev.evaluate(_ring(*lines), build, {"weights": weights})
        json.dumps(r, allow_nan=False)


def test_ring_best_slot_tie_is_deterministic():
    build = model.parse(EVAL_BUILD_XML)
    text = _ring("+5 to Unweighted Stat")
    picks = {ev.evaluate(text, build, {"weights": {}})["slot"] for _ in range(20)}
    assert picks == {"Ring 1"}
