"""MATH-DPS-SANITY: Path of Building outputs that make no sense for the card
(NaN / inf, negative DPS or EHP, zero EHP, an attack build at 0 DPS after a
swap) never reach the card as a number: the check falls back to the stat
weights and says "the calc result looks wrong" (decision 0032)."""

import math

import pytest

from server.al.state import eval_card_text
from server.al.theorycraft import delta
from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import live, model
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML, RARE_GLOVES
from test_tc_delta import FakeCalc, _Builds, _State, _Weights

WRONG = ("Scored with your stat weights. DPS and EHP are not shown because Path of "
         "Building's numbers for this item don't add up. Try the check again.")


def _b():
    return model.parse(EVAL_BUILD_XML)


def _const(dps, ehp):
    return lambda build, swaps: {"dps": dps, "ehp": ehp}


def test_outputs_rejects_nonsense_as_implausible():
    b = _b()
    for dps, ehp in ((-1, 100), (10, -5), (10, 0), (-0.5, -0.5)):
        with pytest.raises(delta.CalcImplausible):
            delta.outputs(_const(dps, ehp), b)
    # still a CalcError, so every existing fallback catches it
    assert issubclass(delta.CalcImplausible, delta.CalcError)
    # NaN / inf stay the plain "not a finite number" CalcError
    with pytest.raises(delta.CalcError):
        delta.outputs(_const(math.nan, 1), b)
    with pytest.raises(delta.CalcError):
        delta.outputs(_const(1, math.inf), b)
    # 0 DPS is a real answer for a build with no damage skill
    assert delta.outputs(_const(0, 100), b) == {"dps": 0.0, "ehp": 100.0}


def test_item_delta_attack_build_at_zero_dps_after_swap_is_implausible():
    b = _b()

    def zero_on_swap(build, swaps):
        return {"dps": 0 if swaps else 500, "ehp": 1000}
    with pytest.raises(delta.CalcImplausible, match="0 DPS"):
        delta.item_delta(zero_on_swap, b, "Gloves", RARE_GLOVES)
    # a build with no DPS to begin with may stay at 0
    d = delta.item_delta(_const(0, 1000), b, "Gloves", RARE_GLOVES)
    assert d["dps"]["pct"] == 0.0


@pytest.mark.parametrize("calc", [
    lambda build, swaps: {"dps": 0 if swaps else 500, "ehp": 1000},
    lambda build, swaps: {"dps": 100, "ehp": -50 if swaps else 1000},
    lambda build, swaps: {"dps": 100, "ehp": 0},
])
def test_evaluate_falls_back_to_weights_with_the_wrong_notice(calc):
    b = _b()
    r = tc_evaluate.evaluate(RARE_GLOVES, b, calc=calc)
    hand = tc_evaluate.evaluate(RARE_GLOVES, b)
    assert r["calc"] == {"source": "weights", "notice": "implausible"}
    assert r["verdict"] == hand["verdict"] and r["comparisons"] == hand["comparisons"]
    assert "dps" not in r["comparisons"][0]


def test_card_says_the_calc_result_looks_wrong():
    st = _State()
    live.LastEval(_Builds(_b()), _Weights(), st,
                  calc=lambda: _const(100, -1)).run(RARE_GLOVES)
    assert st.eval["calc"] == {"source": "weights", "notice": "implausible"}
    t = eval_card_text(st.eval)
    assert t["calc"] == WRONG
    assert "DPS" not in t["line"] and "EHP" not in t["line"]


def test_cached_pob_weights_after_a_wrong_result():
    st = _State()
    last = live.LastEval(_Builds(_b()), _Weights(), st, calc=lambda: FakeCalc())
    last.run(ADVANCED_RING)
    assert st.eval["calc"]["source"] == "pob"
    last.calc = lambda: _const(100, -1)
    last.rerun()
    assert st.eval["calc"] == {"source": "pob_cached", "notice": "implausible"}
    assert eval_card_text(st.eval)["calc"] == (
        "Scored with the stat weights Path of Building measured for this build earlier. "
        "DPS and EHP are not shown because its numbers for this item don't add up. "
        "Try the check again.")


def test_a_sane_calc_is_untouched():
    r = tc_evaluate.evaluate(RARE_GLOVES, _b(), calc=FakeCalc())
    assert r["calc"] == {"source": "pob", "notice": None}
