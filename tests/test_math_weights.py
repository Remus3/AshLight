"""MATH-WEIGHTS: PoB-derived stat weights kept per build (pobweights).

A deterministic fake calc stands in for the PoB bridge (as in
test_tc_delta); every weight is the calc's own number, the cache only
remembers it."""

import threading

import pytest

from server.al import upgrade
from server.al.state import eval_card_text
from server.al.theorycraft import delta
from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import live, model
from server.al.theorycraft import pobweights as pw
from tc_eval_fixtures import EVAL_BUILD_XML, RARE_GLOVES
from test_tc_delta import FakeCalc


def _build(xml=EVAL_BUILD_XML):
    return model.parse(xml)


def _failing(build, swaps):
    raise OSError("bridge died")


KEYS = ["+# to maximum Life", "+#% to Cold Resistance", "Cannot be Frozen"]


def test_cache_probes_each_key_once():
    b, calc, cache = _build(), FakeCalc(), pw.PobWeightCache()
    carrier = b.equipped("Gloves").text
    first = cache.mod_weights(calc, b, "Gloves", carrier, KEYS)
    direct = delta.mod_weights(FakeCalc(), b, "Gloves", carrier, KEYS)
    assert first == direct  # the cache returns PoB's numbers unchanged
    n = len(calc.calls)
    again = cache.mod_weights(calc, b, "Gloves", carrier, list(reversed(KEYS)))
    assert again["weights"] == first["weights"] and len(calc.calls) == n
    # one new key: one base run plus one probe, the old keys not re-probed
    more = cache.mod_weights(calc, b, "Gloves", carrier, KEYS + ["#% increased Attack Speed"])
    assert len(calc.calls) == n + 2
    assert set(more["weights"]) == set(first["weights"]) | {"#% increased Attack Speed"}
    assert cache.probes == 3


def test_flag_only_keys_never_call_the_calc():
    b, calc, cache = _build(), FakeCalc(), pw.PobWeightCache()
    out = cache.mod_weights(calc, b, "Gloves", "x", ["Cannot be Frozen", "Gains: x"])
    assert out == {"weights": {}, "detail": {}} and calc.calls == []
    assert not pw.probeable("Cannot be Frozen") and pw.probeable("+# to Strength")


def test_cache_is_keyed_by_build_slot_carrier_and_blend():
    b, calc, cache = _build(), FakeCalc(), pw.PobWeightCache()
    cache.mod_weights(calc, b, "Gloves", "c1", KEYS[:1])
    n = len(calc.calls)
    cache.mod_weights(calc, b, "Gloves", "c2", KEYS[:1])  # other carrier
    cache.mod_weights(calc, b, "Helmet", "c1", KEYS[:1])  # other slot
    cache.mod_weights(calc, b, "Gloves", "c1", KEYS[:1], blend={"dps": 1, "ehp": 0})
    other = _build(EVAL_BUILD_XML + " ")
    cache.mod_weights(calc, other, "Gloves", "c1", KEYS[:1])
    assert len(calc.calls) == n + 4 * 2


def test_fallback_only_for_the_same_build_and_slot():
    b, cache = _build(), pw.PobWeightCache()
    cache.mod_weights(FakeCalc(), b, "Gloves", b.equipped("Gloves").text, KEYS)
    w = cache.fallback(b, "gloves")
    assert set(w) == {"+# to maximum Life", "+#% to Cold Resistance"}
    assert cache.fallback(b, "Helmet") == {}
    assert cache.fallback(_build(EVAL_BUILD_XML + " "), "Gloves") == {}
    assert cache.fallback(None, "Gloves") == {}
    assert cache.fallback(b, "Gloves", blend={"dps": 1, "ehp": 0}) == {}


def test_bounded_lru():
    b, calc, cache = _build(), FakeCalc(), pw.PobWeightCache(max_entries=2)
    for c in ("a", "b", "c"):
        cache.mod_weights(calc, b, "Gloves", c, KEYS[:1])
    n = len(calc.calls)
    cache.mod_weights(calc, b, "Gloves", "c", KEYS[:1])
    assert len(calc.calls) == n  # newest kept
    cache.mod_weights(calc, b, "Gloves", "a", KEYS[:1])
    assert len(calc.calls) == n + 2  # oldest evicted
    cache.clear()
    assert cache.fallback(b, "Gloves") == {}


def test_calc_error_stores_nothing():
    b, cache = _build(), pw.PobWeightCache()
    with pytest.raises(delta.CalcError):
        cache.mod_weights(_failing, b, "Gloves", "x", KEYS)
    assert cache.fallback(b, "Gloves") == {}


def test_evaluate_with_cache_matches_without_and_saves_probes():
    b = _build()
    plain = tc_evaluate.evaluate(RARE_GLOVES, b, None, calc=FakeCalc())
    calc, cache = FakeCalc(), pw.PobWeightCache()
    first = tc_evaluate.evaluate(RARE_GLOVES, b, None, calc=calc, cache=cache)
    assert first["verdict"] == plain["verdict"] and first["score"] == plain["score"]
    assert first["mod_weights"] == plain["mod_weights"]
    n = len(calc.calls)
    second = tc_evaluate.evaluate(RARE_GLOVES, b, None, calc=calc, cache=cache)
    assert second["score"] == first["score"]
    # the rerun needs only the base and item-delta runs, no probes
    assert len(calc.calls) - n == 2


@pytest.mark.parametrize("calc,notice", [(None, "off"), (_failing, "failed")])
def test_outage_scores_with_this_builds_pob_weights(calc, notice):
    b, cache = _build(), pw.PobWeightCache()
    good = tc_evaluate.evaluate(RARE_GLOVES, b, None, calc=FakeCalc(), cache=cache)
    out = tc_evaluate.evaluate(RARE_GLOVES, b, None, calc=calc, cache=cache)
    assert out["ok"] and out["calc"] == {"source": pw.SOURCE_CACHED, "notice": notice}
    assert out["mod_weights"]["source"] == pw.SOURCE_CACHED
    assert out["score"] == good["score"]
    # PoB weights are linear in this fake calc, so the estimate equals PoB
    assert out["verdict"] == good["verdict"]
    assert abs(out["score_delta"] - good["score_delta"]) < 1e-3
    assert not any("dps" in c for c in out["comparisons"])
    text = eval_card_text(live.compact(out))
    assert "Path of Building measured for this build earlier" in text["calc"]
    up = upgrade.link(out)
    assert up is None or up["weights"]["source"] == pw.SOURCE_CACHED


def test_outage_without_cached_weights_uses_hand_weights():
    b, cache = _build(), pw.PobWeightCache()
    out = tc_evaluate.evaluate(RARE_GLOVES, b, None, calc=None, cache=cache)
    assert out["calc"] == {"source": "weights", "notice": "off"}
    assert out["mod_weights"]["source"] == "hand"
    # another build's PoB weights are never borrowed
    tc_evaluate.evaluate(RARE_GLOVES, _build(EVAL_BUILD_XML + " "), None, calc=FakeCalc(),
                         cache=cache)
    out = tc_evaluate.evaluate(RARE_GLOVES, b, None, calc=None, cache=cache)
    assert out["mod_weights"]["source"] == "hand"


def test_cached_text_for_both_notices():
    for notice, tail in (("off", "calc is off."), ("failed", "Try the check again.")):
        card = {"ok": True, "verdict": "upgrade", "slot": "Gloves", "score_delta": 1,
                "calc": {"source": "pob_cached", "notice": notice},
                "comparisons": [{"slot": "Gloves", "verdict": "upgrade", "score_delta": 1,
                                 "stats": []}]}
        t = eval_card_text(card)["calc"]
        assert t.startswith("Scored with the stat weights Path of Building") and \
            t.endswith(tail) and t.isascii()


def test_last_eval_keeps_one_cache_across_reruns():
    class Builds:
        build = _build()

        def add_listener(self, fn):
            pass

    class Weights:
        def get(self):
            return None

    class State:
        def set_eval(self, card, keep_time=False, at=None):
            self.card = card

    calc = FakeCalc()
    on = [True]
    st = State()
    last = live.LastEval(Builds(), Weights(), st, calc=lambda: calc if on[0] else None)
    last.run(RARE_GLOVES)
    n = len(calc.calls)
    last.rerun()
    assert len(calc.calls) - n == 2
    on[0] = False
    last.rerun()
    assert st.card["calc"]["source"] == pw.SOURCE_CACHED


def test_thread_safe_under_concurrent_checks():
    b, cache = _build(), pw.PobWeightCache()
    errors = []

    def work():
        try:
            for _ in range(20):
                tc_evaluate.evaluate(RARE_GLOVES, b, None, calc=FakeCalc(), cache=cache)
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=work) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert errors == [] and cache.fallback(b, "Gloves")
